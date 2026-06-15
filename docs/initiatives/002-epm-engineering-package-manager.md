# Initiative-002: EPM —— 工程部件包管理器

- **状态：** 倡议 / 讨论中
- **日期：** 2026-06-15
- **作者：** piki 核心团队
- **相关文档：** [ADR-011: Catalog 作为设计权威层](../adr/engine-and-plugins/011-catalog-as-authority-layer.md)、[ADR-007: CAD 资产引用](../adr/visualization/007-cad-asset-reference.md)、[ADL：装配体定义语言](../pitch/03-adl.md)

---

## 摘要

提议建立 **EPM（Engineering Package/Parts Manager）**：面向工程领域的包管理器与注册中心，对标 NPM 与 PyPI，但服务于几何模型、有限元网格、器件型号、服务工法等工程资产。

EPM 解决的核心问题是：工程设计中的可复用部件（parts）缺乏统一的**身份、版本、依赖与分发机制**。当前这些资产散落在共享盘、PLM 系统、厂商网站和邮件附件中，无法被声明式设计语言（ADL）精确引用，也无法在 CI/CD 中被自动校验。

---

## 1. 背景与动机

### 1.1 软件工程的包管理已经成熟，工程领域还没有

软件工程有 NPM、PyPI、Cargo、Maven 等成熟包管理器：

- 每个包有全局唯一身份（name@version）；
- 依赖关系可被机器解析、锁定、复现；
- 包内容可被 CI/CD 在秒级内下载并验证；
- 社区可以基于包快速组合更复杂的系统。

工程领域有可复用部件，但没有等价物：

| 软件工程 | 工程领域 | 当前问题 |
|---|---|---|
| NPM package | 一个标准件、一个设备型号、一个 FEA 网格 | 无统一身份，靠文件名和路径识别 |
| `package.json` | 项目 BOM / 型号清单 | 多为 Excel/PLM 导出，不可机器校验 |
| `node_modules` | 共享盘 / PLM 附件库 | 不可版本锁定，不可离线复现 |
| semver | 型号版本 / 图纸版本 | 各厂商规则不一，无法自动比较 |
| registry | npmjs.org / pypi.org | 无公开的工程部件注册中心 |

### 1.2 为什么 piki 需要 EPM

piki 的 ADL 通过 `model` 和 `catalog` 引用真实世界部件（见 [ADR-011](../adr/engine-and-plugins/011-catalog-as-authority-layer.md)）。但以下问题尚未解决：

1. **大文件存储**：几何数据（STEP、GLB）、有限元网格（INP、MESH）、仿真结果（VTK）不适合进入 Git；
2. **版本与依赖**：一个 Model 可能依赖某个标准件的特定版本，需要可复现的锁定机制；
3. **跨项目复用**：企业希望在多个项目之间共享经过验证的型号库，但又需要私有控制；
4. **CI 可下载**：CI 环境需要在无 GUI、无人工登录的情况下获取所需资产。

EPM 是这些问题的答案。

---

## 2. 愿景与目标

### 2.1 愿景

> 让工程部件像软件包一样可被唯一标识、版本管理、依赖解析和自动分发，使「站在巨人肩膀上设计」成为工程领域的默认工作方式。

### 2.2 具体目标

1. **定义 EPM 包格式**：一个 EPM 包包含清单、ADL 声明、二进制资产和元数据；
2. **建立公共与私有注册中心**：支持社区公共 registry 和企业私有 registry；
3. **实现依赖解析与锁定**：支持语义化版本、范围约束、`epm.lock` 锁定文件；
4. **支持大文件存储**：几何、网格、图纸等二进制资产通过内容寻址存储，Git 仓库只保留引用；
5. **与 ADL / Catalog 集成**：ADL 的 `model` 和 `catalog` 可以直接引用 EPM 包中的部件；
6. **成为行业标准接口**：让设备厂商、仿真服务商、设计院都能发布和消费工程包。

---

## 3. 范围与边界

### 3.1 EPM 做什么

| 能力 | 说明 |
|---|---|
| 包身份与版本 | 每个包有 `name@version` 和唯一 hash；支持预发布版本和 dist-tag |
| 依赖管理 | 包可以声明依赖其他 EPM 包，支持版本范围和锁定 |
| 资产存储 | 内容寻址的二进制存储（几何、网格、图纸、仿真数据） |
| 注册中心 | 公共 registry + 企业私有 registry + 本地缓存 |
| CI 集成 | `epm install` 可在 CI 中无头运行，下载项目所需全部资产 |
| 质量元数据 | 包可声明通过哪些规则检查、生成哪些交付物 |

### 3.2 EPM 不做

| 不做 | 理由 |
|---|---|
| 造价/采购/库存 | 属于 ERP/PLM，EPM 只负责设计阶段的可复用资产 |
| 私有格式解析 | EPM 不解析 STEP/VTK 内容，只负责存储和引用；解析交给插件 |
| 权限审批流程 | 企业权限由 registry 实现方决定，EPM 只定义认证接口 |
| 替代 Git | EPM 存储大文件，ADL 设计声明仍在 Git 中 |

---

## 4. 与 piki 生态的关系

