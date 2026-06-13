# piki

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Landing Page](https://img.shields.io/badge/landing%20page-piki.teal-0d9488)](https://indenscale.github.io/piki/)

> **piki 是一个面向工程设计的文本原生声明式系统建模框架（DSMF）。**
>
> 它包含一套声明式建模语言：用 YAML 声明工程对象，用 Python 规则检查设计合理性，用 Git 管理设计演进。

piki 是 [SDE (Software Defined Engineering)](../Software%20Defined%20Engineering/) 规范的一个参考实现。

## 要求

- Python 3.11+

---

## 一句话理解 piki

把工程设计的检查规则写成代码，每次 `git commit` 前自动运行。就像 Markdown 是文本内容的声明式格式，piki 是工程设计的声明式系统建模框架（DSMF），其核心是一套声明式建模语言。

```python
# rules/power.py
@rule("TELECOM-POWER-001", "PDU 功率预算检查")
def check_pdu_budget(ctx):
    for pdu in ctx.query("pdus"):
        devices = ctx.query("devices", pdu_id=pdu.id)
        load = sum(d.resolved.tdp_w for d in devices)
        ratio = load / pdu.resolved.capacity_w
        assert ratio <= 0.8, f"{pdu.id} 负载率 {ratio:.1%}，超过 80% 阈值"
```

你不需要记住检查功率预算。**规则会记住。**

---

## 能力矩阵

| 能力 | 说明 | 状态 |
|------|------|------|
| **Schema 校验** | YAML 字段类型、范围、必填项自动检查，错误精确到行 | ✅ |
| **外键完整性** | 设备引用的机柜、PDU 必须存在 | ✅ |
| **规则引擎** | Python 函数表达任意业务规则，`@rule` 装饰器注册 | ✅ |
| **Instance/Layout 分离** | 设备身份与部署决策独立管理，Git 分支做方案比选 | ✅ |
| **Tag 过滤** | 正交维度标签（专业、安全分区、所属系统），规则按 Tag 过滤 | ✅ |
| **嵌套项目** | 厂区→子区域→方舱，FQID 全限定引用，跨项目引用 | ✅ |
| **报告生成** | human / json / junit / markdown 四种格式 | ✅ |
| **BOM CSV 导出** | `piki generate bom-csv`，设备清单一键导出 | ✅ |
| **机柜面板图** | `piki generate rack-face-panel`，U 位占用可视化 | ✅ |
| **功率预算汇总** | `piki generate power-budget`，PDU/机柜/各相功率明细 | ✅ |
| **线缆清单** | `piki generate cable-list`，光纤跳线 + 光模块清单 | ✅ |
| **AABB 碰撞检测** | 同一机柜内设备 3D 空间冲突检测 | ✅ |
| **Piki Studio** | 浏览器端 3D 预览 IDE，打开项目即看布局 | ✅ |
| **Git 集成** | `piki init` 自动安装 pre-commit hook，CI/CD 原生支持 | ✅ |
| **LSP 诊断格式** | 输出兼容 Language Server Protocol，IDE 可直接消费 | ✅ |

---

## 快速开始

```bash
pip install piki                # Python 3.11+
piki init --plugin telecom      # 初始化项目
piki check                      # 运行检查
piki report --format markdown   # 生成报告
piki generate bom-csv           # 导出 BOM 清单
```

完整教程见 [samples/](samples/) 目录，每个示例项目可直接运行

---

## 按角色导航

### 🧐 我在评估 piki

理解 piki 解决什么问题、和现有工具的对比：

- **[为什么需要 piki](docs/concepts/00-why-piki.md)** — 从真实事故出发，理解问题本质
- **[声明式建模 vs 传统工具](docs/concepts/00-why-piki.md#声明式建模的优势)** — 多维度对比
- **[路线图](ROADMAP.md)** — 当前进展和未来计划

### 🔧 我要开始用

从零开始建立第一个声明式建模项目：

- **[核心概念与快速上手](docs/concepts/01-core-concepts.md)** — 最小工作示例
- **[编写检查规则](docs/concepts/02-writing-rules.md)** — @rule 装饰器 + QuerySet API
- **[高级用法](docs/concepts/03-advanced.md)** — CI/CD、Generator、嵌套项目
- **[Text-Native & Agent-Oriented](docs/concepts/04-text-native-and-agent-oriented.md)** — piki 的人机协同设计哲学
- **[piki 的生态位](docs/concepts/05-ecosystem-positioning.md)** — 敌、友与中间力量
- **[示例项目](samples/)** — 6 个可直接运行的示例：从入门到嵌套项目

### 🧩 我要扩展 piki

开发行业插件、编写自定义规则和生成器：

- **[核心概念 § Plugin](docs/concepts/01-core-concepts.md)** — 插件架构
- **[编写检查规则](docs/concepts/02-writing-rules.md)** — `@rule` / `@generator` 装饰器 + QuerySet API
- **[ADR-002: 插件架构](docs/adr/002-plugin-architecture.md)** — 为什么用插件而非硬编码
- **[telecom 插件源码](src/piki/extensions/telecom/plugin.py)** — 完整参考实现
- **[datacenter 插件源码](src/piki/extensions/datacenter/plugin.py)** — 多 Family 类型参考实现

---

## Text-Native Declarative System Modeling：文本为什么优于图纸

| 能力 | piki（声明式 YAML） | 图形 CAD / BIM |
|------|-------------------|---------------|
| **设计意图** | 声明"要什么"，系统推导"怎么做" | 手动操作每个点、线、面 |
| **版本控制** | `git diff` 精确到字段 | 二进制文件，diff 无意义 |
| **代码评审** | 像审代码一样审设计 | 截图标注，效率低 |
| **自动化检查** | Python 规则直接读取 | 需解析专有格式 |
| **批量修改** | `sed` / Python 脚本 | 手动逐个点选 |
| **CI/CD 集成** | 原生支持 | 需额外导出步骤 |
| **多人协作** | Git 分支合并 | 文件锁定或冲突 |
| **AI 参与** | YAML 是 LLM 原生格式 | 需 OCR / 视觉模型猜测 |

预览是**只读**的。修改设计？改 YAML，重新生成。文本是设计的**唯一真相源**（Single Source of Truth）。

---

## 参考文档

- **[CLI 命令参考](docs/reference/cli.md)** — 所有命令、参数、示例
- **[API 参考](docs/reference/api.md)** — 核心类与装饰器接口
- **[项目配置参考](docs/reference/configuration.md)** — `piki.toml` 完整字段说明
- **[项目目录结构](docs/reference/project-layout.md)** — 初始化后的目录与文件说明
- **[ADR 存档](docs/adr/)** — 所有关键架构决策记录

---

## 贡献

欢迎贡献！请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发环境搭建、代码规范和 PR 流程。

## 许可证

MIT
