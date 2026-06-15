# AQL：工程设计的查询语言

> SQL 让"查询数据"从程序员的专有技能变成了一种通用语言。工程领域至今没有等价物——我们仍然在用图纸、表格和口头沟通来表达"什么东西存在、放在哪里、怎么连接"。AQL（Assembly Query Language）要成为工程设计的 SQL：一组让人类和 Agent 都能精确表达工程意图的声明式子语言。

---

## 一、工程查询的缺失

软件工程有一条清晰的"从表达到验证"的链条：写代码 → 编译器检查语法 → 类型系统检查一致性 → 测试验证行为 → CI 验证回归。这个链条的每一环都是可被机器自动执行的。

工程设计的等价物是什么？

- "这个东西放在这里" → 写在图纸上，需要人工读取
- "这个接口和那个接口兼容" → 写在规格书里，需要人工比对
- "这个机柜能装下这些设备" → 写在脑子里或 Excel 里，需要人工核算

工程领域缺少的不是计算能力——我们有世界上最强大的 CAD 和 CAE 工具。缺少的是**一种可被机器精确执行的表达语言**，让设计意图不再是"画出来给人看"的东西，而是"写出来让机器检查"的东西。

这就是 AQL 要解决的问题。它不是另一个文件格式，不是另一个建模语言。它是工程设计的查询与约束语言——SQL for Engineering。

---

## 二、三子语言：PDL、PLL、PML

工程设计有三个正交的维度：**存在**（什么东西在那里）、**位置**（它们放在哪里）、**关系**（它们之间怎么耦合）。AQL 用三个子语言分别处理这三个维度：

### PDL：Part Definition Language（部件定义语言）

PDL 回答"什么东西存在"。它定义了工程实体的**身份**和**属性**。

PDL 的核心是一个三层声明体系：

- **类型约束**（代码层）：定义结构规则——"一台服务器必须有哪些字段，字段的取值范围是什么"
- **型号库**（数据层）：提供厂商默认值——"generic-server: tdp_w=300, height_u=2"
- **实例声明**（数据层）：声明实际部署实体——"SRV-01: model=generic-server, tdp_w=250（覆盖默认值）"

```yaml
# 实例声明示例
id: SRV-01
family: TelecomServer
model: generic-server
name: "电信服务器 01"
tdp_w: 250          # 覆盖型号默认值
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

关键设计决策：**身份和位置分离**。Instance 文件只管"是什么"，不管"放哪里"。这意味着一组设备可以有多个部署方案，通过 Git 分支管理，不需要复制 Instance 文件。

### PLL：Part Layout Language（部件布局语言）

PLL 回答"东西放在哪里"。它定义了工程实体的**空间位置**，与 PDL 的身份定义完全解耦。

```yaml
# 布局声明示例
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

这种分离的后果是深远的：改布局不需要碰设备定义；结构工程师和电气工程师可以并行工作；设计方案比选 = Git 分支切换，不需要复制整个项目。

### PML：Part Mating Language（部件配合语言）

PML 回答"东西之间怎么耦合"。这是 AQL 三层中最具独创性的一层——它不仅表达物理配合（螺丝、导轨），还表达广义的设计耦合（流体、热、电磁、时钟同步）。

```yaml
# 配合声明示例：机柜安装约束
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
    value_ref: parent.capacity_per_u_w * child.height_u
```

PML 的关键特征是：**约束在加载时自动验证，而不是延迟到规则遍历**。当一个配合类型声明了 `constrains`，引擎在解析声明的瞬间就检查它——微秒级反馈，不需要遍历所有配合关系再逐一检查。

这引出了一个更深层的概念：设计知识的成熟度曲线。

---

## 三、知识成熟度曲线：Simulation → Rule → Mating

工程设计知识不是一次性生成的。它经历三个演化阶段：

```
Simulation → Rule → Mating（Structural Declaration）
  慢/贵        中等         瞬时/零成本
  隐式知识     显式代码      结构化预防
```

### 第一阶段：Simulation（发现）

一个新约束的最初发现方式往往是昂贵的——有限元仿真、CFD 计算、物理试验、甚至是现场安装失败。反馈延迟：小时到天。

### 第二阶段：Rule（捕获）

