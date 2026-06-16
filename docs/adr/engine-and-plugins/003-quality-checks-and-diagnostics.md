# ADR-003: 多级质量检查体系与统一诊断格式

> 状态：已实现
> 日期：2026-06-12
> 作者：piki 核心团队
> 修订：2026-06-16 — 细化 L1/L4/L5 子层，明确 L6 为签核/评估层

## 背景

工程设计的错误发现得越晚，修复成本越高。传统流程中，不同阶段的检查由不同工具、不同角色执行，标准不统一、结果难追溯。piki 的目标是将尽可能多的检查**左移**到设计阶段，并以统一格式呈现。

本 ADR 记录两个关联决策：检查为什么需要分层、诊断信息为什么选择 LSP 兼容格式。

---

## 1. 为什么多级检查

### 1.1 单一检查层的问题

如果只有一层检查（如"规则引擎"），风格问题（YAML 缩进不一致）和结构错误（字段类型错误）混在一起；快速反馈和深度分析无法区分；严重级别无法表达——"缩进不对"和"PDU 过载"都是"失败"。

### 1.2 检查天然分层

真实工程中，检查按成本和时效天然分层：

```
Layer 0: 文件格式合法性（< 1ms）
    ↓ "这甚至不是合法的 YAML"

Layer 1a: Schema 校验——字段类型与值域（< 10ms）
    ↓ "height_u 必须是 1-48 的整数"

Layer 1b: 风格与约定检查（< 10ms）
    ↓ "实例 ID 应符合 SRV-{rack}-{seq} 命名规范"

Layer 2: 单记录完整性——外键、必填项、Mate 自洽（< 10ms）
    ↓ "rack_id 引用的机柜不存在"

Layer 3: 跨记录业务规则 / 设计规范（10-100ms）
    ↓ "PDU-A 负载率 95%，超过阈值 80%"

Layer 4a: 快速几何检查——AABB、U 位冲突、经验空间规则（< 1s）
    ↓ "SRV-01 与 SRV-02 在 U10 处空间重叠"

Layer 4b: 精确几何检查——CAD 内核干涉、间隙、包容、可达性（1s-1min）
    ↓ "SRV-01 的 PSU 把手与机柜后门干涉 12.3 cm³"

Layer 5a: 快速物理规则——线性热预算、负载率、重量累积（< 1s）
    ↓ "机柜 TDP 总和超过散热容量的 80%"

Layer 5b: 物理仿真验证——CFD、FEA、电磁、振动（1min-1h）
    ↓ "液冷管路压降超过泵的扬程"

Layer 6: 签核与综合评估——交付物验证、专家/AI 评审（1s-10min）
    ↓ "该方案已通过所有下层检查，等待最终 signoff"
```

每一层的输入依赖、执行成本、反馈时效、修复成本都不同。高成本检查（L4b、L5b）与最终签核（L6）通过 `piki verify geom/phys`、`--deep` 或 `piki signoff` 显式启用，不阻塞日常流程。

### 1.3 分层执行策略

- **L0-L2 + L1b**：加载时同步执行，失败立即终止。
- **L3 + L4a + L5a**：`piki check` 默认执行；其中 L3 为 pytest 风格规则函数，L4a/L5a 为低成本几何/物理快速规则。
- **L4b + L5b**：通过显式命令或标志启用（`piki verify geom`、`piki verify phys`、`--deep`），不阻塞日常流程。
- **L6**：通过 `piki signoff` 或 `--signoff` 启用，汇总下层证据并支持专家/AI 综合评估。

---

## 2. 为什么使用 LSP 兼容诊断格式

### 2.1 消费者多样性

诊断信息被多种消费者使用：终端用户（人类可读）、CI 系统（JUnit XML）、IDE（LSP Diagnostic）、PR 评论（Markdown）、报告生成器（JSON）。

### 2.2 LSP 格式的优势

| 维度 | LSP 格式 | 自定义格式 |
|------|---------|-----------|
| 编辑器生态 | VS Code、Vim、JetBrains 原生支持 | 需自行开发插件 |
| 定位精度 | 精确到字符范围（Range） | 通常只有行号 |
| 关联信息 | relatedInformation 支持跨文件引用 | 需自行设计 |
| 扩展性 | data 字段可携带附加信息 | 修改 schema 破坏兼容 |

### 2.3 跨文件关联

工程诊断经常需要"错误在这里，原因在那里"：

```python
diagnostic = Diagnostic.error(
    message="设备 SRV-03 引用的机柜 RACK-A01 不存在",
    location=Location.from_path("instances/SRV-03.yaml", line=4),
    code="TELECOM-FK-001",
    related_information=[
        RelatedInformation(
            location=Location.from_path("instances/racks/"),
            message="机柜目录为空，未定义任何机柜",
        )
    ],
)
```

在 IDE 中：主错误红色波浪线在 `SRV-03.yaml`，关联信息黄色提示在 `racks/`。

### 2.4 位置追踪

诊断的精确位置来自 YAML 源码追踪：PyYAML 解析时记录每个字段的行号和列号，pydantic 校验失败时从 `ValidationError` 定位到具体字段。

### 2.5 统一报告管道

所有报告格式基于同一 Diagnostic 模型，不是"每种格式从原始结果重新解析"：

```
RuleResult → Diagnostic → format_human() / format_json() / format_junit() / format_markdown()
```

---

## 3. 决策总结

| 决策 | 选择 | 核心理由 |
|------|------|----------|
| 检查分层 | L0-L6；L0-L2+L1b 加载时执行，L3+L4a+L5a 默认执行，L4b/L5b 显式启用，L6 签核 | 不同成本、不同时效、不同修复代价 |
| 深度/签核检查 | `--deep`、`piki verify geom/phys`、`--signoff` 显式启用 | 高成本检查与最终 signoff 不阻塞日常流程 |
| 诊断格式 | LSP-compatible Diagnostic | IDE 原生支持、跨文件关联、一次实现 |
| 位置追踪 | PyYAML AST + SourceTrackedDict | 精确到字段级别，零额外解析开销 |
| 报告生成 | 统一 Diagnostic → 多格式序列化 | 避免重复解析，新增格式成本低 |

---

## 参考

- [编写检查规则](../concepts/02-writing-rules.md)
- [Diagnostic API 参考](../reference/06-api.md#diagnostic)
