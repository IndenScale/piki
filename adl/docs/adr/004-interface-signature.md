# ADL-004：接口签名系统

> 状态：设计 → 实现中
> 日期：2026-06-17
> 前置：ADL-003

## 一、动机

ADL-003 引入了 `mating_kind`（face / axis / point / slot / rail），描述"两个接口怎么配合"。但这只覆盖了静态约束——它假设接口在配合后是刚性固定的。现实中的接口具有**参数化的运动自由度**：

- USB-C 可以正插、反插、拔出——三态
- 3.5mm 耳机插头插入后可以绕轴线任意旋转——一个连续自由度
- 抽屉沿导轨可以连续拉出——一个平移自由度
- 三脚插头：先推入（平移），再旋转锁紧——两个顺序阶段
- 螺丝：先旋入到接触面（螺旋运动），再施加扭矩预紧力——两个阶段 + 力约束

这些场景对碰撞检测至关重要：抽屉拉出了 200mm，它的包围盒就不再是"闭合"状态的位置。不建模自由度，碰撞检测就不准。

## 二、核心概念

### 2.1 接口签名（InterfaceSignature）

每个接口声明一个签名，描述它**在配合后允许的运动自由度**。

```python
@dataclass
class InterfaceSignature:
    """接口的运动自由度签名。

    签名描述接口配合后可能出现的位置变化。
    两个接口的签名耦合后产生一个参数化约束集。
    """

    # 离散状态（二值或多值）
    discrete_states: list[DiscreteState]   # 如 [inserted, removed]

    # 连续自由度（配合后允许的连续运动）
    continuous_dofs: list[DOF]            # 如 [rotate_about_z]

    # 参数化阶段：某些自由度仅在特定状态/条件下激活
    stages: list[SignatureStage]
```

### 2.2 离散状态（DiscreteState）

```python
@dataclass
class DiscreteState:
    name: str                    # "inserted", "removed", "reversed"
    label: str                   # 人类可读标签
    transform_delta: Transform   # 相对于"默认配合位置"的变换
    is_default: bool = False     # 是否为默认状态
```

USB-C 母座的签名：
```yaml
discrete_states:
  - { name: removed,   transform_delta: null }      # 不参与配合
  - { name: inserted,  transform_delta: identity, is_default: true }
  - { name: reversed,  transform_delta: { rotation: [0, 0, 180] } }  # 绕 Z 轴翻转 180°
```

### 2.3 连续自由度（DOF）

```python
@dataclass
class DOF:
    """一个连续运动自由度。"""
    type: DOFType               # TRANSLATE | ROTATE | SCREW
    axis: Vec3                  # 运动轴方向（局部坐标）
    range: tuple[float, float]  # [min, max]，单位 mm 或 度
    default_value: float = 0.0  # 默认参数值
```

抽屉的签名：
```yaml
continuous_dofs:
  - { type: TRANSLATE, axis: [0, 0, 1], range: [0, 300], default_value: 0 }
```

耳机线的签名：
```yaml
continuous_dofs:
  - { type: ROTATE, axis: [0, 0, 1], range: [0, 360], default_value: 0 }
```

### 2.4 签名耦合（Signature Coupling）

两个接口配合时，它们的签名耦合产出一个**参数向量**：

```
签名 A + 签名 B → 约束参数集 {d1, d2, ..., dn}
```

耦合规则：
1. **离散状态**：取两端的交集。如一端有 `[inserted, removed]`，另一端有 `[inserted, reversed, removed]`，交集为 `[inserted, removed]`。
2. **连续自由度**：取并集。每个 DOF 的轴从 child 的局部坐标变换到全局。
3. **阶段**：按 `order` 排序，每个阶段激活一组 DOF 和/或离散状态。

### 2.5 参数向量 → 位姿

求解器输入参数向量，输出 child 部件的全局 Transform：

```
P_child_global = P_parent_global
               × T_parent_iface_local      (parent 接口局部位姿)
               × T_mate(discrete_state)    (离散状态变换，如反转)
               × T_dof(d1, d2, ..., dn)    (连续自由度变换)
               × T_child_iface_local⁻¹    (child 接口局部位姿的逆)
```

