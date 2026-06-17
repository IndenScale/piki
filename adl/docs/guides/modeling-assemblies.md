# 装配体建模指南

> 用 ADL 描述一个多零件装配体：从配合关系出发，逐步构建空间定位链。

---

## 核心心智模型

装配体建模有两类文件：

| 文件 | 职责 | 谁先写 |
|------|------|--------|
| `mates/<type>/*.yaml` | **配合关系**——零件之间怎么耦合（面贴合、轴对齐、槽插入） | **先写** |
| `layouts/layout.yaml` | **定位参数**——给 Mate 注入参数值，或给根节点赋绝对坐标 | **后写** |

**顺序不是任意的：先有配合关系，Layout 里填的是配合约束的求解参数，而不是另一套独立的位置描述。**

Layout 中能填两类值：

- **Mate 参数**：`parent` 引用 + `transform` 只是给约束求解器的初始值；Mate 求解后会覆盖
- **绝对坐标**：根节点（没有 Mate 认领的零件）的场景坐标

---

## 第一阶段：Instance + Mate——配合先行

建模的第一步不是"放在哪"，是"怎么配合"。

### 1.1 定义零件和接口

```
my-assembly/
├── instances/
│   └── parts/
│       ├── BASE.yaml
│       └── LID.yaml
└── mates/
    └── face-on-face/
        └── BASE-LID.yaml
```

```yaml
# instances/parts/BASE.yaml
id: BASE
family: AssemblyPartFamily
name: 底座
width_mm: 100
height_mm: 20
depth_mm: 100
interfaces:
  - id: top-face
    interface_type: generic-face
    local_transform:
      translation: [0, 10, 50]
```

```yaml
# instances/parts/LID.yaml
id: LID
family: AssemblyPartFamily
name: 上盖
width_mm: 100
height_mm: 5
depth_mm: 100
interfaces:
  - id: bottom-face
    interface_type: generic-face
    local_transform:
      translation: [0, 0, 50]
```

### 1.2 声明配合（Mate）

```yaml
# mates/face-on-face/BASE-LID.yaml
type: face-on-face
parent: BASE/top-face
child: LID/bottom-face
at:
  distance: 0                          # 面-面间隙为 0
```

**这一步已经完成了位置推导：** 引擎在构建时通过约束求解器，根据 `BASE.top-face` 的全局位姿和 `LID.bottom-face` 的相对变换，解算出 LID 的精确全局位姿。不再需要在 Layout 里再填一遍。

### 1.3 根节点需要绝对坐标

BASE 没有被任何 Mate 认领为 child，它是装配的根。根节点需要在 Layout 中给出绝对坐标：

```yaml
# layouts/layout.yaml
- instance: BASE
  position_x_mm: 0
  position_y_mm: 0
  position_z_mm: 0
```

LID 不需要出现在 Layout 中——它的位姿由 Mate 推导。

---

## 第二阶段：Layout 作为 Mate 的参数注入层

当 Mate 有可调参数（`t`、`theta_deg`、`u`、`v` 等），Layout 可以在 `at` 字段中设置它们的默认值。`parent + transform` 只是给约束求解器的初始近似，最终位姿由 Mate 决定。

### 2.1 铰链门：旋转参数注入

```yaml
# instances/parts/CABINET.yaml
id: CABINET
family: AssemblyPartFamily
width_mm: 600
height_mm: 1000
depth_mm: 400
interfaces:
  - id: door-hinge
    interface_type: hinge-frame
    local_transform:
      translation: [0, 0, 0]
```

```yaml
# instances/parts/DOOR.yaml
id: DOOR
family: AssemblyPartFamily
width_mm: 600
height_mm: 1000
depth_mm: 20
interfaces:
  - id: hinge-side
    interface_type: hinge-leaf
    local_transform:
      translation: [0, 0, 0]
```

```yaml
# mates/face-on-face/CABINET-DOOR.yaml
type: face-on-face
parent: CABINET/door-hinge
child: DOOR/hinge-side
at:
  theta_deg:                           # 旋转参数（注入给约束求解器）
    default: 0
    min: 0
    max: 180
```

