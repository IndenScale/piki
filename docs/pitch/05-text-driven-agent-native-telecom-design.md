# 文本驱动，Agent 原生的通信设计工具链

> **本文档定位：现场演讲 / 路演指导稿**
>
> 面向听众：通信工程师、潜在客户、投资人。
> 目标：用 15-20 分钟讲清楚“为什么 piki 是通信设计的下一代工具链”。
> 因此本文会从第一性原理展开，配合口语、案例和听众互动，部分内容与 `pitch/03-adl.md`、`concepts/01-core-concepts.md` 有重叠，这是为了让未读过技术文档的听众也能跟上。

---

> 通信工程师最熟悉两类工具：Excel 和网管。但当 AI Agent 要来帮忙时，这两类工具都成了障碍。
> 本文解释为什么——以及我们怎么做。

---

## 1. 为什么 AI 和 Agent 做不好通信设计？

先看一个真实场景。

你要给机房加 2 台服务器、1 台交换机。打开 Excel，列设备、配端口、标 U 位、算功率、对齐接口、选光模块、匹配线缆、检查强条……整个过程横跨七八个维度。一个维度忘了，上电就跳闸——**PDU 负载超标、U 位冲突、接口不兼容、线缆不够长、光模块波长不匹配**，每一类错误都有人犯过。

为什么 AI 帮不上忙？

**因为我们的工具不是给 AI 设计的。** 当前的通信设计工具链假设使用者是"有眼睛、有手、经过专业训练的人类"。CAD 图纸是给人看的（diff 不可读），Excel BOM 逻辑藏在合并单元格和 VLOOKUP 里（Agent 无法可靠解析），网管系统是 GUI 操作流（Agent 要模拟鼠标键盘，慢且容易错）。

大模型是"盲的"。它在文本层非常强——能读 YAML、能写 Python 函数、能解释 diff——但它无法通过 GUI 操作 Visio、AutoCAD 或 Excel。

而通信设计，基建布局部分，本质上是 **ME（机械工程）+ AEC（建筑工程）+ 信号工程** 的复合体。我们有物理场仿真（散热、电磁兼容）、有设备选型逻辑（接口兼容性矩阵）、有安装工法前提（工具可达性、维护空间余量）。专业软件非常多，每一款都假设你是坐在屏幕前点鼠标的人类。

**问题不是 AI 不够强，是我们的设计工具没有"盲道"。**

---

## 2. 为什么 AI 在 SE 软件工程和 EDA 领域杀疯了？

看看 AI 在软件工程和芯片设计里做了什么，就能看清差距在哪。

**软件工程领域**，AI 能改代码、修 bug、写测试、过 CI——因为软件工程从第一天就建立在文本上。源代码是纯文本，编译器给结构化反馈（语法错误精确到行号），类型系统在编译时拦截一致性错误，测试套件给出二值判定（pass/fail），git 提供版本追踪和 blame，CI/CD 自动化整个验证管线。

**EDA 领域**，AI 能写 Verilog、生成网表、过 DRC（设计规则检查）。芯片设计的每一步都有自动验证：语法检查 → 逻辑综合 → 布局布线 DRC → LVS（网表一致性对比）→ 时序分析。AMS-IO-Bench 已经证明，让 AI 写结构化设计声明、再拿规则引擎自动验证，通过率可以做到 70% 以上。

这些领域做对了三件事：

### 文本优先（Text-First）

设计意图以结构化文本为唯一真相源。不是为了让人读，而是为了让机器可靠操作——grep、diff、lint、编译、自动化测试。软件有源代码，芯片有 Verilog 和网表。工程设计有什么？DWG 文件和 Excel。

### 分层解耦（Layered Decoupling）

基础设施、类型系统、业务逻辑、接口、横切关注点——每一层有独立的数据模型和验证机制。软件有语法 → 类型 → 单元测试 → 集成测试 → E2E 测试。EDA 有器件库 → 网表 → 布局 → DRC。工程设计呢？全混在一张图里。

### 质量左移（Shift-Left Quality）

