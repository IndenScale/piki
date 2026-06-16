# 工程领域 AI Benchmark 形态与缺口调研

> 状态：**调研草稿**
> 日期：2026-06-13
> 用途：为 [SD-HWE-Bench](../initiatives/001-sd-hwe-bench.md) 和「工程 benchmark 必须可执行」的论述提供论据与事实基础

---

## 摘要

本调研覆盖 AEC、Telecom、EDA/芯片、机械设计四个实体工程领域，以及 EngDesign、Frontier-Eng 等跨领域通用 benchmark，重点回答两个问题：

1. 当前各领域的工程 AI benchmark 主要测什么、怎么验证？
2. 是否存在与 **SD-HWE-Bench**（Software-Defined Hardware Engineering Benchmark）范式接近的工作——即从需求生成**声明式工程设计文本**，并通过**可自动执行的分层规则引擎**进行验证？

核心结论是：**没有任何现有 benchmark 同时满足“跨领域统一声明式文本 + 分层规则校验 + 设计意图层与物理实现层分离”这三个条件**。最接近的是 EDA 领域的代码/网表生成+仿真验证、以及 AMS-IO-Bench 的“设计意图结构化 → 规则校验（DRC/LVS）”流程；AEC-Bench 等文档协调类 benchmark 虽然真实，但本质上仍在测“工程阅读”而非“工程设计”。

---

## 1. 调研范围与方法

### 1.1 覆盖领域

| 领域 | 代表性任务 | 关注的 benchmark 类型 |
|---|---|---|
| AEC（建筑/工程/施工） | 图纸审阅、交叉引用、提交文件比对、BIM 生成 | 文档理解、多模态协调、生成式 BIM |
| Telecom（电信网络） | 拓扑规划、配置生成、故障诊断、容量规划 | 知识问答、根因分析、网络数字孪生 |
| EDA / 芯片设计 | RTL 生成、模拟电路设计、物理验证 | 代码生成、网表生成、DRC/LVS 校验 |
| 机械设计 | 拓扑优化、参数化 CAD、多目标设计 | 生成式设计、物理仿真 |
| 跨领域通用 | 控制器、结构、电路、机器人等综合设计 | 多领域工程设计 benchmark |

### 1.2 评估维度

对每个 benchmark，我们从五个维度记录：

1. **输入**：自然语言、图纸、规范、代码、知识图等。
2. **输出**：答案/报告、代码、网表、参数、结构化文本、3D 模型等。
3. **验证方式**：人工评分、关键词匹配、LLM-as-judge、仿真、规则检查、DRC/LVS 等。
4. **可执行性**：输出是否能被机器直接解析、执行或制造。
5. **与 SD-HWE 的距离**：是否接近“声明式设计 + 规则校验”范式。

---

## 2. AEC 领域：从图纸理解到 BIM 生成

### 2.1 AECV-Bench：图纸视觉理解

- **来源**：arXiv:2601.04819，2026-01
- **任务**：对象计数（门、窗、卧室、厕所）、OCR-based QA、空间推理、文档 QA
- **输入**：真实建筑平面图
- **输出**：计数、答案、空间判断
- **验证**：精确匹配（exact match）、MAPE、LLM-as-judge
- **与 SD-HWE 距离**：**远**。这是典型的文档/视觉 QA benchmark，测的是“AI 能不能读懂图纸”，不涉及设计生成。

### 2.2 AEC-Bench（Nomic / Aurecon）：文档协调 Agent

- **来源**：arXiv:2603.29199v1，2026-03
- **任务**：图纸内审查（intra-sheet）、跨图纸推理（cross-sheet）、项目级文档对齐（project-level coordination），包括 detail-title-accuracy、cross-reference-resolution、submittal-review 等 9 类任务
- **输入**：真实施工图纸集、规范、提交文件
- **输出**：判断、报告、修正建议
- **验证**：关键词匹配、结构化输出检查、专家评分
- **与 SD-HWE 距离**：**较远**。它比 AECV-Bench 更进一步，评估 Agent 在真实工作流中的多文档协调能力，但输出仍是“对现有文档的判断和回答”，不是“可交付的设计声明”。

### 2.3 MCP4IFC：LLM 驱动 BIM 生成

