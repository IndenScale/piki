# 设计知识成熟曲线

工程设计的错误发现得越晚，修复成本越高。仿真很贵，规则遍历较慢，而结构声明可以在加载瞬间就发现问题。

piki 提供了一条把设计知识**从“事后发现”推向“结构性不可能出错”**的演进路径：

```
仿真发现  →  规则检查  →  结构声明
Simulation  →   Rule    →    Mating
```

这条路径就是 **piki 的设计知识成熟曲线（Design Knowledge Maturation Curve）**。

---

## 1. 三个阶段

### 第一阶段：仿真发现（Simulation）

> “我们不知道这个设计会不会出问题，先仿真看看。”

当一个领域的新问题出现时，工程师通常先用仿真、试验或现场运行来发现潜在错误。例如：

- CFD 仿真发现某段管道入口和出口流量不守恒
- 电磁仿真发现发射器和接收器时钟漂移导致误码
- 热仿真发现散热器与芯片接触热阻过高

这个阶段的特征是：

- **成本高**：一次仿真可能需要几秒到几小时
- **反馈慢**：必须等模型建完、网格划分、求解完成
- **覆盖有限**：只能验证已想到的工况
- **知识隐含**：发现的问题存在于仿真报告或工程师头脑中

在 piki 的检查分层（[ADR-003: 多级质量检查体系](../adr/engine-and-plugins/003-quality-checks-and-diagnostics.md)）中，这对应 **L5 物理仿真** 和 **L6 AI 评估**。

---

### 第二阶段：规则检查（Rule）

> “我们知道这个问题，写一条规则在 check 时检查。”

当同一种问题反复出现时，工程师会把它编码为规则：

```python
@rule("FLUID-MASS-001", "管道质量守恒检查")
def check_mass_conservation(ctx):
    for pipe in ctx.query("instances", family="PipeFamily"):
        inlet = pipe.interfaces.find(type="inlet")
        outlet = pipe.interfaces.find(type="outlet")
        assert inlet.flow_rate == outlet.flow_rate, \
            f"{pipe.id} 入口/出口流量不守恒"
```

这个阶段的特征是：

- **成本中等**：`piki check` 运行一次毫秒到秒级
- **反馈更快**：设计阶段就能发现问题
- **知识显式**：规则代码就是设计意图的文档
- **仍有遍历**：通常需要 O(n) 或 O(n×m) 遍历模型

在 piki 的检查分层中，这对应 **L3 跨记录业务规则** 和 **L4 几何检查**。

---

### 第三阶段：结构声明（Mating）

> “我们知道这个问题本质上是 A 和 B 的耦合约束，直接声明在 Mating 里。”

当规则足够稳定、且问题总是关于“某两个东西必须满足某关系”时，它就应该从规则层下沉为语言结构：

```yaml
# mates/fluid/PIPE-01-conservation.yaml
type: mass-conservation
parent: PIPE-01/inlet
child: PIPE-01/outlet
constrains:
  - field: mass_flow_rate_kg_s
    operator: "=="
    value_ref: mass_flow_rate_kg_s
    message: "管道入口质量流量必须等于出口质量流量"
```

这个阶段的特征是：

- **成本极低**：引擎加载时微秒到毫秒级验证
- **反馈即时**：YAML 一保存 IDE 就报红
- **无需遍历**：约束直接绑定在耦合关系上
- **知识结构化**：设计不变量成为语言的一等公民

在 piki 的检查分层中，这对应 **L0 格式合法性**、**L1 Schema 校验** 和 **L2 单记录完整性**。

---

## 2. 映射到 piki 的检查分层

```
L6: AI 评估 ─────────────────────────────┐
L5: 物理仿真 ─────────────────────────────┤  第一阶段：发现未知
                                          │  （成本高，事后）
L4: 几何检查 ─────────────────────────────┤
L3: 跨记录业务规则 ───────────────────────┤  第二阶段：编码已知
                                          │  （成本中等，check 时）
L2: 单记录完整性 ─────────────────────────┤
L1: Schema 校验 ──────────────────────────┤  第三阶段：结构声明
L0: 文件格式合法性 ───────────────────────┘  （成本极低，加载时）
```

**知识越成熟，就越往左下角移动。** 最终的理想状态是：一个领域里几乎所有常见的不变量，都被表达为 Mating type 的默认约束，规则层只处理更高阶的、真正跨多领域的业务判断。

---

## 3. 典型演进案例

### 案例 1：管道质量守恒

**第一阶段 — 仿真发现：**

CFD 仿真发现某些管道设计出现质量不守恒，导致数值发散或物理错误。

**第二阶段 — 规则检查：**

```python
@rule("FLUID-MASS-001", "管道质量守恒检查")
def check_mass_conservation(ctx):
    for pipe in ctx.query("instances", family="PipeFamily"):
        inlet = pipe.interfaces.find(type="inlet")
        outlet = pipe.interfaces.find(type="outlet")
        assert inlet.mass_flow_rate_kg_s == outlet.mass_flow_rate_kg_s, \
            f"{pipe.id} 入口/出口质量流量不守恒"
```

**第三阶段 — 结构声明：**

```yaml
# mates/fluid/PIPE-01-conservation.yaml
type: mass-conservation
parent: PIPE-01/inlet
child: PIPE-01/outlet
constrains:
  - field: mass_flow_rate_kg_s
    operator: "=="
    value_ref: mass_flow_rate_kg_s
```

从此以后，任何管道设计只要声明了 `mass-conservation` Mate，引擎加载时就会自动验证质量守恒，**无需再写规则遍历所有管道**。

