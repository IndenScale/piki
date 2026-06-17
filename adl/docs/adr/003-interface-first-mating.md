# ADL-003：接口优先配合规范

> 状态：设计阶段 → 实现中
> 日期：2026-06-17
> 前置：ADL-002

## 一、动机

当前 Mate 模型同时接受两种引用格式：

- 裸 Instance ID：`parent: RACK-A01, child: SRV-01`
- Interface 引用：`parent: SRV-01/eth0, child: XC-SRV01-ETH0/host`

这带来三个问题：

1. **语义模糊**：`parent: RACK-A01, child: SRV-01` 没有说明"怎么配合"——是导轨安装？是搁板放置？是磁吸？
2. **几何求解不统一**：`_apply_mates_global` 为每个 mate type 硬编码分支（`placed-on`、`rack-mount`），不可扩展。
3. **物理不真实**：现实世界中两个部件的"配合"总是发生在特定的接触面、连接器、安装点上——不是整个物体相交。

**设计原则：接口是配合的唯一入口。部件级配合是语法糖，在编译时消解为接口配合。**

## 二、接口模型增强

### 2.1 InterfaceSpec 扩展

```yaml
# Model 中的 Interface 声明（增强后）
interfaces:
  - id: power-a
    interface_type: IEC-C14
    direction: input
    mating_kind: face            # face | axis | point | slot | rail
    local_transform:
      translation: [0, 30, -350]  # 相对 Instance 原点的位姿 (mm)
      rotation: [0, 0, 0]
      scale: [1, 1, 1]
    mating_params:               # 配合参数（可选）
      normal: [0, 0, 1]          # 配合面法向
      tolerance_mm: 0.5
```

### 2.2 mating_kind 枚举

| mating_kind | 描述 | 几何约束 |
|-------------|------|----------|
| `face` | 面配合（两个平面相贴） | 法向对齐 + 距离 = 0 |
| `axis` | 轴配合（同轴对齐） | 轴线对齐 + 沿轴滑动自由度 |
| `point` | 点配合（球窝关节） | 两点重合 |
| `slot` | 槽配合 | 沿槽方向平移 + 垂直方向约束 |
| `rail` | 导轨配合 | 沿导轨方向平移 + 两个方向约束 |
| `none` | 无几何约束（仅逻辑配对） | 无 |

### 2.3 Interface 兼容性矩阵

```python
# 兼容性由 InterfaceTypeDef 定义
{
    "IEC-C14": {"compatible_with": {"IEC-C13"}},
    "IEC-C13": {"compatible_with": {"IEC-C14"}},
    "SFP28-cage": {"compatible_with": {"SFP28-module"}},
    "SFP28-module": {"compatible_with": {"SFP28-cage"}},
    "RJ45-jack": {"compatible_with": {"RJ45-plug"}},
    "RJ45-plug": {"compatible_with": {"RJ45-jack"}},
}
```

## 三、Mate 规范：仅接受接口引用

### 3.1 语言层

```yaml
# mates/rack-mount/RACK-A01-SRV-01.yaml
type: rack-mount
parent: RACK-A01/mount-rail-left   # ← 必须含 /
child: SRV-01/chassis-left-ears     # ← 必须含 /
```

MateSpec 的 `parent` 和 `child` 字段在 Schema 层强制 `/` 校验。

### 3.2 语法糖：部件 ID 自动消解

```yaml
# 写法 1（语法糖）：工程师只需写部件 ID
type: power-cable
parent: PDU-A
child: SRV-01
```

编译器的 Lowering pass 执行消解：

1. 遍历 `parent` 实例的所有 Interface，找出类型与 `child` 实例的任一 Interface 兼容的候选
2. 遍历 `child` 实例的所有 Interface，找出类型与 `parent` 实例的任一 Interface 兼容的候选
3. 对每一对候选，检查 `mating_kind` 兼容性
4. 如果恰好 1 对 → 自动消解为接口引用
5. 如果 0 对 → 编译错误：`MATE-003: 未找到兼容接口对`
6. 如果 >1 对 → 编译错误：`MATE-004: 接口对不唯一，请显式指定`

```python
# 消解算法伪代码
def resolve_sugar(mate: MateUnit, comp: Compilation) -> MateUnit:
    if "/" in mate.parent_ref.text and "/" in mate.child_ref.text:
        return mate  # 已是接口引用

    parent_inst = comp.instances[mate.parent_ref.text]
    child_inst = comp.instances[mate.child_ref.text]

    candidates = []
    for p_iface in parent_inst.interfaces:
        for c_iface in child_inst.interfaces:
            if is_compatible(p_iface.interface_type, c_iface.interface_type):
                candidates.append((p_iface, c_iface))

    if len(candidates) == 0:
        raise CompileError(f"MATE-003: ...")
    if len(candidates) > 1:
        raise CompileError(f"MATE-004: ...")

    p_iface, c_iface = candidates[0]
    return mate.with_refs(
        parent=f"{parent_inst.id}/{p_iface.id}",
        child=f"{child_inst.id}/{c_iface.id}",
    )
```

