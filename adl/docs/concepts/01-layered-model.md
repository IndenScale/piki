# ADL 分层概念模型：PDL / PML / PLL

> ADL（Assembly Definition Language）用三个正交子语言描述装配体：
> **存在（PDL）→ 耦合（PML）→ 位置（PLL）**。
> 这一顺序对应工程设计的自然流程：先定义有什么，再定义怎么配合，最后定义放在哪。

---

## 一、三层总览

| 层级 | 子语言 | 核心问题 | 对应文件/目录 | 关键概念 |
|------|--------|----------|---------------|----------|
| L1 | **PDL** — Part Definition Language | 什么东西存在？ | `instances/`、`models/`、`catalogs/` | Family、Model、Instance、Part、Assembly、Interface、Footprint、Catalog |
| L2 | **PML** — Part Mating Language | 它们怎么配合？ | `mates/` | Mate、MatingKind、InterfacePairing、MateConstraint、InterfaceSignature、DOF、DiscreteState |
| L3 | **PLL** — Part Layout Language | 它们放在哪里？ | `layouts/` | Layout、LayoutEntry、绝对坐标、相对坐标（parent/transform）、Grid、参数化定位链、全局坐标 |

三层的关键设计原则是**正交分离**：

- 改 PDL（换设备型号）不应触碰 PML 或 PLL。
- 改 PML（换配合方式）不应要求重写 PDL 或 PLL。
- 改 PLL（调整部署位置）不应污染 PDL 或 PML。

这种分离使 Git diff 清晰、多人协作不冲突，也让 Agent 可以逐层操作。

---

## 二、PDL：Part Definition Language（部件定义语言）

PDL 回答"**什么东西存在**"，定义工程实体的身份、类型、属性、接口以及在 Part 内部的位姿。

### 2.1 核心概念

| 概念 | 含义 | 代码/Schema 对应 |
|------|------|------------------|
| **Family** | 型号族：约束结构，定义一类实体必须有哪些字段。 | `pydantic BaseModel`，插件注册 |
| **Model** | 型号：厂商或项目默认值。 | `models/*.yaml` |
| **Instance** | 实例：实际部署的实体，可覆盖 Model 默认值。 | `instances/*.yaml` → `ResolvedInstance` |
| **Part** | 零件：不可再分的物理单元，一种 Instance。 | `family: AssemblyPartFamily` 等 |
| **Assembly** | 装配体：由多个 Part 或子装配体组成。 | `AssemblyFamily`，`children`/`sub_assemblies` |
| **Interface** | 接口：Part/Assembly 对外暴露的可连接点。 | `interfaces[]` → `InterfaceSpec` |
| **Footprint** | 封装：多 pin 连接器，内部包含多个 Interface。 | `footprints[]` → `FootprintSpec` |
| **Catalog** | 目录：权威层数据（厂商、生命周期、服务方法）。 | `catalogs/` → `CatalogEntry` |

### 2.2 文件示例

```yaml
# instances/parts/SFP28-MOD-A.yaml
id: SFP28-MOD-A
family: AssemblyPartFamily
name: SFP28 25G-LR 光模块
part_type: sfp28-transceiver
width_mm: 14
height_mm: 12
depth_mm: 56
interfaces:
  - id: cage-interface
    interface_type: SFP28-module
    direction: bidirectional
    local_transform:
      translation: [0, 6, 28]
  - id: lc-port
    interface_type: generic-face
    local_transform:
      translation: [0, 6, 56]
```

### 2.3 接口位姿与坐标系

每个 Interface 通过 `local_transform` 声明在**所属 Part 局部坐标系**中的位姿：

```yaml
local_transform:
  translation: [x, y, z]   # 单位：mm
  rotation: [rx, ry, rz]   # Z-Y-X 欧拉角，单位：度
  scale: [sx, sy, sz]      # 通常保持 [1, 1, 1]
```

- `translation`：接口原点相对 Part 原点的偏移。
- `rotation`：按 Z→Y→X 顺序旋转，定义接口坐标轴方向。
- 配合面法向等语义可通过 `mating_params.normal` 进一步显式声明。

> 完整 Transform 定义见 `adl/geometry/models.py`。