## 三、签名默认注册表

```python
_SIGNATURE_REGISTRY: dict[str, InterfaceSignature] = {
    # USB-C：可正插、反插、拔出
    "USB-C-receptacle": InterfaceSignature(
        discrete_states=[
            DiscreteState("removed", "拔出", None, is_default=False),
            DiscreteState("inserted", "正插", Transform(), is_default=True),
            DiscreteState("reversed", "反插",
                Transform(rotation=Vec3(z=180)), is_default=False),
        ],
        continuous_dofs=[],
    ),
    "USB-C-plug": InterfaceSignature(
        discrete_states=[
            DiscreteState("removed", "拔出", None),
            DiscreteState("inserted", "正插", Transform(), is_default=True),
            DiscreteState("reversed", "反插",
                Transform(rotation=Vec3(z=180))),
        ],
        continuous_dofs=[],
    ),

    # 3.5mm 音频插头：插入后绕轴线自由旋转
    "TRS-3.5mm-jack": InterfaceSignature(
        discrete_states=[
            DiscreteState("removed", "拔出", None),
            DiscreteState("inserted", "插入", Transform(), is_default=True),
        ],
        continuous_dofs=[
            DOF(DOFType.ROTATE, Vec3(z=1), (0, 360), default_value=0),
        ],
    ),
    "TRS-3.5mm-plug": InterfaceSignature(
        discrete_states=[
            DiscreteState("removed", "拔出", None),
            DiscreteState("inserted", "插入", Transform(), is_default=True),
        ],
        continuous_dofs=[
            DOF(DOFType.ROTATE, Vec3(z=1), (0, 360), default_value=0),
        ],
    ),

    # IEC-C13/C14：只有插入和拔出
    "IEC-C13": InterfaceSignature(
        discrete_states=[
            DiscreteState("removed", "拔出", None),
            DiscreteState("inserted", "插入", Transform(), is_default=True),
        ],
    ),
    "IEC-C14": InterfaceSignature(
        discrete_states=[
            DiscreteState("removed", "拔出", None),
            DiscreteState("inserted", "插入", Transform(), is_default=True),
        ],
    ),

    # 抽屉：插入后连续拉出
    "drawer-slide": InterfaceSignature(
        discrete_states=[
            DiscreteState("closed", "闭合", Transform(), is_default=True),
        ],
        continuous_dofs=[
            DOF(DOFType.TRANSLATE, Vec3(z=1), (0, 300), default_value=0),
        ],
    ),

    # 铰链门：绕 Y 轴旋转
    "hinge": InterfaceSignature(
        discrete_states=[
            DiscreteState("closed", "闭合", Transform(), is_default=True),
        ],
        continuous_dofs=[
            DOF(DOFType.ROTATE, Vec3(y=1), (0, 180), default_value=0),
        ],
    ),
}
```

## 四、与现有 mating_kind 的关系

`mating_kind` 描述"两个接口接触面之间的几何约束关系"（face 相贴, axis 同轴...）。`InterfaceSignature` 描述"配合后,接口所在部件还能怎么动"。

它们正交：

```
mating_kind: face     → 两个面法向对齐
signature: IEC-C13    → 只能插入/拔出,无连续自由度

mating_kind: axis     → 两轴线重合
signature: TRS-3.5mm  → 插入/拔出 + 绕轴旋转
```

## 五、实现范围（本次）

1. `InterfaceSignature` + `DiscreteState` + `DOF` 数据模型
2. 签名默认注册表（USB-C, 3.5mm, IEC-C13/C14, 抽屉, 铰链）
3. 签名耦合算法（两接口签名 → 参数向量）
4. 参数向量 → 位姿的求解器
5. `InterfaceSpec.signature` 可选字段（不填则退化当前行为）

**不做：**
- 多阶段装配（insert → rotate → lock）
- 力/扭矩约束
- 驾驶仿真级运动学
