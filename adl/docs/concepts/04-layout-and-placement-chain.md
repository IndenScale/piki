# 布局与参数化定位链

> PLL（Part Layout Language）回答"东西放在哪里"。它不是独立的位置描述，而是配合约束求解的输入层：给根节点绝对坐标，给无 Mate 实体手动定位，给 Mate 参数提供默认值。

---

## 一、Layout 的职责

ADL 把"身份"与"位置"分离（ADR-001）。Instance 文件回答"是什么"，Layout 文件回答"放哪里"。

Layout 能做三件事：

1. **给根节点绝对坐标**：没有被任何 Mate 认领为 child 的 Part。
2. **给无 Mate 实体相对坐标**：用 `parent + transform` 直接声明位置。
3. **给 Mate 参数注入默认值**：在 `at` 中设置 `t`、`theta_deg` 等参数。

> Layout 中的 `parent/transform` 只是给约束求解器的初始近似；如果同一 Part 同时被 Mate 认领，最终位姿由 Mate 求解器覆盖。

---

## 二、LayoutEntry 字段

`LayoutEntry` 定义在 `adl/models/layout.py`：

| 字段 | 类型 | 说明 |
|------|------|------|
| `instance` | `str` | 引用的 Instance ID |
| `position_x_mm` | `float` | X 绝对坐标，mm |
| `position_y_mm` | `float` | Y 绝对坐标，mm |
| `position_z_mm` | `float` | Z 绝对坐标，mm |
| `parent` | `str` | 父级 Instance ID |
| `transform` | `Transform` | 相对父级的局部位姿 |
| `rack_id` | `str` | 机柜 ID（机房场景） |
| `position_u` | `int` | 机柜 U 位（机房场景） |
| `grid_id` | `str` | 轴网 ID |
| `grid_position` | `[str, str]` | 轴网坐标，如 `[A, "3"]` |

### 2.1 绝对坐标示例

```yaml
# layouts/layout.yaml
- instance: ACCESS-SW
  position_x_mm: 0
  position_y_mm: 0
  position_z_mm: 0
```

### 2.2 相对坐标示例

```yaml
- instance: CASE-01
  position_x_mm: 0
  position_y_mm: 0
  position_z_mm: 0

- instance: DAMP-BOTTOM
  parent: CASE-01
  transform:
    translation: [0, 0, 1]
```

### 2.3 机柜场景示例

```yaml
- instance: SRV-01
  rack_id: RACK-A01
  position_u: 10
  pdu_id: PDU-A
```

---

## 三、坐标优先级

同一条 `LayoutEntry` 中，位姿解析遵循严格优先级（`adl/models/layout.py:resolved_transform`）：

1. **`parent + transform`**（相对坐标）最高；
2. 否则使用显式绝对坐标 `position_x/y/z_mm`；
3. 缺失维度从 `grid_id` + `grid_position` / `row_id` + `bay_index` 解析；
4. 仍未指定的维度默认值为 0。

```yaml
# parent + transform 优先
- instance: CHILD
  parent: PARENT
  transform:
    translation: [10, 0, 0]
  position_x_mm: 100    # 被忽略
```

---

## 四、相对坐标与 parent/transform 链

`parent` 可以形成一条级联链：

```yaml
- instance: A
  position_x_mm: 0

- instance: B
  parent: A
  transform:
    translation: [10, 0, 0]

- instance: C
  parent: B
  transform:
    translation: [0, 5, 0]
```

C 的全局位姿：

```text
P_C_global = T_A × T_B × T_C
```

ADL 提供 `Layout.resolved_transform(instance_id)` 计算整条链。注意该方法不包含 Mate 约束，仅做轻量声明式解析。

---

## 五、Layout 与 Mate 的关系

### 5.1 四种场景

| 场景 | Layout 角色 | Mate 角色 |
|------|-------------|-----------|
| 实体有 Mate 认领其为 child | 通常不写 | 位姿由 Mate 约束求解器决定 |
| 实体是装配根节点 | 必须写绝对坐标 | 无 |
| 实体无 Mate、也无 Layout | 未定位，产出诊断 | 无 |
| Layout 与 Mate 结果冲突 | 初始近似 | 最终结果，可能覆盖 Layout |

