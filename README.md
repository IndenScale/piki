# piki

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **用代码定义世界。**
>
> piki 是 Software-Defined Hardware (SDH) 框架：工程师用声明式 YAML 描述设计意图，用 Python 规则检查设计合理性，在提交前自动发现错误——从语法到功率预算，从 U 位冲突到三维碰撞，全部在秒级内完成。

---

## 一句话

```bash
pip install piki
piki init --plugin telecom
piki check    # 在提交前自动发现设计错误
```

---

## 为什么需要 piki

### 一个真实的问题

你设计了一个机房扩容方案：新增 2 台交换机、1 台防火墙，放在 RACK-A01 的 U18-U20。

你检查了 U 位，没有冲突。你检查了线缆长度，都在合理范围。方案评审通过，施工完成。

上电后，PDU-A 跳闸了。

因为你忘了算功率。PDU-A 上已有 2 台核心交换机，新增设备后总负载超过额定容量的 80%，加上浪涌电流，过载跳闸。这个错误如果在施工前被发现，代价是改几行 YAML；如果在施工后被发现，代价是停机、返工、甚至烧毁设备。

### 问题不在于人不专业

工程设计的约束维度太多：U 位、功率、接口、线缆、散热、重量、兼容性……人脑不适合同时追踪所有维度。Excel 检查表是静态的，CAD/BIM 数据锁在专有格式里，专业软件的规则由厂商定义。

**工程设计缺少一个像软件工程那样的外部约束系统**——编译器检查语法，类型系统检查一致性，测试套件检查行为。Agent 写代码时不需要永远正确，因为 CI 会在秒级内发现错误。工程设计却没有等价物。

### piki 的做法

piki 是 **Headless Engineering** 的工程实现：

- **设计意图以纯文本存在**：YAML 文件是唯一真相源，Agent 和人类都能读写。
- **规则引擎秒级反馈**：把项目经验、国标强条、企业规范写成 Python 规则，`piki check` 在毫秒到秒级内返回结构化诊断。
- **Git / CI/CD 原生**：设计变更可 diff、可 review、可回滚，错误在提交前就被拦截。

> piki 不是另一个 CAD，而是工程设计的**编译器**。

更完整的理念请阅读 [docs/pitch/](docs/pitch/) 下的理念系列，或从 [为什么需要 piki](docs/concepts/00-why-piki.md) 开始。

---

## piki 怎么工作

工程设计 = 什么东西存在 + 它们怎么配合 + 它们放在哪里。

piki 用 **ADL（Assembly Definition Language，装配体定义语言）** 把这三个维度写成声明式文本：

```yaml
# instances/servers/SRV-01.yaml
id: SRV-01
family: ServerFamily
model: generic-server
interfaces:
  - id: eth0
    interface_type: SFP28
```

然后规则引擎自动验证：PDU 功率是否超载、U 位是否冲突、接口是否兼容、三维空间是否碰撞。

ADL 的三层子语言——PDL（部件定义）、PML（部件配合）、PLL（部件布局）——让设计意图、配合关系、空间位置相互独立，可分别版本控制。

> **注意**：ADL 已拆分为独立的 Python 包（见本仓库 `adl/` 目录），可独立安装和使用；piki 作为编排框架，负责插件发现、规则执行和报告输出。ADL 详细规范见 [`adl/docs/`](adl/docs/)，piki 用户视角的介绍见 [ADL：装配体定义语言](docs/pitch/03-adl.md)。

---

## 文本原生：工程设计的新真相源

| 能力           | piki（声明式 YAML）   | 图形 CAD / BIM          |
| -------------- | --------------------- | ----------------------- |
| **版本控制**   | `git diff` 精确到字段 | 二进制文件，diff 无意义 |
| **自动化检查** | Python 规则直接读取   | 需解析专有格式          |
| **批量修改**   | `sed` / grep / 脚本   | 手动逐个点选            |
| **CI/CD 集成** | 原生支持              | 需额外导出步骤          |
| **多人协作**   | Git 分支合并          | 文件锁定或冲突          |
| **AI 参与**    | 文本是 LLM 原生格式   | 需 OCR / 视觉模型猜测   |

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

完整教程和示例：[samples/](samples/) 目录。

---

## 仓库结构

```text
piki/
├── adl/                    # 独立的 ADL（Assembly Definition Language）Python 包
│   ├── src/adl/            #   解析、模型、验证、几何运行时
│   └── docs/               #   ADL 自身的技术规范与架构决策
├── src/piki/               # piki 编排框架（插件、规则、CLI、报告）
├── samples/                # 示例项目
├── docs/                   # piki 用户文档与理念文章
├── tests/                  # piki 框架测试
└── studio/                 # 浏览器端 3D 预览 IDE（可选）
```

---

## 文档

- piki 用户文档导航见 **[docs/index.md](docs/index.md)**。
- ADL 技术规范与架构决策见 **[adl/docs/](adl/docs/)**。

---

## 贡献

欢迎贡献！请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

MIT
