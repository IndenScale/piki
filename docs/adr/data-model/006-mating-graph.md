# ADR-006: 配合图（Mating Graph）——部件耦合关系建模

> 状态：已实现（已修订）
> 日期：2026-06-12
> 修订：2026-06-14 — 将 Mating 从“物理配合”扩展为“设计耦合（Design Coupling）”
> 作者：piki 核心团队
> 依赖：ADR-005（Connection 作为 Instance）、ADR-001（Instance/Layout 分离）

## 背景

piki 当前有三层数据模型，各司其职：

| 层 | 职责 | 回答的问题 |
|---|------|-----------|
| Instance | 设备身份（型号、规格、接口） | "这是什么" |
| Layout | 空间部署（机柜、U 位、坐标） | "放在哪里" |
| Connection | 信号/能量链路（光纤、铜缆、液冷管） | "连了谁" |

但在实际工程设计中，三者之间存在一条巨大的鸿沟：**部件之间的耦合关系**。

服务器不是"放在"机柜里——它是通过挂耳/导轨 **配合** 进机柜的。PDU 不是"放在"机柜里——它是通过卡扣/螺栓 **配合** 进机柜竖梁的。光模块不是"连接"到交换机——它是 **配合** 进 SFP28 笼子的，光纤再配合进光模块。

更进一步，管道入口与出口之间存在**质量守恒耦合**，发射器与接收器之间存在**时钟同步耦合**，散热器与芯片之间存在**热阻耦合**。这些关系不一定有机械接触，也不一定通过实体链路连接，但它们都是设计中必须声明和验证的耦合约束。

```
当前 piki 能表达的：
  RACK-A01 ──[Layout: at 10U]── SRV-01
  SRV-01 ──[Connection: fiber]── SW-01

真实工程中：
  RACK-A01 ──[Mating: rack-mount-19inch @ 10U]── SRV-01
             ├── 导轨承重 ≥ 服务器重量
             ├── 机柜深度 ≥ 服务器深度
             └── 机柜宽度 ≥ 服务器宽度
  SRV-01/power-a ──[Mating: IEC-C13/C14]── PDU-A/out-3
  SRV-01/power-b ──[Mating: IEC-C13/C14]── PDU-B/out-5
  SRV-01/eth1 ──[Mating: SFP28 cage → 光模块]── [Mating: LC → fiber]── SW-01/Gi1/0/1
  PIPE-01/inlet ──[Mating: mass-conservation]── PIPE-01/outlet
  TX-01 ──[Mating: clock-sync]── RX-01
```

**Layout 只表达"在哪"，不表达"怎么配合"。Connection 只表达信号/能量链路，不表达广义的设计耦合。** 这导致大量本该在加载阶段自动验证的约束被下放到了规则层，靠 O(n×m) 遍历来事后检查。

本 ADR 引入 **Mating Graph（配合图）** 作为框架级一等概念，与 Instance、Layout、Connection 并列。

在 piki 中，**Mating（配合）被定义为广义的设计耦合（Design Coupling）**：两个或多个实体/接口之间的耦合关系，它声明了这些实体在功能、物理、电磁、热、流体或时序等方面必须共同满足的设计约束。

> 关于这种定义如何从仿真和规则中演化而来，参见 [设计知识成熟曲线](../concepts/06-knowledge-maturation.md)。

---

## 1. 核心概念

### 1.1 四层模型

```
┌──────────────────────────────────────────────────┐
│  Instance   "这是什么"                             │
│  ┌────────────────────────────────────────────┐   │
│  │  Interface   "有什么口"                      │   │
│  └────────────────────────────────────────────┘   │
└──────────────────────┬───────────────────────────┘
                       │ 被引用
┌──────────────────────▼───────────────────────────┐
│  Mating     "怎么耦合"                             │
│  ┌────────────────────────────────────────────┐   │
│  │  constrains   "耦合条件是什么"               │   │
│  │  pairings     "通过耦合引入的接口配对"        │   │
│  └────────────────────────────────────────────┘   │
└──────┬──────────────────────┬────────────────────┘
       │ 决定物理部署         │ 决定接口级配对
┌──────▼──────────┐  ┌───────▼──────────────────────┐
│  Layout         │  │  Connection                   │
│  "放在哪里"      │  │  "信号/能量从哪到哪"           │
└─────────────────┘  └──────────────────────────────┘
```

