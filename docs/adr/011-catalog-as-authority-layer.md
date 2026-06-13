# ADR-011: Catalog 作为设计权威层——物料、工法与可建造性意图

> 状态：已接受  
> 日期：2026-06-13  
> 作者：piki 核心团队  
> 依赖：ADR-001（项目组织）、ADR-002（插件架构）、ADR-004（Generator 管线）、ADR-007（CAD 资产引用）、ADR-010（Context）

---

## 背景

piki 的 `Model` YAML 当前只是 **Instance 的技术默认值层**：它定义 `height_u`、`tdp_w`、`form_factor` 等参数，但不回答以下问题：

- 这个型号对应真实世界的哪个制造商、哪个 MPN？
- 参数来源是哪一份 datasheet？版本是什么？
- 这个器件的生命周期状态是什么？是否还能采购？
- 安装/服务这个器件需要满足哪些空间、安全、环境前提？
- 同一设计模型能否对应多个厂商实现，或一个企业优选料号？

随着 piki 从电信、数据中心向更广泛的工程领域扩展，上述缺失会越来越明显。尤其在建筑、机电安装、基建场景中，**服务/工法本身**（而不仅是物料）带有大量设计前提条件：作业空间、动火/防坠要求、临时机械、通风条件。这些不是造价问题，而是 **DFM/DFC（Design for Manufacturing / Design for Construction）** 问题，必须在设计阶段被建模和校验。

本 ADR 提出引入 **Catalog** 机制，作为连接「设计模型」与「真实世界权威规格」的独立层。

---

## 1. 核心决策：Catalog 是 Model 的权威身份层

### 1.1 Catalog 与 Model 的职责划分

| 概念 | 职责 | 回答的问题 |
|------|------|-----------|
| **Family** | pydantic 类型约束 | 这个族必须有哪些字段？ |
| **Model** | 技术默认值 | 这个设计型号的参数是什么？ |
| **Catalog** | 真实世界映射与权威来源 | 这个设计型号对应哪个真实料号/工法？来源是否可信？ |
| **Instance** | 实际部署实体 | 这个具体实例是什么、覆盖了什么？ |

**关键决策：Catalog 引用 Model，而不是反过来。**

```yaml
# catalogs/finisar-sfp28.yaml
catalog_id: finisar-ftlx8571d3bcv
family: ComponentCatalogFamily

manufacturer: Finisar
mpn: FTLX8571D3BCV
lifecycle: active

model_ref: sfp28-sr-25g      # 指向 Model
datasheet:
  url: https://example.com/ds.pdf
  hash: sha256:abc123...
  revision: "Rev C"

service_methods:
  - install-fiber-module
```

```yaml
# models/sfp28-sr-25g.yaml
model: sfp28-sr-25g
family: TransceiverFamily

form_factor: SFP28
reach_m: 100
wavelength_nm: 850
```

```yaml
# instances/links/core-link-01.yaml
id: core-link-01
family: CableAssemblyFamily
model: sfp28-sr-25g
```

### 1.2 为什么 Catalog 引用 Model，而不是 Model 引用 Catalog？

| 方案 | 问题 |
|------|------|
| **Model 引用 Catalog** | 同一 Model 可能对应多个 MPN；企业 catalog 是私有的，公共 Model 不应绑定特定 catalog；服务工法可能没有 Model |
| **Catalog 引用 Model** | Model 保持技术中性；多个 CatalogEntry 可指向同一 Model；企业/项目 catalog 可以覆盖公共 Model 的映射 |

---

## 2. Catalog 与 Datasheet 的命名

**机制名称使用 Catalog，Datasheet 作为 CatalogEntry 中的一个引用字段。**

| 术语 | 含义 | 在 piki 中的定位 |
|------|------|-----------------|
| **Catalog** | 可复用的条目库（物料、工法、服务包） | 机制名 |
| **CatalogEntry** | 库中的单个条目 | 一等数据实体 |
| **Datasheet** | 单个具体型号的技术文档 | CatalogEntry 中的 `datasheet` 字段 |