---

## 三、PML：Part Mating Language（部件配合语言）

PML 回答"**它们怎么配合**"，在两个 Part 的接口之间建立几何或逻辑约束。

### 3.1 核心概念

| 概念 | 含义 | 代码/Schema 对应 |
|------|------|------------------|
| **Mate** | 一条配合关系，连接 parent 和 child。 | `MateSpec` |
| **MatingKind** | 配合类型，决定几何约束方程。 | `MatingKind` 枚举 |
| **Interface Pairing** | 接口级配对，记录 Mate 带来的具体接口连接。 | `InterfacePairing` |
| **MateConstraint** | 配合引入的固有约束，加载时自动验证。 | `MateConstraint` |
| **InterfaceSignature** | 接口运动自由度签名，描述配合后还能怎么动。 | `InterfaceSignature` |
| **DOF** | 连续自由度（平移/旋转/螺旋）。 | `DOF` + `DOFType` |
| **DiscreteState** | 离散状态（插入/拔出/闭合/反插等）。 | `DiscreteState` |

### 3.2 MatingKind 枚举

`mating_kind` 描述两个接口接触面之间的几何约束关系（见 `adl/compiler/mating_kinds.py`）：

| 取值 | 描述 | 约束自由度数 |
|------|------|--------------|
| `face` | 面贴合：法向对齐 + 距离 = 0 | 3 |
| `axis` | 轴配合：两轴线重合 | 4 |
| `point` | 点配合：两点重合 | 3 |
| `slot` | 槽配合：沿一个方向平移 | 2 |
| `rail` | 导轨配合：沿导轨方向平移 | 5 |
| `none` | 无几何约束，仅逻辑配对 | 0 |

### 3.3 自由度签名（ADL-004）

`InterfaceSignature` 描述配合后部件还允许哪些运动：

- **DiscreteState**：离散位置，如 `inserted`、`removed`、`reversed`。
- **Continuous DOF**：连续自由度，如抽屉拉出、铰链开门、螺丝旋入。

内置签名注册表（`adl/geometry/interface_signature.py`）已包含 USB-C、3.5mm 耳机、IEC、抽屉滑轨、铰链、SFP28、RJ45、螺丝孔等类型。

### 3.4 文件示例（接口优先配合）

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
```

```yaml
# mates/face-on-face/CABINET-DOOR.yaml
type: face-on-face
parent: CABINET/door-hinge
child: DOOR/hinge-side
at:
  theta_deg:
    default: 0
    min: 0
    max: 180
```

> PML 采用"接口优先"原则：Mate 的 `parent`/`child` 推荐写成 `instance_id/interface_id` 形式。裸 Instance ID 是语法糖，由 Lowering pass 消解为接口引用。详见 ADL-003。

---

## 四、PLL：Part Layout Language（部件布局语言）

PLL 回答"**它们放在哪里**"，给没有 Mate 认领的实体、或作为配合求解的根节点提供空间位置。

### 4.1 核心概念

| 概念 | 含义 | 代码/Schema 对应 |
|------|------|------------------|
| **Layout** | 一个项目的完整部署声明。 | `Layout` |
| **LayoutEntry** | 单条部署记录。 | `LayoutEntry` |
| **绝对坐标** | 直接给出 X/Y/Z 坐标。 | `position_x_mm` / `position_y_mm` / `position_z_mm` |
| **相对坐标** | 通过 `parent` + `transform` 级联定位。 | `parent` + `transform` |
| **Grid** | 轴网：把符号坐标解析为绝对坐标。 | `Grid` |
| **参数化定位链** | 从根节点到当前节点的 Transform 级联链。 | `Layout.resolved_transform()` |
| **全局坐标** | 考虑 Layout 与 Mate 约束后，Part 在世界坐标系中的最终位姿。 | `AssemblyScene` / `GeometryProvider` |

### 4.2 文件示例

```yaml
# layouts/layout.yaml
- instance: ACCESS-SW
  position_x_mm: 0
  position_y_mm: 0
  position_z_mm: 0

- instance: ODF-PANEL
  position_x_mm: 0
  position_y_mm: 200
  position_z_mm: 0
