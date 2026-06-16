# Initiative-004: 质量左移工具链

- **状态：** 倡议 / 讨论中
- **日期：** 2026-06-15
- **作者：** piki 核心团队
- **相关文档：** [ADR-003: 多级质量检查与统一诊断](../adr/engine-and-plugins/003-quality-checks-and-diagnostics.md)、[ADL：装配体定义语言](../pitch/03-adl.md)、[Initiative-003: GitHub 即工程设计](./003-github-as-engineering-design.md)

---

## 摘要

提议建立面向 ADL 工程设计的 **质量左移工具链（Shift-Left Quality Toolchain）**。核心目标是把设计缺陷的发现时机尽可能提前：从编辑保存时的 Linter 提示，到提交前的静态分析，再到 CI 中的 DRC（Design Rule Check），让工程错误在变成实物之前被拦截。

这一工具链由 **Linter、静态分析与 DRC** 三层能力组成，是 piki `check` 命令的核心，也是 [SD-HWE-Bench](./001-sd-hwe-bench.md) 自动评分和 [GitHub 即工程设计](./003-github-as-engineering-design.md) CI 质量门的基础能力。

---

## 1. 背景与动机

### 1.1 工程设计缺少「编译器」

软件工程有编译器和 linter：

- 语法错误在保存时标红；
- 类型错误在编译时捕获；
- 代码风格由 linter 统一；
- 潜在 bug 由静态分析预警。

工程设计的等价物是什么？

- CAD 里的 DRC 大多针对几何（间距、重叠、短路），不针对设计意图；
- BIM  clash detection 慢且依赖具体文件格式；
- 工程师的经验规则分散在规范、手册和审图人的脑袋里；
- 一个设计错误往往要到仿真、试制或现场安装时才被发现。

piki 的 ADL 已经让设计意图文本化，下一步是让这些文本可以被「编译」和「检查」。

### 1.2 为什么现在是正确时机

- ADL 已经成为独立 Python 包（[ADR-012](../adr/engine-and-plugins/012-adl-as-independent-package.md)），可以复用其解析器和模型；
- [ADR-003](../adr/engine-and-plugins/003-quality-checks-and-diagnostics.md) 已经定义了 L0-L6 的分层质量检查框架；
- piki 的插件架构允许领域规则以 Python 函数形式注册；
- 诊断格式已经向 LSP-compatible 方向演进，可以接入编辑器。

---

## 2. 愿景与目标

### 2.1 愿景

> 让工程设计拥有像软件一样的即时反馈工具链：保存 ADL 文件时就能看到语法和语义错误，提交前就能通过规则校验，CI 中自动运行 DRC，让设计错误在变成实物之前被拦截。

### 2.2 具体目标

1. **Linter**：ADL / YAML / TOML 语法检查、风格统一、命名规范；
2. **静态分析**：未引用实例、悬空接口、循环依赖、冗余声明、潜在矛盾等；
3. **DRC 工具链**：领域设计规则检查（电气、机械、热、流体等），支持间距、容量、兼容性、可达性等约束；
4. **统一诊断格式**：所有工具输出一致的 `Diagnostic` 对象，支持位置、级别、修复建议；
5. **编辑器集成**：通过 LSP 或 CLI 输出，让 VS Code / Vim / Emacs 实时显示诊断；
6. **可扩展规则库**：社区和厂商可以贡献领域规则，形成开放的工程规则生态。

---

## 3. 范围与边界

### 3.1 工具链做什么

| 工具 | 层级 | 能力 |
|---|---|---|
| `adl lint` | L0-L1 | YAML/TOML 语法、schema 校验、命名风格 |
| `adl validate` | L2 | 引用完整性、Mate 自洽、Layout 合法性、Catalog 解析 |
| `piki check` | L3-L4 | 领域规则、生成物检查、DRC |
| `piki drc` | L3-L5 | 专门的设计规则检查命令，支持几何/空间/物理约束 |
| LSP server | L0-L4 | 编辑器实时诊断 |

### 3.2 工具链不做什么

| 不做 | 理由 |
|---|---|
| 替代专业仿真求解器 | DRC 是快速规则校验，仿真仍由 Ansys/Cadence 等完成 |
| 解析私有 CAD 格式 | 通过 EPM 引用开放格式（STEP/glTF/VTK），不深入 DWG/RVT 解析 |
| 自动修复所有问题 | 先提供诊断和修复建议，复杂决策留给工程师 |
| 替代人工审图 | DRC 拦截可规则化错误，专家审查仍是 L6 |

---

## 4. 与 piki 现有质量框架的关系

piki 的质量检查分层已在 [ADR-003: 多级质量检查与统一诊断](../adr/engine-and-plugins/003-quality-checks-and-diagnostics.md) 中定义。与本工具链的对应关系如下：

| 层级 | 负责工具 | 说明 |
|---|---|---|
| L0-L1 | `adl lint` | 语法与 Schema 校验 |
| L2 | `adl validate` | 引用、Mate、Layout、Catalog 自洽 |
| L3-L4 | `piki check` | 领域规则与生成物检查 |
| L5 | `piki drc --deep` | 外部仿真/求解器验证 |
| L6 | 人工 | 专家审查 |

完整层级定义、诊断格式与实现 rationale 见 [ADR-003](../adr/engine-and-plugins/003-quality-checks-and-diagnostics.md)。