错误发现得越早，修复成本越低。软件从静态分析（linter）到测试套件，再到 AB 测试和蓝绿发布，每一步都有自动验证。EDA 从 DRC 到多物理场仿真再到硬件在环测试，每一层都左移一级。工程设计呢？等到施工现场上不了架才返工。

**Git Workflow、CI/CD、变更管理、Issue 追踪——这四个词在软件领域是基础设施，在通信设计领域是梦想。**

但梦想是可以实现的。因为通信设计的约束密度天然比代码更高：功率不等式、U 位容量、接口兼容性矩阵、信号拓扑完整性——每一项都是确定性的、秒级可评估的。缺的不是约束，是把约束暴露出来的基础设施。

---

### Agent 自己来行不行？——过程式编排的幻觉

一个很自然的想法是：让 Agent 直接操作现有的工具链。

登录 DCIM，注册设备、注册线缆、创建端口映射、录入 TDP 和运行参数。打开 Excel，出 BOM 表。打开 Visio，画施工图。打开网管系统，下发配置。

**理论上是可行的。** 一个扩容场景——加 2 台服务器、1 台交换机——涉及的步骤是有限的。Agent 按脚本走一遍：登录 → 填表单 → 点确认 → 下一台。如果中间卡住了，重试就好。

**实际上，这只在 Demo 里能跑通。** 原因很简单：项目规模一大，涉及部件一多，过程式编排就会崩溃。

一个 42U 标准机柜的完整扩容设计，可能涉及：

- 20+ 台设备，每台有 2-4 个接口，每个接口需要匹配光模块和线缆类型
- 双路 PDU 供电，需要分配 A/B 路并保证负载均衡
- 既有设备不可动（brownfield），新增设备必须避开已有 U 位
- 光模块波长、速率、距离、接头类型四项精确匹配
- 线缆长度在机柜内部、跨机柜、跨列头柜三种场景下完全不同

**每一步都是依赖推理的，不是靠 API 调用序列能糊过去的。** Agent 必须理解："这台设备的 eth0 是 SFP28，所以我需要 SFP28-SR 光模块，光纤跳线是 LC-LC 单模 2 米，对端接在 SW-01 的 Gi1-0-3 口，而 Gi1-0-3 必须先是空的才能接"。这不是把"填表单"自动化能解决的问题——这是 **工程直觉**，而且是 **Multi-Hop 工程直觉**。

当 Agent 从"填 3 个表单"变成"协调 20 台设备、40 个端口、15 根光纤跳线、10 个光模块、2 条 PDU 负载曲线"时，每多一层依赖，成功率就乘一个衰减系数。过程式编排没有全局结构，每一步的状态都散落在 DCIM 的页面和 Excel 的单元格里。Agent 无法在操作前就验证"这个设计的整体是否自洽"，只能做完一步看一步——而最后一步失败了，前面 19 步可能是白做。

更致命的是**事务性（Transactionality）**的缺失。

软件工程的每一次部署都有事务性保障：要么全部成功，要么全部回滚。数据库有 ACID。Kubernetes 有声明式调谐——你声明期望状态，系统自己算 delta，确保终态一致。

过程式编排完全相反。Agent 在 DCIM 里创建了 15 台设备、注册了 20 根线缆、关联了 8 个端口映射——然后第 9 个端口被占用了。**系统不知道前 8 步和第 9 步是一个原子操作。** 前面的数据已经写进去了，DCIM 里留下了一堆半成品：设备创建了但没配端口，线缆注册了但没关联两端。下一次扩容时这些"僵尸数据"会变成下一轮冲突的源头。

而声明式设计天然是事务的。YAML 文件里的所有 Instance、Mate、Layout、Connection 是一个完整的快照。`piki check` 在加载瞬间就判断这个快照是否自洽。如果自洽，整体生效；如果冲突，引擎告诉你哪里不对——**在写进 DCIM 之前**。变更实施前系统是完整状态，变更实施后系统仍然是完整状态。中间没有不一致的过渡态。

