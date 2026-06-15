# Initiative-003: GitHub 即工程设计

- **状态：** 倡议 / 讨论中
- **日期：** 2026-06-15
- **作者：** piki 核心团队
- **相关文档：** [ADR-012: ADL 作为独立 Python 包](../adr/engine-and-plugins/012-adl-as-independent-package.md)、[ADR-007: CAD 资产引用](../adr/visualization/007-cad-asset-reference.md)、[ADL：装配体定义语言](../pitch/03-adl.md)、[Initiative-002: EPM](./002-epm-engineering-package-manager.md)

---

## 摘要

提议将 **GitHub/Git 作为工程设计的真相源与协作入口**：几何数据、有限元网格、CAD 资产等大文件通过 [EPM](./002-epm-engineering-package-manager.md) 注册与分发，Git 仓库中只保留轻量的 ADL 声明；同时通过 CI/CD 流水线自动执行设计质量检查，让「提交即校验」成为工程设计的默认体验。

这一动议的核心主张是：**工程设计的文本真相源不应该被大文件绑架**。Git 擅长管理文本和协作历史，但不擅长管理几何与网格；EPM 擅长管理大文件和依赖，但不擅长表达设计意图。两者结合，才能让工程设计真正进入「软件定义」时代。

---

## 1. 背景与动机

### 1.1 当前工程设计的版本控制困境

工程团队已经在尝试用 Git 管理设计，但很快遇到三个问题：

1. **大文件让仓库膨胀**：一个 STEP 模型几百 MB，一个 FEA 网格几个 GB，`git clone` 变成灾难；
2. **Git LFS 并不理想**：LFS 解决了存储问题，但增加了运维复杂度，且与设计语义无关；
3. **设计意图被淹没在二进制中**：PR 里只能看到「某个文件变了」，看不到「为什么变、结构影响是什么」。

结果是：Git 变成了备份工具，而不是设计协作工具。

### 1.2 软件工程已经证明的路径

软件工程的协作模式是：

```text
源代码（文本） → Git 仓库 → PR → CI 自动测试 → 合并
```

代码审查可以精确到行，CI 可以在秒级内验证改动是否破坏现有功能。这种「提交即校验」的文化是软件工程效率的基石。

工程设计可以复用同一条路径，只要解决一个问题：**让设计意图以文本形式存在于 Git 中，让大文件以引用形式存在于 EPM 中**。

---

## 2. 愿景与目标

### 2.1 愿景

> 工程设计仓库的默认形态是一个 Git 仓库：其中只有轻量的 ADL 声明、规则、生成器配置和 CI 脚本；几何、网格、图纸等大文件通过 EPM 引用。每一次提交都自动触发设计质量检查，PR 审查讨论的是设计意图而非文件大小。

### 2.2 具体目标

1. **ADL 作为 Git 中的唯一设计真相源**：Instance、Model、Catalog、Layout、Mating 全部以 YAML 文本存在；
2. **大文件进入 EPM 注册**：几何数据（STEP/GLB）、有限元网格（INP/MESH）、图纸（PDF/DWG）等通过 EPM 包分发，Git 中只保留内容寻址引用；
3. **无需 Git LFS**：用 EPM 的内容寻址存储和本地缓存替代 LFS；
4. **CI/CD 设计质量门**：在 GitHub Actions / GitLab CI 等流水线中运行 `piki check`，覆盖 L0-L4 规则；
5. **PR 即设计评审**：Reviewer 看到的是 ADL diff 和规则检查结果，而不是二进制文件；
6. **可复现的设计环境**：`git clone` + `epm install` + `piki check` 即可复现完整设计状态。

---

## 3. 范围与边界

### 3.1 测什么 / 做什么

| 能力 | 说明 |
|---|---|
| ADL 文本化设计 | 所有设计意图以 ADL YAML 形式进入 Git |
| EPM 大文件引用 | 几何、网格、图纸等通过 `epm://` 或内容 hash 引用 |
| CI 质量检查 | 每次提交/PR 自动运行 `piki check` |
| 设计 diff | PR 中展示 ADL 字段级差异和规则影响范围 |
| 可复现环境 | `git clone` 后可通过 `epm install` 还原完整设计 |

### 3.2 不做什么

| 不做 | 理由 |
|---|---|
| 替代 GitHub/GitLab | 复用现有平台，不重新发明代码托管 |
| 替代 CAD/CAE 工具 | CAD/BIM/仿真仍是下游消费和求解工具 |
| 在 Git 中存储大文件 | 这是 EPM 的职责 |
| 实时协同编辑 | 先解决「提交即校验」，再考虑实时协同 |

---

## 4. 架构设想

```text
┌─────────────────────────────────────────────────────────────┐
│                        Git 仓库                              │
│  instances/      ← ADL 实例声明（文本）                      │
│  models/         ← ADL 型号默认值（文本）                    │
│  catalogs/       ← ADL 型录引用（文本）                      │
│  layouts/        ← ADL 布局声明（文本）                      │
│  matings/        ← ADL 配合声明（文本）                      │
│  rules/          ← 自定义规则（Python）                      │
│  piki.toml       ← 插件与 EPM 依赖配置                       │
│  .github/workflows/piki-check.yml                            │
└───────────────────────────┬─────────────────────────────────┘
                            │ git push / PR
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      CI/CD 流水线                            │
│  epm install → piki check → 生成报告 → 评论 PR               │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        ▼                                       ▼
┌─────────────────────┐               ┌─────────────────────┐
│    EPM Registry     │               │   piki 规则引擎      │
│  几何 / 网格 / 图纸  │               │  L0-L4 自动校验      │
└─────────────────────┘               └─────────────────────┘
```

