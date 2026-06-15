# ADR-010: 多上下文工程设计——用 Context 统一建模外部、保密、标段、粗糙设计与自然环境实体

> 状态：勘察 / 提案中
> 日期：2026-06-12
> 作者：piki 核心团队
> 依赖：ADR-001（项目组织）、ADR-005（Connection 与 Interface）、ADR-006（Mating Graph）

---

## 背景

piki 当前假设：**项目中的每个 Instance 都是本次工程要设计、采购或部署的资产**。这个假设在绿地（greenfield）项目中成立，但真实工程往往更复杂。除了「既有设施」之外，还经常遇到以下五类情况：

| 场景                       | 说明                                                     | 例子                                                 |
| -------------------------- | -------------------------------------------------------- | ---------------------------------------------------- |
| **既有资产（Brownfield）** | 现场已经存在、本次不修改但要参与校验                     | 既有机柜、既有 PDU、既有风管                         |
| **保密/控制权分离**        | 资产存在，但数据由另一团队控制，本团队只能只读引用       | 安全网络设备、军方/政府涉密设施                      |
| **标段/分包边界**          | 资产属于另一个合同包，不在本次设计范围内，但与本包有接口 | HVAC 包的风机、土建包的电缆沟                        |
| **设计尚未细化**           | 只存在粗略描述，需要占位参与空间/资源/接口检查           | 方案早期的「某型交换机（待定）」、概念阶段的设备占位 |
| **自然环境**               | 没有图纸、没有所有权、以勘察/测量数据形式存在的空间约束  | 地质层、地下水位、岩体、冻土、既有地形               |

这些实体的共同点是：**它们不是本次工程的「内部」资产，但又必须在设计检查中被看到**。如果硬塞进当前 Instance 模型，会遇到一系列问题：

- BOM 生成器把它们当成要采购的新设备。
- 规则无法区分「本次新增」与「外部参考」，导致检查策略混乱。
- 缺少数据来源、可信度、管理方等元数据，无法判断约束的硬度。
- 保密/标段数据需要独立的访问控制与可见性策略，当前模型没有表达位置。

本 ADR 提出用 **Context（上下文）** 这一统一概念来建模上述所有实体。

---

## 1. 核心概念：Context

### 1.1 一句话定义

**Context 是一组 Instance 的归属声明：它们属于哪个设计上下文。**

每个 Instance 都属于且仅属于一个 Context。默认 Context 是本次工程本身（`internal` 或 `main`），其他 Context 用于表达外部、保密、标段、粗糙设计等需要被引用但不被本次工程拥有的实体。

```
Project
├── Context: internal（默认） → 本次工程资产
├── Context: existing         → 既有设施
├── Context: classified-net   → 保密网络（只读）
├── Context: package-hvac     → HVAC 标段资产
├── Context: concept          → 概念/粗糙设计占位
└── Context: natural-env      → 自然环境/地质勘察
```

### 1.2 为什么用 Context 统一建模

| 替代方案                      | 问题                                                                         |
| ----------------------------- | ---------------------------------------------------------------------------- |
| 用 `status` 区分              | `operating` 可以表示「已运行」，但无法表达「保密」「标段」                   |
| 用 Tag 约定                   | `tags.owner = "external"` 太脆弱，无法携带访问控制、来源系统等结构化元数据   |
| 用独立 `external/` 目录       | 只能表达「外部」，无法表达「保密」「标段」「粗糙设计」；且会割裂 Family 复用 |
| 用 Mate/Connection 未解析引用 | 没有几何/资源数据，无法做碰撞、功率预算                                      |

Context 统一了这些场景：

- **Brownfield** = Context `existing`
- **保密资产** = Context `classified-net`，access = read-only
- **其他标段** = Context `package-hvac`
- **粗糙设计** = Context `concept`，trust_level = assumed
- **自然环境** = Context `natural-env`，无明确 owner，trust_level 来自勘察数据

---

## 2. Context 的声明方式

### 2.1 `piki.toml` 中声明 Context 元数据