```text
┌─────────────────────────────────────────────┐
│                   piki 项目                  │
│  instances/ models/ catalogs/ layouts/      │
│  piki.toml  ← 声明依赖的 EPM 包              │
└─────────────────┬───────────────────────────┘
                  │ epm install
                  ▼
┌─────────────────────────────────────────────┐
│                    EPM                        │
│  包索引 → 依赖解析 → 内容寻址存储 → 本地缓存   │
└─────────────────┬───────────────────────────┘
                  │
     ┌────────────┼────────────┐
     ▼            ▼            ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│ 公共 Registry │ 企业 Registry │ 本地缓存   │
└─────────┘ └─────────┘ └─────────┘
```

### 4.1 EPM 与 Catalog 的关系

- **Catalog** 回答「这个型号对应哪个真实世界的料号/工法」；
- **EPM** 回答「这个型号/工法的完整数据包在哪里、如何下载、依赖什么」。

一个 CatalogEntry 可以引用一个 EPM 包：

```yaml
# catalogs/finisar-sfp28.yaml
catalog_id: finisar-ftlx8571d3bcv
family: ComponentCatalogFamily
model_ref: sfp28-sr-25g
package:
  name: finisar/sfp28-sr-25g
  version: "^1.2.0"
  registry: https://registry.piki.dev
```

### 4.2 EPM 与 ADL 的关系

ADL 负责「设计声明」，EPM 负责「声明背后的资产分发」。ADL 文件中只保留轻量级引用，实际几何/网格在 `epm install` 后进入本地缓存，生成器和可视化工具按需读取。

---

## 5. 包格式建议

一个最小 EPM 包：

```text
finisar-sfp28-sr-25g-1.2.0/
├── epm.toml              # 包清单
├── adl/
│   ├── models/
│   │   └── sfp28-sr-25g.yaml
│   └── catalogs/
│       └── finisar-ftlx8571d3bcv.yaml
└── assets/
    ├── step/
    │   └── sfp28-sr-25g.step
    └── datasheet.pdf
```

`epm.toml` 示例：

```toml
[package]
name = "finisar/sfp28-sr-25g"
version = "1.2.0"
description = "Finisar 25G SR SFP28 transceiver model"
license = "MIT"

[dependencies]
"piki/std-optics" = "^2.0.0"
"mfg/iec-connector" = ">=1.0.0, <2.0.0"

[assets]
step = "assets/step/sfp28-sr-25g.step"
datasheet = "assets/datasheet.pdf"

[quality]
rules = ["piki-telecom@^1.0"]
passed = ["DIM-001", "THERMAL-003"]
```

---

## 6. 实现路径建议

### 阶段一：MVP（3-6 个月）

- 定义 `epm.toml` 包清单格式；
- 实现本地包打包与解包命令：`epm pack`、`epm install`；
- 支持内容寻址的本地缓存；
- 与 piki 的 `catalog` 和 `model` 解析集成；
- 发布 3-5 个示例公共包（标准件、电信设备等）。

### 阶段二：注册中心（6-12 个月）

- 实现公共 registry 原型（HTTP API、搜索、版本列表）；
- 支持企业私有 registry 和认证；
- 实现 `epm publish`、`epm login`、`epm search`；
- 引入 `epm.lock` 锁定文件，保证 CI 可复现。

### 阶段三：生态（12-24 个月）

- 与设备厂商合作发布官方认证包；
- 支持几何/网格资产的内容寻址去重；
- 建立包质量评分和规则徽章机制；
- 探索与 PLM/ERP 的标准集成接口。

---

## 7. 风险与挑战

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| 大文件存储成本高 | 公共 registry 运营负担重 | 优先企业私有 registry，公共 registry 限流/收费 |
| 厂商不愿开放数据 | 公共包数量不足 | 从白牌设备、开源标准件入手，建立示范效应 |
| 与 PLM 系统冲突 | 企业已有物料管理流程 | 不替代 PLM，作为设计阶段的前置缓存和分发层 |
| 版本语义复杂 | 工程资产版本规则多样 | 允许自定义版本策略，但默认推荐 semver |
| 安全与合规 | 二进制资产可能含恶意内容 | 包签名、hash 校验、企业 registry 白名单 |

---

## 8. 决策待讨论项

1. **EPM 是否作为独立项目/仓库，还是 piki 子项目？**
2. **包名命名空间如何划分？** 是否采用 `厂商/型号` 两级？
3. **是否先实现 CLI 再实现 registry，还是两者并行？**
4. **大文件存储是否复用 IPFS / OCI / 自研内容寻址存储？**
5. **是否支持将 EPM 包直接作为 Git submodule 的替代方案？**

---

## 9. 下一步行动

1. **社区讨论**：收集对 `epm.toml` 格式和 registry 接口的反馈；
2. **RFC 拆分**：创建 `rfcs/00x-epm-package-format.md`，细化包格式、依赖解析、锁定机制；
3. **原型实现**：在 piki 仓库中创建 `epm/` 子目录，实现 MVP CLI；
4. **示例包**：将现有 telecom/datacenter 插件中的型号数据打包为首批 EPM 示例。

---

## 相关阅读

- [ADR-011: Catalog 作为设计权威层](../adr/engine-and-plugins/011-catalog-as-authority-layer.md)
- [ADR-007: CAD 资产引用](../adr/visualization/007-cad-asset-reference.md)
- [ADL：装配体定义语言](../pitch/03-adl.md)
- [Initiative-003: GitHub 即工程设计](./003-github-as-engineering-design.md)