### 4.1 Git 中存放什么

```text
my-engineering-project/
├── piki.toml
├── .github/
│   └── workflows/
│       └── piki-check.yml
├── instances/
│   ├── rack-a01.yaml
│   └── srv-01.yaml
├── models/
│   └── generic-server.yaml
├── catalogs/
│   └── finisar-sfp28.yaml
├── layouts/
│   └── rack-a01.yaml
├── matings/
│   └── rack-mounts.yaml
└── rules/
    └── custom-clearance.py
```

### 4.2 EPM 中存放什么

```text
finisar/sfp28-sr-25g@1.2.0/
├── adl/
│   ├── models/sfp28-sr-25g.yaml
│   └── catalogs/finisar-ftlx8571d3bcv.yaml
└── assets/
    ├── step/sfp28-sr-25g.step
    └── datasheet.pdf
```

### 4.3 ADL 如何引用 EPM 资产

```yaml
# instances/core-link-01.yaml
id: core-link-01
family: CableAssemblyFamily
model: sfp28-sr-25g
catalog:
  id: finisar-ftlx8571d3bcv
  source: epm
  package: finisar/sfp28-sr-25g@1.2.0
```

或更直接的资产引用：

```yaml
# models/bracket-a.yaml
model: bracket-a
family: MechanicalPartFamily
geometry:
  step:
    epm: mfg/bracket-a@2.1.0#assets/step/bracket-a.step
    hash: sha256:def456...
```

---

## 5. CI/CD 设计质量检查

### 5.1 最小流水线

```yaml
# .github/workflows/piki-check.yml
name: piki-check
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: piki/setup-piki@v1
      - run: epm install
      - run: piki check --strict
      - run: piki report --format markdown --output report.md
      - uses: piki/comment-pr@v1
        with:
          report: report.md
```

### 5.2 检查层级

| 层级 | 检查内容 | 工具 |
|---|---|---|
| L0 | YAML / TOML 语法 | ADL parser |
| L1 | Schema / 类型 / FK 引用 | ADL validator |
| L2 | Mate / Layout / Catalog 自洽 | ADL validator |
| L3 | 领域规则（电信、数据中心、机械等） | piki plugins |
| L4 | 生成物检查（BOM、报告、3D 场景） | piki generators |
| L5 | 仿真验证（可选） | 外部求解器 |
| L6 | 专家审查（可选） | 人工 |

CI 默认覆盖 L0-L4，L5-L6 作为可选深度检查。

---

## 6. 实现路径建议

### 阶段一：MVP（3-6 个月）

- 完成 [EPM MVP](./002-epm-engineering-package-manager.md)；
- 在 piki 示例项目中实践「ADL + EPM 引用」模式；
- 提供 GitHub Actions 模板；
- 实现 `piki check` 的 CI 友好输出（JSON / JUnit / Markdown）。

### 阶段二：PR 体验（6-12 个月）

- 开发 GitHub App / Action，自动在 PR 中评论规则检查结果；
- 支持 ADL 字段级 diff 可视化；
- 支持规则影响范围提示（例如："此改动影响 3 个 instance 的功率预算"）。

### 阶段三：规模化（12-24 个月）

- 与企业 GitHub/GitLab 实例集成；
- 支持多分支设计比选（每个分支是一个设计方案）；
- 建立「设计模板仓库」，新项目可通过 template repo 一键启动。

---

## 7. 风险与挑战

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| 工程师不习惯文本化设计 |  adoption 慢 | 保留 GUI 预览和可视化，降低迁移成本 |
| EPM 不可用导致 CI 失败 | 外部依赖风险 | 支持本地缓存、企业私有 registry、离线模式 |
| 大文件引用失效 | 设计无法还原 | 强制 hash 校验，EPM 包不可变 |
| CAD/BIM 厂商封闭格式 | 无法导出为文本/引用 | 优先支持开放格式（STEP、glTF、VTK） |
| 性能问题 | 大型项目 `piki check` 变慢 | 增量检查、缓存、并行化 |

---

## 8. 决策待讨论项

1. **是否强制所有项目使用 EPM，还是保留 Git LFS 作为备选？**
2. **ADL 引用 EPM 资产的语法是否采用 `epm://` URL 还是内容 hash？**
3. **CI 默认检查层级是 L0-L3 还是 L0-L4？**
4. **是否先聚焦 GitHub，再支持 GitLab / Gitea？**
5. **PR 评论由 GitHub Action 实现还是独立 GitHub App？**

---

## 9. 下一步行动

1. **完成 EPM MVP**：没有 EPM，「GitHub 即工程设计」无法实现；
2. **创建示例仓库**：一个完整的「ADL + EPM + GitHub Actions」示例项目；
3. **RFC 拆分**：创建 `rfcs/00x-adl-epm-asset-reference.md`，细化 ADL 引用 EPM 资产的语法；
4. **CI 输出增强**：让 `piki check` 的输出更适合 GitHub Actions / PR 评论消费。

---

## 相关阅读

- [Initiative-002: EPM 工程部件包管理器](./002-epm-engineering-package-manager.md)
- [Initiative-004: 质量左移工具链](./004-shift-left-quality-toolchain.md)
- [ADR-012: ADL 作为独立 Python 包](../adr/engine-and-plugins/012-adl-as-independent-package.md)
- [ADR-007: CAD 资产引用](../adr/visualization/007-cad-asset-reference.md)
- [ADL：装配体定义语言](../pitch/03-adl.md)
