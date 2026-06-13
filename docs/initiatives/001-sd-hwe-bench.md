# Initiative-001: SD-HWE-Bench —— 软件定义工程的能力竞技场

- **状态：** 倡议 / 讨论中
- **日期：** 2026-06-13
- **作者：** piki 核心团队与社区
- **相关文档：** [软件定义工程（SDE）](../pitch/00-software-defined-engineering.md)、[ADR-003: 多级质量检查](../adr/003-quality-checks-and-diagnostics.md)、[piki 的生态位](../concepts/05-ecosystem-positioning.md)

---

## 摘要

提议发起 **SD-HWE-Bench**（Software-Defined Hardware Engineering Benchmark），一个面向实体工程领域的开放式端到端能力评测基准。它评估大模型/工程 Agent 在声明式工程建模任务中的表现：从自然语言需求生成结构化的工程设计声明，通过规则校验，并产出可交付的工程制品。

SD-HWE-Bench 不是 piki 主项目的功能，而是由 piki 社区发起并维护的**独立倡议**。piki 提供声明式建模语言、规则引擎和评分基础设施，但 benchmark 本身属于更广泛的 SDE 生态。

---

## 1. 背景与动机

### 1.1 为什么工程领域需要自己的 SWE-Bench

软件工程已经拥有 SWE-Bench 这样的事实标准：真实 GitHub issue、可自动验证的测试套件、清晰的 Pass@1 指标。它让「AI 能否真正改代码」成为可测量、可竞争的问题，直接推动了代码 Agent 的爆发。

但实体工程领域——数据中心、电信基础设施、机电系统、暖通、制造等——缺乏类似的基准。现有的评测要么停留在问答式知识考察，要么局限于单一领域的小规模数据集，无法回答一个更根本的问题：

> **AI 能否像工程师一样，把模糊需求变成正确、合规、可交付的设计声明？**

这正是 SDE 要解决的问题。如果设计意图不能以结构化文本存在、不能被规则自动校验，工程 Agent 就无法获得可验证的奖励信号，RLVR 飞轮就无法建立。

### 1.2 piki 为什么适合发起这个倡议

piki 的架构天然适合作为 SD-HWE-Bench 的基础设施：

| piki 能力 | 对 benchmark 的价值 |
|---|---|
| YAML 声明式建模 | 模型输出可被直接解析、校验、评分 |
| Family/Model/Instance/Interface 四层栈 | 支持从简单填空到复杂综合的分层任务 |
| L0-L6 分层规则引擎 | 评分标准天然映射到规则层级 |
| 插件架构 | 易于扩展到不同工程领域 |
| 生成器管线 | 可评估 BOM、布局、连接、报告等交付物 |
| Git 原生 | 数据集可版本化、可协作贡献 |

但 piki 只是**基础设施提供者之一**。SD-HWE-Bench 应该保持开放，允许其他声明式工程框架、仿真工具和数据集接入。

---

## 2. 愿景与目标

### 2.1 愿景

> 让实体工程领域拥有像 SWE-Bench 之于软件工程一样的事实标准 benchmark，使「工程 Agent 是否真正懂设计」变得可测量、可竞争、可复现。

### 2.2 具体目标

1. **定义任务范式**：从自然语言/需求文档生成声明式工程设计，并通过自动校验。
2. **建立评分体系**：不仅看文本是否生成，更看设计是否满足约束、是否可交付。
3. **促进 RLVR**：为工程 Agent 提供可验证奖励信号，推动模型在物理约束、长程规划、多目标权衡上的能力提升。
4. **连接生态**：让 AI Labs、仿真厂商、设计院、设备供应商有共同的竞技场。
5. **保持开放**：数据集、评分工具、leaderboard 全部开源，避免单一流派垄断。

---

## 3. 范围与边界

### 3.1 测什么

SD-HWE-Bench 测的是**声明式工程设计能力**，核心任务是：

> 给定工程需求，生成一组正确的工程设计声明，使其通过规则校验并产出有效交付物。

具体包括：

- 选择合适的 Family 与 Model；
- 声明 Instance 的属性与覆盖值；
- 定义 Layout、Connection、Mating；
- 处理多上下文（既有设施、保密网络、自然环境等）；
- 生成 BOM、施工报告、3D 场景等制品。

### 3.2 不测什么

为了保持边界清晰，以下能力**明确不在核心范围内**：

| 能力 | 原因 | 可能的扩展 |
|---|---|---|
| 物理仿真正确性 | 超出声明式建模层，依赖专业求解器 | 可作为 `--deep` 级别的附加评分 |
| CAD/BIM 交互操作 | SDE 主张 GUI 不应是唯一入口 | 不鼓励以 VLM 点击 GUI 的方式参赛 |
| 手绘草图识别 | 属于感知层，不是设计推理层 | 可作为输入模态，但评分仍以文本输出为准 |
| 项目管理/成本优化 | 超出设计意图层 | 留给 PLM/ERP 生态 |

