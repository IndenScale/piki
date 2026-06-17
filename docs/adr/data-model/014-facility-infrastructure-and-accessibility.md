# ADR-014: 机房基础设施与可达性分析

> 状态：实现中
> 日期：2026-06-16
> 作者：piki 核心团队
> 依赖：ADR-001（项目组织模型）、ADR-006（Mating Graph）、ADR-013（层级相对坐标布局）
> 修订说明：将机房设计中常被忽略但影响 DRC 的「非部件元素」提升为一等概念，包括空间区域、运动包络与承重能力。

## 背景

ADR-013 让 Layout 可以表达「谁相对于谁放在哪」，但机房里的很多关键设计元素并不是传统意义上的「设备/部件」：

- **防静电地板 / 抬高地板**：它有厚度、有钢架网格、有架空层，承载所有机柜载荷。
- **物流斜坡**：连接室外地面与抬高地板，坡度、宽度、转弯半径决定设备能否进场。
- **门**：不仅是几何体，开合时会扫过一个空间区域，必须保证不与机柜/走线架碰撞。
- **除尘地垫 / 粘尘垫**：门前的一片区域，与门扇扫掠区有净距要求。
- **车辆动线**：平板车、液压车、机柜运输推车的虚拟路径，需要检查转弯包络。
- **承重能力**：地板/楼板的均布载荷与集中载荷，决定了能否上高密度机柜或未来扩容。

这些元素如果不建模，后续 DRC 就只能做静态几何碰撞，无法回答：

- 门开到 110° 会不会撞到 RACK-C01？
- 上高密度机柜后，局部地板承重是否超限？
- 平板车从门外到 A-B 通道的转弯会不会擦到机柜？
- 斜坡顶端是否与抬高地板平齐？

本 ADR 引入 **Space（空间约束实体）**、**KinematicEnvelope（运动包络）** 和 **LoadCapacity（承重能力）** 三类基础抽象，并在 telecom 领域扩展出具体类型与 DRC 规则。

---

## 1. 核心概念

### 1.1 三层实体

```
Facility（实体基础设施）       Space（无形空间/约束区域）      Structure/Load（能力属性）
  ├─ 门 (door)                   ├─ 车辆动线 (vehicle-path)     ├─ 承重能力
  ├─ 抬高地板 (raised-floor)     ├─ 门开合扫掠区                ├─ 集中载荷
  ├─ 钢架网格 (floor-grid)       ├─ 除尘地垫区域                └─ 动态系数
  ├─ 物流斜坡 (ramp)             ├─ 维护净空区
  ├─ 供电柜 (power-cabinet)      └─ 地板下架空层 (plenum-zone)
  ├─ ODF
  └─ 消防气瓶 (fire-suppression)
```

### 1.2 Facility vs Space vs Load

| | Facility | Space | LoadCapacity |
|---|---|---|---|
| 是否有物理 BOM | 是（或可视化为实体） | 否 | 否 |
| 是否参与碰撞检测 | 是 | 是 | 作为被引用的能力值 |
| 是否有 transform | 是 | 是（通过 Layout） | 否，挂接在 Facility/Instance 上 |
| 典型例子 | 门、斜坡、供电柜 | 车辆路径、扫掠区、地垫 | 地板承重 800kg/m² |

### 1.3 基础抽象与领域类型的分层

```
ADL 基础模型（跨领域复用）
  ├─ KinematicEnvelope
  ├─ Space
  └─ LoadCapacity

piki telecom plugin（机房领域）
  ├─ FacilityFamily.facility_type = raised-floor | floor-grid | ramp | door | ...
  ├─ FacilityFamily.kinematics = KinematicEnvelope
  ├─ FacilityFamily.load_capacity = LoadCapacity
  ├─ SpaceFamily.space_type = vehicle-path | clearance-zone | sticky-mat | plenum-zone
  └─ Mate type = must-clear | must-be-inside | minimum-distance
```

---

## 2. 数据模型

### 2.1 ADL 基础抽象

```python
# adl/models/geometry.py

class KinematicEnvelope(BaseModel):
    """运动包络：描述一个刚体在特定运动下的扫掠空间。"""

    type: Literal["hinged-door", "sliding-door", "revolving", "custom"] = "hinged-door"
    hinge_axis: Vec3 = Field(default_factory=lambda: Vec3(x=0, y=0, z=1))
    hinge_position: Vec3 = Field(default_factory=Vec3)  # 在局部坐标系中
    swing_range_deg: tuple[float, float] = (0.0, 110.0)
    sweep_segments: int = Field(default=8, ge=2, le=64)


class Space(BaseModel):
    """无形空间区域，用于表达虚拟动线、净空区、地垫等。"""

    type: Literal["box", "corridor", "waypoints", "cylinder"] = "box"
    # box: size
    size: Vec3 | None = None
    # corridor: 中心线 + 宽度 + 高度
    centerline: list[Vec3] | None = None
    corridor_width_mm: float | None = None
    corridor_height_mm: float | None = None
    # waypoints: 路径点 + 半径
    waypoints: list[Vec3] | None = None
    waypoint_radius_mm: float | None = None


class LoadCapacity(BaseModel):
    """承重能力：用于地板、楼板、货架等承载实体。"""

    uniform_load_kg_m2: float = Field(default=0.0, ge=0.0)
    point_load_kg: float = Field(default=0.0, ge=0.0)
    max_concentrated_load_kg: float = Field(default=0.0, ge=0.0)
    dynamic_factor: float = Field(default=1.0, ge=1.0)
```

