# piki

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Agent Native 工业软件的第一个参考实现。**
>
> piki 让工程设计变得像软件一样可定义、可校验、可协作。工程师（或 Agent）用声明式语言描述设计意图，piki 在提交前自动发现错误——从 YAML 语法到三维空间碰撞，全部在秒级内完成。

---

## 一句话

```bash
pip install piki
piki init --plugin telecom
piki check    # 在提交前自动发现设计错误
```

---

## 为什么是 piki

当前的大模型无法可靠操作工业软件——它们是"盲的"，而工业软件是为人类眼手协调设计的 GUI。piki 是 **Headless Engineering** 的工程实现：设计意图以纯文本存在，Agent 直接读写，规则引擎在毫秒级返回结构化验证结果。

更完整的理念请阅读：

| | 文章 | 说什么 |
|---|---|---|
| 1 | [软件定义硬件（SDH）](docs/pitch/01-why-sdh.md) | 为什么这件事必须发生——大模型与工业软件的范式错配 |
| 2 | [Agent Native 工业软件](docs/pitch/02-agent-native.md) | 新品类是什么——五项原则与生态位 |
| 3 | [ADL：装配体定义语言](docs/pitch/03-adl.md) | 怎么表达——PDL/PML/PLL 三子语言 |
| 4 | [Engineering RLVR](docs/pitch/04-engineering-rlvr.md) | 怎么进化——可验证奖励驱动工程 AI |

---

## 文本为什么优于图纸

| 能力 | piki（声明式 YAML） | 图形 CAD / BIM |
|---|---|---|
| **版本控制** | `git diff` 精确到字段 | 二进制文件，diff 无意义 |
| **自动化检查** | Python 规则直接读取 | 需解析专有格式 |
| **批量修改** | `sed` / grep / 脚本 | 手动逐个点选 |
| **CI/CD 集成** | 原生支持 | 需额外导出步骤 |
| **多人协作** | Git 分支合并 | 文件锁定或冲突 |
| **AI 参与** | 文本是 LLM 原生格式 | 需 OCR / 视觉模型猜测 |

预览是**只读**的。修改设计？改文本，重新生成。文本是设计的**唯一真相源**。

---

## 快速开始

```bash
pip install piki                # Python 3.11+
piki init --plugin telecom      # 初始化电信项目
piki check                      # 运行所有检查
piki report --format markdown   # 生成报告
piki generate bom-csv           # 导出 BOM 清单
```

完整教程和示例：`[samples/](samples/)` 目录。

---

## 文档

- **[为什么需要 piki](docs/concepts/00-why-piki.md)** — 从真实事故出发
- **[核心概念](docs/concepts/01-core-concepts.md)** — Family → Model → Instance 声明体系
- **[编写检查规则](docs/concepts/02-writing-rules.md)** — @rule 装饰器 + QuerySet API
- **[CLI 参考](docs/reference/07-cli.md)** — 所有命令
- **[API 参考](docs/reference/06-api.md)** — 核心类与装饰器
- **[配置参考](docs/reference/01-configuration.md)** — piki.toml 完整字段
- **[架构决策记录](docs/adr/)** — 关键设计决策与理由
- **[路线图](ROADMAP.md)** — 当前进展和未来计划

---

## 贡献

欢迎贡献！请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

MIT