### 5.2 Mate 覆盖 Layout 的警告

当同一 Part 在 Layout 中声明了位姿，又被 Mate 认领时：

```yaml
# layouts/layout.yaml
- instance: PCB-01
  parent: CASE-01
  transform:
    translation: [6, 6, 10]

# mates/pcb-standoff-mount/CASE-01-PCB-01.yaml
type: pcb-standoff-mount
parent: CASE-01
child: PCB-01
```

引擎输出：

```text
[WARNING] ASSEMBLY-002: 'PCB-01' 的位姿由 Mate 'pcb-standoff-mount' 重新计算，
与 Layout 声明存在差异: 平移 Δ=(+0.0, +0.0, -2.0)mm
```

---

## 六、参数化定位链

### 6.1 纯 Layout 链

```text
P_global = T_root
         × T_parent1
         × T_parent2
         × ...
         × T_self
```

### 6.2 Layout + Mate 混合链

```text
P_global = T_layout_root
         × T_layout_chain
         × T_mate(state, dofs)
         × T_child_iface_local⁻¹
```

其中 `T_mate(state, dofs)` 由 PML 层决定，可以参数化变化：

- 抽屉拉出 200mm；
- 门打开 90°；
- USB-C 从 inserted 切换到 reversed。

---

## 七、全局坐标

全局坐标是 ADL 求解的最终结果：每个 Part 在世界坐标系中的位姿。

计算输入：

- PDL：`local_transform`、`BBox`、几何资产；
- PML：`mating_kind`、`signature`、`at` 参数；
- PLL：根节点坐标、无 Mate 实体的手动定位、Mate 参数默认值。

计算输出：

- `global_transform`：Part 在世界坐标系中的 Transform；
- `controls`：可交互的 DOF 参数和离散状态。

入口：`adl/geometry/assembly_builder.py` 和 `adl/geometry/assembly_scene.py`。

---

## 八、Grid：符号坐标到绝对坐标

对于机房、建筑等有规则网格的场景，可以用 Grid 避免手写大量坐标。

```yaml
# grids/room-grid.yaml
id: ROOM-GRID
type: orthogonal
origin: [0, 0, 0]
axes:
  - direction: [0, 1, 0]
    lines:
      A: 0
      B: 1200
  - direction: [1, 0, 0]
    lines:
      "1": 0
      "2": 3000
```

```yaml
# layouts/layout.yaml
- instance: RACK-A03
  grid_id: ROOM-GRID
  grid_position: [A, "2"]
```

解析结果：`RACK-A03` 的全局坐标为 `(3000, 0, 0)`。

---

## 九、常见错误

| 错误 | 说明 | 处理/诊断 |
|------|------|-----------|
| 同一 Instance 在 Layout 中出现两次 | 重复部署条目 | 校验报错 |
| Layout 引用不存在的 Instance | 外键错误 | 校验报错 |
| parent 链成环 | `A → B → C → A` | 校验报错（`Layout.detect_cycles()`） |
| Layout 与 Mate 结果冲突 | 差异超过阈值 | `ASSEMBLY-002` |
| grid_id 不存在 | 轴网未定义 | `GRID-001` |
| grid_position 越界 | 轴号不在 Grid 中 | `GRID-002` |

---

## 十、决策树

```text
这个 Part 有 Mate 认领它为 child 吗？
├── 有
│   └── 不需要写 Layout（根节点除外）
│   └── 如果是根节点，在 Layout 中给绝对坐标
└── 没有
    └── 在 Layout 中写绝对坐标或 parent/transform
```

---

## 十一、与相关机制的衔接

- 接口与坐标系 → [接口与坐标系](02-interface-and-coordinate-system.md)
- 配合类型与自由度 → [配合类型与自由度](03-mating-kinds-and-dof.md)
- ADL 分层总览 → [ADL 分层概念模型](01-layered-model.md)
- Layout 格式规范 → `piki/docs/reference/05-layout.md`
- 装配体建模指南 → [装配体建模指南](../guides/modeling-assemblies.md)
