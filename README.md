# piki

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 工程设计的挑剔伙伴。在提交评审和交底前，把问题找出来。

piki 是 [SDE (Software Defined Engineering)](../Software%20Defined%20Engineering/) 规范的一个参考实现。

**要求：Python 3.11+**

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
- piki 是工具：让 SDE 规范落地为可执行的检查、生成、报告

## 功能

- **型号库管理**：从厂商 datasheet 导入设备/材料/构件规格
- **规则引擎**：将国标、企标、项目特定要求编码为可自动执行的检查规则
- **设计校验**：在提交前自动检查 Schema 合规、外键完整、业务规则
- **报告生成**：根据 FS as DB 数据自动生成设计报告
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
```

完整教程：[10 分钟上手](docs/concepts/01-quickstart.md)

## 文档

按学习顺序阅读：

1. **[为什么需要 piki](docs/concepts/00-why-piki.md)** — 从真实事故出发，理解问题与解决方案
2. **[10 分钟上手](docs/concepts/01-quickstart.md)** — 最小工作示例：新增服务器 → 发现 PDU 过载 → 修正
3. **[核心概念](docs/concepts/02-core-concepts.md)** — Family（型号族）、Plugin（行业插件）、Registry（注册表）、Rule（规则）
4. **[编写检查规则](docs/concepts/03-writing-rules.md)** — 从实际问题出发，学习写规则
5. **[高级用法](docs/concepts/04-advanced.md)** — CI/CD 集成、多插件协作、性能优化

参考文档：

- **[CLI 命令参考](docs/reference/cli.md)** — 所有命令、参数、示例
- **[API 参考](docs/reference/api.md)** — 核心类与装饰器接口
- **[项目配置参考](docs/reference/configuration.md)** — `piki.toml` 完整字段说明
- **[项目目录结构](docs/reference/project-layout.md)** — 初始化后的目录与文件说明

[📖 文档首页](docs/index.md)

## 与 folder-db 的关系

|          | folder-db                | piki                       |
| -------- | ------------------------ | -------------------------- |
| 定位     | 数据访问层               | 框架层                     |
| 核心能力 | Schema、CRUD、外键       | 型号库、规则引擎、报告生成 |
| 约束表达 | 有限（类型、范围、枚举） | 无限（Python 函数）        |
| 适用场景 | 小规模、人直接编辑       | 中大规模、SDK 驱动         |

- folder-db 管"数据对不对"（结构约束）
- piki 管"设计合不合理"（业务规则）
- piki 可以读写 folder-db 格式，但不依赖它

## 贡献

欢迎贡献！请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发环境搭建、代码规范和 PR 流程。

## 许可证

MIT