**`hinge-frame` + `hinge-leaf`** 两个接口类型在 ADL 中已预注册旋转 DOF（绕 Y 轴 0°~180°）。`theta_deg` 参数暴露给约束求解器，同时也导出为前端滑块控件。

根节点 CABINET 的 Layout：

```yaml
# layouts/layout.yaml
- instance: CABINET
  position_x_mm: 0
  position_y_mm: 0
  position_z_mm: 0
```

DOOR 不在 Layout 中——它的位姿由铰链配合约束完全决定。

### 2.2 槽配合：推入参数注入

```yaml
# mates/slot/CAGE-MODULE.yaml
type: slot
parent: CAGE/slot-1
child: MODULE/pin
at:
  t:                                  # 沿槽方向的推入距离
    default: 10
    min: 0
    max: 40
```

`t` 是槽配合的推入参数，约束求解器沿 `slot_dir` 方向推入 `t` mm 后确定 child 的位姿。

---

## 第三阶段：Layout `parent/transform` 的真实角色

上一阶段我们看到：Matt 约束求解后，child 的位姿完全由 Mate 决定。那 Layout 里的 `parent/transform` 还有什么用？

**两个用途：**

1. **给没有 Mate 的固定装配关系提供定位**（如 PCB 的 standoff 螺柱位置已知，直接用 Layout 声明即可）
2. **作为 Mate 约束求解的初始近似**，加速求解器收敛——但最终结果仍由 Mate 覆盖

### 3.1 纯 Layout 定位（无 Mate 场景）

```yaml
# layouts/layout.yaml
- instance: CASE-01
  position_x_mm: 0
  position_y_mm: 0
  position_z_mm: 0

- instance: DAMP-BOTTOM
  parent: CASE-01
  transform:
    translation: [0, 0, 1]
```

底壳隔音垫的配合没有标准接口类型，用手写 `parent/transform` 直接声明位置即可。

### 3.2 Layout + Mate 共存（求解器初始值）

```yaml
# layouts/layout.yaml
- instance: CASE-01
  position_x_mm: 0
# ...
- instance: PCB-01
  parent: CASE-01
  transform:
    translation: [6, 6, 10]           # 初始近似——Mate 求解后会覆盖
```

```yaml
# mates/pcb-standoff-mount/CASE-01-PCB-01.yaml
type: pcb-standoff-mount
parent: CASE-01
child: PCB-01
at:
  standoff_positions: [top-left, top-right, bottom-left, ...]
```

引擎先根据 Layout 算出 PCB-01 的基础位姿，然后 Mate 解算覆盖。如果两者差异超过阈值，产生 `ASSEMBLY-002` WARNING 提示用户审阅。

---

## 第四阶段：运动自由度——接口签名

每个接口类型在 ADL 中有预定义的**运动学签名（InterfaceSignature）**，描述配合后仍有哪些自由度。

| 接口类型对 | 自由度 | 离散状态 |
|-----------|--------|---------|
| `hinge-frame` ↔ `hinge-leaf` | 绕 Y 轴旋转 0°~180° | closed（默认） |
| `SFP28-cage` ↔ `SFP28-module` | 无连续自由度 | removed / inserted（默认） |
| `IEC-C13` ↔ `IEC-C14` | 无连续自由度 | removed / inserted（默认） |
| `USB-C-receptacle` ↔ `USB-C-plug` | 无连续自由度 | removed / inserted（默认）/ reversed |
| `screw-hole` ↔ `screw-thread` | 螺旋旋入 0~25mm | removed / seated（默认） |
| `drawer-slide-female` ↔ `drawer-slide-male` | Z 轴平移 0~300mm | closed（默认） |
| `RJ45-jack` ↔ `RJ45-plug` | 无连续自由度 | removed / inserted（默认） |
| `TRS-3.5mm-jack` ↔ `TRS-3.5mm-plug` | 绕 Z 轴旋转 0°~360° | removed / inserted（默认） |

构建后 `AssemblyScene.controls` 会将 DOF 参数导出为前端滑块，离散状态导出为按钮。

---

## 第五阶段：子装配体——可复用的配合模块