### 2.2 FacilityFamily 扩展

```python
class FacilityFamily(BaseModel):
    id: str
    name: str = ""
    facility_type: str  # door | raised-floor | floor-grid | ramp | power-cabinet | odf | fire-suppression | ...
    room_id: str = ""
    width_mm: float = 0
    depth_mm: float = 0
    height_mm: float = 0
    floor_x_mm: float = 0
    floor_y_mm: float = 0
    position_z_mm: float = 0
    orientation_deg: float = 0
    kinematics: KinematicEnvelope | None = None  # 用于门/盖板等
    load_capacity: LoadCapacity | None = None     # 用于地板/货架/斜坡等
    assets: GeometryAssets | None = None
    tags: Tags = Field(default_factory=Tags)
```

### 2.3 新增 SpaceFamily

```python
class SpaceFamily(BaseModel):
    id: str
    name: str = ""
    space_type: str  # vehicle-path | clearance-zone | sticky-mat | plenum-zone | access-aisle
    room_id: str = ""
    shape: Space
    scope: str = "background"  # background / context / new
    tags: Tags = Field(default_factory=Tags)
```

### 2.4 YAML 示例

#### 门（带运动包络）

```yaml
# instances/facilities/DOOR-MAIN.yaml
id: DOOR-MAIN
family: FacilityFamily
name: 机房主门
facility_type: door
width_mm: 200
depth_mm: 1200
height_mm: 2200
floor_x_mm: -100
floor_y_mm: 2000
orientation_deg: 0
kinematics:
  type: hinged-door
  hinge_axis: [0, 0, 1]
  hinge_position: [0, 0, 0]
  swing_range_deg: [0, 110]
  sweep_segments: 16
```

#### 车辆动线

```yaml
# instances/spaces/VEHICLE-PATH-MAIN.yaml
id: VEHICLE-PATH-MAIN
family: SpaceFamily
name: 主物流通道
space_type: vehicle-path
room_id: ROOM-01
shape:
  type: corridor
  centerline:
    - [0, 2600, 0]
    - [1000, 2600, 0]
    - [1800, 2600, 0]
  corridor_width_mm: 1800
  corridor_height_mm: 2200
```

#### 抬高地板（带承重能力）

```yaml
# instances/facilities/RAISED-FLOOR.yaml
id: RAISED-FLOOR
family: FacilityFamily
name: 防静电抬高地板
facility_type: raised-floor
width_mm: 4600
depth_mm: 7600
height_mm: 400
floor_x_mm: 0
floor_y_mm: 0
position_z_mm: 0
load_capacity:
  uniform_load_kg_m2: 800
  point_load_kg: 2000
  max_concentrated_load_kg: 4000
  dynamic_factor: 1.2
```

---

## 3. 引擎行为

### 3.1 加载阶段

1. 解析 Facility/Space 实例时，识别 `kinematics`、`shape`、`load_capacity` 字段。
2. 对带 `kinematics` 的 Facility，预计算若干采样角度下的 AABB 包络。
3. 对 `Space` 实例，根据 `type` 构建 AABB 或 corridor 几何。
4. 校验 `LoadCapacity` 数值非负，`dynamic_factor >= 1`。

### 3.2 DRC 规则

| 规则 ID | 名称 | 输入 | 行为 |
|---|---|---|---|
| `TELECOM-ACCESS-001` | 门开合扫掠区无碰撞 | 带 kinematics 的门 + 周围实例 | 将门从 `swing_range_deg` 扫过，检查扫掠体 AABB 是否与其他实例 AABB 相交 |
| `TELECOM-ACCESS-002` | 车辆路径有效 | `vehicle-path` Space + 机柜/设施 | 检查 corridor 宽度 ≥ 车宽 + 安全边距；转弯处按最小转弯半径生成包络，检查不碰撞 |
| `TELECOM-LOAD-001` | 地板承重 sufficient | 地板 `LoadCapacity` + 机柜总重 | 累加各机柜及设备重量，检查是否超过均布/集中载荷 |
| `TELECOM-LOAD-002` | 高密度机柜局部集中载荷 | 相邻重载机柜 | 判断局部区域载荷是否超过 `max_concentrated_load_kg` |
| `TELECOM-FLOOR-001` | 斜坡与抬高地板配合 | ramp Facility + raised-floor Facility | 检查 ramp 顶端高度与 raised-floor 高度匹配，坡度在规范内 |

