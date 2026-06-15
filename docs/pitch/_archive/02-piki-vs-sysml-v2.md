# piki 与 SysML v2：不同的心智模型与认识论

> SysML v2 问的是：“如何在一个统一模型中精确描述系统？”  
> piki 问的是：“如何用可版本化的文本声明设计意图，并让机器在加载瞬间就发现问题？”

这不是功能清单的对比，而是**心智模型**和**认识论**的对比。

---

## 一、为什么要写这篇对比

任何向工程师、投资人或学术界介绍 piki 的人，都会被问到同一个问题：

> “这和 SysML v2 有什么区别？”

SysML v2 是系统工程领域最权威、最完整的建模语言。它由 OMG 标准化，有 KerML 作为形式化基础，覆盖结构、行为、需求、分析、验证等方方面面。如果 piki 的回答只是“我们更轻量”或“我们用 YAML”，那不仅低估了 piki，也误解了 SysML v2。

真正的区别更深：

- **SysML v2 的核心单位是“模型元素”**；piki 的核心单位是“文本文件”。
- **SysML v2 追求在单一模型中把握系统全貌**；piki 追求把设计知识逐步沉淀为可版本化的耦合约束。
- **SysML v2 主要服务于人类系统工程师**；piki 从一开始就为 Agent 与人类协同设计。

理解这些差异，才能正确选择工具、设计工作流、并向外部解释 piki 的价值。

---

## 二、SysML v2 是什么

SysML v2 是 OMG 主导的新一代系统建模语言，目标是取代基于 UML Profile 的 SysML v1。它的核心设计包括：

- **KerML 基础**：形式化、模块化的内核建模语言。
- **Definition / Usage 模式**：`part def Vehicle` 定义类型，`part car : Vehicle` 定义具体使用。
- **多重视图**：结构、行为、需求、分析、验证统一在一个模型中。
- **文本 + 图形双语法**：既可用 `.sysml` 文件编辑，也可画 diagram。
- **标准化 API**：支持工具互操作和数字线程。

SysML v2 的心智模型可以概括为：

> **“构建一个充分完整、形式一致、可多视图呈现的系统模型。”**

这个模型是真相源。工程师在其中添加 part、port、connection、requirement、constraint，通过视图、仿真和分析来验证设计。

---

## 三、piki 是什么

piki 是一个面向实体工程的**文本原生领域特定建模语言（DSML）**，以 YAML 为具体语法，以 Git 为版本基座，以规则引擎和生成器为执行框架。

piki 把工程设计拆为三个正交子语言：

- **PDL（Part Definition Language）**：部件定义——“这是什么？”
- **PLL（Part Layout Language）**：部件布局——“放在哪里？”
- **PML（Part Mating Language）**：部件耦合——“必须满足什么约束？”

piki 的心智模型可以概括为：

> **“用可 diff、可 review、可被 Agent 读写的文本声明设计意图，并通过加载时约束和规则检查自动验证。”**

piki 不试图在一个统一模型中描述系统的所有方面。它专注于**设计意图层**：设备是什么、放在哪里、如何耦合、遵循什么规则、生成什么交付物。

---

## 四、心智模型对比

| 维度             | SysML v2                                         | piki                                                 |
| ---------------- | ------------------------------------------------ | ---------------------------------------------------- |
| **真相源形态**   | 模型（model file / repository）                  | 文本文件（YAML）                                     |
| **版本控制对象** | 模型版本                                         | Git 中的文件行级历史                                 |
| **核心操作单元** | Model element：`part`、`port`、`connection`      | File：`Instance`、`Layout`、`Mate`、`Connection`     |
| **空间与身份**   | 混合在 `part` / `occurrence` / `spatial item` 中 | `Instance` 与 `Layout` 文件级分离                    |
| **部件间关系**   | `connection` / `interface` / `bind`              | `Connection`（流动通道）+ `Mating`（耦合约束）双概念 |
| **领域扩展方式** | Profile / library / stereotype                   | Python 插件 + `Mate` type 注册                       |
| **主要使用者**   | 系统工程师 / MBSE 专家                           | Agent + 工程师协同                                   |
| **设计表达重点** | 完整系统模型                                     | 设计意图 + 可交付物                                  |
| **错误发现时机** | 建模时 / 仿真时                                  | 文本编辑时 / `piki check` 时 / 仿真时                |

