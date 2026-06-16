# ADR-013: 层级相对坐标布局

> 状态：已实现
> 日期：2026-06-16
> 作者：piki 核心团队
> 依赖：ADR-001（项目组织模型）、ADR-006（Mating Graph）
> 修订说明：将 ADR-006 §7 中“接口的位置/朝向/空间坐标（留给后续 ADR 或 Layout 扩展）”提升为由 Layout 的 `parent/transform` 机制覆盖。

## 背景

ADR-006 把 Layout 的职责定义为 **“放在哪里”**，Mate 的职责定义为 **“怎么耦合”**，二者正交、互不替代。这个分工在机柜、PDU、服务器等扁平部署场景下工作良好。

但随着装配体层级加深，纯全局坐标开始出现明显问题：

- **子装配体复用困难**：同一个 `SUB-ALPHA` 子装配体被放到 3 个不同位置时，必须重复描述其中每个零件的全局坐标。
- **移动父级时子级不一致**：移动一个 `AssemblyFamily` 时，其 `children` 或 `sub_assemblies` 中的每个实例都要单独改坐标，容易遗漏。
- **与 Mating 层级语义割裂**：Mate Graph 已经表达了 `parent/child` 的层级承载关系，但 Layout 却用全局坐标描述位置，两者在“谁依附于谁”上口径不一致。

因此，Layout 需要在保留全局坐标能力的同时，支持 **基于父级局部坐标系的相对位姿**。

---

## 1. 核心概念

### 1.1 两种坐标模式共存

```
模式 A：绝对坐标（保留）
  instance: PDU-01
  rack_id: RACK-A
  position_u: 10

模式 B：相对坐标（新增）
  instance: PCB-01
  parent: SUB-ALPHA
  transform:
    translation: [6, 6, 10]   # 相对于父级原点的 mm
    rotation: [0, 0, 0]       # 欧拉角，单位度
```

一个 `LayoutEntry` 要么用绝对模式，要么用相对模式，不允许同时填写两套坐标。

### 1.2 坐标系约定

- **全局坐标系**：项目级绝对坐标系，沿用现有 `position_x_mm / position_y_mm / position_z_mm`。
- **局部坐标系**：以父级 `LayoutEntry` 的全局位姿为原点的坐标系。
- **单位**：长度毫米（mm），旋转角度为度（°）。
- **旋转顺序**：Z-Y-X（偏航-俯仰-翻滚，Yaw-Pitch-Roll）。

### 1.3 装配树 vs 配合图

| | Assembly Tree（新增） | Mate Graph（ADR-006） |
|---|---|---|
| 表达的关系 | 空间上的父子依附 | 设计上的耦合约束 |
| 来源字段 | `LayoutEntry.parent` | `MateSpec.parent / MateSpec.child` |
| 边是否有 transform | 有 | 无 |
| 遍历方向 | 父 → 子 | 双向 |
| 回答的问题 | “这个 part 装在哪个 part 里面” | “这两个 part 必须满足什么约束” |

Assembly Tree 由 Layout 构建，Mate Graph 由 `mates/` 构建。两者可以重叠（例如父级相同），但职责不同。

---

## 2. 数据模型

### 2.1 LayoutEntry 扩展

```python
from dataclasses import dataclass
from adl.models.geometry import Transform

@dataclass
class LayoutEntry:
    instance: str

    # 绝对坐标模式
    rack_id: str | None = None
    position_u: int | None = None
    pdu_id: str | None = None
    row_id: str | None = None
    bay_index: int | None = None
    grid_id: str | None = None
    position_x_mm: float | None = None
    position_y_mm: float | None = None
    position_z_mm: float | None = None

    # 相对坐标模式
    parent: str | None = None
    transform: Transform | None = None
```

校验规则：

- `parent` 与任意绝对坐标字段互斥。
- `parent` 指向的实例必须在同一项目的 Layout 中定义，或在子装配体范围内解析。
- `parent` 不能指向自身。
- `transform` 缺省时默认为单位变换（`translation=[0,0,0], rotation=[0,0,0]`）。

### 2.2 Transform 复用