- **来源**：arXiv:2511.05533v1，2025-10
- **任务**：通过 MCP 工具调用，让 LLM 查询、创建、编辑 IFC 模型
- **输入**：自然语言（如“添加 5 米长的墙”）
- **输出**：IFC 模型或操作 IFC 的 Python 代码
- **验证**：人工检查 IFC 语义完整性
- **与 SD-HWE 距离**：**中等**。它涉及生成结构化建筑模型，但缺乏统一的规则校验层，验证依赖人工，且输出格式是 IFC 而非跨领域声明式文本。

### 2.4 小结

AEC 领域的 benchmark 主要围绕**图纸和文档**展开。它们反映了一个行业现实：AEC 的真相源仍然是图纸、规范和 PDF。AEC-Bench 测量的是 AI 对这一旧范式的适应能力，而不是 AI 生成新设计的能力。

---

## 3. Telecom 领域：运维与诊断为主，设计生成 benchmark 稀缺

### 3.1 TeleQnA / TaleQnAD：领域知识问答

- **来源**：3GPP/电信标准问答数据集
- **任务**：多选题问答，覆盖电信领域知识
- **输入**：选择题
- **输出**：答案
- **验证**：Accuracy
- **与 SD-HWE 距离**：**很远**。纯知识问答，无生成、无验证。

### 3.2 NeMoEval：网络生命周期管理

- **来源**：多篇 GenAI for Network Monitoring and Management 综述引用
- **任务**：流量分析、容量规划、拓扑设计、部署规划、诊断
- **输入**：网络拓扑图 + 文本
- **输出**：分析结果或规划建议
- **验证**：未形成统一 benchmark
- **与 SD-HWE 距离**：**较远**。覆盖设计相关任务，但缺乏标准化输出格式和自动验证机制。

### 3.3 TN-RCA530：故障根因分析

- **来源**：arXiv:2507.18190v1，2025-07
- **任务**：基于知识图和告警数据定位根因节点
- **输入**：网络拓扑知识图 + 告警
- **输出**：根因节点
- **验证**：ground truth 对比
- **与 SD-HWE 距离**：**较远**。这是诊断推理 benchmark，不是设计生成 benchmark。

### 3.4 GenAI for NETCONF/YANG 配置生成

- **来源**：GEANT 白皮书《The Rise of Generative AI in Network Management》（2025）、IETF AINetOps draft
- **任务**：将高层策略翻译为 NETCONF/YANG 配置、BGP/OSPF 路由配置
- **输入**：自然语言策略或网络拓扑
- **输出**：NETCONF XML/YANG 数据、CLI 配置
- **验证**：数字孪生（GNS3）、实际设备、YANG schema 校验
- **与 SD-HWE 距离**：**中等**。输出是可执行配置，验证也开始引入结构化检查，但任务集中在网络运维配置，不是跨领域的工程设计声明。

### 3.5 小结

**Telecom 是设计生成类 benchmark 最稀缺的领域之一**。现有工作绝大多数集中在知识问答、故障诊断、配置生成和 NetOps，几乎没有针对“从需求生成电信网络拓扑、设备选型、连接关系并自动校验”的标准 benchmark。这与 Telecom 行业的数据高度分散、设备厂商接口不统一、网络设计高度依赖经验有关。

---

## 4. EDA / 芯片设计领域：最接近 SWE-Bench 的工程分支

### 4.1 VerilogEval / RTLLM / ChipBench：RTL 代码生成 + 仿真验证

- **来源**：
  - VerilogEval（ICCAD 2023）
  - RTLLM（ASP-DAC 2024）
  - OpenLLM-RTL（ICCAD 2024）
  - ChipBench（arXiv:2601.21448v1，2025-10）
- **任务**：根据自然语言描述生成 Verilog/VHDL 模块
- **输入**：自然语言规格
- **输出**：Verilog/VHDL 代码
- **验证**：testbench 仿真（iVerilog、Verilator）、功能对比 golden reference
- **与 SD-HWE 距离**：**较近**。这是工程领域最接近 SWE-Bench 的范式：生成可执行代码 + 自动测试验证。局限在于只覆盖数字电路单一领域，且验证以仿真为主，缺少 L0-L5a 的快速规则校验与 L6 签核评估。

### 4.2 AMSbench / AnalogCoder / SPICED：模拟电路设计

- **来源**：
  - AMSbench（arXiv:2505.24138v2，2025-05）
  - AnalogCoder / SPICED 等
- **任务**：
  - AMSbench：电路 schematic 识别、功能分析、电路设计、testbench 生成
  - AnalogCoder/SPICED：模拟电路 sizing 与优化