| 概念 | 是什么 | 存在形式 | 双向性 |
|------|--------|---------|--------|
| **Instance** | 设备/方舱/PDU 的身份定义 | 独立 YAML 文件 | 无（单向声明） |
| **Mating** | 两个实体之间的设计耦合关系 | 独立 YAML 文件（`mates/` 目录） | 双向（引擎构建正向+反向索引） |
| **Layout** | 设备的空间部署位置 | `layouts/layout.yaml` | 单向（按 Instance ID 查找） |
| **Connection** | 两个 Interface 之间的信号/能量链路 | 独立 Instance YAML | 双向（通过 from_interface/to_interface） |

### 1.2 三层耦合粒度

```
L1: 实体级耦合（Entity Coupling）
    两个实体之间的空间、物理或功能关系。
    例：rack-mount、thermal-contact、wireless-link、mass-conservation。

    mate rack-mount:
      type: rack-mount-19inch
      child: SRV-01
      parent: RACK-A01

L2: 接口级耦合（Interface Coupling）
    依附于 L1 耦合。设备装进承载物时，电源口和管理口自然归入耦合关系。

    pairings:
      - from: SRV-01/power-a
        to: PDU-A/out-3
        type: power-iec-c14-c13

L3: 跨耦合链的链路耦合
    双方不在同一个 L1 耦合关系中（跨机柜光纤、跨方舱液冷管路、无线链路）。
    存在于独立的 Connection Instance 中，但需通过接口耦合来验证两端兼容性。

    mate optical-link:
      type: optical-link
      endpoints:
        - SRV-01/eth1
        - SW-01/Gi1/0/1
      media: OM4-LC-LC
```

---

## 2. Mating 数据模型

### 2.1 设计原则

1. **独立放置**：Mate 不内嵌在 Instance 中。Instance 表达"设备是什么"，Mate 表达"设备和别的东西怎么耦合"。二者正交，变更粒度不同（改设备 vs 改关系），必须分离。与 ADR-001 中 Instance/Layout 分离的理由一致。

2. **双向索引**：引擎加载所有 Mate 后构建正向和反向索引。从 SRV-01 可以查到它配合了 RACK-A01，从 RACK-A01 可以查到它承载了哪些子设备。不需要规则遍历来反向推导。

3. **类型感知**：Mate 的 `type` 字段决定了耦合双方的约束条件。引擎在加载时自动验证 `constrains`，不依赖规则层。

4. **不与 Layout 重复**：Layout 保留"空间位置"职责。Mate 的 `at` 字段（如 U 位）是耦合的锚点参数，Layout 可能以此为参考，但 Layout 的变更不影响 Mate 结构。

### 2.2 Schema

