# ADL：装配体定义语言

> 工程领域至今没有自己的 SQL。我们用图纸表达"什么东西存在"，用 Excel 表达"放在哪里"，用口头约定表达"怎么连接"。ADL（Assembly Definition Language）要做的事很简单：让装配体的理想状态可以被文本声明、被引擎验证、被版本控制。

---

## 一、ADL 与 piki 的边界

ADL 现在是一个**独立的 Python 包**（`adl`），拥有自己独立的 `pyproject.toml` 和发布周期。它只关心一件事：

> **把文本声明加载成结构化的内存模型，并给出加载层自洽性诊断。**

piki 则是一个**纯粹的编排框架**，负责：

- 发现并加载插件
- 调用 `adl.project.ProjectLoader` 加载项目
- 调用 `adl.validation.ADLValidator` 获取 L2 诊断
- 执行插件规则与生成器
- 格式化并输出报告

```text
┌─────────────────────────────────────────────┐
│                   piki                        │
│  插件发现 → ADL 加载 → 规则/生成器 → 报告     │
└─────────────────┬───────────────────────────┘
                  │ depends on
                  ▼
┌─────────────────────────────────────────────┐
│                    adl                        │
│  parsing → project → validation → diagnostics │
└─────────────────────────────────────────────┘
```

这种拆分意味着：

- ADL 可以**独立使用**于任何需要声明式工程建模的场景；
- piki 可以**只关注编排语义**，不需要理解 YAML 解析或模型合并细节；
- 未来即使仓库分离，也只需要把 `adl` 目录抽走即可。

### 代码库结构

```text
piki/
├── adl/                        # 独立 PyPI 包
│   ├── pyproject.toml
│   ├── README.md
│   └── src/adl/
│       ├── parsing/            # YAML 解析与源码追踪
│       ├── models/             # Instance / Model / MateSpec / Layout 等
│       ├── project/            # ProjectLoader
│       ├── types/              # TypeRegistry / MateType 可扩展类型
│       ├── validation/         # ADLValidator
│       └── diagnostics.py      # Diagnostic 基础设施
├── src/piki/                   # piki 框架（纯编排器）
│   └── core/
│       ├── plugin.py           # 插件基类（register_types / register_rules / register_generators）
│       ├── project.py          # 项目加载编排
│       ├── engine/             # Checker / Context / Registry
│       └── reporting/          # 报告格式化
└── tests/
```

---

## 二、工程表达的三重缺失

软件工程有一条从"表达"到"验证"的清晰链条：写代码 → 编译器检查语法 → 类型系统检查一致性 → 测试验证行为 → CI 验证回归。每个环节都可以被机器自动执行。

工程设计的等价物是什么？

- **"什么东西存在"** → 写在图纸或模型文件里，需要特定软件打开，diff 不可读。
- **"它们怎么相互配合"** → 写在规格书、邮件、老师傅的经验里，需要人工比对。
- **"它们放在哪里"** → 写在布局图或 BIM 里，改一次位置可能牵动多个文件。

工程领域不缺计算能力。CAD、CAE、EDA 工具强大到可以模拟一颗螺丝的应力分布。缺的是**一种可被机器精确执行的表达语言**——让设计意图不再是"画出来给人看"，而是"写出来让机器检查"。

这就是 ADL 要解决的问题。它不是另一个文件格式，也不是另一个建模语言。它是**装配体的定义语言**：用文本精确声明一组工程实体及其理想状态，让规则引擎在毫秒到秒级内判断现实（或当前设计）是否偏离该状态。

---

## 三、三子语言：PDL / PML / PLL

装配体有三个正交维度：**存在**、**耦合**、**位置**。ADL 用三个子语言分别处理，顺序不可随意调换——它对应设计从概念到物理的自然流程。

### PDL：Part Definition Language（部件定义语言）

PDL 回答"什么东西存在"。它定义工程实体的**身份**、**类型**、**属性**和**接口**。

核心是一个三层声明体系：

- **类型约束**（代码层）：一个 Family 必须有哪些字段，字段值域是什么。
- **型号库**（数据层）：厂商或项目默认值，如 `generic-server: tdp_w=300, height_u=2`。
- **实例声明**（数据层）：实际部署的实体，如 `SRV-01: model=generic-server, tdp_w=250`。

```yaml
# instance.yaml
id: SRV-01
family: TelecomServer
model: generic-server
name: "电信服务器 01"
tdp_w: 250
interfaces:
  - id: eth0
    interface_type: SFP28
    direction: bidirectional
  - id: eth1
    interface_type: SFP28
    direction: bidirectional
  - id: power-a
    interface_type: IEC-C14
  - id: power-b
    interface_type: IEC-C14
```

关键设计决策：**身份与位置分离**。Instance 文件只回答"是什么"，不回答"放哪里"。同一组设备可以有多个部署方案，通过 Git 分支管理，不需要复制 Instance 文件。

### PML：Part Mating Language（部件配合语言）

PML 回答"它们怎么耦合"。它不仅表达物理配合（螺丝、导轨、插接），也表达广义的设计耦合（流体、热、电磁、时钟同步、功率分配）。

```yaml
# mating.yaml
type: rack-mount-19inch
parent: RACK-A01
child: SRV-01
constrains:
  - field: depth_mm
    operator: "<="
    value_ref: parent.usable_depth_mm
  - field: width_mm
    operator: "<="
    value_ref: parent.rail_width_mm
  - field: tdp_w
    operator: "<="
    value_ref: "parent.capacity_per_u_w * child.height_u"
```

PML 的关键特征是：**约束在加载时自动验证，而不是延迟到规则遍历**。一个配合类型声明了 `constrains`，引擎在解析的瞬间就检查它——微秒级反馈，不需要遍历所有关系再逐一判断。