```

```yaml
# 相对坐标示例
- instance: CASE-01
  position_x_mm: 0
  position_y_mm: 0
  position_z_mm: 0

- instance: DAMP-BOTTOM
  parent: CASE-01
  transform:
    translation: [0, 0, 1]
```

### 4.3 Layout 与 Mate 的关系

| 场景 | 行为 |
|------|------|
| 实体有 Mate 认领其为 child | 位姿由 Mate 约束求解器决定，通常不需要 Layout 条目。 |
| 实体是装配根节点 | 必须在 Layout 中给出绝对坐标或父级引用。 |
| 实体无 Mate、也无 Layout | 编译器产出未定位诊断。 |
| Layout 与 Mate 结果冲突 | 产出 `ASSEMBLY-002` WARNING，提示差异。 |

### 4.4 坐标优先级

同一条 `LayoutEntry` 中，位姿解析遵循：

1. `parent + transform`（相对坐标）最高；
2. 否则使用显式绝对坐标 `position_x/y/z_mm`；
3. 缺失维度从 `grid_id` + `grid_position` / `row_id` + `bay_index` 解析；
4. 仍未指定的维度默认值为 0。

> 完整 Layout 格式规范见 `piki/docs/reference/05-layout.md`。

---

## 五、从三层到全局位姿：参数化定位链

ADL 求解全局位姿的输入是三层数据的组合：

```text
PDL 提供：Part/Interface 的局部几何（local_transform、BBox）
PML 提供：接口之间的约束关系（mating_kind、signature、at 参数）
PLL 提供：根节点坐标 + 无 Mate 实体的手动定位
        ↓
   约束求解器
        ↓
全局坐标（global_transform）+ 运动控制参数（controls）
```

### 5.1 参数化定位链公式

对于有 Mate 的 child Part，其全局位姿由以下链式乘积决定：

```text
P_child_global = P_parent_global
               × T_parent_iface_local      (PDL：parent 接口局部位姿)
               × T_mate(discrete_state)    (PML：离散状态变换)
               × T_dof(d1, d2, ..., dn)    (PML：连续自由度变换)
               × T_child_iface_local⁻¹    (PDL：child 接口局部位姿的逆)
```

- `P_parent_global` 本身可能来自另一条 Mate 链，也可能来自 PLL 给定的根节点坐标。
- `T_dof(...)` 使同一装配体可以参数化地表达"抽屉拉出 200mm"、"门打开 90°"等状态。

### 5.2 运动控制导出

配合求解后，`AssemblyScene.controls` 导出：

- **连续自由度** → 前端滑块控件（如铰链角度、抽屉拉出距离）。
- **离散状态** → 按钮/下拉选择（如 USB-C 正插/反插/拔出）。

---

## 六、文件目录与层级对应

```text
my-assembly/
├── piki.toml
├── instances/              # ← PDL
│   ├── parts/
│   │   ├── PART-A.yaml
│   │   └── PART-B.yaml
│   └── assembly/
│       └── SUB-ASSY.yaml
├── models/                 # ← PDL（型号默认值，可选）
│   └── part-model.yaml
├── catalogs/               # ← PDL（权威层，可选）
│   └── vendor-catalog.yaml
├── mates/                  # ← PML
│   ├── face-on-face/
│   │   └── A-B.yaml
│   └── slot/
│       └── CAGE-MODULE.yaml
└── layouts/                # ← PLL
    └── layout.yaml
```

---

## 七、与相关文档的衔接

| 想深入了解 | 阅读 |
|-----------|------|
| PML 接口优先设计 | [ADL-003：接口优先的配合建模](../adr/003-interface-first-mating.md) |
| 接口运动自由度签名 | [ADL-004：接口签名系统](../adr/004-interface-signature.md) |
| 装配体建模流程 | [装配体建模指南](../guides/modeling-assemblies.md) |
| PDL Instance 格式 | `piki/docs/reference/04-instance.md` |
| PLL Layout 格式 | `piki/docs/reference/05-layout.md` |
| ADL 在 piki 中的定位 | `piki/docs/pitch/03-adl.md` |
| 编译器架构 | [ADL-002：编译器架构设计](../adr/002-compiler-architecture.md) |