```python
from pydantic import BaseModel, Field
from typing import Literal

class MateConstraint(BaseModel):
    """耦合引入的固有约束。引擎在加载时自动验证。"""
    field: str                 # 子设备字段：depth_mm
    operator: Literal["<=", ">=", "<", ">", "==", "!="]
    value_ref: str             # 父设备字段：depth_mm 或常量：1000
    message: str = ""          # 违反时的错误描述

class InterfacePairing(BaseModel):
    """依托于 Mate 的接口级配对（L2）。"""
    child_port: str            # SRV-01/power-a
    parent_target: str         # PDU-A/out-3
    type: str = ""             # power-iec-c14-c13 | copper-rj45-cat6a | ...

class MateSpec(BaseModel):
    """一个设计耦合关系。"""
    type: str                  # rack-mount-19inch | bolt-mount | clip-mount | optical-link | mass-conservation | clock-sync | ...
    parent: str                # 耦合方 Instance ID（承载物或参照物）
    child: str                 # 被耦合方 Instance ID
    at: dict[str, Any] | None = None  # 耦合锚点：{u_start: 10, u_span: 2} 或 {grid_id: "B-3"}

    # 耦合的固有约束（引擎加载时自动验证）
    constrains: list[MateConstraint] = Field(default_factory=list)

    # 通过这个耦合关系建立的接口配对（L2）
    pairings: list[InterfacePairing] = Field(default_factory=list)
```

### 2.3 YAML 文件示例

#### 机械配合（L1）

```yaml
# mates/rack-mount/SRV-01-in-RACK-A01.yaml
type: rack-mount-19inch
parent: RACK-A01
child: SRV-01
at:
  u_start: 10
  u_span: 2
constrains:
  - field: depth_mm
    operator: "<="
    value_ref: depth_mm
    message: "服务器深度超过机柜深度，无法安装"
  - field: width_mm
    operator: "<="
    value_ref: mounting_width_mm
    message: "服务器宽度超过机柜安装宽度"
  - field: weight_kg
    operator: "<="
    value_ref: rail_capacity_kg_per_pair
    message: "服务器重量超过导轨承重"
pairings:
  - child_port: power-a
    parent_target: PDU-A/out-3
    type: power-iec-c14-c13
  - child_port: power-b
    parent_target: PDU-B/out-5
    type: power-iec-c14-c13
  - child_port: eth0
    parent_target: SW-MGMT/Gi0/1
    type: copper-rj45-cat6a
```

#### 流体守恒耦合（L2）

```yaml
# mates/fluid/PIPE-01-conservation.yaml
type: mass-conservation
parent: PIPE-01/inlet
child: PIPE-01/outlet
constrains:
  - field: mass_flow_rate_kg_s
    operator: "=="
    value_ref: mass_flow_rate_kg_s
    message: "管道入口质量流量必须等于出口质量流量"
  - field: pressure_pa
    operator: ">="
    value_ref: min_pressure_drop_pa
    message: "管道压降低于设计下限，可能出现流动不稳定"
```

#### 时钟同步耦合（L1）

```yaml
# mates/wireless/TX-01-to-RX-01.yaml
type: clock-sync
parent: TX-01
child: RX-01
constrains:
  - field: clock_ppb
    operator: "<="
    value_ref: max_clock_drift_ppb
    message: "发射器与接收器时钟漂移超出同步预算"
  - field: sync_protocol
    operator: "=="
    value_ref: sync_protocol
    message: "收发双方时钟同步协议不一致"
```

#### 跨链路耦合（L3）

```yaml
# mates/optical/SRV-01-eth1-to-SW-01.yaml
type: optical-link
parent: SW-01/Gi1/0/1
child: SRV-01/eth1
media: OM4-LC-LC
length_m: 3.0
constrains:
  - field: interface_type
    operator: "=="
    value_ref: interface_type
    message: "两端接口类型不兼容"
```

### 2.4 目录结构

```
project/
├── instances/
│   ├── devices/          # 设备 Instance
│   ├── racks/            # 机柜 Instance
│   └── connections/      # 连接 Instance（保留，用于 L3 链路）
├── mates/
│   ├── rack-mount/       # 机柜装配配合
│   ├── power/            # 电源接口配合
│   ├── signal/           # 信号接口配合（铜缆/光纤）
│   ├── fluid/            # 流体守恒耦合
│   ├── wireless/         # 无线/时序耦合
│   └── bolt-mount/       # 螺栓装配配合
├── layouts/
│   └── layout.yaml       # 空间部署位置
└── piki.toml
```