## 四、几何约束求解器

### 4.1 统一求解算法

所有 mate 最终都是接口配合，求解器不需要枚举 mate type：

```python
def solve_mate_constraint(
    parent_global: Transform,
    parent_iface: InterfaceSpec,
    child_global: Transform,
    child_iface: InterfaceSpec,
    mate_type: str,  # 仅用于覆盖默认参数
) -> Transform:
    """从两个接口的局部坐标 + mating_kind 推导 child 的全局位姿。"""
    kind = child_iface.mating_kind  # face | axis | point | ...

    # 接口的世界坐标
    p_world = parent_global @ parent_iface.local_transform
    c_world = child_global @ child_iface.local_transform

    if kind == "face":
        # 法向对齐 + 面距离 = 0
        return solve_face_mate(p_world, c_world, child_iface.mating_params)
    elif kind == "axis":
        return solve_axis_mate(p_world, c_world, child_iface.mating_params)
    elif kind == "point":
        return solve_point_mate(p_world, c_world)
    elif kind == "rail":
        return solve_rail_mate(p_world, c_world, child_iface.mating_params)
    elif kind == "slot":
        return solve_slot_mate(p_world, c_world, child_iface.mating_params)
    else:
        return child_global  # "none": 不参与几何约束
```

**不需要** `if mate.type == "placed-on"` 分支。`placed-on` 只是语法糖：
- parent 底面接口：`mating_kind: face, normal: [0, -1, 0]` 
- child 顶面接口：`mating_kind: face, normal: [0, 1, 0]`
- 求解器计算两面相贴 → child 的 z = parent 顶面 z + child 半高

### 4.2 接口默认 mating 参数

每个 InterfaceType 在 TypeSystem 中注册默认的 `mating_kind` 和 `mating_params`，用户不写时自动填充：

```python
# teleco 插件注册
type_system.register_interface_type("SFP28-cage", mating_kind="slot")
type_system.register_interface_type("SFP28-module", mating_kind="slot")
type_system.register_interface_type("IEC-C14", mating_kind="face")
type_system.register_interface_type("IEC-C13", mating_kind="face")
```

## 五、AABB 碰撞检测 Pass

### 5.1 Pass 设计

```python
class SpatialCollisionPass(Pass):
    """L4 碰撞检测：在 MIR 阶段运行。"""
    name = "spatial-collision"
    stage = PassStage.MIR
    description = "AABB 碰撞检测，产出 SPATIAL-00x 诊断"

    def run(self, ctx: PassContext) -> PassResult:
        resolved = ctx.resolved
        # 1. 收集所有有 BBox 的 resolved instance 及其全局 Transform
        objects = [
            (inst.fqid, inst.bbox, inst.global_transform)
            for inst in resolved.resolved_instances.values()
            if inst.bbox is not None and inst.global_transform is not None
        ]

        # 2. O(n²) 朴素检测（初期）
        for i in range(len(objects)):
            for j in range(i + 1, len(objects)):
                id_a, bbox_a, tf_a = objects[i]
                id_b, bbox_b, tf_b = objects[j]
                if aabb_overlap(bbox_a, tf_a, bbox_b, tf_b):
                    # 忽略 Mate 约束中的合法接触（通过 mate_graph 判断）
                    yield Diagnostic(
                        severity=Severity.WARNING,
                        code="SPATIAL-001",
                        message=f"{id_a} 与 {id_b} 发生空间碰撞",
                    )
```

### 5.2 碰撞排除规则

- 两个 Instance 之间存在 Mate 关系 → 合法接触，不报告
- 同一装配体内的子部件 → 不报告（由装配体的几何定义保证）
- 非实体 Instance（如 Room、Context）→ 跳过

## 六、迁移计划

### Phase 1：接口模型增强（本次）

1. `InterfaceSpec` 增加 `local_transform`、`mating_kind`、`mating_params`
2. `MateSpec` 增加 Schema 校验：parent/child 必须含 `/`（或通过语法糖消解后含 `/`）
3. `TypeSystem` 增加 `InterfaceTypeDef.mating_kind` 和 `.mating_params` 默认值

### Phase 2：Lowering 语法糖消解（本次）

1. `LoweringPass` 增加 `MateSugarResolveSubPass`
2. 兼容性矩阵查询

### Phase 3：几何求解器统一（本次）

1. 实现统一的 `solve_mate_constraint()` 基于 mating_kind
2. 替换 `_apply_mates_global` 中的硬编码分支

### Phase 4：碰撞检测（本次）

1. 实现 `SpatialCollisionPass`
2. AABB overlap 算法 + Mate 排除规则

## 七、向后兼容

- 旧 YAML 文件中裸 Instance ID 的 Mate 引用通过语法糖消解自动迁移
- 无法消解的（多对候选）产生编译警告而非错误（初期），提示用户显式指定接口
- `non_overridable` 标记自动应用到 `local_transform` 字段（Instance 不能覆盖）
