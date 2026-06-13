# Catalog 格式规范

> Catalog 是 piki 的**设计权威层**（ADR-011）——连接设计模型（Model）与真实世界规格：制造商、料号、生命周期、Datasheet、服务工法等。
>
> Catalog 不是第六个维度，而是**跨维度的引用层**。

## 基本结构

Catalog 文件位于项目本地 `catalogs/` 目录，或企业/插件提供的型录库中。每个 YAML 文件是一个 **CatalogEntry**。

```text
catalogs/
├── components/                 # 物料型录条目
│   └── finisar-sfp28.yaml
└── service-methods/            # 工法/服务型录条目
    └── install-fiber-module.yaml
```

## 两类 CatalogEntry

### `ComponentCatalogFamily` — 物料型录条目

用于真实世界可采购器件。

```yaml
# catalogs/components/finisar-sfp28.yaml
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

model_ref: sfp28-sr-25g         # 指向 Model
datasheet:
  url: https://example.com/ds.pdf
  hash: sha256:abc123...
  revision: "Rev C"

service_methods:
  - install-fiber-module
  - clean-fiber-connector
```

#### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `catalog_id` | `str` | ✅ | 型录条目唯一标识 |
| `family` | `str` | ✅ | 固定为 `ComponentCatalogFamily` |
| `manufacturer` | `str` | ❌ | 制造商 |
| `mpn` | `str` | ❌ | 制造商料号 |
| `sku` | `str` | ❌ | SKU |
| `lifecycle` | `str` | ❌ | 生命周期：`active` / `preferred` / `restricted` / `nrnd` / `eol`，默认 `active` |
| `revision` | `str` | ❌ | 版本/修订 |
| `certifications` | `list[str]` | ❌ | 认证列表 |
| `model_ref` | `str` | ❌ | 指向的 Model ID |
| `datasheet` | `dict` | ❌ | `url` / `hash` / `revision` |
| `service_methods` | `list[str]` | ❌ | 引用的 ServiceMethodCatalogEntry ID 列表 |

### `ServiceMethodCatalogFamily` — 工法/服务型录条目

用于表达实施一项工程服务所需的前提条件，是 DFM/DFC 的核心。

```yaml
# catalogs/service-methods/install-fiber-module.yaml
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

#### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `catalog_id` | `str` | ✅ | 型录条目唯一标识 |
| `family` | `str` | ✅ | 固定为 `ServiceMethodCatalogFamily` |
| `service_type` | `str` | ❌ | 服务类型描述 |
| `applicable_to_families` | `list[str]` | ❌ | 适用的 Instance Family 列表 |
| `workspace` | `dict` | ❌ | 作业空间要求 |
| `safety` | `dict` | ❌ | 安全要求 |
| `temporary_works` | `list[dict]` | ❌ | 临时工程/机械需求 |
| `labor` | `list[dict]` | ❌ | 人工需求 |
| `standard_ref` | `str` | ❌ | 参考标准 |

## 来源优先级

Catalog 支持四级来源，覆盖优先级与 ADR-001 的嵌套项目继承一致：

```text
Project catalog > Parent project catalog > Enterprise catalog > Public catalog
```

| 层级 | 位置 | 来源标记 | 说明 |
|------|------|----------|------|
| **Project** | 项目本地 `catalogs/` | `project` | 项目团队维护的特殊定制件、临时方案 |
| **Parent** | 父项目 `catalogs/` | `parent` | 嵌套项目继承的型录 |
| **Enterprise** | `[catalogs] enterprise` 配置的目录 | `enterprise` | 企业优选物料、认证供应商 |
| **Public** | 插件 `catalog_dir` 目录 | `public` | 通用型号、白牌设备、标准工法 |

### 覆盖示例

同一 Model 可在不同层级有多个 CatalogEntry：

```yaml
# public catalog
sfp28-sr-25g:
  catalog_id: generic-sfp28-sr-25g
  model_ref: sfp28-sr-25g
  lifecycle: active
```

```yaml
# enterprise catalog
sfp28-sr-25g:
  catalog_id: acme-approved-sfp28
  model_ref: sfp28-sr-25g
  manufacturer: Finisar
  mpn: FTLX8571D3BCV
  lifecycle: preferred
```

最终生效的是项目级 catalog 条目，但其底层 Model 仍来自公共/企业层。

## 解析与查找规则

### 默认查找

当 Instance 引用 `model: sfp28-sr-25g` 时，引擎按优先级查找指向该 Model 的 CatalogEntry。

### 显式指定

```yaml
id: core-link-01
family: CableAssemblyFamily
model: sfp28-sr-25g
catalog:
  id: acme-approved-sfp28
  source: enterprise
```

`source` 可选值：`project`、`parent`、`enterprise`、`public`。

### 多 CatalogEntry 指向同一 Model

允许存在多个 CatalogEntry 指向同一 Model。Instance 未显式指定时，由优先级决定；需要多选一的场景（如替代料评估）由专门的生成器或规则处理，不污染 Instance 解析。

## 规则查询

Catalog 数据注入到 `resolved.catalog`，被引用的 ServiceMethodCatalogEntry 合并为 `resolved.service_method`。

```python
# 按生命周期过滤
eol_parts = ctx.query("instances", catalog__lifecycle="eol")

# 按企业扩展字段过滤
preferred = ctx.query("instances", catalog__lifecycle="preferred")

# 按服务工法要求过滤
hot_work = ctx.query("instances", service_method__fire_watch_required=True)
esd_required = ctx.query("instances", service_method__workspace__esd_required=True)
```

## 边界

piki 核心与内置插件不做：

- 实时价格、库存、供应商比价
- 自动汇总造价、预算、投标报价
- 定额版本管理与地区定额适配
- 施工进度、资源排期、甘特图
- 在 Catalog schema 中内置价格字段

这些属于 generator / 企业插件的消费层。Catalog schema 允许通过 `extra="allow"` 透传企业自定义字段（如 `enterprise.price_cny`），piki 核心不校验但透传，企业 generator 可读取。

## 参考

- [ADR-011: Catalog 作为设计权威层](../adr/011-catalog-as-authority-layer.md)
- [03-model.md](03-model.md)
- [04-instance.md](04-instance.md)