当一个装配体有可复用的子组件时，可以嵌套。

### 5.1 子装配体实例

```yaml
# instances/assembly/SUB-ALPHA.yaml
id: SUB-ALPHA
family: AssemblyFamily
name: 字母区子装配体
assembly_type: sub-assembly
children: []
sub_assemblies: []
```

### 5.2 子装配体内部的 Mate

```
mates/switch-plate-snap/PLATE-01-SW-A.yaml   # 子装配体内部配合
mates/pcb-standoff-mount/CASE-01-PCB-01.yaml  # SUB-ALPHA 内部 PCB 到 CASE
```

### 5.3 子装配体自身的 Mate

```yaml
# mates/plate-gasket-mount/CASE-01-PLATE-01.yaml
type: plate-gasket-mount
parent: CASE-01
child: PLATE-01
```

PLATE-01 是 SUB-ALPHA 的成员，配合到 CASE-01 上。SUB-ALPHA 本身不需要在 Layout 中有独立条目——它的位姿由 PLATE-01 的配合链推导。

---

## 第六阶段：冲突检测——Layout 参数与 Mate 解算结果不一致

当同一个零件在 Layout 中声明了 `parent/transform`，同时又有 Mate 认领它时，引擎自动检测差异。

### 会触发 WARNING

```yaml
# layouts/layout.yaml
- instance: PCB-01
  parent: CASE-01
  transform:
    translation: [6, 6, 10]          # 手写的近似值
```

```yaml
# mates/pcb-standoff-mount/CASE-01-PCB-01.yaml
type: pcb-standoff-mount
parent: CASE-01
child: PCB-01
```

引擎输出：

```
[WARNING] ASSEMBLY-002: 'PCB-01' 的位姿由 Mate 'pcb-standoff-mount' 重新计算，
与 Layout 声明存在差异: 平移 Δ=(+0.0, +0.0, -2.0)mm
```

### 不会触发

- child 没有 Layout entry（纯 Mate 驱动）——完全合法
- Layout 值与 Mate 结果一致（差异 <0.5mm 且 <0.1°）

---

## 完整决策树

```
这个零件有配合关系吗？
├── 有 → 写 Mate
│       └── 需要在 Layout 里给根节点绝对坐标吗？
│           ├── 是根节点 → Layout 写绝对坐标
│           └── 不是根节点 → 不用写 Layout（Mate 推导位姿）
│
└── 没有 → Layout 写 parent/transform 或绝对坐标
```

## 文件布局模板

```
my-assembly/
├── piki.toml
├── models/                              # 型号库（可选）
├── instances/
│   ├── assembly/
│   │   ├── TOP.yaml                     # 根装配体
│   │   └── SUB-FOO.yaml                # 子装配体
│   └── parts/
│       ├── PART-A.yaml
│       └── PART-B.yaml
├── mates/                               # ★ 配合先行
│   ├── face-on-face/
│   │   └── A-B.yaml
│   └── slot/
│       └── CAGE-MODULE.yaml
└── layouts/
    └── layout.yaml                      # ★ 根节点坐标 + Mate 参数
```

---

## 参考

| 需要理解 | 读 |
|---------|---|
| Mate 的配合类型与约束语法 | [ADR-006：配合图（Mating Graph）](../../docs/adr/data-model/006-mating-graph.md) |
| Layout 与 Mate 的覆盖规则 | [ADR-013 §9](../../docs/adr/data-model/013-relative-coordinate-layout.md#9-layout-与-mate-的定位优先级与覆盖规则) |
| Layout 的 parent/transform 级联机制 | [ADR-013：层级相对坐标布局](../../docs/adr/data-model/013-relative-coordinate-layout.md) |
| Layout 格式速查 | [Layout 格式规范](../../docs/reference/05-layout.md) |
| 约束求解器实现 | `adl/geometry/constraint_solver.py` |
| 接口签名注册表 | `adl/geometry/interface_signature.py` |
| AssemblyBuilder 构建管线 | `adl/geometry/assembly_builder.py` |
| 完整键盘示例 | [samples/03-mechanical-keyboard](../../samples/03-mechanical-keyboard/) |