```toml
[project]
name = "telecom-expansion"

[contexts.internal]
name = "本次工程"
access = "editable"
include_in_bom = true

[contexts.existing]
name = "既有设施"
managed_by = "facility-ops"
source_system = "cmdb"
trust_level = "verified"
access = "read-only"
include_in_bom = false
include_in_collision = true

[contexts.classified-net]
name = "保密网络"
managed_by = "security-ops"
access = "classified"
include_in_bom = false
include_in_report = false

[contexts.package-hvac]
name = "HVAC 标段"
managed_by = "hvac-contractor"
access = "read-only"
include_in_bom = false

[contexts.concept]
name = "概念占位"
trust_level = "assumed"
access = "editable"
include_in_bom = false

[contexts.natural-env]
name = "自然环境"
source_system = "geological-survey"
trust_level = "as_designed"
access = "read-only"
include_in_bom = false
include_in_collision = true
include_in_report = false
```

### 2.2 Instance 上的 `context` 字段

```yaml
# instances/contexts/existing/RACK-A01.yaml
id: RACK-A01
family: RackFamily
context: existing
status: operating
name: 既有机柜 A01
total_u: 42
power_capacity_w: 8000
```

```yaml
# instances/contexts/concept/ROUGH-SWITCH.yaml
id: ROUGH-SWITCH
family: ServerFamily
context: concept
name: 接入交换机（型号待定）
height_u: 1
tdp_w: 150
interfaces:
  - id: eth0
    interface_type: SFP28
```

```yaml
# instances/contexts/natural-env/GW-LEVEL.yaml
id: GW-LEVEL
family: ReferenceFamily
context: natural-env
name: 地下水位
geometry:
  type: aabb
  min: [0, 0, -8.5]
  max: [100, 200, -6.0]
```

### 2.3 目录约定（可选）

把不同 Context 的 Instance 放在 `instances/contexts/{context_id}/` 目录下，引擎自动将该目录下所有 Instance 的默认 `context` 设为对应值。Instance 仍可显式覆盖。

```
instances/
├── devices/                 # 默认 context = internal
│   └── SRV-01.yaml
└── contexts/
    ├── existing/
    │   └── RACK-A01.yaml
    ├── package-hvac/
    │   └── HVAC-01.yaml
    └── concept/
        └── ROUGH-SWITCH.yaml
```

---

## 3. Context 元数据字段

### 3.1 Instance 层字段

| 字段      | 类型  | 必填 | 说明            |
| --------- | ----- | ---- | --------------- |
| `context` | `str` | ❌   | 默认 `internal` |

### 3.2 `piki.toml` 中 Context 配置

| 字段                   | 类型   | 必填 | 说明                                    |
| ---------------------- | ------ | ---- | --------------------------------------- |
| `name`                 | `str`  | ✅   | 人类可读名称                            |
| `managed_by`           | `str`  | ❌   | 管理责任方                              |
| `source_system`        | `str`  | ❌   | 数据来源系统                            |
| `trust_level`          | `str`  | ❌   | `verified` / `as_designed` / `assumed`  |
| `access`               | `str`  | ❌   | `editable` / `read-only` / `classified` |
| `include_in_bom`       | `bool` | ❌   | 是否进入采购清单                        |
| `include_in_collision` | `bool` | ❌   | 是否参与空间/碰撞检查                   |
| `include_in_report`    | `bool` | ❌   | 是否出现在默认报告中                    |

---

## 4. 替代方案

### 方案 A：仅增加 `scope` 字段

只区分 `internal` / `external` / `reference`。

**缺点**：

- 无法表达「保密」「标段」「粗糙设计」等更细粒度场景。
- 没有集中配置访问控制、来源系统、报告可见性的地方。

### 方案 B：为每种场景单独建概念

分别引入 `ExternalInstance`、`ClassifiedInstance`、`PackageInstance`、`PlaceholderInstance`。

**缺点**：

- 概念爆炸，引擎、规则、生成器都要单独处理。
- 同一个既有设备可能同时是「外部」+「保密」+「来自 HVAC 包」，单一分类无法表达交叉属性。

### 方案 C：用 Tag + 目录约定

