# 核心概念与快速上手

> 理解 piki 声明式建模的核心：Family → Model → Instance → Interface 数据模型，Layout 部署分离，Rule 规则引擎。
>
> 就像 Kubernetes 用 YAML 声明 Pod，piki 用 YAML 声明工程对象。你写"要什么"，piki 负责"对不对"。

---

## 快速验证：5 分钟看效果

不需要手动创建项目，直接运行示例：

```bash
cd samples/01-telecom-expansion
piki check
```

你会看到检查报告，列出所有规则是否通过。

> 完整的 10 分钟互动教程（含修改 → 发现问题 → 修正的流程）见 [samples/](../../samples/) 目录。

---

## 1. Family：型号族（约束结构）

**问题**：服务器都有高度、功耗、重量，但 Dell R740 和 HP DL380 数值不同。如何统一约束、差异取值？

**Family** 定义"这类设备必须有什么字段、什么类型"。它只声明约束，不提供具体数值。

```python
# piki-telecom 插件定义
class ServerFamily(BaseModel):
    id: str
    name: str
    model: str
    height_u: int = Field(default=2, ge=1, le=48)
    tdp_w: float = Field(default=300, gt=0)
    psu_count: int = Field(default=1, ge=1)
```

Family 只能用 pydantic 类定义，通过插件注册。不支持 YAML 配置——Family 是代码（约束逻辑），不是数据。

→ 详细格式：[reference/02-family.md](../reference/02-family.md)

---

## 2. Model：型号（默认值）

**问题**：Family 只说了"服务器必须有 height_u"，但没说是多少。厂商规格存哪？

**Model** 是 Family 的具体实现，提供默认值：

```yaml
# models/devices/generic-server.yaml
model: generic-server
family: ServerFamily

height_u: 2
tdp_w: 300
psu_count: 1
psu_redundancy: false
```

Model 来源：插件自带 + 项目本地 `models/` 目录。

→ 详细格式：[reference/03-model.md](../reference/03-model.md)

---

## 3. Instance：实例（实际部署值）

**问题**：Model 提供默认值，但实际部署时可能需要覆盖。如何记录实际值？

**Instance** 是实际部署的设备，可覆盖 Model 的默认值：

```yaml
# instances/servers/SRV-01.yaml
id: SRV-01
family: ServerFamily
name: 服务器-01
model: generic-server
status: installed
tdp_w: 250  # 覆盖 Model 默认值 300
```

Instance 只写决策字段（型号、实际功耗），规格字段从 Model 自动补齐。

→ 详细格式：[reference/04-instance.md](../reference/04-instance.md)

---

## 4. Interface：可连接点

**问题**：一台服务器有多个网络口、多个电源口。Connection 需要精确引用某个口，而不是整台设备。

**Interface** 是 Instance 对外暴露的可连接点，内嵌在 Instance 中：

```yaml
# instances/servers/SRV-01.yaml（片段）
interfaces:
  - id: eth0
    interface_type: SFP28
    direction: bidirectional
  - id: power-a
    interface_type: IEC-C14
    direction: input
```

引用语法：`instance_id/interface_id`（如 `SRV-01/eth0`），在 Connection 实例中使用。

> Interface 不是独立的 Instance，而是内嵌在 Instance 的 `interfaces` 列表中。