### 3.3 与软件工程 benchmark 的关键区别

| 维度 | SWE-Bench | SD-HWE-Bench |
|---|---|---|
| 输入 | GitHub issue 描述 | 工程需求文档/自然语言描述 |
| 输出 | 代码 patch | 声明式工程文本（如 piki YAML） |
| 验证 | 单元测试/集成测试 | 规则引擎 + 结构校验 + 生成物检查 |
| 正确性 | 大多二值（pass/fail） | 支持 partial credit（部分满足约束） |
| 多解性 | 通常有确定解 | 通常存在多个合法设计 |

---

## 4. 命名建议

倡议文档阶段提出两个候选名称，供社区讨论：

| 名称 | 含义 | 优点 | 缺点 |
|---|---|---|---|
| **HWE-Bench** | Hardware Engineering Benchmark | 简洁、直接 | "Hardware" 容易被狭义理解为芯片/电路 |
| **SD-HWE-Bench** | Software-Defined Hardware Engineering Benchmark | 准确传达声明式、文本驱动、Agent 友好的理念 | 稍长 |

**当前倾向：SD-HWE-Bench**。它强调这不是传统硬件设计 benchmark，而是「软件定义」范式下的工程能力评测，与 piki 推动的 SDE 叙事一致。

---

## 5. 与现有 benchmark 的差异化

近期已有大量工程 AI benchmark 涌现。它们在测量对象上可分为多个层级：知识问答（如 TeleQnA）、文档理解（如 AECV-Bench）、文档协调 Agent（如 AEC-Bench）、代码/网表生成（如 VerilogEval、ChipBench）、约束生成与优化（如 EngDesign、Frontier-Eng），以及最接近 SD-HWE 范式的结构化设计意图 + 规则校验（如 AMS-IO-Bench）。更完整的梳理见 [《工程领域 AI Benchmark 形态与缺口调研》](./001-sd-hwe-bench-benchmark-survey.md)。

SD-HWE-Bench 与代表性工作的差异化可概括如下：

| 现有工作 | 侧重点 | SD-HWE-Bench 的差异 |
|---|---|---|
| **AEC-Bench / AECV-Bench** | 图纸审阅、交叉引用、文档协调 | 我们不测「读图找错」，而测「生成可被制造安装的设计声明」 |
| **EngDesign** | 跨领域工程设计 + 仿真验证 | 我们更聚焦「声明式建模 + 规则校验 + 工程交付」的完整工作流 |
| **Frontier-Eng** | 固定预算下的生成式优化 | 我们不只优化已有 artifacts，而从需求生成完整设计声明 |
| **VerilogEval / RTLLM / ChipBench** | 数字电路 RTL 生成 | 我们不局限在芯片，而是覆盖更广泛的实体工程系统 |
| **AMSbench / PICBench** | 模拟/光子集成电路 | 我们不深入晶体管级，而是关注系统级工程意图表达 |
| **AMS-IO-Bench** | AMS I/O ring 结构化设计 + DRC/LVS | 我们受其启发，但追求跨领域统一声明式语言与分层规则引擎 |
| **EngiAI / EngiBench** | 多 Agent 工具调用 + 拓扑优化 | 我们更强调「文本真相源 + 规则驱动」的范式 |

核心定位：

> **SD-HWE-Bench 不是「设计并通过仿真」，而是「用声明式文本正确表达工程意图并通过规则校验」。**

这与 SWE-Bench「修改代码并通过测试」的范式更接近。详细论证见 [SWE-Bench for HWE](../pitch/01-swe-bench-for-hwe.md)。

---

## 6. 与 piki 主项目的关系

这是本倡议最重要的治理问题之一。

### 6.1 关系定位

| 方面 | piki 主项目 | SD-HWE-Bench 倡议 |
|---|---|---|
| 性质 | 开源软件框架 | 社区评测基准与数据集 |
| 代码归属 | `src/piki/` 等 | 独立仓库（若孵化） |
| 决策主体 | piki 核心维护者 | 社区治理委员会 |
| 更新频率 | 随框架版本发布 | 持续收录新任务，定期发布数据集版本 |
| 与 piki 的接口 | 提供规则引擎、CLI、API | 调用 piki 作为默认评分基础设施 |

### 6.2 piki 提供的支持

- 默认使用 piki YAML 作为任务输出格式；
- 默认使用 piki 规则引擎进行 L0-L4 评分；
- 允许从 piki samples/ 项目改造为 benchmark 任务；
- 在官方文档中引用并推广该倡议。

### 6.3 piki 不提供/不承诺的支持

- 不将 benchmark 数据集纳入主仓库；
- 不强制所有 piki 用户必须参与 benchmark；
- 不为某个模型厂商特殊优化评分逻辑。