通过 `tags.context = "existing"` 和 `instances/external/` 目录表达。

**缺点**：

- Tag 是自由键值，无法做框架级默认行为（BOM 过滤、报告可见性）。
- 目录约定只能表达「外部」，不能表达「保密」「标段」等。

### 方案 D：Context 字段 + `piki.toml` 配置（推荐）

用统一的 `context` 字段归属 Instance，用 `piki.toml` 声明每个 Context 的策略。

**优点**：

- 一个概念覆盖 brownfield、保密、标段、粗糙设计、自然环境五种场景。
- 框架级默认行为：BOM、碰撞、报告可基于 Context 配置自动决策。
- 规则作者只需 `ctx.query("instances", context="internal")` 即可过滤。
- 向后兼容：未声明 `context` 的实例默认 `internal`。

**结论**：采用方案 D。

---

## 5. 引擎行为

### 5.1 加载阶段

1. 解析 `piki.toml` 中的 `[contexts]`，构建 Context 元数据表。
2. 扫描 `instances/contexts/{context_id}/` 目录，为该目录下 Instance 设置默认 `context`。
3. 解析每个 Instance 的 `context` 字段；缺省 → `internal`。
4. 校验 `context` 值是否已在 `piki.toml` 中声明（可选，可配置为 Warning）。
5. 将 `context` 与对应 Context 配置合并，写入 `_resolved`。

### 5.2 查询与过滤

```python
# 只查本次新增设备
new_devices = ctx.query("devices", context="internal")

# 查所有设备（含既有/标段/占位），用于功率预算
all_devices = ctx.query("devices")

# 查特定 Context
existing = ctx.query("instances", context="existing")
```

### 5.3 生成器默认行为

| 生成器            | 默认行为                                              | 可覆盖                 |
| ----------------- | ----------------------------------------------------- | ---------------------- |
| `bom-csv`         | 只包含 `include_in_bom = true` 的 Context             | `--include-contexts`   |
| `cable-list`      | 排除 `include_in_bom = false` 的 Context              | —                      |
| `power-budget`    | 包含所有 Context，用于真实负载                        | `--context-only`       |
| `rack-face-panel` | 可渲染不同 Context 为不同底色                         | —                      |
| `report`          | 排除 `include_in_report = false` 的 Context（如保密） | `--include-classified` |

### 5.4 规则影响

- **空间/碰撞规则**：默认包含 `include_in_collision = true` 的 Context。
- **资源预算规则**：默认包含所有 Context，因为资源占用是真实的。
- **采购/命名规范规则**：默认只检查 `internal`。

```python
@rule("TELECOM-POWER-001")
def check_pdu_budget(ctx):
    for pdu in ctx.query("pdus"):
        # 所有 context 的设备都参与负载计算
        devices = ctx.query("devices", pdu_id=pdu.id)
        total = sum(d.resolved.tdp_w for d in devices)
        assert total / pdu.capacity_w <= ctx.config.get("power_threshold", 0.8)
```

### 5.5 Layout 与外部 Context

- `read-only` / `classified` Context 的 Instance，其位置字段默认不可被 `layout.yaml` 覆盖。
- `editable` Context（如 `concept`）的位置可以被 Layout 覆盖，便于方案比选。

### 5.6 自然环境 Context 的特殊性

自然环境（地质层、地下水位、岩体、冻土等）与人工资产不同：

- **无所有权**：没有 `managed_by`，来源是勘察报告或测量数据。
- **无 Family**：通常用 `ReferenceFamily` 或领域插件定义的 `GeologyFamily` 表达。
- **表达形式**：多为空间边界（AABB、mesh、等高面）或约束面（如「基础底面不得进入此区域」）。
- **可信度分级**：`verified`（已钻探）、`as_designed`（基于邻近项目推测）、`assumed`（概念阶段假定）。
- **默认策略**：`include_in_bom = false`，`include_in_collision = true`，`include_in_report = false`。

```yaml
# instances/contexts/natural-env/ROCK-LAYER-A.yaml
id: ROCK-LAYER-A
family: ReferenceFamily
context: natural-env
name: 中风化岩层 A
source_system: geological-survey
trust_level: verified
geometry:
  type: mesh
  asset: $PROJECT_ROOT/assets/geology/rock-layer-a.gltf
```

