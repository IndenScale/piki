# piki 文档

> **Text-Native CAD** — 设计的本质是决策，不是画图。
>
> 用文本定义工程对象，用规则检查设计合理性，用 Git 管理设计演进。

## 快速开始

新用户建议按以下顺序阅读：

1. **[为什么需要 piki](concepts/00-why-piki.md)** — 从真实事故出发，理解问题与解决方案
2. **[10 分钟上手](concepts/01-quickstart.md)** — 最小工作示例：新增服务器 → 发现 PDU 过载 → 修正
3. **[核心概念](concepts/02-core-concepts.md)** — Family（型号族）、Plugin（行业插件）、Registry（注册表）、Rule（规则）
4. **[编写检查规则](concepts/03-writing-rules.md)** — 从实际问题出发，学习写规则
5. **[高级用法](concepts/04-advanced.md)** — CI/CD 集成、多插件协作、性能优化
6. **[AI Readiness](concepts/05-ai-readiness.md)** — 为什么 Text-Native + 开源是 AI 参与工程设计的前提

## 架构决策记录 (ADR)

记录 piki 的关键技术决策及其理由：

- **[ADR-001: 几何引擎与物理引擎](adr/001-geometry-and-physics-engine.md)** — 为什么引入 OpenUSD、在工具链的什么位置集成、范围边界
- **[ADR-002: 文本格式与一实例一文件](adr/002-text-native-and-file-per-instance.md)** — 为什么使用 YAML、为什么每个实例/型号独立文件
- **[ADR-003: 插件架构](adr/003-plugin-architecture.md)** — 为什么用插件管理领域知识，而非硬编码或配置驱动
- **[ADR-004: 多级质量检查](adr/004-multi-level-quality-checks.md)** — 从 L0 格式检查到 L6 AI 评估的分层体系
- **[ADR-005: LSP 兼容诊断](adr/005-lsp-compatible-diagnostics.md)** — 为什么诊断格式与 Language Server Protocol 对齐

## 参考文档

按需查阅的速查手册：

- **[CLI 命令参考](reference/cli.md)** — 所有命令、参数、示例
- **[API 参考](reference/api.md)** — 核心类与装饰器接口
- **[项目配置参考](reference/configuration.md)** — `piki.toml` 完整字段说明
- **[项目目录结构](reference/project-layout.md)** — 初始化后的目录与文件说明

## 参与贡献

- 开发环境搭建与贡献流程：[CONTRIBUTING.md](../CONTRIBUTING.md)
- 问题反馈与功能建议：[GitHub Issues](https://github.com/indenscale/piki/issues)

## 相关项目

- [folder-db](https://github.com/indenscale/folder-db) — piki 的底层数据访问层，负责 YAML 读写与基础 CRUD
- [SDE (Software Defined Engineering)](../Software%20Defined%20Engineering/) — piki 遵循的规范框架
