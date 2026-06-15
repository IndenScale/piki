# 架构决策记录（ADR）

> 按架构层级组织，而非按时间顺序。阅读时从 **数据模型** 开始，理解系统"存什么"，再到 **引擎与插件** 理解"怎么跑"，最后到 **可视化** 理解"怎么看"。

---

## 数据模型

定义 piki 的核心数据结构：Instance、Interface、Connection、Mating、Context。

| ADR | 主题 | 状态 |
|-----|------|------|
| [001](data-model/001-project-organization.md) | 项目组织：嵌套结构、物理空间、正交标签 | ✅ 已实现 |
| [005](data-model/005-connection-as-instance.md) | Connection 与 Interface 模型 | ✅ 已实现 |
| [006](data-model/006-mating-graph.md) | Mating Graph：部件耦合关系建模 | ✅ 已实现 |
| [010](data-model/010-brownfield-reference-instance.md) | 多上下文建模：既有/保密/标段/自然环境 | 🔍 提案中 |

## 引擎与插件

定义 piki 的执行机制：插件、质量检查、生成器、Catalog 权威层。

| ADR | 主题 | 状态 |
|-----|------|------|
| [002](engine-and-plugins/002-plugin-architecture.md) | 插件架构：领域知识的封装边界 | ✅ 已实现 |
| [003](engine-and-plugins/003-quality-checks-and-diagnostics.md) | 多级质量检查 L0-L6 与统一诊断格式 | ✅ 已实现 |
| [004](engine-and-plugins/004-generator-as-deliverable-pipeline.md) | Generator：从文本真相源到工程交付物 | ✅ 已实现 |
| [011](engine-and-plugins/011-catalog-as-authority-layer.md) | Catalog：物料、工法与可建造性意图 | ✅ 已接受 |
| [012](engine-and-plugins/012-adl-as-independent-package.md) | ADL 作为独立 Python 包 | ✅ 已实现 |

## 可视化

定义 piki 的 3D 呈现策略与 Studio IDE。

| ADR | 主题 | 状态 |
|-----|------|------|
| [007](visualization/007-cad-asset-reference.md) | CAD 资产引用与白牌标准型号 | ✅ 已实现 |
| [008](visualization/008-spatial-visualization-strategy.md) | 空间可视化：OpenUSD/glTF 选型 | ✅ 已实现 |
| [009](visualization/009-piki-studio.md) | Piki Studio：浏览器端工程设计 IDE | ✅ 已实现 |