### 关键差异一：模型 vs 文件

SysML v2 的真相源是一个**模型**。无论用文本语法还是图形语法，最终都是同一个模型。piki 的真相源是**一组文本文件**。

这带来根本不同的工作方式：

- **SysML v2**：打开工具，加载模型，在模型中增删改 element。
- **piki**：用编辑器或 Agent 直接修改 `instances/SRV-01.yaml`、`mates/rack-mount/SRV-01-in-RACK-A01.yaml`、`layouts/layout.yaml`。

文本文件意味着：

- `git diff` 直接显示设计变更；
- PR review 可以逐行讨论设计决策；
- Agent 可以用标准工具读写，无需理解专有模型格式。

### 关键差异二：统一模型 vs 正交维度

SysML v2 倾向于把结构、行为、空间、接口等放进同一个模型。`part` 可以同时有属性、端口、状态、动作和空间范围。

piki 则强制把设计拆成独立文件维度：

- `instances/`：设备身份与规格
- `layouts/layout.yaml`：空间部署
- `mates/`：部件耦合约束
- `instances/connections/`：信号/能量链路
- `instances/contexts/`：归属与可见性策略

这种拆分让**方案比选变得极其简单**：改 `layouts/layout.yaml` 就可以生成一个全新部署方案，而不需要复制整个模型。

### 关键差异三：Connection vs Mating

SysML v2 用 `connection`、`interface`、`bind` 表达部件之间的各种关系。piki 则明确区分两种关系：

- **Connection**：信号/能量/物质的**流动通道**（光纤、电源线、液冷管、无线射频链路）。
- **Mating**：部件之间的**设计耦合与约束**（机械装配、接口配对、质量守恒、时钟同步、热接触）。

这个区分是 piki 的核心创新之一。SysML v2 的 `connection` 既表达“光纤从 A 到 B”，也隐含“两端接口必须兼容”；piki 把前者交给 `Connection`，把后者交给 `Mating` 的 `constrains`。

---

## 五、认识论对比

如果说心智模型是“怎么组织信息”，认识论就是“怎么产生和验证知识”。

|                  | SysML v2                     | piki                                         |
| ---------------- | ---------------------------- | -------------------------------------------- |
| **知识来源**     | 领域专家在模型中一次性形式化 | 从仿真/现场中逐步沉淀                        |
| **知识形态**     | 模型即知识                   | YAML + 规则 + Mate type                      |
| **知识演进**     | 模型版本迭代                 | 设计知识成熟曲线：Simulation → Rule → Mating |
| **验证方式**     | 模型一致性检查、仿真、分析   | 加载时约束 + 规则检查 + 可选深度仿真         |
| **错误修复成本** | 取决于发现阶段               | 越低层检查，成本越低                         |
| **人机关系**     | 人以模型为中心操作           | Agent 写 YAML，人类审阅，Git 追踪            |

### SysML v2 的认识论：模型即真理

SysML v2 假设：一个经验丰富的系统工程师能够构建一个足够完整的系统模型，这个模型就是设计的权威表达。验证就是检查模型内部的一致性，以及通过仿真和分析检查模型是否符合需求。

这种认识论的优势是：

- 模型内部关系严密；
- 适合复杂系统的全局分析；
- 有成熟的 MBSE 方法论支撑。

挑战在于：

- 模型构建成本高，需要专业训练；
- 模型变更难以像代码一样被 diff 和 review；
- Agent 难以直接参与模型编辑。

### piki 的认识论：知识逐步成熟

piki 的认识论更接近软件工程：

> **设计知识不是一次性建立起来的，而是从经验中逐步沉淀、从运行时推向编译期的。**

这就是 [设计知识成熟曲线](../concepts/06-knowledge-maturation.md)：

```
仿真发现  →  规则检查  →  结构声明
Simulation  →   Rule    →    Mating
```