原因：

1. Catalog 能覆盖物料和服务方法；服务方法没有传统意义上的 datasheet。
2. piki 需要的是一个可共享、可索引、可覆盖的**库机制**，而不是单份文档机制。
3. 与 ROADMAP 中的「在线注册中心——社区共享的型号库」口径一致。

---

## 3. Catalog 支持三级来源

Catalog 不是单一来源，而是支持 **public / enterprise / project** 三级，覆盖优先级与 ADR-001 的嵌套项目继承一致：

```
Project catalog > Parent project catalog > Enterprise catalog > Public catalog
```

| 层级 | 位置 | 管理方 | 典型内容 |
|------|------|--------|---------|
| **Public** | piki SDK 内置 / 社区在线 registry | piki 社区 / 插件维护者 | 通用型号、白牌设备、标准工法 |
| **Enterprise** | 企业私有 catalog repo / 内部 registry | 企业架构/采购/工程部门 | 企业优选物料、认证供应商、内部标准 |
| **Project** | 项目本地 `catalogs/` | 项目团队 | 特殊定制件、项目特供料号、临时方案 |

### 3.1 三级覆盖示例

公共 catalog：

```yaml
# public catalog
sfp28-sr-25g:
  catalog_id: generic-sfp28-sr-25g
  model_ref: sfp28-sr-25g
  lifecycle: active
```

企业 catalog：

```yaml
# enterprise catalog
sfp28-sr-25g:
  catalog_id: acme-approved-sfp28
  model_ref: sfp28-sr-25g
  manufacturer: Finisar
  mpn: FTLX8571D3BCV
  lifecycle: preferred
```

项目 catalog：

```yaml
# project catalog
sfp28-sr-25g:
  catalog_id: site-trial-sfp28
  model_ref: sfp28-sr-25g
  manufacturer: DemoVendor
  lifecycle: provisional
```

最终生效的是项目级 catalog 条目，但其底层 Model 仍来自公共/企业层。

---

## 4. CatalogEntry 的两类形态

### 4.1 ComponentCatalogEntry（物料型录条目）

用于真实世界可采购器件：

```yaml
catalog_id: finisar-ftlx8571d3bcv
family: ComponentCatalogFamily

manufacturer: Finisar
mpn: FTLX8571D3BCV
sku: FTLX8571D3BCV-XXX
lifecycle: active               # active / preferred / restricted / nrnd / eol
revision: "Rev C"

certifications:
  - RoHS
  - REACH

model_ref: sfp28-sr-25g
datasheet:
  url: https://example.com/ds.pdf
  hash: sha256:abc123...
  revision: "Rev C"

service_methods:
  - install-fiber-module
  - clean-fiber-connector
```

### 4.2 ServiceMethodCatalogEntry（工法/服务型录条目）

用于表达实施一项工程服务所需的前提条件，是 DFM/DFC 的核心：

```yaml
catalog_id: install-fiber-module
family: ServiceMethodCatalogFamily

service_type: 光模块安装与清洁
applicable_to_families:
  - TransceiverFamily

workspace:
  min_clearance_mm: 600
  access_width_mm: 600
  lighting_lux: 300
  esd_required: true

safety:
  fall_protection_required: false
  fire_watch_required: false
  ventilation_required: false
  hot_work_permit_required: false
  ppe:
    - esd_wrist_strap
    - safety_glasses

temporary_works:
  - type: fiber_inspection_scope
    count: 1
  - type: cleaning_kit
    count: 1

labor:
  - role: 网络工程师
    count: 1

standard_ref: IEC 61300-3-35
```

---

## 5. 与 piki 现有维度的集成

Catalog 不是第六个维度，而是**跨维度的引用层**。

