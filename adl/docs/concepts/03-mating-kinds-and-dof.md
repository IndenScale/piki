# 配合类型与自由度

> PML（Part Mating Language）的核心是两个接口之间的几何约束。`mating_kind` 决定静态约束方程，`InterfaceSignature` 决定配合后允许的运动自由度。

---

## 一、MatingKind：静态几何约束

`MatingKind` 枚举定义在 `adl/compiler/mating_kinds.py`，描述两个接口接触面之间的几何关系。

| 取值    | 描述                                    | 约束自由度数 | 典型场景                     |
| ------- | --------------------------------------- | ------------ | ---------------------------- |
| `face`  | 面贴合：法向对齐 + 距离 = 0             | 3            | 法兰密封、盖板贴合、PCB 安装 |
| `axis`  | 轴配合：两轴线重合                      | 4            | 轴与轴承孔、螺栓与通孔       |
| `point` | 点配合：两点重合                        | 3            | 球窝关节、定位销             |
| `slot`  | 槽配合：沿一个方向平移 + 其余方向约束   | 2            | SFP 插槽、键槽               |
| `rail`  | 导轨配合：沿导轨方向平移 + 两个方向约束 | 5            | 机柜滑轨、抽屉导轨           |
| `none`  | 无几何约束，仅逻辑配对                  | 0            | 电气信号、数据协议、功率分配 |

> "约束自由度数" 指配合本身消除的自由度。剩余自由度由 `InterfaceSignature` 进一步描述。

---

## 二、各配合类型的几何含义

### 2.1 `face` — 面贴合

两个平面法向对齐且距离为 0。接口局部坐标系的 Z 轴通常即为法向。

```yaml
# parent 接口：面朝 +Z
mating_kind: face
mating_params:
  normal: [0, 0, 1]

# child 接口：面朝 -Z
mating_kind: face
mating_params:
  normal: [0, 0, -1]
```

约束：

- 两法向共线反向；
- 两平面重合（child 沿法向平移到贴合位置）。

### 2.2 `axis` — 同轴

两条轴线重合，保留沿轴平移和绕轴旋转两个自由度（除非被 signature 进一步限制）。

```yaml
mating_kind: axis
mating_params:
  axis_dir: [0, 1, 0] # 轴线方向
```

约束：

- 两轴方向向量共线；
- 两轴上一点重合。

### 2.3 `point` — 点重合

两个点重合，保留三个旋转自由度。

```yaml
mating_kind: point
```

### 2.4 `slot` — 槽配合

一个方向平移自由，其余五个自由度被约束（面贴合 + 横向限位）。

```yaml
mating_kind: slot
mating_params:
  slot_dir: [0, 0, 1] # 平移方向
```

### 2.5 `rail` — 导轨配合

沿导轨方向平移，横向两个方向被约束，保留绕导轨轴的旋转。

```yaml
mating_kind: rail
mating_params:
  rail_dir: [0, 1, 0]
```

### 2.6 `none` — 逻辑配对

无几何约束，仅记录两个接口之间的逻辑关系。用于电气连接、数据流、功率分配等。

---

## 三、InterfaceSignature：运动自由度签名

`InterfaceSignature` 定义在 `adl/geometry/interface_signature.py`，描述**配合后**接口所在 Part 还允许哪些运动。

```python
@dataclass
class InterfaceSignature:
    discrete_states: list[DiscreteState]
    continuous_dofs: list[DOF]
    stages: list[SignatureStage]
```

### 3.1 离散状态（DiscreteState）

不可连续过渡的位置状态：

| 状态名     | 含义          | 示例                 |
| ---------- | ------------- | -------------------- |
| `inserted` | 已插入/已配合 | USB-C 插入、螺丝旋紧 |
| `removed`  | 已拔出/未配合 | 插头拔出             |
| `reversed` | 反向插入      | USB-C 反插           |
| `closed`   | 闭合          | 抽屉闭合、门闭合     |

```yaml
# 概念示例
discrete_states:
  - name: removed
    transform_delta: null
  - name: inserted
    transform_delta: identity
    is_default: true
  - name: reversed
    transform_delta:
      rotation: [0, 0, 180]
```

### 3.2 连续自由度（DOF）

配合后允许连续变化的位置参数：

| 类型        | 含义                        | 单位  | 示例                       |
| ----------- | --------------------------- | ----- | -------------------------- |
| `translate` | 沿轴平移                    | mm    | 抽屉拉出距离               |
| `rotate`    | 绕轴旋转                    | 度    | 铰链开门角度、耳机插头旋转 |
| `screw`     | 螺旋运动（平移 + 旋转耦合） | mm/度 | 螺丝旋入                   |

```yaml
# 概念示例
continuous_dofs:
  - type: rotate
    axis: [0, 1, 0]
    range: [0, 180]
    default_value: 0
    label: 开门角度
```

### 3.3 签名耦合规则

两个接口配合时，签名耦合产生一个参数向量：