这就是过程式编排和声明式建模的根本差异：前者是用动作序列制造终态（容易断裂），后者是用描述直接表达终态（可验证）。通信设计的复杂度越高，这个差异越致命。

## 3. ADL（装配体定义语言）是什么

**SQL 让人类和程序用同一种语言精确表达"我要查询什么"。ADL 让人类和 Agent 用同一种语言精确表达"什么东西存在、它们怎么配合、它们放在哪里"。**

ADL（Assembly Definition Language，装配体定义语言）有三个子语言，分别处理装配体的三个正交维度：

### PDL：设备表（Part Definition Language）

回答"什么东西存在"——设备的身份、类型、属性和接口。

```yaml
# models/devices/generic-server.yaml
model: generic-server
family: ServerFamily

height_u: 2
tdp_w: 300
depth_mm: 715
width_mm: 445
weight_kg: 18.5

# instances/devices/SRV-01.yaml
id: SRV-01
name: 服务器-01
model: generic-server
status: installed
interfaces:
  - id: eth0
    interface_type: SFP28
    direction: bidirectional
  - id: power-a
    interface_type: IEC-C14
    direction: input
```

**PDL 有三层：**

- **Family**（类型约束）——"服务器必须有哪些字段，值域是什么？"这个写在代码里。
- **Model**（型号默认值）——"通用服务器：tdp_w=300, height_u=2"。
- **Instance**（实例声明）——"SRV-01：model=generic-server，实际 tdp_w=250（覆盖型号默认值）"。

### PML：线缆表（Part Mating Language）

回答"两个实体怎样耦合"——机械配合、接口配对、守恒约束、同步关系。

```yaml
# mates/rack-mount/RACK-A01-SRV-01.yaml
type: rack-mount-19inch
parent: RACK-A01
child: SRV-01
constrains:
  - field: depth_mm
    operator: "<="
    value_ref: depth_mm
    message: "设备深度不能超过机柜深度"
```

**PML 的约束在引擎加载时自动验证。** 不需要写遍历代码，不需要遍历所有设备。配合关系声明之时，校验就已经完成。

### PLL：面板图和端口图（Part Layout Language）

回答"放在哪里"——设备部署到哪个机柜、哪个 U 位、接哪个 PDU。

```yaml
# layouts/layout.yaml
- instance: SRV-01
  position_u: 10
  pdu_id: PDU-A
  rack_id: RACK-A01
- instance: SRV-02
  position_u: 14
  pdu_id: PDU-A
  rack_id: RACK-A01
```

**Layout 和设备定义是分离的。** 方案比选 = 切 Git 分支，只改 layout.yaml，不碰设备定义。这就解决了"Excel 里复制粘贴多方案"的噩梦。

### ADL 的核心设计：正交分离

| 维度                 | ADL 子语言 | 位置                   | 独立版本控制 |
| -------------------- | ---------- | ---------------------- | ------------ |
| 身份（什么东西存在） | PDL        | `instances/` `models/` | ✅           |
| 耦合（怎么配合）     | PML        | `mates/`               | ✅           |
| 位置（放在哪里）     | PLL        | `layouts/`             | ✅           |

**三个文件独立 commit，独立 diff，独立回滚。** 结构工程师改位置不会触碰电气工程师的设备定义。Agent 可以逐文件操作，不需要解析一个巨大的统一模型。

---

## 4. 用 ADL 描述一个站点设计

一个真实的电信扩容场景：机房 RACK-A01 里已有 2 台服务器（SRV-01, SRV-02）和 1 台接入交换机（SW-01），双路 PDU 供电。现在要新增 2 台服务器、部署端口分配、验证功率和空间。

### 第一层：设备表（PDL）

先给新设备建模。型号库已经定义好（`models/devices/generic-server.yaml`），直接引用即可：

```yaml
# instances/devices/SRV-03.yaml
id: SRV-03
name: 服务器-03
model: generic-server
tdp_w: 250 # 实际功耗覆盖型号默认值 300W
interfaces:
  - id: eth0
    interface_type: SFP28
    direction: bidirectional
  - id: power-a
    interface_type: IEC-C14
    direction: input
```