目录名 = Mate type。Mate type 由领域插件注册，每个 type 对应一个 Pydantic Schema，定义该类型耦合的合法 `pairings` 子类型和默认 `constrains`。

---

## 3. 引擎行为

### 3.1 加载阶段

```
1. 扫描 mates/ 目录，按 type 分组加载所有 Mate YAML
2. 对每个 Mate：
   a. 用 mate type 的 Pydantic Schema 验证结构
   b. 解析 constrains，逐条验证 child[field] operator parent[value_ref]
   c. 失败时产生 Diagnostic（Severity.ERROR，定位到 Mate 文件行号）
   d. 将 Mate 注册到双向索引：
      - parent.mated_children += [child]
      - child.mated_parents += [parent]
   e. 解析 pairings，将每个 pairing 注册到接口级双向索引
3. 构建配合图（有向图），供规则函数沿边遍历
```

### 3.2 约束验证示例

引擎加载 `SRV-01-in-RACK-A01.yaml` 时：

```python
# 引擎内部（伪代码）
for constraint in mate.constrains:
    child_value = registry.get_instance(mate.child).resolved[constraint.field]   # 715
    parent_value = registry.get_instance(mate.parent).resolved[constraint.value_ref]  # 800
    if not evaluate(child_value, constraint.operator, parent_value):
        raise Diagnostic(
            severity=ERROR,
            message=constraint.message,
            location=mate.source_location,
            code="MATE-CONSTRAINT-001",
        )
```

**规则作者不需要写 `check_device_physical_fit` 规则**。这个检查在加载 Mate 时就完成了。

### 3.3 Context 增强

```python
class Context:
    def mated_children(self, instance_id: str, mate_type: str | None = None) -> list:
        """返回指定 Instance 的所有子设备（顺配合图向下）。"""

    def mated_parents(self, instance_id: str) -> list:
        """返回指定 Instance 的所有父承载物（顺配合图向上）。"""

    def mated_chain(self, instance_id: str) -> list:
        """返回从根承载物到该 Instance 的完整配合路径。"""

    def mated_pairings(self, instance_id: str) -> list:
        """返回该 Instance 通过所有 Mate 建立的接口配对。"""
```

---

## 4. 规则层的影响

### 4.1 可废弃的规则

有了 Mate + 引擎自动约束验证，以下规则不再需要：

| 规则 ID | 名称 | 原因 |
|---------|------|------|
| `check_device_physical_fit` | 设备物理尺寸匹配 | Mate 的 `constrains` 自动验证 |
| `check_rack_3d_collision` 的部分职责 | 设备空间冲突 | 同一父承载物下的 Mate 锚点冲突由引擎检查 |
| `check_liquid_loop_flow` 的部分职责 | 液冷流量匹配 | 顺 Mate 链反向索引，不再需要 O(n×m) 遍历 |
| `check_mass_conservation` | 管道质量守恒 | 提升为 `mass-conservation` Mate type |
| `check_clock_sync_budget` | 收发时钟同步 | 提升为 `clock-sync` Mate type |
| 部分 `FK-001` 职责 | 外键完整性 | Mate 中的 parent/child 引用在加载时就验证存在性 |

### 4.2 规则简化

有了配合图后，业务规则只需沿图遍历：

```python
# 现在：O(n×m) 遍历
@rule("DC-PUE-001", "PUE 估算检查")
def check_pue_estimate(ctx):
    max_pue = ctx.config.get("max_pue", 1.4)
    total_it_power = 0.0
    total_cooling_power = 0.0
    for device in ctx.query("equipment"):
        if device.equipment_type == "compute":
            total_it_power += device.power_kw
        elif device.equipment_type == "cooling":
            total_cooling_power += device.power_kw
    # ...

# 有了配合图后：
@rule("DC-PUE-001", "PUE 估算检查")
def check_pue_estimate(ctx):
    for container in ctx.query("containers", container_type="liquid-cooling"):
        # 直接沿 Mate 反向索引获取所有子设备
        it_power = container.mated_equipment.where(type="compute").sum("power_kw")
        cooling_power = container.mated_equipment.where(type="cooling").sum("power_kw")
        # ...
```