- **第一阶段**：通过 CFD、电磁仿真、热仿真或现场调试，发现某类设计错误。
- **第二阶段**：把这类错误写成 `@rule`，在 `piki check` 时自动检查。
- **第三阶段**：当规则足够稳定，且错误本质上是“两个东西之间必须满足某关系”时，把它提升为 `Mate` type 的默认约束，在引擎加载时就验证。

这种认识论的优势是：

- 门槛低，可以从简单场景开始；
- 知识沉淀为可复用的语言结构；
- Agent 可以直接读写和验证；
- Git 历史本身就是知识演进记录。

---

## 六、一个具体例子：服务器装入机柜

同样表达“SRV-01 装入 RACK-A01 的第 10U”，两种语言的心智差异一目了然。

### SysML v2 风格

```sysml
package RackSystem {
    part def Rack;
    part def Server;

    part rack : Rack {
        part server : Server;
        // 空间位置通过 occurrence / spatial item 表达
        // 约束通过 assert constraint 表达
    }
}
```

所有信息都在同一个模型命名空间中。空间位置、部件身份、装配约束都是 `part` 或其属性的不同方面。

### piki 风格

```yaml
# instances/SRV-01.yaml
id: SRV-01
family: ServerFamily
model: generic-2u-server
```

```yaml
# mates/rack-mount/SRV-01-in-RACK-A01.yaml
type: rack-mount-19inch
parent: RACK-A01
child: SRV-01
at:
  u_start: 10
  u_span: 2
constrains:
  - field: depth_mm
    operator: "<="
    value_ref: depth_mm
```

```yaml
# layouts/layout.yaml
- id: SRV-01
  rack_id: RACK-A01
  u_start: 10
```

三个文件回答三个不同问题：设备是什么、如何耦合、放在哪里。你可以只改 `layouts/layout.yaml` 把 SRV-01 移到第 12U，而 `instances/SRV-01.yaml` 和 `mates/...` 完全不变。

---

## 七、何时用 SysML v2，何时用 piki

两者不是零和关系。

### 更适合 SysML v2 的场景

- 需要完整系统模型的航空航天、汽车、防务项目；
- 强 MBSE 流程，有专职系统建模团队；
- 需要形式化需求追溯、行为建模、多视图呈现；
- 组织已投资 SysML 工具链和培训。

### 更适合 piki 的场景

- 数据中心、电信、暖通、制造等实体工程领域；
- 需要快速方案比选、Git 版本控制、Agent 自动编辑；
- 设计意图需要被规则引擎自动验证并生成交付物；
- 团队希望从简单 YAML 开始，逐步沉淀领域知识。

### 互补关系

一个可能的未来工作流是：

> **SysML v2 负责早期系统架构和需求定义；piki 负责详细设计意图、布局方案、耦合约束和交付物生成。**

SysML v2 回答“系统应该做什么、由哪些子系统组成”；piki 回答“这些子系统具体如何部署、如何配合、如何被自动校验”。

---

## 八、结论

SysML v2 和 piki 都在解决“如何用模型/文本描述复杂工程系统”，但它们的心智模型不同：

- **SysML v2 是“模型为中心”**：在统一模型中精确、完整、多视图地描述系统。
- **piki 是“文本与耦合为中心”**：用可版本化的文件声明设计意图，并把工程不变量沉淀为加载时可验证的耦合约束。

它们的认识论也不同：

- **SysML v2 相信模型可以一次性把握系统**；
- **piki 相信设计知识是逐步成熟的**，并通过 Simulation → Rule → Mating 的曲线不断左移错误发现时机。

如果你需要一个成熟的、全面的、由人类系统工程师主导的建模语言，SysML v2 是更自然的选择。

如果你需要一个**文本原生、Git 友好、Agent 可操作、从设计意图直接生成交付物**的工程设计语言，piki 提供了一条不同的路径。

---

## 参考

- [SysML v2 Specification](https://www.omg.org/spec/SysML/2.0/) — OMG 官方规范
- [ADR-006: Mating Graph](../adr/006-mating-graph.md) — piki 的耦合约束建模
- [设计知识成熟曲线](../concepts/06-knowledge-maturation.md) — Simulation → Rule → Mating 的演进路径
- [软件定义工程（SDE）](00-software-defined-engineering.md) — piki 推动的工业设计范式变革