当同一个问题反复出现，工程师会把它写成检查规则——一段代码，遍历所有相关实体并执行断言。反馈延迟：毫秒到秒。

```python
# 规则示例：PDU 功率预算检查
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

这就是 **Knowledge Maturation**：知识从"事后发现"进化到"结构上不可能出错"。三个真实案例：

| 领域 | Simulation 阶段 | Rule 阶段 | Mating 阶段 |
|---|---|---|---|
| 管道 | CFD 仿真压降 | 规则检查管径 | `mass-conservation` 配合类型 |
| RF | EM 仿真时钟偏移 | 规则检查信号完整性 | `clock-sync` 配合类型 |
| 机柜 | 现场安装失败 | 规则检查尺寸匹配 | `rack-mount-19inch` 配合类型 |

这不是一次性建模——它是一个**演化过程**。一个领域的成熟度体现在它有多少约束已经进入了 Mating 层。

---

## 四、AQL 与 SysML v2 的根本差异

SysML v2 尝试在一个统一模型中处理所有维度：part、port、connection、occurrence、spatial item 都混在同一个模型里。

AQL 的核心设计哲学是**正交分离**：

| 维度 | SysML v2 | AQL |
|---|---|---|
| 身份 | part/occurrence | PDL（独立文件） |
| 位置 | spatial item（混在模型中） | PLL（独立布局文件） |
| 耦合 | connection/interface/bind | PML（独立配合文件） |
| 引用 | 模型内导航 | `instance_id/interface_id` 文本语法 |

这种分离带来的好处是：

- **独立版本控制**：改布局的 commit 不会触碰设备定义文件，diff 清晰、回滚安全
- **独立并发**：结构工程师和电气工程师不会在同一个文件上冲突
- **Agent 友好**：Agent 可以逐文件操作，不需要解析一个巨大的统一模型
- **渐进成熟**：约束可以独立地从 Rule 层升级到 Mate 层，不需要重构模型结构

---

## 五、AQL 的查询能力

AQL 不仅是一种定义语言，也是一种查询语言。它提供了一套从 SQL 借用的查询范式：

- 过滤：`context.query("devices", rack_id="RACK-A01")` —— 按条件筛选
- 排序：`.order_by("position_u")` —— 按字段排序
- 比较运算符：`tdp_w__gt=500`（大于）、`name__contains="SRV"`（包含）
- 聚合：`.count()`, `.aggregate()`, `.group_by()` —— 统计与分组

这不是重新发明 SQL——这是 SQL 思想在工程设计领域的自然延伸。工程查询的本质是："在满足条件 X 的所有实体中，找出违反约束 Y 的那些。"

---

## 六、AQL 的生态系统角色

AQL 三子语言在整个 SDE 栈中的位置：

```
┌──────────────────────────────────────────┐
│              人类 & Agent                │
│    (自然语言 / Sketch / 直接写声明)       │
└──────────────────┬───────────────────────┘
                   │ 输出 AQL 声明
                   ▼
┌──────────────────────────────────────────┐
│           AQL (PDL + PLL + PML)          │
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

AQL 是"写"的层，规则引擎是"检"的层，生成器是"产"的层，可视化是"看"的层。各司其职，不做混淆。

AQL 理念的参考实现是 [piki](https://github.com/indenscale/piki)——一个开源的 Text-Native 声明式系统建模框架。

---

## 七、结语

SQL 的诞生不是因为数据库需要一种查询语言，而是因为**人类和程序需要一种通用语言来精确表达"我要查询什么"**。同样，AQL 不是因为工程设计需要一个新的文件格式——而是因为人类和 Agent 需要一种通用语言来精确表达：

- 什么东西存在（PDL）
- 它们放在哪里（PLL）
- 它们之间怎么配合（PML）

当这三个问题可以被结构化表达、自动验证、版本化管理时，工程设计就从"画图的艺术"变成了"可编译的知识"。

---

## 继续阅读

- [软件定义工程（SDE）：大模型落地工业的必由之路](01-why-sde.md)
- [Agent Native 工业软件：为 Agent 时代重新设计底层](02-agent-native.md)
- [Engineering RLVR：可验证奖励如何驱动工程 AI](04-engineering-rlvr.md)