→ 详细格式：[reference/04-instance.md#interface](../reference/04-instance.md#interface实例的可连接点)

---

## 数据模型总结

```text
Family（约束结构）
  └── Model（厂商默认值）
        └── Instance（实际部署值，可覆盖）
              └── Interface[]（可连接点）
```

| 层级 | 定义位置 | 内容 | 示例 |
|------|---------|------|------|
| Family | 插件代码（pydantic） | 字段约束 | `height_u: int = Field(ge=1, le=48)` |
| Model | `models/` YAML | 厂商规格默认值 | `height_u: 2` |
| Instance | `instances/` YAML | 实际部署值 + 覆盖 | `tdp_w: 250` |
| Interface | Instance 内嵌 | 可连接点 | `id: eth0, interface_type: SFP28` |

解析过程：

```python
family = registry.get_family("ServerFamily")     # 约束校验
model = registry.get_model("generic-server")     # 默认值
instance = load_yaml("instances/SRV-01.yaml")    # 覆盖值 + interfaces
resolved = model.defaults + instance.overrides   # 合并
pydantic.validate(resolved, family)              # Schema 校验
```

---

## 5. Layout：部署决策

Instance 声明**设备是什么**。部署位置（放哪、接哪）在 Layout 中独立管理：

```yaml
# layout.yaml
- instance: SRV-01
  rack_id: RACK-A01
  position_u: 10
  pdu_id: PDU-A
```

**分离的价值**：

- **方案比选即 Git 分支**：同一设备，分支 A 放 RACK-A01，分支 B 放 RACK-B01，合并时只冲突 `layout.yaml`
- **协作解耦**：结构工程师改 `layout.yaml`，设备工程师改 `instances/`，不产生冲突

→ 详细格式：[reference/05-layout.md](../reference/05-layout.md)

---

## 6. Rule：检查规则

规则是**用 Python 表达的业务知识**。piki 内置规则自动运行，你还可以用 `@rule` 装饰器编写自定义规则：

```python
# rules/power.py
from piki import rule, Context

@rule("TELECOM-POWER-001", "PDU 功率预算检查")
def check_pdu_budget(ctx: Context):
    threshold = ctx.config.get("power_threshold", 0.8)
    for pdu in ctx.query("instances", family="PduFamily"):
        devices = ctx.query("instances", pdu_id=pdu.id)
        load = sum(d.resolved.tdp_w for d in devices)
        assert load / pdu.resolved.capacity_w <= threshold
```

→ 详细教程：[编写检查规则 →](02-writing-rules.md)

---

## 7. Plugin：行业插件

Plugin 是 Family + Rule + Generator 的打包单元，封装一个行业的领域知识：

| 插件 | 行业 | Family | 规则数 |
|------|------|--------|--------|
| `telecom` | 电信/数据中心机柜级 | Rack / PDU / Server | 7 |
| `datacenter` | 模块化数据中心方舱级 | Container / PowerUnit / Equipment / Connection | 5 |

启用插件：在 `piki.toml` 中 `[plugins] enabled = ["telecom"]`。

→ 插件架构：[ADR-002](../adr/engine-and-plugins/002-plugin-architecture.md)

---

## 概念关系图

```text
┌─────────────────────────────────────────────────────────────┐
│                    Plugin（行业插件）                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Family    │  │    Rule     │  │      Library        │  │
│  │  （约束结构） │  │ （业务检查） │  │    （型号默认值）    │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         └────────────────┼─────────────────────┘             │
│                          ▼                                   │
│                   ┌─────────────┐                            │
│                   │   Registry  │  ← 运行时中央目录           │
│                   └──────┬──────┘                            │
│                          │                                   │
│  ┌────────────┐  ┌───────┴──────┐  ┌──────────────┐         │
│  │  Instance  │  │   Layout     │  │   Generator  │         │
│  │ ┌────────┐ │  │ layout.yaml  │  │ BOM/面板图    │         │
│  │ │Interface│ │  │ rack_id /    │  │ piki check   │         │
│  │ └────────┘ │  │ pdu_id       │  └──────────────┘         │
│  └────────────┘  └──────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

---

## ADL：这些概念的语言规范

上文介绍的 Family / Model / Instance / Layout 等概念，对应 **ADL（Assembly Definition Language，装配体定义语言）** 中的子语言：

- **PDL（Part Definition Language）**：定义“什么东西存在”——对应 Family → Model → Instance → Interface
- **PLL（Part Layout Language）**：定义“东西放在哪里”——对应 Layout
- **PML（Part Mating Language）**：定义“部件之间如何耦合”——对应 Mate / Connection

ADL 的设计哲学、三子语言规范与正交分离 rationale，详见 [ADL：装配体定义语言](../pitch/03-adl.md)。

各层涉及的具体概念（Part、Interface、Assembly、Mating、DOF、参数化定位链、全局坐标）以及与代码模型的对应关系，详见 [ADL 分层概念模型](../../adl/docs/concepts/01-layered-model.md)。

---

## 下一步

- [编写检查规则 →](02-writing-rules.md)
- [高级用法：CI/CD、Generator →](03-advanced.md)
- [ADL 语言规范 →](../pitch/03-adl.md)
- [ADL 分层概念模型 →](../../adl/docs/concepts/01-layered-model.md)
- [了解项目目录结构 →](../reference/00-project-layout.md)