**TDP 覆盖是关键**：厂商标称 300W，实际典型工况 250W。ADL 允许 Instance 层覆写型号默认值，但物理尺寸不能乱改（标记为 `piki_non_overridable`）。

### 第二层：线缆表 + 配合图（PML）

声明光模块、光纤跳线和机械装配：

```yaml
# mates/rack-mount/RACK-A01-SRV-03.yaml
type: rack-mount-19inch
parent: RACK-A01
child: SRV-03
constrains:
  - field: depth_mm
    operator: "<="
    value_ref: depth_mm
  - field: weight_kg
    operator: "<="
    value_ref: max_load_kg

# instances/transceivers/SFP28-SR-SRV03-ETH0.yaml
id: SFP28-SR-SRV03-ETH0
family: TransceiverFamily
model: sfp28-sr
mate_to: SRV-03/eth0

# instances/port_connections/CONN-SRV03-SW01.yaml
id: CONN-SRV03-SW01
family: PortConnectionFamily
from_port: SRV-03/eth0
to_port: SW-01/Gi1-0-3
cable_type: LC_LC_SMF_2M
```

**引擎会自动校验：** 机柜深度够不够、光模块接口兼容吗、收发两端波长一致吗、光纤弯曲半径满足吗。

### 第三层：面板图和端口图（PLL）

```yaml
# layouts/layout.yaml
- instance: SRV-03
  position_u: 18
  pdu_id: PDU-A
  rack_id: RACK-A01
```

保存后运行 `piki generate rack-face-panel-svg`，机柜面板图自动生成。SRV-03 上架后占 U18-U19，引擎立即检查是否与现有 SRV-02（U14-U15）冲突、PDU-A 功率总和是否超标。

### 一次完整的设计循环

```bash
# 1. 写设备定义、配合声明、布局部署
edit instances/devices/SRV-03.yaml
edit mates/rack-mount/RACK-A01-SRV-03.yaml
edit layouts/layout.yaml

# 2. 运行规则校验
$ piki check
instances/devices/SRV-03.yaml:8:3 error [TELECOM-RACK-001]
  SRV-03 U18-U19 与 SW-01 U20 无冲突，通过

layouts/layout.yaml:7:1 error [TELECOM-POWER-001]
  PDU-A 负载 1120W/2000W = 56% → 未超标，通过

# 3. 生成交付物
$ piki generate bom-csv          # BOM 清单（设备 ID / 型号 / 机柜 / U 位 / PDU / 功耗）
$ piki generate cable-list       # 线缆清单（光纤跳线 + 光模块 + 长度 + 端口对端）
$ piki generate rack-face-panel-svg  # 机柜 U 位面板图 SVG
$ piki generate power-budget     # 功率预算汇总（每台设备 TDP / 每 PDU 总负载 / 负载率）
```

**从设计到交付，不画图、不手动算功率、不对 Excel 查表。** YAML 是唯一真相源，一切交付物都从它派生。

---

## 5. 这有什么好处？

### 自动导出 BOM

`piki generate bom-csv` 自动遍历所有设备 Instance，解析型号默认值 + 实例覆盖值，生成 CSV：设备 ID / 型号 / 机柜 / U 位 / PDU / TDP / 高度。采购直接拿去下单。

### 自动生成作业指导书

面板图（SVG）+ 端口图（CSV）+ 线缆表（CSV） + 功率预算汇总，四份交付物一键生成。施工队看图就能上架、接线、上电。不再需要工程师手画 Visio 面板图和 Excel 端口映射表。

### 结合定额库自动算造价

型号库（`models/`）里可以标注物料编码和单价。生成器读取所有 Instance，汇总设备数量 × 单价、光模块数量 × 单价、线缆长度 × 单价 → **自动造价清单**。结合各地定额库（以 Catalog 引用层接入），工时定额也一并产出。

### 自动检查设计规范

