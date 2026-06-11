# ADR-008: Instance 与 Layout 分离

> 状态：草案
> 日期：2026-06-11
> 作者：piki 核心团队

## 背景

piki 当前的 Instance YAML 同时承载了两类信息：

```yaml
# devices/SRV-01.yaml — 当前状态
id: SRV-01
model: generic-server
rack_id: RACK-A01
position_u: 10
pdu_id: PDU-A
tdp_w: 250
```

| 字段 | 性质 | 变更频率 | 变更原因 |
|------|------|---------|---------|
| `model`, `tdp_w` | Instance 自身属性（这台设备是什么） | 低 | 更换型号、改配置 |
| `rack_id`, `position_u`, `pdu_id` | Layout 决策（放在哪、接入谁） | 高 | 方案比选、布局优化 |

这两类信息缝在同一文件里导致三个问题：

1. **方案比选退化成文件操作**：比较三个布局方案需要复制三份 Instance 文件或反复修改同一份，Git diff 被 Instance 自身体属性的不变部分污染。
2. **协作冲突发生在不相关的维度**：结构工程师改 `rack_id`、电气工程师改 `pdu_id`，改的是同一个文件的不同字段，Git 报冲突，而实际上两个决策互不干涉。
3. **Instance 不可跨项目复用**：同一台设备（相同型号、相同覆盖参数）在不同机房中部署时，需要重新写完整的 Instance + Layout，无法独立引用 Instance 的定义。

本 ADR 记录 Instance 与 Layout 分离的决策：数据结构、文件组织、解析规则和方案比选机制。

---

## 1. 核心决策：Instance 与 Layout 分离为两个独立的概念层

### 1.1 定义

| 概念 | 定义 | 文件位置 | 稳定性 |
|------|------|---------|--------|
| **Instance** | 物理设备的声明（型号、覆盖参数、固资编号） | `instances/` | 高（除非设备本身变更） |
| **Layout** | 部署决策（放在哪个机柜、哪个 U 位、接入哪个 PDU、接到哪个端口） | `layouts/` | 低（方案比选就是改这些） |

### 1.2 Instance 文件

```yaml
# instances/compute/SRV-01.yaml
id: SRV-01
model: generic-server
tdp_w: 250                    # 可选覆盖：实际功耗低于型号默认值
```

Instance 不包含任何空间位置信息。它只声明**这台设备是什么**。

Instance 可以通过 `config_override` 覆盖 Model 默认值，但覆盖字段受白名单约束：

- **可覆盖**：功耗、重量、风扇转速等运行参数（同一型号不同批次或降额运行）
- **不可覆盖**：物理尺寸（`height_u`、`depth_mm`、`width_mm`）——物理外壳不变，覆盖会导致几何碰撞失效

多台同型号设备各自有独立的 Instance 文件：

```text
instances/compute/
├── SRV-01.yaml    # model: generic-server, tdp_w: 250
├── SRV-02.yaml    # model: generic-server（无覆盖，继承 Model 默认值）
└── SRV-03.yaml    # model: generic-server, tdp_w: 280
```

它们共享型号 `generic-server`，但它们是三个独立的物理个体，有独立的固资编号、独立的配置覆盖、独立的生命周期。

### 1.3 Layout 文件

Layout 文件是**唯一的真相源**，描述当前方案中所有 Instance 的部署位置：

```yaml
# layouts/room-1/layout.yaml
- instance: SRV-01
  rack_id: RACK-A01
  position_u: 10
  pdu_id: PDU-A

- instance: SRV-02
  rack_id: RACK-A01
  position_u: 12
  pdu_id: PDU-A

- instance: SRV-03
  rack_id: RACK-A02
  position_u: 5
  pdu_id: PDU-B
```

**每个子项目只有一个 Layout 文件。** Layout 的粒度与项目一一对应。物理空间是天然的 sharding key，同一空间内的物理耦合（振动、热量、电磁）必须在一个 Layout 文件中检查，拆散会丢失空间上下文。不需要在每个子项目内拆出多个 Layout 文件来按专业或按系统管理——这些正交维度通过 Tag（ADR-009）表达。