- **输入**：文本描述、schematic 图像、网表模板
- **输出**：SPICE netlist、Spectre testbench、器件参数
- **验证**：SPICE 仿真、Netlist Edit Distance（NED）、pass@k
- **与 SD-HWE 距离**：**较近**。输出是可直接仿真的网表，但仍是领域专用格式，且验证依赖 SPICE 仿真。

### 4.3 AMS-IO-Bench：结构化设计意图 → DRC/LVS

- **来源**：AAAI 2026，arXiv/AAAI v40i2
- **任务**：wirebond-packaged AMS I/O ring 自动化设计
- **输入**：自然语言设计意图
- **输出**：JSON / Python 中间格式 → 工业级 I/O ring 交付物
- **验证**：DRC + LVS，最终用于 28nm CMOS 流片
- **与 SD-HWE 距离**：**很近**。这是目前发现的最接近 SD-HWE 范式的现有工作：
  - 将模糊设计意图结构化为可验证的中间格式；
  - 通过工业规则（DRC/LVS）自动校验；
  - 输出直接用于制造（tape-out）。
  - 局限：领域限定在 AMS I/O ring，未跨领域，也未使用统一的声明式语言。

### 4.4 小结

EDA/芯片设计是工程 AI benchmark 最先进的分支，已经形成了以“生成代码/网表 + 仿真验证”为核心的成熟范式。但现有工作大多：

- 聚焦单一组件级别（模块、OTA、I/O ring）；
- 验证依赖仿真，缺少快速、低成本的分层规则引擎；
- 输出格式领域专用（Verilog、SPICE、GDS），跨领域通用性差。

---

## 5. 机械设计领域：从拓扑优化到多目标生成

### 5.1 BikeBench：多目标约束下的自行车设计

- **来源**：arXiv:2508.00830，2025-05
- **任务**：生成满足空气动力学、人体工学、结构力学、可用性等目标的自行车设计
- **输入**：文本或图像提示
- **输出**：参数化模型、CAD/XML、SVG、PNG
- **验证**：多物理仿真 + 人工评分 + 数据集相似度
- **与 SD-HWE 距离**：**中等**。强调约束满足和多目标权衡，但输出格式多样，验证不统一。

### 5.2 EngDesign-Mech / Frontier-Eng 机械类任务

- **来源**：EngDesign（NeurIPS 2025 D&B）、Frontier-Eng（arXiv:2604.12290，2026-04）
- **任务**：拓扑优化、机构设计、控制器设计等
- **输入**：自然语言 + 可选图像
- **输出**：参数、代码、控制器
- **验证**：物理仿真（FEM、MuJoCo、PyBullet）
- **与 SD-HWE 距离**：**较近**。强调约束满足和仿真验证，但输出仍非统一声明式文本。

### 5.3 小结

机械设计领域的 benchmark 正在从“几何生成”转向“约束满足 + 性能验证”，但输出格式碎片化（CAD、STL、参数表、代码），缺少像软件工程 test suite 那样统一、可复现的验证层。

---

## 6. 跨领域通用工程 Benchmark

### 6.1 EngDesign

- **来源**：arXiv:2509.16204v2，NeurIPS 2025 D&B
- **规模**：101 个任务，9 个工程领域
- **输入**：自然语言需求
- **输出**：任务特定的结构化参数或代码（Pydantic schema）
- **验证**：领域专用仿真（MATLAB、Cadence、Webots 等），部分信用评分（0-100）
- **与 SD-HWE 距离**：**较近**。关键贡献是提出“工程设计能力不能只用 QA 测，必须用仿真验证可执行输出”，并支持部分信用。但输出格式按任务定制，不是跨领域统一语言。

### 6.2 Frontier-Eng

- **来源**：arXiv:2604.12290v1，2026-04
- **规模**：47 个任务，5 个工程类别
- **核心范式**：generative optimization——Agent 在固定交互预算内迭代编辑可执行 artifacts，接收 verifier 反馈并改进
- **输入**：上下文 + 初始可行解 + 可执行 evaluator
- **输出**：优化后的代码/参数/策略
- **验证**：工业级仿真器、求解器、参考实现（read-only verifier，防 reward hacking）
- **与 SD-HWE 距离**：**较近**。它强调的是“工程不是一次性答题，而是预算内的迭代优化”，这一点与 SD-HWE 的 RLVR 愿景一致。但它偏重**优化已有设计**，而不是**从零生成完整设计声明**。

