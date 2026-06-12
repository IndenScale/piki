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
3. **[ADR-002: 插件架构](adr/002-plugin-architecture.md)** — 为什么用插件而非硬编码
4. **[telecom 插件源码](../src/piki/extensions/telecom/plugin.py)** — 完整参考实现
5. **[datacenter 插件源码](../src/piki/extensions/datacenter/plugin.py)** — 多 Family 类型参考实现

---

## 架构决策记录 (ADR)

记录 piki 的关键技术决策及其理由，按影响范围排列：

- **[ADR-001: 项目组织模型](adr/001-project-organization.md)** — Instance/Layout 分离、嵌套项目、正交 Tag
- **[ADR-002: 插件架构](adr/002-plugin-architecture.md)** — 为什么用 Python 插件而非配置或硬编码
- **[ADR-003: 多级质量检查与统一诊断](adr/003-quality-checks-and-diagnostics.md)** — L0-L6 分层检查、LSP 兼容诊断格式
- **[ADR-004: 空间可视化策略](adr/004-spatial-visualization-strategy.md)** — OpenUSD 选型、碰撞检测、glTF 过渡
- **[ADR-005: Piki Studio](adr/005-piki-studio.md)** — 浏览器端 IDE、自研 USDA 解析器
- **[ADR-006: CAD 资产引用](adr/006-cad-asset-reference.md)** — 引用而非嵌入、白牌型号、资产完整性

---

## 参考文档

- **[CLI 命令参考](reference/07-cli.md)** — 所有命令、参数、示例
- **[API 参考](reference/06-api.md)** — 核心类与装饰器接口
- **[项目配置参考](reference/01-configuration.md)** — `piki.toml` 完整字段说明
- **[项目目录结构](reference/00-project-layout.md)** — 初始化后的目录与文件说明

---

## 工具

- **[Piki Studio](../studio/)** — 浏览器端 3D 预览 IDE，打开项目即看布局
- **[SDE (Software Defined Engineering)](../Software%20Defined%20Engineering/)** — piki 遵循的规范框架

## 参与贡献

- 开发环境搭建与贡献流程：[CONTRIBUTING.md](../CONTRIBUTING.md)
- 问题反馈与功能建议：[GitHub Issues](https://github.com/indenscale/piki/issues)
