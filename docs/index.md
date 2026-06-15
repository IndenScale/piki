# piki 文档

> **在提交工程设计前，自动检查规则，把问题找出来。**
>
> 用 YAML 声明工程对象，用 Python 规则检查设计合理性，用 Git 管理设计演进。

---

## 按角色导航

### 🧐 评估 piki

1. **[为什么需要 piki](concepts/00-why-piki.md)** — 从真实事故出发，理解问题与解决方案
2. **[软件定义工程（SDE）](pitch/01-why-sde.md)** — 大模型落地工业的必由之路
3. **[Agent Native 工业软件](pitch/02-agent-native.md)** — 为 Agent 时代重新设计底层
4. **[AQL：工程设计的查询语言](../../aql/README.md)** — PDL + PLL + PML 三子语言
5. **[Engineering RLVR](pitch/04-engineering-rlvr.md)** — 可验证奖励如何驱动工程 AI
6. **[路线图](../ROADMAP.md)** — 当前进展和未来计划

### 🔧 使用 piki

1. **[核心概念与快速上手](concepts/01-core-concepts.md)** — Family → Model → Instance → Interface + Layout + Rule
2. **[编写检查规则](concepts/02-writing-rules.md)** — 从实际问题出发，学习写规则
3. **[高级用法 & AI Readiness](concepts/03-advanced.md)** — CI/CD、Generator、AI 为何需要 Text-Native
4. **[Text-Native & Agent-Oriented](concepts/04-text-native-and-agent-oriented.md)** — piki 的人机协同设计哲学
5. **[piki 的生态位](concepts/05-ecosystem-positioning.md)** — 敌、友与中间力量
6. **[设计知识成熟曲线](concepts/06-knowledge-maturation.md)** — 从仿真到规则到 Mating 的设计知识演进
7. **[示例项目](../samples/)** — 2 个精选示例：设备扩容 + 数据中心建设

### 🧩 扩展 piki

1. **[插件架构](concepts/01-core-concepts.md#7-plugin)** — Plugin 概念与内置插件
2. **[编写检查规则](concepts/02-writing-rules.md)** — `@rule` / `@generator` 装饰器 + QuerySet API
3. **[架构决策记录 (ADR)](adr/README.md)** — 按数据模型 / 引擎与插件 / 可视化三层组织
4. **[telecom 插件源码](../src/piki/extensions/telecom/plugin.py)** — 完整参考实现
5. **[datacenter 插件源码](../src/piki/extensions/datacenter/plugin.py)** — 多 Family 类型参考实现

---

## Pitch 系列（核心理念）

四篇文章从范式到引擎，逐层深入 piki 的设计哲学：

1. **[01 - 软件定义工程（SDE）](pitch/01-why-sde.md)** — 范式宣言：大模型与工业软件之间的交互范式错配，以及 Headless Engineering 的解决方案
2. **[02 - Agent Native 工业软件](pitch/02-agent-native.md)** — 品类定义：五项原则（声明式、CLI 优先、开发数据格式、Git/CICD、开源知识网络）
3. **[03 - AQL：工程设计的查询语言](../../aql/README.md)** — 技术规范：PDL（部件定义）+ PLL（部件布局）+ PML（部件配合）三子语言
4. **[04 - Engineering RLVR](pitch/04-engineering-rlvr.md)** — 驱动引擎：分层规则引擎作为 RLVR 奖励信号，SD-HWE-Bench 基线数据

---

## 架构决策记录 (ADR)

记录 piki 的关键技术决策及其理由，按核心主线到辅助体验的顺序排列：

- **[ADR-001: 项目组织模型](adr/data-model/001-project-organization.md)** — Instance/Layout 分离、嵌套项目、正交 Tag
- **[ADR-002: 插件架构](adr/engine-and-plugins/002-plugin-architecture.md)** — 为什么用 Python 插件而非配置或硬编码
- **[ADR-003: 多级质量检查与统一诊断](adr/engine-and-plugins/003-quality-checks-and-diagnostics.md)** — L0-L6 分层检查、LSP 兼容诊断格式
- **[ADR-004: 生成器](adr/engine-and-plugins/004-generator-as-deliverable-pipeline.md)** — 从文本真相源到工程交付物
- **[ADR-005: Connection 与 Interface](adr/data-model/005-connection-as-instance.md)** — Interface 模型、Connection 实例、引用语法
- **[ADR-006: Mating Graph](adr/data-model/006-mating-graph.md)** — 部件耦合关系建模（机械配合、守恒、同步等）
- **[ADR-007: CAD 资产引用](adr/visualization/007-cad-asset-reference.md)** — 引用而非嵌入、白牌型号、资产完整性
- **[ADR-008: 空间可视化策略](adr/visualization/008-spatial-visualization-strategy.md)** — OpenUSD 选型、碰撞检测、glTF 过渡
- **[ADR-009: Piki Studio](adr/visualization/009-piki-studio.md)** — 浏览器端 IDE、自研 USDA 解析器
- **[ADR-010: 多上下文工程设计](adr/data-model/010-brownfield-reference-instance.md)** — 用 Context 统一建模外部、保密、标段、粗糙设计与自然环境实体（勘察中）

---

## 功能需求提案 (RFC)

具体技术特性的设计方案与讨论：

- **[RFC-001: Telecom 接口类型体系](rfcs/001-telecom-interface-types.md)** — 接口类型枚举、兼容性矩阵、线缆映射

---

## 社区倡议 (Initiatives)

需要社区共同决策的战略性提案与跨项目倡议：

- **[Initiative-001: SD-HWE-Bench](initiatives/001-sd-hwe-bench.md)** — 面向实体工程领域的开放式端到端能力评测基准

---

## 参考文档

- **[CLI 命令参考](reference/07-cli.md)** — 所有命令、参数、示例
- **[API 参考](reference/06-api.md)** — 核心类与装饰器接口
- **[项目配置参考](reference/01-configuration.md)** — `piki.toml` 完整字段说明
- **[项目目录结构](reference/00-project-layout.md)** — 初始化后的目录与文件说明

---

## 工具

- **[Piki Studio](../studio/)** — 浏览器端 3D 预览 IDE，打开项目即看布局

## 参与贡献

- 开发环境搭建与贡献流程：[CONTRIBUTING.md](../CONTRIBUTING.md)
- 问题反馈与功能建议：[GitHub Issues](https://github.com/indenscale/piki/issues)
