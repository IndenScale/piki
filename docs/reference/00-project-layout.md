# 项目目录结构（Scaffold）

> 一个 piki 项目初始化后包含哪些目录和文件，以及各自的用途。
>
> 这是 piki 的**核心约定**——目录名即概念名，没有例外目录。

## 概览

```text
my-project/
├── piki.toml                 # 项目元数据（根目录标记、插件、配置）
├── .gitignore                # 忽略缓存和生成产物
├── .piki_cache/              # 解析缓存（可选，gitignore）
│
├── models/                   # 项目本地型号库（可选）
│   └── devices/
│       ├── generic-server.yaml
│       └── dell-r740.yaml
│
├── catalogs/                 # 项目本地型录库（可选，ADR-011）
│   ├── components/
│   │   └── finisar-sfp28.yaml
│   └── service-methods/
│       └── install-fiber-module.yaml
│
├── instances/                # 所有实例（设备身份）
│   ├── racks/
│   │   └── RACK-A01.yaml
│   ├── pdus/
│   │   ├── PDU-A.yaml
│   │   └── PDU-B.yaml
│   └── servers/
│       ├── SRV-01.yaml
│       └── SRV-02.yaml
│
├── layout.yaml               # 部署决策（每个子项目一个）
├── modules/                  # Layout 可复用模块（可选）
│   └── standard-rack.yaml
│
├── rules/                    # 项目自定义规则
│   ├── __init__.py
│   ├── power.py
│   └── rack_space.py
│
└── generators/               # 项目自定义生成器（可选）
    └── my_report.py
```

## 核心文件

### `piki.toml`

项目根标记文件。piki 通过向上扫描 `piki.toml` 确定项目边界。

```toml
# piki.toml
[project]
name = "my-datacenter"
version = "1.0.0"

[plugins]
enabled = ["telecom"]

[plugins.telecom]
power_threshold = 0.4
rack_usage_threshold = 0.8
```

| 字段              | 说明                                           |
| ----------------- | ---------------------------------------------- |
| `project.name`    | 项目名称                                       |
| `project.version` | 项目版本                                       |
| `plugins.enabled` | 启用的插件列表                                 |
| `plugins.<name>`  | 插件专属配置，可在规则中通过 `ctx.config` 读取 |
| `rules`           | 全局规则配置                                   |
| `performance`     | 性能相关配置（缓存、并行）                     |
| `output`          | 输出格式配置                                   |

→ 完整配置参考：[01-configuration.md](01-configuration.md)

---

## 概念目录

### `models/` — 型号库（可选）

项目本地型号库。每个 YAML 文件是一个 **Model**，提供 Family 的默认值。

```yaml
# models/devices/generic-server.yaml
model: generic-server
family: ServerFamily

height_u: 2
tdp_w: 300
psu_count: 1
psu_redundancy: false
```

- 必须包含 `model`（型号 ID）和 `family`（所属 Family）
- 若插件已提供所需型号，此目录可缺省
- 来源优先级：**项目本地 `models/` > 插件自带型号库**
- 详见：[03-model.md](03-model.md)

---

### `catalogs/` — 型录库（可选，ADR-011）

项目本地型录库。每个 YAML 文件是一个 **CatalogEntry**，把 Model 映射到真实世界的制造商、料号、生命周期或服务工法。

```yaml
# catalogs/components/finisar-sfp28.yaml
catalog_id: finisar-ftlx8571d3bcv
family: ComponentCatalogFamily

manufacturer: Finisar
mpn: FTLX8571D3BCV
lifecycle: active
model_ref: sfp28-sr-25g

datasheet:
  url: https://example.com/ds.pdf
  revision: "Rev C"
```

```yaml
# catalogs/service-methods/install-fiber-module.yaml
catalog_id: install-fiber-module
family: ServiceMethodCatalogFamily

service_type: 光模块安装与清洁
applicable_to_families:
  - TransceiverFamily

workspace:
  min_clearance_mm: 600
  esd_required: true
```

- 必须包含 `catalog_id` 和 `family`
- `family` 当前支持 `ComponentCatalogFamily` 和 `ServiceMethodCatalogFamily`
- 来源优先级：**Project > Parent > Enterprise > Public**，与 ADR-001 嵌套继承一致
- Instance 通过 `model` 隐式绑定，或通过 `catalog.id` / `catalog.source` 显式绑定
- 子目录仅用于组织，不影响加载
- 详见：[08-catalog.md](08-catalog.md)

---

### `instances/` — 实例（必填）

**所有实例统一放在此目录下。** 每个 YAML 文件是一个 **Instance**，声明具体的物理设备。

```yaml
# instances/servers/SRV-01.yaml
id: SRV-01
family: ServerFamily
model: generic-server
status: installed
tdp_w: 250
```

- 必须包含 `id`
- 可通过 `family` 或 `model` 推导 Family
- Instance 字段会覆盖 Model 的默认值
- 子目录仅用于组织，不影响 collection（统一为 `instances`）
- 详见：[04-instance.md](04-instance.md)