本动议的重点是把 L0-L5 工具化、产品化、可扩展化。

---

## 5. 诊断格式与 LSP 集成

### 5.1 Diagnostic 对象

```python
@dataclass
class Diagnostic:
    code: str           # 如 "MATE-001"
    severity: str       # error / warning / info
    message: str        # 人类可读描述
    location: Location  # 文件、行、列
    rule_id: str | None
    fix: Fix | None     # 可选的自动修复建议
```

### 5.2 CLI 输出示例

```bash
$ piki check
instances/srv-01.yaml:12:3 error [POWER-003] PDU PDU-A 负载 92% 超过 80% 阈值
models/generic-server.yaml:8:1 warning [CATALOG-002] 型号未关联 CatalogEntry
layouts/rack-a01.yaml:22:5 error [LAYOUT-001] SRV-02 与 SRV-03 在 U20-U21 空间冲突
```

### 5.3 LSP Server

```bash
piki lsp
```

提供：

- 保存时实时诊断；
- 跳转到定义（Model → Family，Instance → Model）；
- 查找引用；
- 代码操作（快速修复）。

---

## 6. DRC 工具链的特殊性

DRC 在 EDA 领域已经是一个成熟概念（间距、宽度、天线效应等）。在 piki 中，DRC 应被扩展为跨领域的「设计规则检查」：

| 领域 | DRC 示例 |
|---|---|
| 数据中心 | 机柜功率不超过 PDU 容量 80%；设备前后预留维护空间 |
| 电信 | 光模块波长匹配；光纤弯曲半径；端口速率一致 |
| 机械 | 零件间隙；螺栓可达性；装配顺序无干涉 |
| 热设计 | 散热通道无阻塞；TDP 总和不超过冷却能力 |
| 流体 | 管径满足流量；泵扬程足够；无死区 |

DRC 规则应以声明式或 Python 函数形式注册：

```python
@rule("DRC-MECH-001", "零件间最小间隙", severity="error")
def check_part_clearance(ctx: Context):
    for a, b in ctx.query_pairs("mechanical_parts"):
        clearance = ctx.geometry.clearance(a.id, b.id)
        assert clearance >= 2.0, \
            f"{a.id} 与 {b.id} 间隙 {clearance}mm < 2.0mm"
```

---

## 7. 实现路径建议

### 阶段一：Linter + LSP（3-6 个月）

- 完善 `adl lint` 命令，覆盖 YAML/TOML 语法和命名风格；
- 将 `ADLValidator` 的诊断格式统一为 LSP-compatible；
- 实现基础 LSP server：`piki lsp`；
- 发布 VS Code 插件原型。

### 阶段二：静态分析与 DRC（6-12 个月）

- 增强 `adl validate` 的静态分析能力（未引用、循环依赖、冗余等）；
- 实现 `piki drc` 命令，支持空间/几何/物理规则；
- 建立 DRC 规则库，覆盖电信、数据中心、机械领域；
- 与 [EPM](./002-epm-engineering-package-manager.md) 集成，读取几何/网格资产。

### 阶段三：生态与平台（12-24 个月）

- 开放规则市场，允许厂商和社区贡献规则包；
- 规则包本身通过 EPM 分发；
- 与 [SD-HWE-Bench](./001-sd-hwe-bench.md) 集成，作为自动评分基础设施；
- 支持更多编辑器（Vim、Emacs、JetBrains）。

---

## 8. 风险与挑战

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| 规则爆炸 | 规则数量过多导致维护困难 | 分层治理：核心规则、插件规则、企业规则 |
| 假阳性过多 | 用户不信任 linter | 默认规则保守，允许项目级覆盖和抑制 |
| 几何 DRC 性能差 | 大型装配体检查慢 | 空间索引、增量检查、LOD 简化 |
| 与现有 CAD DRC 冲突 | 用户困惑 | 明确 piki DRC 聚焦「设计意图层」，不替代 CAD DRC |
| 规则版权与合规 | 行业标准规则可能受版权保护 | 优先实现开源标准，商业标准通过插件扩展 |

---

## 9. 决策待讨论项

1. **Linter 是否作为独立命令 `adl lint`，还是合并到 `piki check`？**
2. **DRC 规则是否采用声明式 DSL，还是只支持 Python 函数？**
3. **是否优先支持 VS Code，再支持其他编辑器？**
4. **静态分析是否默认启用，还是作为 `--strict` 选项？**
5. **如何管理规则的版本和弃用？**

---

## 10. 下一步行动

1. **审计现有诊断输出**：整理 `adl` 和 `piki` 当前所有诊断，统一格式；
2. **LSP server 原型**：实现 `piki lsp` 的最小可用版本；
3. **规则库模板**：为电信/数据中心插件提供 DRC 规则编写指南；
4. **RFC 拆分**：创建 `rfcs/00x-shift-left-quality-toolchain.md`，细化诊断格式、规则 DSL、LSP 协议实现。

---

## 相关阅读

- [ADR-003: 多级质量检查与统一诊断](../adr/engine-and-plugins/003-quality-checks-and-diagnostics.md)
- [ADL：装配体定义语言](../pitch/03-adl.md)
- [Initiative-001: SD-HWE-Bench](./001-sd-hwe-bench.md)
- [Initiative-003: GitHub 即工程设计](./003-github-as-engineering-design.md)