复用 `adl/models/geometry.py` 中已有的 `Transform`：

```python
class Transform(BaseModel):
    translation: Vec3
    rotation: Vec3
    scale: Vec3
```

在 Layout 场景下，`scale` 固定为 `[1, 1, 1]`，不参与空间位姿计算。

### 2.3 YAML 示例

#### 子装配体复用

```yaml
# layouts/layout.yaml
- instance: TOP-ASSEMBLY
  position_x_mm: 0
  position_y_mm: 0
  position_z_mm: 0

- instance: SUB-ALPHA-01
  parent: TOP-ASSEMBLY
  transform:
    translation: [100, 0, 50]
    rotation: [0, 0, 90]

- instance: PLATE-01
  parent: SUB-ALPHA-01
  transform:
    translation: [6, 6, 8]
    rotation: [0, 0, 0]

- instance: PCB-01
  parent: SUB-ALPHA-01
  transform:
    translation: [6, 6, 10]
    rotation: [0, 0, 0]
```

#### 与绝对坐标混合

```yaml
- instance: RACK-A01
  position_x_mm: 0
  position_y_mm: 0
  position_z_mm: 0

- instance: SRV-01
  rack_id: RACK-A01
  position_u: 10

- instance: COOLING-MANIFOLD-01
  parent: RACK-A01
  transform:
    translation: [0, 0, 1800]
    rotation: [0, 0, 0]
```

---

## 3. 引擎行为

### 3.1 加载阶段

```
1. 扫描 layouts/layout.yaml，加载所有 LayoutEntry。
2. 校验每个 LayoutEntry：
   a. 绝对坐标模式与相对坐标模式不能混用。
   b. parent 引用必须存在。
   c. parent 不能形成环。
3. 按依赖顺序构建全局位姿缓存：
   a. 先解析无 parent 的条目（绝对坐标）。
   b. 再按拓扑顺序解析有 parent 的条目，将父级全局位姿与子级局部 transform 级联。
4. 提供 `resolved_transform(instance_id)` API，返回全局位姿。
```

### 3.2 级联计算

全局位姿 = 父级全局位姿 × 子级局部 transform

```python
def resolve_global_transform(instance_id: str) -> Transform:
    entry = registry.get_layout_entry(instance_id)
    if entry.parent is None:
        return Transform.from_absolute(entry)
    parent_global = resolve_global_transform(entry.parent)
    return compose(parent_global, entry.transform)
```

### 3.3 Context API 增强

```python
class Context:
    def layout_parent(self, instance_id: str) -> str | None:
        """返回实例在空间装配树中的直接父级。"""

    def layout_children(self, instance_id: str) -> list[str]:
        """返回实例在空间装配树中的直接子级。"""

    def layout_ancestors(self, instance_id: str) -> list[str]:
        """返回从根到该实例的父级路径。"""

    def layout_descendants(self, instance_id: str) -> list[str]:
        """返回该实例下的所有后代实例。"""

    def resolved_transform(self, instance_id: str) -> Transform:
        """返回实例在项目全局坐标系下的解析后位姿。"""
```

---

## 4. 与现有 ADR 的关系

### 4.1 与 ADR-001（项目组织模型）

ADR-001 确立了 Instance 与 Layout 的分离。本 ADR 保持该分离：位姿信息仍在 `layouts/layout.yaml` 中，不进入 Instance 定义。

### 4.2 与 ADR-006（Mating Graph）

本 ADR **不替代** Mate Graph，而是补充空间层级表达：

- Mate 仍然回答“怎么耦合”。
- Layout 回答“放在哪里”，现在可以回答“相对于谁放在哪里”。
- Mate 的 `parent/child` 可以继续与 Layout 的 `parent` 不一致：例如两个零件通过螺栓 Mate 耦合，但各自在子装配体中的相对位置由 Layout 定义。

### 4.3 与 ADR-008（空间可视化策略）

3D 可视化管线从 Layout 读取全局位姿。相对坐标机制下，可视化层仍然消费 `resolved_transform()` 的结果，无需感知局部坐标系。

---

