# piki

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Text-Native CAD** — 设计的本质是决策，不是画图。
>
> 用文本定义工程对象，用规则检查设计合理性，用 Git 管理设计演进。
> 在提交评审和交底前，把问题找出来。

piki 是 [SDE (Software Defined Engineering)](../Software%20Defined%20Engineering/) 规范的一个参考实现。

**要求：Python 3.11+**

---

## 什么是 Text-Native CAD？

Text-Native CAD 是一种**声明式建模**方式：

```yaml
# devices/SRV-01.yaml — 声明一台服务器的部署意图
id: SRV-01
model: dell-r740
rack_id: RACK-A01
position_u: 10
pdu_id: PDU-A
```

你声明设计意图（"SRV-01 放在 RACK-A01 的 U10，接入 PDU-A"），piki 负责解析、校验、生成预览和报告。

文本是设计的**唯一真相源**（Single Source of Truth）。预览、BOM、碰撞检查都是派生视图，随时可以重新生成。

### 为什么是文本（声明式）？

| 能力 | 声明式文本 | 交互式图形 |
|------|-----------|-----------|
| **设计意图** | 声明"要什么"，系统推导"怎么做" | 手动操作每个点、线、面 |
| **版本控制** | `git diff` 精确到字段 | 二进制文件，diff 无意义 |
| **代码评审** | 像审代码一样审设计 | 截图标注，效率低 |
| **自动化检查** | Python 规则直接读取 | 需解析专有格式 |
| **批量修改** | `sed` / `jq` / Python 脚本 | 手动逐个点选 |
| **CI/CD 集成** | 原生支持 | 需额外导出步骤 |
| **多人协作** | Git 分支合并 | 文件锁定或冲突 |

### 预览与可视化

piki 支持将文本设计导出为 **OpenUSD** 场景，用于：

- **3D 预览**：在 USD Viewer 中查看布局
- **碰撞检查**：自动检测物理空间冲突
- **与其他工具集成**：BIM、数字孪生平台直接读取

> 预览是**只读**的。修改设计？改 YAML，重新生成。

---

## 核心思想

工程设计中的错误成本极高：

- 结构梁配筋不足 → 返工、延期、安全隐患
- 电信设备 PDU 超容 → 宕机、业务中断
- 线缆长度超限 → 信号衰减、反复调试

piki 在工程师提交方案前（`git commit` 之前），像一位挑剔的审校者，自动检查数据完整性、规范符合性和设计合理性。

## 定位

```
SDE（思想框架）
  └── piki（参考实现）
        ├── piki-cli          # 命令行工具 ✅
        ├── piki-sdk-{lang}   # 多语言 SDK — 规划中
        └── piki-registry     # 型号与规则注册中心 — 规划中
```

- SDE 是规范：定义 Git 工作流、语义化 ID、目录结构、文本优先
- piki 是工具：让 SDE 规范落地为可执行的检查、生成、报告、预览

## 功能

- **型号库管理**：从厂商 datasheet 导入设备/材料/构件规格
- **规则引擎**：将国标、企标、项目特定要求编码为可自动执行的检查规则
- **设计校验**：在提交前自动检查 Schema 合规、外键完整、业务规则、碰撞冲突
- **报告生成**：根据设计数据自动生成 BOM、检查报告
- **OpenUSD 导出**：生成可预览的 3D 场景
- **Git 原生**：所有变更即 commit，所有检查即 pre-commit hook

## 安装

```bash
pip install piki
```

> **要求：** Python 3.11 或更高版本。

## 快速开始

```bash
# 初始化项目
piki init --plugin telecom

# 录入现有设施
# racks/RACK-A01.yaml
# devices/SRV-01.yaml

# 编写新增方案
# devices/SRV-03.yaml

# 运行检查
piki check

# 生成报告
piki report --format markdown

# 导出 OpenUSD 预览（可选）
piki export usd --output scene.usda
```

完整教程：[10 分钟上手](docs/concepts/01-quickstart.md)

## 文档

按学习顺序阅读：

1. **[为什么需要 piki](docs/concepts/00-why-piki.md)** — 从真实事故出发，理解问题与解决方案
2. **[10 分钟上手](docs/concepts/01-quickstart.md)** — 最小工作示例：新增服务器 → 发现 PDU 过载 → 修正
3. **[核心概念](docs/concepts/02-core-concepts.md)** — Family（型号族）、Plugin（行业插件）、Registry（注册表）、Rule（规则）
4. **[编写检查规则](docs/concepts/03-writing-rules.md)** — 从实际问题出发，学习写规则
5. **[高级用法](docs/concepts/04-advanced.md)** — CI/CD 集成、多插件协作、性能优化
6. **[AI Readiness](docs/concepts/05-ai-readiness.md)** — 为什么 Text-Native + 开源是 AI 参与工程设计的前提

参考文档：

- **[CLI 命令参考](docs/reference/cli.md)** — 所有命令、参数、示例
- **[API 参考](docs/reference/api.md)** — 核心类与装饰器接口
- **[项目配置参考](docs/reference/configuration.md)** — `piki.toml` 完整字段说明
- **[项目目录结构](docs/reference/project-layout.md)** — 初始化后的目录与文件说明

[📖 文档首页](docs/index.md)

## 与 folder-db 的关系

|          | folder-db                | piki                       |
| -------- | ------------------------ | -------------------------- |
| 定位     | 数据访问层               | Text-Native CAD 框架       |
| 核心能力 | Schema、CRUD、外键       | 型号库、规则引擎、报告生成、USD 导出 |
| 约束表达 | 有限（类型、范围、枚举） | 无限（Python 函数）        |
| 适用场景 | 小规模、人直接编辑       | 中大规模、SDK 驱动         |

- folder-db 管"数据对不对"（结构约束）
- piki 管"设计合不合理"（业务规则 + 空间冲突）
- piki 可以读写 folder-db 格式，但不依赖它

## 贡献

欢迎贡献！请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发环境搭建、代码规范和 PR 流程。

## 许可证

MIT