1. **离散状态取交集**：两端都支持的状态才是合法状态。
2. **连续自由度以 child 为准**：child 的 DOF 暴露给控制面板。
3. **阶段（Stage）取 parent**：多阶段装配顺序由 parent 决定。

```text
签名 A {inserted, removed}  +  签名 B {inserted, reversed, removed}
─────────────────────────────────────────────────────────────────
                    → {inserted, removed}
```

---

## 四、从参数向量到全局位姿

配合求解器输入参数向量，输出 child Part 的全局 Transform：

```text
P_child_global = P_parent_global
               × T_parent_iface_local
               × T_discrete(state)
               × T_dof(d1) × T_dof(d2) × ...
               × T_child_iface_local⁻¹
```

- `T_parent_iface_local`：parent 接口在 parent Part 局部坐标系中的位姿（PDL）。
- `T_discrete(state)`：离散状态变换（如反插旋转 180°）。
- `T_dof(di)`：连续自由度在当前参数值下的变换。
- `T_child_iface_local⁻¹`：child 接口局部位姿的逆。

> 完整实现见 `adl/geometry/interface_signature.py:SignatureCoupling.compute_child_transform_full()`。

---

## 五、内置签名注册表

`adl/geometry/interface_signature.py` 内置了常见接口类型的默认签名：

| 接口类型                                    | 离散状态                      | 连续 DOF            |
| ------------------------------------------- | ----------------------------- | ------------------- |
| `USB-C-receptacle` / `USB-C-plug`           | removed / inserted / reversed | 无                  |
| `TRS-3.5mm-jack` / `TRS-3.5mm-plug`         | removed / inserted            | 绕 Z 轴旋转 0°~360° |
| `IEC-C13` / `IEC-C14`                       | removed / inserted            | 无                  |
| `drawer-slide-female` / `drawer-slide-male` | closed                        | Z 轴平移 0~300mm    |
| `hinge-frame` / `hinge-leaf`                | closed                        | 绕 Y 轴旋转 0°~180° |
| `SFP28-cage` / `SFP28-module`               | removed / inserted            | 无                  |
| `RJ45-jack` / `RJ45-plug`                   | removed / inserted            | 无                  |
| `screw-hole` / `screw-thread`               | removed / seated              | 螺旋旋入 0~25mm     |

插件可以通过 `register_signature()` 扩展此表。

---

## 六、Mate 文件格式

Mate 文件位于 `mates/<mate_type>/<...>.yaml`，格式由 `adl/parsing/mate_loader.py` 解析：

```yaml
# mates/sfp-insert/SW-SFP28-A.yaml
type: slot
parent: ACCESS-SW/sfp28-port-25
child: SFP28-MOD-A/cage-interface
at:
  t:
    default: 0
    min: 0
    max: 56
constrains:
  - field: depth_mm
    operator: "<="
    value_ref: depth_mm
pairings: []
```

| 字段         | 说明                                          |
| ------------ | --------------------------------------------- |
| `type`       | 配合类型，可选，默认取目录名                  |
| `parent`     | 承载方引用，推荐 `instance_id/interface_id`   |
| `child`      | 被配合方引用，推荐 `instance_id/interface_id` |
| `at`         | 配合参数，注入给约束求解器                    |
| `constrains` | 固有约束，加载时自动验证                      |
| `pairings`   | 接口级配对记录                                |

---

## 七、接口兼容性

两个接口能否配合，取决于：

1. `interface_type` 兼容性矩阵（`InterfaceTypeDef.compatible_with`）；
2. `mating_kind` 兼容性（如 `face` 与 `face` 配合）；
3. 方向 `direction` 是否匹配（如 `output` 对 `input`）。

兼容性检查由 `InterfaceCompatPass` 在 MIR 阶段执行（ADL-002）。

---

## 八、常见错误

| 错误                    | 说明                                         | 处理/诊断           |
| ----------------------- | -------------------------------------------- | ------------------- |
| 接口类型不兼容          | 两个接口的 `interface_type` 不在兼容性矩阵中 | 校验报错            |
| mating_kind 不匹配      | 如 `face` 与 `axis` 无法直接配合             | `MATE-002`          |
| 裸 Instance ID 消解失败 | 找不到兼容接口对                             | `MATE-003`          |
| 接口对不唯一            | 多个候选接口对，需显式指定                   | `MATE-004`          |
| DOF 参数越界            | `at` 中的值超出 `range`                      | 求解器 clamp 或报错 |

---

## 九、与相关机制的衔接

- 接口与坐标系 → [接口与坐标系](02-interface-and-coordinate-system.md)
- 布局与全局位姿 → [布局与参数化定位链](04-layout-and-placement-chain.md)
- 接口优先配合设计 → [ADL-003：接口优先的配合建模](../adr/003-interface-first-mating.md)
- 接口运动自由度签名 → [ADL-004：接口签名系统](../adr/004-interface-signature.md)
- 编译器 Pass 管线 → [ADL-002：编译器架构设计](../adr/002-compiler-architecture.md)