## 5. 范围边界

### 本 ADR 覆盖

- ✅ `LayoutEntry` 可选 `parent + transform`
- ✅ 绝对坐标与相对坐标两种模式共存
- ✅ 装配树构建（`layout_parent / layout_children / layout_ancestors / layout_descendants`）
- ✅ 全局位姿级联解析（`resolved_transform`）
- ✅ 环检测与加载期校验
- ✅ 与 Mate Graph 的职责划分

### 本 ADR 明确不覆盖

- ❌ 接口级位姿/朝向（一个设备上某个接口的局部坐标）
- ❌ 动态装配约束/关节（旋转副、滑动副、齿轮副等运动学约束）
- ❌ 连续变形或非刚性装配（焊缝变形、热膨胀补偿）
- ❌ 替代 Mate Graph 的 `parent/child` 语义
- ❌ 替代绝对坐标模式

---

## 6. 向后兼容

| 数据 | 处理 |
|------|------|
| 现有 `layouts/layout.yaml` 绝对坐标条目 | 完全兼容，无需改动 |
| 现有 `LayoutEntry` 字段 | 全部保留，新增 `parent` 和 `transform` 为可选 |
| 现有 Mate 文件 | 不受影响 |
| 现有可视化/规则代码 | 只要消费 `resolved_transform()`，无需改动 |
| 无 `parent` 的项目 | 装配树为空，现有逻辑照常运行 |

---

## 7. 决策总结

| 决策 | 选择 | 核心理由 |
|------|------|---------|
| 坐标模式 | 绝对 + 相对两种模式可选共存 | 简单场景保留绝对坐标，复杂装配体用相对坐标 |
| 相对坐标归属 | `LayoutEntry.parent + transform` | Layout 本来就负责“放在哪里”，不要侵入 Mate 的“怎么耦合” |
| 坐标系原点 | 父级 LayoutEntry 的全局位姿 | 与现有绝对坐标自然衔接 |
| 旋转表示 | 欧拉角 Z-Y-X，单位度 | 工程配置更直观，与常见 CAD/机器人工具一致 |
| 环检测 | 加载阶段报错 | 无环是解析全局位姿的前提 |
| scale | 固定 `[1,1,1]` | Layout 表达位姿，不表达缩放；缩放由 Instance/Asset 自己负责 |
| 与 Mate 的关系 | 正交补充 | Mate 管设计耦合，Layout 管空间位姿 |

---

## 8. 替代方案与拒绝理由

### 方案 A：把相对位姿放进 `MateSpec`

```yaml
- type: fixed
  parent: PLATE-01
  child: PCB-01
  constrains:
    - type: relative_transform
      translation: [0, 0, 2]
      rotation: [0, 0, 0]
```

**拒绝理由**：

- Mate 的职责是“设计耦合约束”，不是“空间部署”。把位姿放进去会让 Mate 同时承担 Layout 的职责。
- 子装配体复用场景下，Mate 是关系文件，不方便表达“某个子装配体实例被放到哪里”。
- ADR-006 的分工会变模糊。

### 方案 B：完全用相对坐标替换绝对坐标

**拒绝理由**：

- 机柜/PDU/服务器等扁平场景下，绝对坐标更直观。
- 破坏现有所有 sample 项目和用户配置。
- 项目级根实例必须有全局参考，不可能全部相对。

### 方案 C：用四元数代替欧拉角

**拒绝理由**：

- 欧拉角对人类阅读和手写 YAML 更友好。
- 工程配置中万向节锁不是主要风险；如后续需要，可在不破坏 schema 的情况下增加 `rotation_quat` 字段。

---

## 9. 参考

- [ADR-001: 项目组织模型](001-project-organization.md) — Instance/Layout 分离先例
- [ADR-006: 配合图（Mating Graph）](006-mating-graph.md) — Mate 与 Layout 的职责划分
- [ADR-008: 空间可视化策略](../visualization/008-spatial-visualization-strategy.md) — 3D 全局位姿消费方
- [设计知识成熟曲线](../concepts/06-knowledge-maturation.md) — 结构声明优先于规则遍历
