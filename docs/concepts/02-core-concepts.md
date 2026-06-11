# 核心概念

> 理解 piki 声明式建模的核心：Family（型号族）→ Model（型号）→ Instance（实例）三层模型。
>
> 就像 Kubernetes 用 YAML 声明 Pod 配置，piki 用 YAML 声明工程对象。你写"要什么"，piki 负责"对不对"。

---

## 1. Family：型号族（约束结构）

### 问题

同一类设备（如服务器）有共同属性：都有高度、功耗、重量。但不同型号（Dell R740 vs HP DL380）具体数值不同。如何**统一约束、差异取值**？

### 解决方案

**Family** 是 pydantic 类，定义"这类设备必须有什么字段、什么类型"：

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

Family 只**声明**约束结构，不提供具体数值。具体数值由 Model 提供。

### 嵌套继承

```text
ServerFamily               ← 插件定义（pydantic 类）
  └── generic-server.yaml  ← Model：默认值 2U / 300W
  └── dell-r740.yaml       ← Model：默认值 2U / 350W
```

| 方式 | 问题 | Family 方案 |
|------|------|------------|
| 纯 YAML 无约束 | 写错字段类型发现不了 | pydantic 自动校验 |
| 数据库 DDL | 改结构需迁移 | YAML + pydantic，改文件即生效 |

---

## 2. Model：型号（默认值）

### 问题

Family 只定义了"服务器必须有 height_u 和 tdp_w"，但没说具体是多少。Dell R740 是 2U/350W，HP DL380 是 2U/500W。这些**厂商规格**存在哪？

### 解决方案：型号库

**Model** 是 Family 的一个具体实现，提供默认值：

```yaml
# library/devices/generic-server.yaml
model: generic-server
family: ServerFamily

physical:
  height_u: 2

power:
  tdp_w: 300
  psu_count: 1
```

Model 来自两个来源：

1. **插件自带**：`piki-telecom` 安装时附带常用型号
2. **项目本地**：`library/` 目录下项目自己维护的型号

---

## 3. Instance：实例（实际部署值）

### 问题

Model 提供了默认值，但实际部署时可能需要覆盖。例如 `generic-server` 默认功耗 300W，但某台实际只有 250W。如何**记录实际值**？

### 解决方案：设计记录

**Instance** 是实际部署的设备，可覆盖 Model 的默认值：

```yaml
# instances/SRV-01.yaml
id: SRV-01
family: ServerFamily
name: 服务器-01
model: generic-server
status: installed
tdp_w: 250  # 覆盖 Model 默认值 300
```

Instance 只写**决策字段**（型号、实际功耗），规格字段（height_u、默认 tdp_w）从 Model 自动补齐。

---

## 三层结构总结

```text
Family（pydantic 类，声明约束结构）
  └── Model（YAML，声明厂商默认值）
        └── Instance（YAML，声明实际部署值，可覆盖）
```

| 层级 | 定义位置 | 内容 | 示例 |
|------|---------|------|------|
| Family | 插件代码（pydantic） | 字段约束 | `height_u: int = Field(ge=1, le=48)` |
| Model | `library/` YAML | 厂商规格默认值 | `height_u: 2` |
| Instance | `instances/` YAML | 实际部署值 + 覆盖 | `tdp_w: 250` |

解析过程：

```python
# piki 自动完成
family = registry.get_family("ServerFamily")     # 约束校验
model = registry.get_model("generic-server")     # 默认值
instance = load_yaml("instances/SRV-01.yaml")    # 覆盖值
resolved = model defaults + instance overrides   # 合并
pydantic.validate(resolved, family)              # Schema 校验
```

---

## 4. Layout：部署决策（ADR-008）

Instance 文件声明**设备是什么**。部署位置（放哪、接哪）在 Layout 中独立管理：

```yaml
# instances/SRV-01.yaml       ← 只声明身份
id: SRV-01
family: ServerFamily
model: generic-server
tdp_w: 250
```

```yaml
# layouts/layout.yaml          ← 只声明部署
entries:
  - instance: SRV-01
    rack_id: RACK-A01
    position_u: 10
    pdu_id: PDU-A
```

**分离的价值**：同一个设备，Git 分支可以做不同部署方案——分支 A 放 RACK-A01，分支 B 放 RACK-B01，合并时只冲突 `layout.yaml`，Instance 文件无冲突。

---

## 5. Rule：检查规则

规则是**用 Python 表达的业务知识**。piki 内置规则（Schema 校验、外键检查、Layout 引用完整性）自动运行。你还可以用 `@rule` 装饰器编写自定义规则：

```python
# rules/power.py
from piki import rule, Context

@rule("TELECOM-POWER-001", "PDU 功率预算检查")
def check_pdu_budget(ctx: Context):
    threshold = ctx.config.get("power_threshold", 0.8)
    for pdu in ctx.query("pdus"):
        devices = ctx.query("devices", pdu_id=pdu.id)
        load = sum(d.resolved.tdp_w for d in devices)
        assert load / pdu.resolved.capacity_w <= threshold
```

详细教程：[编写检查规则 →](03-writing-rules.md)

---

## 6. Plugin：行业插件

Plugin 是 Family + Rule + Generator 的打包单元，封装一个行业的领域知识：

```python
class TelecomPlugin(Plugin):
    name = "telecom"

    def register_families(self, registry):
        registry.add_family("RackFamily", RackFamily)
        registry.add_family("PduFamily", PduFamily)
        registry.add_family("ServerFamily", ServerFamily)

    def register_rules(self, checker):
        checker.add_rule("TELECOM-POWER-001", "PDU 功率预算检查", check_pdu_budget)
        # ... 更多规则

    def register_generators(self, checker):
        checker.add_generator("bom-csv", "BOM CSV 导出", generate_bom_csv)
```

当前内置两个插件：

| 插件 | 行业 | Family | 规则数 |
|------|------|--------|--------|
| `telecom` | 电信/数据中心机柜级 | Rack / PDU / Server | 7 |
| `datacenter` | 模块化数据中心方舱级 | Container / PowerUnit / Equipment / Connection | 5 |

---

## 概念关系图

```text
┌─────────────────────────────────────────────────────────────┐
│                    Plugin（行业插件）                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Family    │  │    Rule     │  │      Library        │  │
│  │  （约束结构） │  │ （业务检查） │  │    （型号默认值）    │  │
│  │ ServerFamily │  │PDU功率检查  │  │ generic-server.yaml │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         └────────────────┼─────────────────────┘             │
│                          ▼                                   │
│                   ┌─────────────┐                            │
│                   │   Registry  │  ← 运行时中央目录           │
│                   └──────┬──────┘                            │
│                          │                                   │
│         ┌────────────────┼────────────────┐                  │
│         ▼                ▼                ▼                  │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Instance  │  │   Generator  │  │    Report    │         │
│  │  设计记录   │  │  BOM/面板图/标签│  │   检查报告    │         │
│  │ SRV-01.yaml│  │  export_bom() │  │  piki check  │         │
│  └────────────┘  └──────────────┘  └──────────────┘         │
│                                                              │
│  ┌────────────┐                                              │
│  │   Layout   │  ← 部署决策（ADR-008）                        │
│  │ layout.yaml│     rack_id / position_u / pdu_id            │
│  └────────────┘                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 下一步

- [学习写规则 →](03-writing-rules.md)
- [高级用法：CI/CD 集成、Generator 配置 →](04-advanced.md)