把 PML 放在 PLL 之前，是因为它更靠近设计意图。布局只是配合关系在物理空间的一种实现；而配合关系（如"这台服务器必须接入这个 PDU"）往往先于具体 U 位确定。

### PLL：Part Layout Language（部件布局语言）

PLL 回答"东西放在哪里"。它定义工程实体的**空间位置**，与 PDL 的身份定义、PML 的耦合定义完全解耦。

```yaml
# layout.yaml
entries:
  - instance: SW-01
    rack_id: RACK-A01
    position_u: 42

  - instance: SRV-01
    rack_id: RACK-A01
    position_u: 18
    pdu_id: PDU-A

  - instance: SRV-02
    rack_id: RACK-A01
    position_u: 20
    pdu_id: PDU-A
```

PLL 放在最后一层，是因为它是最易变的维度。结构设计、电气设计、热设计都可能要求调整布局。如果布局与身份或耦合混在同一个文件里，每一次 U 位调整都会触发不必要的 diff 和冲突。

三层的顺序因此是：**先定义存在，再定义关系，最后定义空间**。这也是多数工程设计的实际流程：概念设计 → 逻辑/接口设计 → 物理布局。

---

## 四、知识成熟度曲线：Simulation → Rule → Mating

工程设计知识不是一次性生成的。它经历三个演化阶段：

```
Simulation → Rule → Mating（Structural Declaration）
  慢/贵        中等         瞬时/零成本
  隐式知识     显式代码      结构化预防
```

### 第一阶段：Simulation（发现）

一个新约束的最初发现方式往往是昂贵的——有限元仿真、CFD 计算、物理试验、甚至是现场安装失败。反馈延迟：小时到天。

### 第二阶段：Rule（捕获）

当同一个问题反复出现，工程师会把它写成检查规则：一段代码，遍历相关实体并执行断言。反馈延迟：毫秒到秒。

```python
# rule.py
@rule
def check_pdu_power(context):
    for pdu in context.query("pdus"):
        devices = context.query("devices", pdu_id=pdu.id)
        total_load = sum(d.tdp_w for d in devices)
        capacity = pdu.capacity_w
        assert total_load <= capacity * 0.8, \
            f"PDU {pdu.id}: {total_load}W/{capacity}W (>80%)"
```

### 第三阶段：Mating（预防）

当约束变得足够稳定——"这件事在所有项目里都是对的"——它可以被升级为配合类型。引擎在加载时自动校验，不需要任何遍历。反馈延迟：微秒。

| 领域 | Simulation 阶段 | Rule 阶段          | Mating 阶段                  |
| ---- | --------------- | ------------------ | ---------------------------- |
| 管道 | CFD 仿真压降    | 规则检查管径       | `mass-conservation` 配合类型 |
| RF   | EM 仿真时钟偏移 | 规则检查信号完整性 | `clock-sync` 配合类型        |
| 机柜 | 现场安装失败    | 规则检查尺寸匹配   | `rack-mount-19inch` 配合类型 |

一个领域的成熟度，体现在它有多少约束已经进入了 Mating 层。

---

## 五、ADL 与 SysML v2 的根本差异

SysML v2 尝试在一个统一模型中处理所有维度：part、port、connection、occurrence、spatial item 都混在同一个模型里。

ADL 的核心设计哲学是**正交分离**：

| 维度 | SysML v2                      | ADL                                     |
| ---- | ----------------------------- | --------------------------------------- |
| 身份 | part / occurrence             | PDL（独立文件）                         |
| 耦合 | connection / interface / bind | PML（独立配合文件）                     |
| 位置 | spatial item（混在模型中）    | PLL（独立布局文件）                     |
| 引用 | 模型内导航                    | `instance_id` / `interface_id` 文本语法 |

这种分离带来四个直接好处：

- **独立版本控制**：改布局的 commit 不会触碰设备定义文件，diff 清晰、回滚安全。
- **独立并发**：结构工程师和电气工程师不会在同一个文件上冲突。
- **Agent 友好**：Agent 可以逐文件操作，不需要解析一个巨大的统一模型。
- **渐进成熟**：约束可以独立地从 Rule 层升级到 Mating 层，不需要重构模型结构。

---

## 六、ADL 在 SDH 栈中的位置

ADL 三子语言在整个软件定义硬件栈中的位置：

```
┌──────────────────────────────────────────┐
│              人类 & Agent                │
│    (自然语言 / Sketch / 直接写声明)       │
└──────────────────┬───────────────────────┘
                   │ 输出 ADL 声明
                   ▼
┌──────────────────────────────────────────┐
│           ADL (PDL + PML + PLL)          │
│         文本声明，唯一真相源              │
└──────────────────┬───────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌────────┐  ┌──────────┐  ┌──────────┐
│ 规则引擎 │  │  生成器   │  │ 3D 可视化 │
│ L0-L6   │  │ BOM/图纸  │  │（消费层） │
└────────┘  └──────────┘  └──────────┘
```

ADL 是"写"的层，规则引擎是"检"的层，生成器是"产"的层，可视化是"看"的层。各司其职，不做混淆。

---

## 七、结语

SQL 的诞生不是因为数据库需要一种查询语言，而是因为**人类和程序需要一种通用语言来精确表达"我要查询什么"**。同样，ADL 不是因为工程设计需要一个新的文件格式——而是因为人类和 Agent 需要一种通用语言来精确表达：

- 什么东西存在（PDL）
- 它们怎么配合（PML）
- 它们放在哪里（PLL）

当这三个问题可以被结构化表达、自动验证、版本化管理时，工程设计就从"画图的艺术"变成了"可编译的知识"。