14 条规则已经就绪：

| 规则                     | 检查内容                               |
| ------------------------ | -------------------------------------- |
| TELECOM-POWER-001        | PDU 功率预算（负载超 80% 报警）        |
| TELECOM-POWER-002        | PDU 相线平衡（多相不均衡告警）         |
| TELECOM-RACK-001         | U 位冲突（同机柜设备重叠检测）         |
| TELECOM-RACK-002         | 机柜容量（设备总 U 位不超阈值）        |
| TELECOM-RACK-003         | 物理尺寸匹配（设备深度/宽度 vs 机柜）  |
| TELECOM-COLLISION-001    | 3D AABB 碰撞检测                       |
| TELECOM-PORT-001         | 端口占用冲突                           |
| TELECOM-CONN-001/002/003 | 连接端点存在性/类型兼容性/线缆类型匹配 |
| INTERFACE-COMPAT-001     | 接口兼容性矩阵（SFP28 ↔ SFP+/SFP28）   |

每一条都是"你必须记住但经常忘记"的强条。规则是 Python 函数，每次 `piki check` 都在毫秒到秒级跑完。错误精确到行号——**像编译器的报错一样精确**。

### 更进一步：知识从"事后检查"变成"结构性不可能出错"

这是 ADL 最底层的设计哲学。工程师的 know-how 有三重归宿：

1. **仿真发现** → "我们不知道会出问题，先仿真看看"（反馈慢，小时级）
2. **规则检查** → "我们知道这个问题，写条规则在 check 时遍历"（反馈快，秒级）
3. **结构声明** → "这个问题本质上是 A 和 B 的耦合，直接声明在 Mating 里"（加载时自动校验，微秒级）

当一个约束从规则变成 Mating（如 `rack-mount-19inch` 的深度匹配），它就不再需要主动检查——引擎在加载 YAML 时自动完成。**知识从"人工检查项"变成了"语言结构的默认约束"。**

这就是 piki 的设计知识成熟曲线：仿真 → 规则 → 结构声明。一个领域的成熟度，体现在它有多少约束已经进入了 Mating 层。

---

## 6. 怎么上手

### 你不用学，让 Agent 学

piki 是 **文本原生且 Agent 友好** 的。文本 YAML 是唯一真相源，Agent 可以直接读写；CLI 是第一接口，`piki check` / `piki generate` 全部通过命令行完成，输出结构化诊断（LSP 兼容格式，支持 VS Code / Vim 集成）；GUI（Piki Studio 3D 预览）只是给人看的消费层，Agent 不碰。

日常工作流：

- **你**说自然语言："给 RACK-A01 加 2 台服务器，双路 PDU 供电，冗余 25G 上行"
- **Agent**：
  1. 读型号库，选匹配的服务器型号
  2. 生成 Instance YAML + Mate YAML + Layout 条目
  3. 跑 `piki check`，修正违规
  4. 跑 `piki generate`，出 BOM + 面板图 + 端口图
  5. 给你看 diff，你点 approve

**增量用户**（刚入行的通信工程师）：不需要学 AutoCAD，不需要学 Visio，不需要背强条。对着 Agent 说需求就行。

**存量专家**（资深站点设计工程师）：把你知道的强条写成 Python 规则函数（10 行），把常用设备录入型号库（5 行 YAML），把团队经验变成可执行的约束而不是锁在柜子里的报告。

### 三步走

```bash
# 1. 安装
pip install piki

# 2. 创建项目
piki init my-project --plugin telecom

# 3. 跑检查
piki check
```

项目骨架自动生成：`models/`（型号库）、`instances/`（设备定义）、`mates/`（配合关系）、`layouts/`（部署布局）、`rules/`（自定义规则）、`piki.toml`（项目配置）。

参考示例项目 `samples/01-telecom-expansion`，里面有完整的扩容场景——型号库、设备定义、端口连接、光模块、光纤跳线、配合图、布局、规则，跑一遍就懂了。

---

## 7. 呼吁贡献

