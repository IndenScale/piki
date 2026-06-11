# piki 文档

> **在提交工程设计前，自动检查规则，把问题找出来。**
>
> 用 YAML 声明工程对象，用 Python 规则检查设计合理性，用 Git 管理设计演进。

---

## 按角色导航

### 🧐 评估 piki

1. **[为什么需要 piki](concepts/00-why-piki.md)** — 从真实事故出发，理解问题与解决方案
2. **[AI Readiness](concepts/05-ai-readiness.md)** — piki vs 手绘图纸 vs Excel vs BIM 对比矩阵
3. **[路线图](../ROADMAP.md)** — 当前进展和未来计划

### 🔧 使用 piki

1. **[10 分钟上手](concepts/01-quickstart.md)** — 最小工作示例：新增服务器 → 发现 PDU 过载 → 修正
2. **[核心概念](concepts/02-core-concepts.md)** — Family → Model → Instance 三层模型 + Layout 分离
3. **[编写检查规则](concepts/03-writing-rules.md)** — 从实际问题出发，学习写规则
4. **[高级用法](concepts/04-advanced.md)** — CI/CD 集成、多插件协作、Generator 配置
5. **[示例项目](../samples/)** — 6 个可直接运行的示例：从入门到嵌套项目

### 🧩 扩展 piki

1. **[核心概念 § Plugin](concepts/02-core-concepts.md)** — 插件架构
2. **[编写检查规则](concepts/03-writing-rules.md)** — `@rule` / `@generator` 装饰器 + QuerySet API
3. **[ADR-003: 插件架构](adr/003-plugin-architecture.md)** — 为什么用插件而非硬编码
4. **[telecom 插件源码](../src/piki/extensions/telecom/plugin.py)** — 完整参考实现
5. **[datacenter 插件源码](../src/piki/extensions/datacenter/plugin.py)** — 多 Family 类型参考实现

---

## 架构决策记录 (ADR)

记录 piki 的关键技术决策及其理由：

- **[ADR-001: 几何引擎与物理引擎](adr/001-geometry-and-physics-engine.md)** — 为什么引入 OpenUSD、范围边界
- **[ADR-002: 文本格式与一实例一文件](adr/002-text-native-and-file-per-instance.md)** — 为什么 YAML、为什么每个实例独立文件
- **[ADR-003: 插件架构](adr/003-plugin-architecture.md)** — 为什么用插件管理领域知识
- **[ADR-004: 多级质量检查](adr/004-multi-level-quality-checks.md)** — L0-L6 分层检查体系
- **[ADR-005: LSP 兼容诊断](adr/005-lsp-compatible-diagnostics.md)** — 为什么诊断格式与 Language Server Protocol 对齐
- **[ADR-006: Piki Studio](adr/006-piki-studio-web-viewer.md)** — 浏览器端 3D 预览 IDE、与 CLI 的关系
- **[ADR-007: CAD 资产引用](adr/007-cad-asset-reference.md)** — 引用而非嵌入、多专业集成
- **[ADR-008: Instance 与 Layout 分离](adr/008-instance-layout-separation.md)** — 设备身份与部署决策分离、Git 分支方案比选
- **[ADR-009: 嵌套项目与 CDE](adr/009-nested-projects-and-cde.md)** — 嵌套项目、FQID、正交 Tag

---

## 参考文档

- **[CLI 命令参考](reference/cli.md)** — 所有命令、参数、示例
- **[API 参考](reference/api.md)** — 核心类与装饰器接口
- **[项目配置参考](reference/configuration.md)** — `piki.toml` 完整字段说明
- **[项目目录结构](reference/project-layout.md)** — 初始化后的目录与文件说明

---

## 工具

- **[Piki Studio](../studio/)** — 浏览器端 3D 预览 IDE，打开项目即看布局
- **[SDE (Software Defined Engineering)](../Software%20Defined%20Engineering/)** — piki 遵循的规范框架

## 参与贡献

- 开发环境搭建与贡献流程：[CONTRIBUTING.md](../CONTRIBUTING.md)
- 问题反馈与功能建议：[GitHub Issues](https://github.com/indenscale/piki/issues)