**关键约定**：`instances/` 是唯一的实例目录。Rack、PDU、Server 都是实例，通过 `family` 区分类型，不应在根目录另设 `racks/`、`pdus/` 等目录。

---

### `layout.yaml` — 部署决策（必填）

每个子项目只有一个 Layout 文件，描述当前方案中所有 Instance 的部署位置。

```yaml
# layout.yaml
- instance: SRV-01
  rack_id: RACK-A01
  position_u: 10
  pdu_id: PDU-A

- instance: SRV-02
  rack_id: RACK-A01
  position_u: 8
  pdu_id: PDU-A
```

- 描述"设备放哪、接哪"，不描述"设备是什么"
- 支持模块引用（见下文 `modules/`）
- 详见：[05-layout.md](05-layout.md)

---

### `modules/` — Layout 模块（可选）

可复用的 Layout 片段，供 `layout.yaml` 引用。类似 Terraform module 或硬件 IP 核。

```yaml
# modules/standard-rack.yaml
- instance: "{{prefix}}-SW-01"
  rack_id: "{{rack_id}}"
  position_u: 42

- instance: "{{prefix}}-SW-02"
  rack_id: "{{rack_id}}"
  position_u: 40
```

- 模块不是独立的 Layout，只能被 `layout.yaml` 引用
- 支持模板变量（`{{param}}`）
- 详见：[05-layout.md#模块引用](05-layout.md)

---

### `rules/` — 自定义规则（可选）

项目自定义规则，按主题分组。

```python
# rules/power.py
from piki import rule, Context

@rule("PROJECT-POWER-001", "项目功率检查")
def check_project_power(ctx: Context):
    threshold = ctx.config.get("power_threshold", 0.8)
    # ...
```

- 规则 ID 建议格式：`{领域}-{主题}-{序号}`，如 `TELECOM-POWER-001`
- 详见：[编写检查规则 →](../concepts/02-writing-rules.md)

---

### `generators/` — 自定义生成器（可选）

项目自定义生成器，通过 `piki generate` 调用。

---

## 缓存与生成产物

### `.piki_cache/` — 解析缓存

以下目录建议加入 `.gitignore`：

```gitignore
.piki_cache/
```

- `.piki_cache/`: 解析缓存，加速增量检查

### `dist/` — 交付产物

`dist/` 是生成器（Generator）的默认输出根目录，按交付场景分类：

```text
dist/
├── 施工图/                 # 施工队看图施工
│   ├── rack-panel-RACK-A01.svg
│   └── rack-panel-RACK-A02.svg
├── 采购清单/               # 采购/供应链
│   ├── bom.csv
│   └── cable-list.csv
└── 设计评审/               # 方案交底/甲方沟通
    └── power-budget.csv
```

| 约定 | 说明 |
|---|---|
| 目录名 | `dist/` 固定根目录，子目录按交付场景命名 |
| Git 策略 | 建议 `gitignore`；可对里程碑版本 `git add` 做快照存档 |
| 场景映射 | 在 `piki.toml` 的 `[generators.dist.targets]` 中配置 |
| 显式覆盖 | `piki generate --output /path/to/file.csv` 优先级高于 dist 约定 |
| 受众 | 子目录使用中文命名，面向施工队/采购/甲方等非开发人员 |

**配置示例**（`piki.toml`）：

```toml
[generators]
enabled = ["bom-csv", "rack-face-panel-svg", "power-budget", "cable-list"]

[generators.dist]
root = "dist"

[generators.dist.targets]
bom-csv = "采购清单"
rack-face-panel-svg = "施工图"
power-budget = "设计评审"
cable-list = "采购清单"
```

产物可从 YAML 随时重新生成，不应进入日常版本 diff。

---

## 嵌套项目

piki 支持嵌套项目（ADR-001）。每个子项目有独立的目录结构：

```text
parent-project/
├── piki.toml
├── instances/               # 父项目共享实例
├── layout.yaml              # 父项目 Layout（可为空或引用子项目）
├── rules/
│
└── floor-1/                 # 子项目
    ├── piki.toml
    ├── instances/           # 楼层特有实例
    ├── layout.yaml          # 楼层 Layout
    └── rules/
```

子项目继承父项目的：

- `piki.toml` 参数（同名字段覆盖）
- `models/` 型号库（可追加）
- `instances/` 实例（可追加，同名覆盖）
- 插件和规则

Layout **不继承**——每个子项目有独立的 `layout.yaml`。

---

## 字段命名空间约定

- **Model** 中推荐使用嵌套命名空间，如 `physical.height_u`、`power.tdp_w`
- **Instance** 中可以直接写扁平字段，如 `height_u: 2`、`tdp_w: 250`，piki 会自动覆盖对应 Model 字段
- 解析后的完整对象可通过 `d.resolved.height_u` 或 `d.height_u` 访问