### 6.3 EngiAI / EngiBench

- **来源**：arXiv:2605.19743v2，2026-05
- **任务**：多 Agent 协作的工程设计
- **输入**：自然语言需求
- **输出**：设计 + 工具调用序列
- **验证**：设计质量（IoU、约束满足、目标达成）+ 工具使用效率
- **与 SD-HWE 距离**：**中等**。关注 Agent 如何调用工具完成设计，但输出格式和验证方式仍偏领域专用。

---

## 7. 综合对比表

| Benchmark | 领域 | 输入 | 输出 | 验证方式 | 可执行性 | 与 SD-HWE 距离 |
|---|---|---|---|---|---|---|
| AECV-Bench | AEC | 图纸 | 计数/答案 | exact match / LLM judge | 低 | 远 |
| AEC-Bench | AEC | 图纸/规范/提交文件 | 判断/报告 | 关键词/专家评分 | 低 | 较远 |
| MCP4IFC | AEC | 自然语言 | IFC/Python | 人工验证 | 中 | 中等 |
| TeleQnA | Telecom | 选择题 | 答案 | accuracy | 低 | 很远 |
| TN-RCA530 | Telecom | 知识图+告警 | 根因节点 | ground truth | 低 | 较远 |
| NETCONF/YANG 配置生成 | Telecom | 策略/拓扑 | XML/YANG/CLI | 数字孪生/schema | 高 | 中等 |
| VerilogEval / RTLLM | EDA | 自然语言 | Verilog | testbench 仿真 | 高 | 较近 |
| ChipBench | EDA | 自然语言 | Verilog + 调试 | iVerilog/Verilator | 高 | 较近 |
| AMSbench | EDA | 文本/图像 | SPICE netlist/testbench | SPICE 仿真 | 高 | 较近 |
| **AMS-IO-Bench** | EDA | 自然语言 | JSON/Python → I/O ring | **DRC + LVS** | 高 | **很近** |
| BikeBench | 机械 | 文本/图像 | CAD/XML/SVG/PNG | 多物理仿真+人工 | 中 | 中等 |
| EngDesign | 跨领域 | 自然语言 | 参数/code/netlist | 仿真/专家脚本 | 高 | 较近 |
| Frontier-Eng | 跨领域 | 问题+初始解 | 可执行 artifacts | 工业仿真/求解器 | 高 | 较近 |
| EngiAI | 跨领域 | 自然语言 | 设计+工具调用 | IoU/约束/工具使用 | 中 | 中等 |

---

## 8. 关键发现

### 发现 1：工程 AI benchmark 呈现“两极分化”

- **一极：知识/文档/感知类**。代表：AECV-Bench、AEC-Bench、TeleQnA、TN-RCA。测的是“AI 懂不懂工程”。
- **另一极：代码/仿真生成类**。代表：VerilogEval、EngDesign、Frontier-Eng。测的是“AI 能不能生成可执行设计”。

SD-HWE-Bench 明确应站在第二极，但更进一步：**不是生成任意可执行代码，而是生成跨领域统一的声明式工程设计文本，并通过分层规则引擎快速验证**。

### 发现 2：最接近 SD-HWE 范式的现有工作是 AMS-IO-Bench

AMS-IO-Bench 的范式几乎就是 SD-HWE 在芯片 I/O ring 领域的预演：

- 自然语言设计意图 → 结构化中间格式（JSON/Python）；
- 工业规则校验（DRC/LVS）；
- 输出直接用于流片制造。

它证明了 SD-HWE 范式在真实工业流程中的可行性。SD-HWE 要做的是把它从单一领域扩展到更广泛的实体工程系统。

### 发现 3：没有任何现有 benchmark 同时满足 SD-HWE 的四个核心特征

1. **跨多个实体工程领域**（电信、数据中心、机械、环境等）；
2. **输出是统一的声明式文本**（如 piki YAML），而非领域专用代码/netlist/参数；
3. **验证是分层的规则引擎**（L0-L5a 快速规则校验 + L4b/L5b 精确几何/物理验证 + L6 专家/AI 签核评估）；
4. **设计意图与位置/连接/配合分离**（Instance/Layout/Connection/Mating 多层建模）。

### 发现 4：AEC-Bench 是 2026 年最具影响力的“工程 Agent”benchmark，但它的测量对象需要被重新定位