**遍历次数从 O(n_containers × n_equipment) 降到 O(n_containers × n_mated_children)**，后者在实际项目中远小于前者。

### 4.3 知识沉淀路径

Mate type 的注册标志着领域知识从“仿真发现”到“规则检查”再到“结构声明”的成熟。具体参见 [设计知识成熟曲线](../concepts/06-knowledge-maturation.md)。

---

## 5. 与 Layout 和 Connection 的关系

### 5.1 与 Layout 的分工

| | Layout | Mating |
|---|---|---|
| 回答的问题 | "放在哪里" | "怎么耦合" |
| 是否有约束 | 无 | 有（`constrains`） |
| 变更粒度 | 运维优化、方案比选 | 设备选型变更、耦合标准变更 |
| 独立性 | 改 U 位不影响 Mate | 改 Mate 不影响其他设备的 Layout |
| 地址格式 | `rack_id + position_u` | `parent + child + pairing_type` |

二者共存，互不替代。Layout 是空间视图，Mate 是耦合关系视图。同一项目可以有多套 Layout 方案（通过 Git 分支），但 Mate 是相对稳定的物理/功能事实。

### 5.2 与 Connection 的分工

扩展后的 Mating 与 Connection 边界如下：

| | Connection (ADR-005) | Mating（扩展后） |
|---|---|---|
| 回答的问题 | "信号/能量从 A 口到 B 口" | "A 和 B 必须共同满足什么" |
| 核心语义 | **流动通道** | **设计耦合与约束** |
| 是否有物理介质 | 通常有（光纤、铜缆、管道） | 可有可无 |
| 方向性 | 有向（from → to） | 通常双向/无向 |
| 层级 | L3（跨耦合链） | L1（实体）/ L2（接口） |
| 例子 | OM4-LC-LC 光纤、液冷管路、无线射频链路 | 挂耳装配、C14-C13 配对、质量守恒、时钟同步、热接触 |

Connection 不消失。Connection 仍用于表达跨耦合链的链路（不同机柜之间的光纤、不同方舱之间的管线、无线射频通道）。但 Connection 两端接口的兼容性可以通过 Mate 的关系图来辅助验证——如果两边接口都依附于已知的 Mate，引擎知道它们的物理/功能上下文。

---

## 6. 插件扩展

### 6.1 Mate Type 注册

领域插件可以注册新的 Mate type：

```python
class TelecomPlugin(Plugin):
    def register_mate_types(self, registry):
        registry.add_mate_type("rack-mount-19inch", RackMountMate)
        registry.add_mate_type("power-iec-c14-c13", PowerIECMate)
        registry.add_mate_type("optical-link", OpticalLinkMate)
```

流体或无线领域插件可以注册非物理耦合类型：

```python
class FluidPlugin(Plugin):
    def register_mate_types(self, registry):
        registry.add_mate_type("mass-conservation", MassConservationMate)
        registry.add_mate_type("pressure-boundary", PressureBoundaryMate)

class WirelessPlugin(Plugin):
    def register_mate_types(self, registry):
        registry.add_mate_type("clock-sync", ClockSyncMate)
        registry.add_mate_type("freq-pair", FrequencyPairMate)
```

### 6.2 默认约束

每个 Mate type 可以定义默认 `constrains`，实例化时不需要重复声明：

```python
class RackMountMate(BaseModel):
    type: Literal["rack-mount-19inch"] = "rack-mount-19inch"
    parent: str
    child: str
    at: dict[str, Any] | None = None
    constrains: list[MateConstraint] = Field(default_factory=lambda: [
        MateConstraint(field="depth_mm", operator="<=", value_ref="depth_mm"),
        MateConstraint(field="width_mm", operator="<=", value_ref="mounting_width_mm"),
        MateConstraint(field="weight_kg", operator="<=", value_ref="rail_capacity_kg_per_pair"),
    ])
```