piki 是一个开源项目（Apache 2.0），当前版本 0.1.0 Alpha。telecom 插件已经可用（14 条规则 + 5 个生成器），但型号库、规则库、价格库——这些**领域数据**比框架代码更重要。

### 能不能把你们遇到的设备、光模块、线缆、接头贡献到型号库里？

每一条贡献都是在线表格的降维打击——让所有通信工程师都能复用你的型号数据：

```yaml
# models/devices/hw-ce6800.yaml
model: hw-ce6800
family: ServerFamily
height_u: 1
tdp_w: 180
depth_mm: 600
width_mm: 442
weight_kg: 8.5
interfaces:
  - id: port-1
    interface_type: SFP28
    count: 48
  - id: port-49
    interface_type: QSFP28
    count: 6
```

同样的格式贡献光模块型号（`sfp28-lr`、`qsfp28-sr4`、`sfp-plus-lr`）、线缆型号（`lc-lc-smf-2m`、`lc-lc-smf-10m`）、接头类型（`lc-upc`、`sc-apc`）。

### 能不能基于型号库，建立我们的采购报价库？

型号 YAML 里加一个 `unit_price_cny` 字段，BOM 生成器自动汇总金额。或者在 `catalogs/` 目录按 Catalog 格式维护独立的报价引用层（Catalog 是跨维度引用层，支持从厂商、分销商、企业内部 ERP 三个来源取值，优先级可控）。Agent 出扩容方案时直接附带造价估算——**从需求到报价，一条命令**。

### 能不能把强条写成静态检查或测试套件？

通信设计领域有大量的强条（强制性规范）：

- "核心设备必须双路供电，且来自不同 PDU"
- "光模块收发光功率必须在链路预算范围内"
- "同机柜内设备 TDP 总和不得超过散热容量"
- "设备前后必须预留维护空间（前 ≥800mm，后 ≥600mm）"

每一条都可以是 10 行 Python：

```python
@rule("TELECOM-REDUNDANCY-001", "核心设备必须双路供电")
def check_dual_psu(ctx: Context):
    for srv in ctx.query("instances", family="ServerFamily"):
        if srv.resolved.psu_redundancy is False:
            diagnosis.warning(
                f"{srv.id} 缺少双路供电冗余",
                location=srv.location,
                rule_id="TELECOM-REDUNDANCY-001"
            )
```

写完规则，`piki check` 自动在所有项目里执行。**一次编写，永久受益。** 你的强条不再锁在 PDF 规范文件里——它变成了会说话的约束。

---

## 结语

通信设计正处在和 15 年前软件工程一模一样的拐点。

- 15 年前，程序员用 FTP 传代码、没有 git、没有 CI/CD、没有测试套件。后来有了 GitHub + Jenkins + JUnit，软件工程的量产质量飞跃了。
- 今天，通信工程师用 Excel 出方案、用微信传文件、用大脑记强条。验收靠人工逐项打勾，经验随人退休流失。

piki 要做的是把软件工程花了 20 年建立起来的那套基础设施——**文本真相源、分层解耦、自动验证、Git 工作流、CI/CD、Issue 追踪**——搬到通信设计领域。

但框架只是骨架。真正让这个生态活起来的，是你们的型号库、你们的强条、你们的定额数据、你们的安装经验。

**GitHub 上的每一个 PR，都是在帮下一个通信工程师少加一晚上班。**

---

> piki: `pip install piki` · [github.com/indenscale/piki](https://github.com/indenscale/piki) · Apache 2.0

---

## 继续阅读

- [软件定义硬件（SDH）：实体工程的必由之路](01-why-sdh.md) — 形式化程度光谱与 SDH 世界观
- [SDH 框架的设计原则：文本原生与 Agent 友好](02-agent-native.md) — 五项设计原则
- [ADL：装配体定义语言](03-adl.md) — PDL/PML/PLL 三子语言详解
- [Engineering RLVR：可验证奖励如何驱动工程 AI](04-engineering-rlvr.md) — SD-HWE-Bench 评测基线