| 维度 | Catalog 如何集成 |
|------|-----------------|
| **Instance** | Instance 通过 `model` 间接获得 CatalogEntry；也可显式 `catalog.id` + `catalog.source` |
| **Layout** | ServiceMethodCatalogEntry 的 `workspace` 要求可在 Layout 中预留作业空间；临时工程可作为 `context: temporary` 的 Instance 放入 Layout |
| **Connection** | 临时供电、通风、消防水管等临时 Connection 可随服务方法派生 |
| **Mating** | 临时支撑、脚手架底座与永久结构的配合可用 Mating 建模 |
| **Context** | ADR-010 的 Context 可扩展 `temporary` / `construction` 类型，表达临时工程身份 |

---

## 6. 解析与查找规则

### 6.1 默认查找

当 Instance 引用 `model: sfp28-sr-25g` 时，引擎按以下优先级查找指向该 Model 的 CatalogEntry：

1. Project catalog
2. Parent project catalog
3. Enterprise catalog
4. Public catalog

### 6.2 显式指定

Instance 可显式指定 catalog 来源，用于需要精确控制的场景：

```yaml
id: core-link-01
family: CableAssemblyFamily
model: sfp28-sr-25g
catalog:
  id: acme-approved-sfp28
  source: enterprise
```

### 6.3 多 CatalogEntry 指向同一 Model

允许存在多个 CatalogEntry 指向同一 Model。Instance 未显式指定时，由优先级决定；需要多选一的场景（如替代料评估）由专门的生成器或规则处理，不污染 Instance 解析。

---

## 7. 规则与生成器增强

### 7.1 示例规则

```python
@rule("CATALOG-LIFECYCLE-001", "禁止在 BOM 中使用 EOL 器件", priority=10)
def check_eol_parts(ctx: Context):
    for inst in ctx.query("instances", catalog__lifecycle="eol"):
        if inst.context != "existing":
            raise Diagnostic(f"{inst.id} 使用 EOL 器件 {inst.catalog.mpn}")
```

```python
@rule("DFM-WORKSPACE-001", "动火作业需预留防火间距", priority=10)
def check_hot_work_clearance(ctx: Context):
    for inst in ctx.query("instances", service_method__fire_watch_required=True):
        # 校验 Layout 中该 Instance 周围是否有足够防火间距
        ...
```

### 7.2 示例生成器

| 生成器 | 输出 |
|--------|------|
| `procurement-bom` | 带 manufacturer、MPN、lifecycle 的采购 BOM |
| `temporary-works-plan` | 临时工程布置与空间需求 |
| `equipment-rental-list` | 吊车、脚手架、发电机、电缆牵引机等临时机械需求 |
| `safety-plan` | 动火、高空、密闭空间、ESD 等作业清单 |
| `constructability-report` | 可建造性评估 |

---

## 8. 边界：piki 核心不做，但 generator 可以消费

Catalog 机制必须守住 piki「设计意图层 + 规则校验层」的边界。这里需要区分两个层面：

- **piki 核心与内置插件**：不内置、不维护、不承诺造价/采购/进度能力。
- **generator / 下游消费层**：作为 ADR-004 定义的交付物管线，可以从 piki 的结构化数据中派生任何项目需要的输出，包括算量、造价、施工计划等。

### 8.1 piki 核心与内置插件不做

| 不做 | 理由 |
|------|------|
| 实时价格、库存、供应商比价 | 属于 ERP/采购系统；价格易变，不宜作为设计真相源 |
| 自动汇总造价、预算、投标报价 | 属于造价管理 / 项目管理工具 |
| 定额版本管理与地区定额适配 | 维护负担重，且易滑向造价管理 |
| 施工进度、资源排期、甘特图 | 属于项目管理工具 |
| 在 Catalog schema 中内置价格字段 | 避免核心 schema 被企业特定计价规则污染 |
| 嵌入 PDF/STEP/热模型 | 遵循 ADR-007「引用而非嵌入」 |

### 8.2 generator / 企业插件可以做

piki 不限制 generator 的输出深度。只要设计意图数据足够完整，下游 generator 可以产出：