### 3.3 Mate 类型扩展

为表达空间配合关系，新增 Mate 类型：

- `must-clear`：child 的运动包络不能与 parent 相交。
- `must-be-inside`：child 必须位于 parent 的空间内。
- `minimum-distance`：child 与 parent 保持最小净距。

示例：

```yaml
# mates/door-swing-clearance/DOOR-MAIN-RACK-C01.yaml
type: must-clear
parent: RACK-C01
child: DOOR-MAIN
notes: 主门 110° 开合不得与 C 列首机柜碰撞
```

---

## 4. 与现有 ADR 的关系

### 4.1 与 ADR-001（项目组织模型）

保持 Instance/Layout 分离：基础设施与空间区域都是 Instance，位姿仍在 `layouts/layout.yaml` 中。

### 4.2 与 ADR-006（Mating Graph）

Mating 的职责从「部件耦合」扩展到「空间耦合」。`must-clear`、`must-be-inside`、`minimum-distance` 等 Mate 类型不引入新的接口配对，只声明空间约束。

### 4.3 与 ADR-013（层级相对坐标布局）

Space 和 Facility 都通过 Layout 的 `parent + transform` 挂接到 ROOM/ROW/DOOR 下。例如 `VEHICLE-PATH-MAIN` 可以 `parent: ROOM-01`，`STICKY-MAT-MAIN` 可以 `parent: DOOR-MAIN`。

---

## 5. 范围边界

### 本 ADR 覆盖

- ✅ `SpaceFamily` 作为无形空间/约束区域的一等概念
- ✅ `FacilityFamily` 的 `kinematics` 与 `load_capacity` 扩展
- ✅ `KinematicEnvelope`、`Space`、`LoadCapacity` 三个 ADL 基础抽象
- ✅ 机房领域常用 facility_type / space_type 的语义约定
- ✅ DRC 规则：门开合、车辆路径、地板承重、斜坡配合
- ✅ Mate 空间约束类型：`must-clear`、`must-be-inside`、`minimum-distance`

### 本 ADR 明确不覆盖

- ❌ 实时物理仿真或精确刚体动力学
- ❌ 机器人/AGV 的复杂运动学逆解
- ❌ 动态载荷时序分析（地震、冲击）
- ❌ 消防气流的 CFD 仿真
- ❌ 精确 CAD 扫掠体（第一阶段用 AABB 近似）

---

## 6. 向后兼容

| 数据 | 处理 |
|------|------|
| 现有 Facility 实例 | `kinematics`、`load_capacity` 为可选，不加则行为不变 |
| 现有 Layout 文件 | 不强制要求 Space 条目，无 Space 的项目照常运行 |
| 现有 Mate 文件 | 新增空间 Mate 类型为可选，不影响已有 mate |
| 现有 DRC 规则 | 新增规则只在相关字段存在时触发，不会误报 |
| 前端 | 新增 family 会被当作未知类型显示，不会阻断加载；后续可逐步添加可视化 |

---

## 7. 决策总结

| 决策 | 选择 | 核心理由 |
|---|---|---|
| 抽象层级 | ADL 提供通用抽象，telecom plugin 提供领域类型 | 保持跨领域复用，避免 FacilityFamily 膨胀 |
| Space 是否独立 Family | 是，新增 `SpaceFamily` | 与 Facility 区分：无形区域不参与 BOM，但参与 DRC |
| 运动包络表示 | `KinematicEnvelope` 参数化 + AABB 采样近似 | 足够支持 DRC，避免引入重型 CAD 内核 |
| 承重能力 | `LoadCapacity` 挂在 Facility/Instance 上 | 地板、货架、斜坡等承载实体都可复用 |
| 空间约束 | 通过新增 Mate 类型表达 | 与 ADR-006 的 Mating Graph 自然衔接 |
| 第一阶段精度 | AABB 近似 | 快速落地，后续可替换为 OBB 或精确扫掠体 |

---

## 8. 参考

- [ADR-001: 项目组织模型](001-project-organization.md) — Instance/Layout 分离先例
- [ADR-006: 配合图（Mating Graph）](006-mating-graph.md) — Mate 的广义耦合定义
- [ADR-013: 层级相对坐标布局](013-relative-coordinate-layout.md) — Space/Facility 的层级挂接方式
- [设计知识成熟曲线](../concepts/06-knowledge-maturation.md) — 从规则遍历到结构声明的演化