---

## 7. 实现路径建议

### 7.1 分阶段推进

#### 阶段一：MVP（3-6 个月）

- 基于 piki 现有 samples 构造 50-100 个任务；
- 覆盖 1-2 个领域（如数据中心、电信扩容）；
- 评分以 `piki check` L0-L3 通过率为核心指标；
- 发布 alpha 数据集和 leaderboard 原型。

#### 阶段二：跨领域扩展（6-12 个月）

- 引入机械、暖通、环境等领域任务；
- 增加综合任务（多约束、多方案比选、增量修改）；
- 引入 partial credit 评分；
- 建立社区贡献流程。

#### 阶段三：生产级 benchmark（12-24 个月）

- 私有测试集防止过拟合；
- 引入 L5-L6 可选仿真/专家评估；
- 与学术会议/工业会议合作发布；
- 孵化独立组织或基金会治理。

### 7.2 任务类型示例

```text
任务：为一个 42U 机柜设计计算节点部署方案。

需求：
- 部署 8 台 2U 通用服务器，单台 TDP 250W；
- 部署 2 台 1U 接入交换机，单台 TDP 80W；
- 2 台 1U PDU，每路容量 16A/230V；
- 服务器 eth0 必须接入交换机；
- 总功率不得超过 PDU 容量的 80%。

期望输出：
- instances/ 下的设备声明；
- layout.yaml 中的机柜布局；
- connections/ 下的网络连接；
- 通过 piki check 所有规则。
```

---

## 8. 治理结构（提议）

### 8.1 决策主体

倡议初期由 piki 核心团队发起并维护。当任务数超过 200 或出现多个领域维护者时，迁移到更正式的社区治理：

- **技术委员会**：负责 benchmark 框架、评分标准、数据集质量；
- **领域维护者**：每个工程领域（电信、数据中心、机械等）一名负责人；
- **社区贡献者**：提交任务、规则、评测结果。

### 8.2 贡献流程

1. 提交 Task Proposal（需求 + 期望输出 + 评分规则）；
2. 领域维护者审核技术正确性；
3. 技术委员会审核评分可复现性；
4. 合并到数据集，发布新版本；
5. 更新 leaderboard。

### 8.3 与 piki 核心团队的边界

- piki 核心团队保留对「是否使用 piki 作为默认基础设施」的决策权；
- benchmark 的任务内容、评分细则、命名、治理由 SD-HWE-Bench 社区决定；
- piki 核心团队不单独决定 benchmark 的商业化或标准组织归属。

---

## 9. 风险与挑战

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| 数据集构建成本高 | 进度慢、覆盖窄 | 从 piki samples 改造，鼓励社区贡献 |
| 评分标准主观性强 |  leaderboard 公信力不足 | 以规则引擎为客观基础，引入 partial credit |
| 模型过拟合/记忆 | 分数虚高 | 定期更新任务、保留私有测试集 |
| 仿真工具链依赖 | 部分任务难以自动化 | L5-L6 作为可选扩展，不强求 |
| 生态竞争 | EngDesign 等已起步 | 差异化定位，专注声明式建模 + 规则校验 |
| 社区精力分散 | 影响 piki 主项目开发 | benchmark 独立仓库与治理，不并入核心 |

---

## 10. 决策待讨论项

本倡议需要社区确认以下问题：

1. **是否正式启动 SD-HWE-Bench 倡议？**
2. **名称确定为 SD-HWE-Bench 还是 HWE-Bench？**
3. **是否先在 piki 组织下创建独立仓库？**
4. **初始覆盖哪 1-2 个领域？**
5. **是否接受 piki 作为默认评分基础设施？**
6. **是否立即进入 RFC 阶段，设计 benchmark 框架 API？**

---

## 11. 下一步行动

1. **社区讨论**：在 GitHub Discussions 或相关渠道收集反馈；
2. **RFC 拆分**：若倡议通过，创建 `rfcs/002-sde-hwe-bench-framework.md`，设计数据集格式、评分 API、leaderboard 接口；
3. **治理 ADR**：创建 `adr/011-sde-hwe-bench-governance.md`，记录 piki 与 benchmark 的边界决策；
4. **MVP 启动**：从 piki samples 改造第一批任务，建立可运行的评分流水线。

---

## 相关阅读

- [软件定义工程（SDE）](../pitch/00-software-defined-engineering.md)
- [SWE-Bench for HWE](../pitch/01-swe-bench-for-hwe.md)
- [工程领域 AI Benchmark 形态与缺口调研](./001-sd-hwe-bench-benchmark-survey.md)
- [piki 的生态位](../concepts/05-ecosystem-positioning.md)
- [ADR-003: 多级质量检查与统一诊断](../adr/003-quality-checks-and-diagnostics.md)
- [ADR-001: 项目组织模型](../adr/001-project-organization.md)