| 能力 | 由谁实现 | 数据来源 |
|------|---------|---------|
| 算量表 | 项目/企业 generator | Instance + Layout + ServiceMethodCatalogEntry |
| 造价估算 | 企业插件 generator | Catalog 企业扩展字段 + 工程量 |
| 采购比价单 | 企业插件 generator | 企业 catalog 中的供应商扩展字段 |
| 施工工序卡 | 项目 generator | ServiceMethodCatalogEntry |
| 进度计划 / 甘特图 | 项目 generator | ServiceMethodCatalogEntry 中的工时与前置条件 |

### 8.3 Catalog schema 的扩展策略

Catalog schema 本身保持价格无关，但允许企业通过插件扩展私有字段：

```yaml
# piki 核心识别的字段
catalog_id: acme-approved-sfp28
manufacturer: Finisar
mpn: FTLX8571D3BCV
lifecycle: preferred

# 企业插件自定义字段，piki 核心透传
enterprise:
  price_cny: 1200
  supplier_code: SUP-001
  quote_date: 2026-06-01
  region_quota: GB-XXX-001
```

piki 核心对 `enterprise.*` 透传但不校验；企业 generator 可以读取并输出造价、比价或采购单。

---

## 9. 目录结构建议

```text
piki-project/
├── piki.toml
├── models/
│   └── sfp28-sr-25g.yaml
├── catalogs/
│   ├── components/
│   │   └── finisar-sfp28.yaml
│   └── service-methods/
│       └── install-fiber-module.yaml
├── instances/
│   └── ...
└── enterprise-catalog/        # 通过 git submodule 或 piki.toml 引用
    └── ...
```

### piki.toml 配置示例

```toml
[project]
name = "my-datacenter"

[plugins]
enabled = ["telecom", "datacenter"]

[catalogs]
public = true
enterprise = "git@internal:piki-enterprise-catalog.git"
# project 级 catalog 自动读取 catalogs/
```

---

## 10. 决策总结

| 决策 | 选择 | 核心理由 |
|------|------|----------|
| 机制名称 | **Catalog** | 覆盖物料与服务方法，与「型号库」口径一致 |
| Datasheet 定位 | CatalogEntry 中的引用字段 | datasheet 是单型号技术文档，不是库机制 |
| Catalog 与 Model 关系 | **Catalog 引用 Model** | Model 保持技术中性，支持多 MPN 映射和企业覆盖 |
| Catalog 层级 | **Public / Enterprise / Project** | 支持社区共享、企业私有、项目特化 |
| 覆盖优先级 | Project > Parent > Enterprise > Public | 与 ADR-001 嵌套项目继承一致 |
| 服务方法 | 作为 **ServiceMethodCatalogEntry** | 将 DFM/DFC 前提条件纳入设计校验 |
| 边界 | 不做造价/进度/比价 | 保持 piki 在设计意图层 |

---

## 实现状态

- ✅ 已落地核心机制：
  - `ComponentCatalogFamily` / `ServiceMethodCatalogFamily` 数据模型
  - 四级来源加载与优先级（Project / Parent / Enterprise / Public）
  - Instance 解析时注入 `resolved.catalog` 与 `resolved.service_method`
  - QuerySet 支持 `catalog__*` / `service_method__*` 嵌套查询
  - 内置 L2 检查 `CATALOG-001`、`CATALOG-002`
  - telecom 插件规则 `CATALOG-LIFECYCLE-001` 与生成器 `procurement-bom`
  - `piki init` 自动创建 `catalogs/` 目录与示例型录
- 📚 参考文档：`docs/reference/08-catalog.md`

## 参考

- [ADR-001: 项目组织模型](../adr/001-project-organization.md)
- [ADR-002: 插件架构](../adr/002-plugin-architecture.md)
- [ADR-004: Generator 交付物管线](../adr/004-generator-as-deliverable-pipeline.md)
- [ADR-007: CAD 资产引用](../adr/007-cad-asset-reference.md)
- [ADR-010: 多上下文工程设计](../adr/010-brownfield-reference-instance.md)