---

### 案例 2：收发器时钟同步

**第一阶段 — 仿真发现：**

系统联调时发现无线链路误码率过高，追踪到时钟同步精度不足。

**第二阶段 — 规则检查：**

```python
@rule("RF-CLOCK-001", "收发时钟同步预算检查")
def check_clock_sync(ctx):
    for link in ctx.query("instances", family="WirelessLinkFamily"):
        tx = ctx.query("instances", id=link.tx_ref).first()
        rx = ctx.query("instances", id=link.rx_ref).first()
        assert abs(tx.clock_ppb - rx.clock_ppb) <= link.max_drift_ppb, \
            f"{link.id} 时钟漂移超出预算"
```

**第三阶段 — 结构声明：**

```yaml
# mates/wireless/TX-01-RX-01.yaml
type: clock-sync
parent: TX-01
child: RX-01
constrains:
  - field: clock_ppb
    operator: "<="
    value_ref: max_clock_drift_ppb
```

---

### 案例 3：服务器机柜装配

**第一阶段 — 仿真/现场发现：**

现场安装时发现某服务器深度超过机柜深度，无法安装。

**第二阶段 — 规则检查：**

```python
@rule("RACK-FIT-001", "设备物理尺寸匹配")
def check_device_fit(ctx):
    for srv in ctx.query("instances", family="ServerFamily"):
        rack = ctx.query("instances", id=srv.layout.rack_id).first()
        assert srv.resolved.depth_mm <= rack.resolved.depth_mm, \
            f"{srv.id} 深度超过机柜 {rack.id}"
```

**第三阶段 — 结构声明：**

```yaml
# mates/rack-mount/SRV-01-in-RACK-A01.yaml
type: rack-mount-19inch
parent: RACK-A01
child: SRV-01
constrains:
  - field: depth_mm
    operator: "<="
    value_ref: depth_mm
```

这是 piki 最早一批被结构化的耦合约束，也印证了这条曲线的通用性：从仿真到现场经验，到规则，再到 Mating。

---

## 4. 为什么这条曲线很重要？

### 4.1 它是 piki 的核心方法论

piki 不是一开始就要把所有东西都写成声明。它的使用方式是**演进式**的：

1. **早期**：用仿真和规则探索未知
2. **中期**：把稳定的问题写成规则
3. **后期**：把规则中关于“两个东西之间关系”的不变量提升为 Mating type

### 4.2 它决定了规则层和 Mating 层的分工

- **规则层**不会消失，但它会向上移动：处理更复杂、更跨领域、更需要业务判断的问题
- **Mating 层**吸收底层的、重复的、关系明确的不变量

### 4.3 它是领域知识成熟的标志

当一个插件开始大量注册 Mate type 时，说明这个领域的设计知识已经被很好地形式化了。例如：

- telecom 插件：`rack-mount-19inch`、`power-iec-c14-c13`、`optical-link`
- fluid 插件：`mass-conservation`、`pressure-boundary`
- wireless 插件：`clock-sync`、`freq-pair`

这些 Mate type 就是该领域的**可复用设计契约**。

### 4.4 它是 piki 的长期资产

仿真工具会被替代，CAD 工具会被替代，但一个领域里被形式化的耦合约束会长期沉淀为语言资产。它们以 YAML 形式存在于 Git 中，可以被 diff、被 review、被 Agent 读写。

---

## 5. 与 PDL / PLL / PML 的关系

这条成熟曲线直接解释了为什么 piki 需要 **PML（Part Mating Language）** 作为独立子语言：

| 子语言 | 承载的设计知识 | 例子 |
|---|---|---|
| **PDL** | 部件是什么、有什么属性 | 服务器型号、管道规格、发射器参数 |
| **PLL** | 部件放在哪里、什么位姿 | 机柜 U 位、管道走向、天线安装点 |
| **PML** | 部件之间必须满足什么耦合约束 | 机械装配、质量守恒、时钟同步、热接触 |

PDL 和 PLL 回答的是“单个部件”的问题，PML 回答的是“部件之间关系”的问题。而设计知识成熟曲线的终点，正是把部件间的不变量沉淀到 PML 中。

---

## 6. 实践建议

1. **不要试图一开始就把所有规则都变成 Mating**
   先用仿真和规则探索，等模式稳定、重复出现时再提升。

2. **判断能否提升为 Mating 的标准**
   - 是否总是关于两个（或多个）实体/接口之间的关系？
   - 约束是否可以用 `field operator value_ref` 表达？
   - 是否在不同项目中反复出现？
   如果三个答案都是“是”，就适合做成 Mate type。

3. **保留规则的演进空间**
   即使已经做成了 Mating，也可以在规则层补充更高阶的检查。例如 `mass-conservation` Mate 保证流量相等，规则层再检查总流量是否满足系统需求。

4. **为 Mate type 写文档**
   每个 Mate type 都是领域契约，应该说明它的物理/工程含义、默认约束、典型用法和反例。

---

## 7. 一句话总结

> **仿真是发现未知，规则是捕获已知，Mating 是把已知变成语言结构。PML 就是让工程设计从“事后检查”走向“结构性不可能出错”的那一层。**

---

## 参考

- [ADR-003: 多级质量检查体系](../adr/engine-and-plugins/003-quality-checks-and-diagnostics.md) — L0-L6 检查分层
- [ADR-006: Mating Graph](../adr/data-model/006-mating-graph.md) — 配合图与耦合约束建模
- [核心概念](01-core-concepts.md) — Family / Model / Instance / Layout / Mating 的关系