---

## 6. 保密与访问控制

`access = classified` 的 Context 在默认生成器/报告中不可见。未来可扩展：

- 通过 `--clearance` 参数控制可见性。
- 在 CI 中通过环境变量或密钥决定是否能加载 classified Context。
- 对 classified Context 的 Instance 文件进行加密存储（`enc:` 前缀）。

本 ADR 只定义语义；具体加密/权限机制留给后续 ADR。

---

## 7. 新增内置规则

| 规则 ID       | 说明                                                                | 层级 |
| ------------- | ------------------------------------------------------------------- | ---- |
| `CONTEXT-001` | `context` 取值必须已在 `piki.toml` 中声明                           | L1   |
| `CONTEXT-002` | `read-only` / `classified` Context 的 Instance 被 Layout 覆盖时报错 | L2   |
| `CONTEXT-003` | `classified` Context 的 Instance 出现在默认 BOM 中时报错            | L2   |

---

## 8. 范围边界

### 本 ADR 覆盖

- ✅ Context 作为 Instance 归属的统一抽象
- ✅ `context` 字段 + `piki.toml` [contexts] 配置
- ✅ 目录约定 `instances/contexts/{context_id}/`
- ✅ Context 级别的默认生成器/报告/碰撞行为
- ✅ 规则查询时的 Context 过滤约定

### 本 ADR 明确不覆盖

- ❌ 外部系统自动同步（`piki sync`）
- ❌ Context 级别的加密/权限/访问控制实现
- ❌ Context 级别的版本/变更追踪
- ❌ 连续介质建模（焊缝、管道沿线）

---

## 9. 向后兼容

| 数据                                     | 处理                                                            |
| ---------------------------------------- | --------------------------------------------------------------- |
| 无 `context` 的旧 Instance               | 默认 `internal`，行为完全不变                                   |
| 使用 `tags.scope` 或 `tags.owner` 的项目 | 建议迁移到 `context` + `[contexts]`                             |
| 现有生成器                               | 未识别 Context 的生成器仍输出全部实例，可逐步升级               |
| 现有 Layout                              | 引用 `read-only` Context 实例时，引擎发出警告而非报错（过渡期） |

---

## 10. 决策总结

| 决策                              | 选择                                   | 核心理由                                                     |
| --------------------------------- | -------------------------------------- | ------------------------------------------------------------ |
| 外部/保密/标段/粗糙设计/自然环境的统一表达 | `context` 字段 + `[contexts]` 配置     | 一个概念覆盖五类场景，避免概念爆炸                           |
| 默认 Context                      | `internal`                             | 绿地项目无感知                                               |
| Context 声明位置                  | `piki.toml` + 目录约定                 | 集中配置策略，文件层面可分离                                 |
| Context 与 Family 关系            | Context orthogonal（正交）于 Family    | 既有机柜仍可用 `RackFamily`，保密交换机仍可用 `ServerFamily` |
| 生成器默认过滤                    | 基于 Context 配置自动决策              | 避免每个生成器硬编码过滤逻辑                                 |
| 规则过滤                          | 通过 `ctx.query(context=...)` 显式声明 | 策略透明，避免默认策略隐藏错误                               |

---

## 11. 待回答问题

1. `context` 字段名是否会与运行时 `Context` 类产生混淆？是否需要改名为 `context_id` 或 `design_context`？
2. Context 是否可以嵌套？例如 `context = "package-hvac/rough"`。
3. 跨项目继承时，父项目的 Context 是否自动继承到子项目？
4. `classified` Context 的加载是否应支持基于文件路径或环境变量的动态解密？

---

## 参考

- [ADR-001: 项目组织模型](../data-model/001-project-organization.md)
- [ADR-005: 连接关系实例化与接口模型](../data-model/005-connection-as-instance.md)
- [ADR-006: 配合图（Mating Graph）](../data-model/006-mating-graph.md)
- [Instance 格式规范](../reference/04-instance.md)