AEC-Bench 的优势是真实、多模态、覆盖实际工作流。但它的输出本质上是**对现有文档内容的回答和判断**，对应 AEC 行业“图纸和规范是真相源”的现状。

SD-HWE 要主张的是：**工程 AI 的终极能力不是读图找错，而是生成能被制造、安装和验证的设计**。AEC-Bench 测量的是旧范式下的辅助能力，SD-HWE 测量的是新范式下的核心能力。

### 发现 5：Telecom 是 SD-HWE 最有机会建立先发优势的领域

 Telecom 领域缺乏成熟的生成式设计 benchmark，而 piki 的 telecom/datacenter 插件已经具备基础规则库。如果能够率先发布面向电信网络/数据中心设计的 SD-HWE 任务集，可以填补该领域的空白。

---

## 9. 对第二篇 Pitch 的启示

基于以上调研，第二篇 pitch 的核心论证可以沿着以下结构展开：

### 9.1 核心命题

> 当前工程领域的 AI benchmark 正在重复软件工程早期的问题：大量 benchmark 测量“AI 懂不懂工程”（问答、文档理解、图纸识别），少数 benchmark 开始测量“AI 能不能生成可执行设计”（代码、netlist、参数）。但工程能力的真正标志是：AI 能不能把模糊需求变成**正确、合规、可交付的设计声明**，并且这个声明能被**自动规则引擎**快速验证。

### 9.2 三段论

1. **AEC-Bench 测的是“工程阅读”**：图纸审阅、交叉引用、提交文件比对——这些工作重要，但本质是辅助性的。它回答的问题是“AI 能不能像初级工程师一样读图找错”。
2. **VerilogEval/ChipBench/AMS-IO-Bench 测的是“工程编码/制图”**：在 EDA 领域已经证明，生成可执行 artifacts + 自动验证是有效的 benchmark 范式。但它局限于单一领域，输出格式不统一。
3. **EngDesign/Frontier-Eng 迈出了关键一步**：约束满足、可执行验证、部分信用、迭代优化。但输出仍是任务特定的参数或代码，缺少跨领域统一的声明式语言和分层规则引擎。

### 9.3 SD-HWE 的独特定位

SD-HWE 不是否定上述工作，而是把它们放在同一个进化谱系中，并指向最高层级：

```text
问答 → 文档理解 → 代码/网表生成 → 仿真验证 → 声明式设计 + 分层规则校验
                ↑ EDA 已走到这里    ↑ EngDesign/Frontier-Eng 接近这里
                                              ↑ SD-HWE 要在这里建立新基准
```

### 9.4 可引用的关键事实

- AECV-Bench 在 symbol-centric counting 上准确率仅 0.40-0.55，说明当前多模态模型仍是“文档助手”而非“图纸读者”。
- AEC-Bench 的 submittal-review 任务最高分仅 62.0，说明跨文档协调仍很困难。
- AMS-IO-Bench 实现 70%+ DRC+LVS 通过率，证明“结构化设计意图 → 规则校验”范式在工业中可行。
- Telecom 领域几乎没有面向设计生成的标准 benchmark，是空白市场。

---

## 10. 未解决问题与下一步

1. **是否需要直接与 AEC-Bench 作者/团队对话？** 了解他们对“设计生成”方向的看法，避免树敌。
2. **是否需要更深入地研究 AMS-IO-Bench 的输出格式？** 它可能是 SD-HWE 最有说服力的“先例”。
3. **是否需要调研更多工业界的内部 benchmark？** 如 Cadence/Synopsys/Autodesk 是否有未公开的评估方式。
4. **是否需要定义 SD-HWE 与 EngDesign/Frontier-Eng 的更精确边界？** 这三者最容易被混淆。

---

## 参考来源

- AECV-Bench: arXiv:2601.04819
- AEC-Bench: arXiv:2603.29199v1
- MCP4IFC: arXiv:2511.05533v1
- TN-RCA530: arXiv:2507.18190v1
- VerilogEval: ICCAD 2023
- RTLLM: ASP-DAC 2024
- ChipBench: arXiv:2601.21448v1
- AMSbench: arXiv:2505.24138v2
- AMS-IO-Bench: AAAI 2026 v40i2
- BikeBench: arXiv:2508.00830
- EngDesign: arXiv:2509.16204v2
- Frontier-Eng: arXiv:2604.12290v1
- EngiAI: arXiv:2605.19743v2