Layout 文件内允许按 discipline 分 section，以支持不同专业对同一空间的独立表达需求。但文件级别仍是一个：`layout.yaml`。

### 1.4 方案比选：Layout 唯一，Git 分支承载方案

**不在同一项目内维护多份 layout 文件。** Layout 文件在给定分支上是唯一的真相源。

方案比选通过 Git 分支实现：

```bash
git branch design-v2    # 方案 B: SRV-01 放在 RACK-A02
git branch design-v3    # 方案 C: SRV-01 接入 PDU-B
```

每个分支上的 `layouts/room-1/layout.yaml` 是该方案的唯一真相源。`git diff main..design-v2` 精确显示布局层的变化，不被 Instance 自身属性的不变字段污染。

### 1.5 多环境部署（非比选）

同一台设备出现在两个**物理上不同的部署环境**中（非比选，同时存在），通过嵌套项目结构处理。详见 ADR-009。

---

## 2. 解析规则

```
1. 加载 Instance（instances/） → 获取设备属性（model, 覆盖参数）
2. 加载 Layout（layouts/）     → 获取部署决策（rack_id, position_u, pdu_id）
3. 合并：instance.resolved → Instance 属性 + Layout 决策 + Model 默认值
```

合并后的 `resolved` 对象包含所有字段，规则引擎在 `resolved` 上执行检查。

```python
# 伪代码
instance = load_instance("SRV-01")       # {model: generic-server, tdp_w: 250}
model = registry.get_model(instance.model) # {height_u: 1, tdp_w: 300, ...}
layout = load_layout("room-1").get("SRV-01") # {rack_id: RACK-A01, position_u: 10, pdu_id: PDU-A}

resolved = {**model.defaults, **instance.overrides, **layout}
# {model: generic-server, height_u: 1, tdp_w: 250, rack_id: RACK-A01, position_u: 10, pdu_id: PDU-A}
```

---

## 3. 对规则引擎的影响

规则引擎的查询 API 不再需要"通过 Instance 查 layout"。分离后查询更清晰：

```python
# 当前（耦合）
devices = ctx.query("devices", rack_id="RACK-A01")

# 分离后
layout = ctx.layout("room-1")           # 获取 layout 数据
instances = ctx.instances()              # 获取所有 instance
devices = layout.instances_in("RACK-A01") # 通过 layout 查询位置
```

Layout 层可以独立查询：
- "RACK-A01 U10 放了什么？" → `layout.at("RACK-A01", 10)`
- "PDU-A 接了多少设备？" → `layout.connected_to("PDU-A")`
- "哪些 U 位空闲？" → `layout.free_positions("RACK-A01")`

---

## 4. 影响与权衡

### 4.1 有利影响

- **方案比选即 Git 分支**：`git diff` 精确到布局字段，不被 Instance 属性污染
- **协作解耦**：结构工程师改 `layouts/`，设备工程师改 `instances/`，不产生 Git 冲突
- **Instance 可跨项目复用**：同一设备在不同机房的部署，引用同一个 Instance 定义
- **Layout 查询独立**：空间查询、容量统计直接在 Layout 层完成

### 4.2 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 文件数量增加（每台设备一个 Instance 文件） | Instance 文件非常小（3-5 行），文件数量与物理设备一一对应；piki 扫描性能已有验证 |
| Layout 引用不存在的 Instance | `piki check` 增加 L2 引用完整性检查 |
| Instance 被删除后 Layout 残留引用 | 同上 |

---

## 5. 与其他 ADR 的关系

| ADR | 关系 |
|-----|------|
| ADR-002（一实例一文件） | Instance 仍保持一实例一文件；Layout 是独立层，不改变 Instance 的原则 |
| ADR-004（多级质量检查） | Instance-Layout 引用完整性属于 L2；Layout 中的空间冲突属于 L4 |
| ADR-007（CAD 资产引用） | 资产引用在 Model/Instance 层，Layout 不声明资产路径 |
| ADR-009（嵌套项目结构） | 多环境部署通过项目嵌套处理，而非多 layout 文件 |