用户的 `mates/` YAML 中可以不写 `constrains`，引擎自动应用默认约束。

---

## 7. 范围边界

### 本 ADR 覆盖

- ✅ Mate 作为一等概念，独立于 Instance 放置
- ✅ 三层耦合粒度（L1 实体 / L2 接口 / L3 跨链路）
- ✅ 引擎加载时自动验证 `constrains`
- ✅ 双向索引构建（`mated_parents` / `mated_children`）
- ✅ Context 增强（沿图遍历 API）
- ✅ 领域插件注册 Mate type
- ✅ 默认约束（mate type 级别定义）
- ✅ 非物理耦合类型（流体守恒、时钟同步、热耦合等）

### 本 ADR 明确不覆盖

- ❌ 连续场耦合（CFD、电磁场仿真、热传导有限元）—— piki 只表达离散耦合约束，连续场分析留给外部求解器
- ❌ 配合/耦合的时序/工序（先螺栓再焊接、启动顺序）—— 不在 piki 核心范围内
- ❌ 接口的位置/朝向/空间坐标（留给后续 ADR 或 Layout 扩展）
- ❌ Connection 的替代 —— Connection 保留，Mate 补充耦合约束维度
- ❌ Layout 的替代 —— Layout 保留空间位置职责

---

## 8. 向后兼容

| 数据 | 处理 |
|------|------|
| 现有 `LayoutEntry.pdu_id` | 保留，Mate 增加后 Layout 中可逐步移除 `pdu_id`（由 Mate 推导） |
| 现有 Connection Instance | 不受影响，Mate 的 L3 可选择性替代部分 Connection |
| 现有 `check_device_physical_fit` 等规则 | 保留但标记 deprecated，Mate 接管后可以废弃 |
| 无 Mate 的项目 | 引擎仅构建空配合图，所有现有规则照常运行 |
| 现有 `mates/` 下的物理配合文件 | 完全兼容，schema 未发生破坏性变更 |

---

## 9. 决策总结

| 决策 | 选择 | 核心理由 |
|------|------|----------|
| Mate vs Instance | 独立于 Instance 放置 | 设备定义和设备关系是正交维度，变更粒度不同 |
| Mate vs Layout | 共存，不替代 | Layout 管空间位置，Mate 管耦合约束 |
| Mate vs Connection | 共存，互补 | Mate（L1/L2）表达耦合约束，Connection（L3）保留跨链路流动表达 |
| 约束验证 | 引擎加载时自动验证 | 不应把工程不变量下放为规则遍历 |
| 双向索引 | 引擎构建 | 排查时需沿配合链追溯，不能靠规则反向推导 |
| 默认约束 | Mate type 级别定义 | 减少用户重复声明，保持一致性 |
| 文件组织 | `mates/{mate_type}/` | 目录即分类，一个 Mate 一个文件，Git 粒度最优 |
| 非物理耦合 | 纳入 Mating 范围 | 质量守恒、时钟同步、热耦合等本质上是同一种“设计耦合” |

---

## 参考

- [ADR-001: 项目组织模型](../data-model/001-project-organization.md) — Instance/Layout 分离先例
- [ADR-002: 插件架构](../engine-and-plugins/002-plugin-architecture.md) — 插件注册 Mate type
- [ADR-003: 多级质量检查体系](../engine-and-plugins/003-quality-checks-and-diagnostics.md) — L0-L6 检查分层
- [ADR-005: 连接关系实例化与接口模型](../data-model/005-connection-as-instance.md) — Connection 建模
- [设计知识成熟曲线](../concepts/06-knowledge-maturation.md) — 仿真 → 规则 → Mating 的演进路径
