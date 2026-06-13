# Instance 格式规范

> Instance 是 piki 的**实例层**——声明具体的物理设备，可覆盖 Model 的默认值。
>
> 所有 Instance 统一放在 `instances/` 目录下，通过 `family` 字段区分类型。

## 基本结构

```yaml
# instances/servers/SRV-01.yaml
id: SRV-01
family: ServerFamily
model: generic-server
name: 服务器-01
status: installed
tdp_w: 250
```

## 必填字段

| 字段 | 类型  | 说明                   |
| ---- | ----- | ---------------------- |
| `id` | `str` | 实例唯一标识，全局唯一 |

## 可选字段

| 字段      | 类型   | 说明                                                         |
| --------- | ------ | ------------------------------------------------------------ |
| `family`  | `str`  | Family 名称。若省略，从 `model` 推导                         |
| `model`   | `str`  | 引用的 Model ID。省略时无默认值                              |
| `catalog` | `dict` | 显式指定 CatalogEntry：`id` + 可选 `source`（ADR-011）       |
| `name`    | `str`  | 人类可读名称                                                 |
| `status`  | `str`  | 生命周期状态：`planned`、`installed`、`operating`、`retired` |
| `tags`    | `dict` | 标签键值对，用于规则过滤和视图筛选                           |

## 覆盖规则

Instance 可以覆盖 Model 的默认值：

```yaml
# Model: generic-server（默认 tdp_w: 300）
# Instance: SRV-02（实际功耗 250W）
id: SRV-02
family: ServerFamily
model: generic-server
tdp_w: 250 # 覆盖 Model 默认值 300
```

**不可覆盖的字段**：

当 Instance 试图覆盖标记为 `non_overridable` 的字段时，piki 报错：

```yaml
# ❌ 错误：试图覆盖不可覆盖字段
id: SRV-03
family: ServerFamily
model: generic-server
height_u: 4 # ERROR: height_u 标记为 non_overridable
```

```
[ERROR] SCHEMA-002: Instance 'SRV-03' 试图覆盖不可覆盖字段 'height_u'
```

## 生命周期状态

| 状态        | 说明               | 颜色编码          |
| ----------- | ------------------ | ----------------- |
| `planned`   | 计划部署，尚未采购 | 🔵 蓝色           |
| `installed` | 已上架安装         | 🟢 绿色           |
| `operating` | 已上电运行         | 🟢 绿色（或更亮） |
| `retired`   | 已退役，待下架     | ⚪ 灰色           |

状态用于面板图颜色编码和规则过滤：

```python
# 只检查已安装的设备
installed = ctx.query("instances", status="installed")

# 检查计划中但尚未安装的设备
planned = ctx.query("instances", status="planned")
```

## 标签（Tags）

Instance 通过 `tags` 声明非空间维度的归属：

```yaml
# instances/servers/SRV-01.yaml
id: SRV-01
family: ServerFamily
model: generic-server
status: installed

tags:
  discipline: "compute" # 专业：计算
  security_zone: "dmz" # 安全分区
  contract_package: "pkg-1" # 标段
  system: "web-cluster-a" # 所属系统
  phase: "phase-2" # 建设阶段
  owner: "zhangsan@example.com" # 负责人
```

标签是**正交维度**，与物理空间（文件路径）独立：

| 维度      | 表达方式                  | 原因                   |
| --------- | ------------------------- | ---------------------- |
| 物理空间  | `instances/` 下的文件路径 | 主键，决定 Layout 归属 |
| 专业      | `tags.discipline`         | 正交标签               |
| 安全分区  | `tags.security_zone`      | 正交标签               |
| 标段      | `tags.contract_package`   | 正交标签               |
| 系统/回路 | `tags.system`             | 正交标签               |

规则按标签触发：

```python
@rule("NUCLEAR-SAFETY-001")
def check_containment_hvac(ctx):
    instances = ctx.query(
        "instances",
        tags__security_zone="containment",
        tags__discipline="hvac"
    )
    for i in instances:
        assert i.resolved.seismic_rating >= 9
```

## 目录组织

`instances/` 下的子目录仅用于组织，不影响 collection：

```text
instances/
├── racks/
│   └── RACK-A01.yaml       # family: RackFamily
├── pdus/
│   ├── PDU-A.yaml          # family: PduFamily
│   └── PDU-B.yaml          # family: PduFamily
├── servers/
│   ├── SRV-01.yaml         # family: ServerFamily
│   └── SRV-02.yaml         # family: ServerFamily
└── network/
    └── SW-01.yaml          # family: SwitchFamily
```

**所有实例统一在 `instances` collection 中**，通过 `family` 查询：

```python
racks = ctx.query("instances", family="RackFamily")
pdus = ctx.query("instances", family="PduFamily")
servers = ctx.query("instances", family="ServerFamily")
```

## 与 Layout 的关系

Instance **不包含**部署位置信息。位置在 `layout.yaml` 中独立管理：

```yaml
# instances/SRV-01.yaml  ← 只声明"是什么"
id: SRV-01
family: ServerFamily
model: generic-server
status: installed
```

```yaml
# layout.yaml  ← 只声明"放哪、接哪"
- instance: SRV-01
  rack_id: RACK-A01
  position_u: 10
  pdu_id: PDU-A
```

分离的价值：

- 同一设备可在不同 Git 分支有不同部署方案
- 结构工程师改 `layout.yaml`，设备工程师改 `instances/`，不产生冲突

→ 详见：[05-layout-format.md](05-layout-format.md)

## Interface：实例的可连接点

Instance 通过 `interfaces` 字段声明对外暴露的可连接点。每个 Interface 是该 Instance 上的一个物理/逻辑端口。

```yaml
# instances/servers/SRV-01.yaml
id: SRV-01
family: ServerFamily
model: generic-server
status: installed

interfaces:
  - id: eth0
    interface_type: SFP28
    direction: bidirectional
    description: "管理口"
  - id: eth1
    interface_type: SFP28
    direction: bidirectional
    description: "业务口-1"
  - id: power-a
    interface_type: IEC-C14
    direction: input
    description: "A路电源"
```

### Interface 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | `str` | ✅ | Instance 内唯一标识：`eth0`、`power-a`、`hole-3` |
| `interface_type` | `str` | ✅ | 接口类型：`SFP28`、`IEC-C14`、`M16-bolt-hole`、`RJ45` 等 |
| `direction` | `str` | ❌ | `input` / `output` / `bidirectional`，默认 `bidirectional` |
| `description` | `str` | ❌ | 人类可读描述 |
| `specs` | `dict` | ❌ | 接口自身的规格键值对（自由扩展，由领域插件定义约束） |

带 specs 的示例：

```yaml
interfaces:
  - id: eth0
    interface_type: SFP28
    direction: bidirectional
    specs:
      speed_gbps: 25
      connector: LC
      media: SMF
```

### Interface 引用语法

在 Connection 实例中使用 `instance_id/interface_id` 格式引用 Interface：

```yaml
# instances/connections/CONN-01.yaml
id: CONN-01
family: ConnectionFamily
from_interface: SRV-01/eth0
to_interface: SW-01/Gi1-0-1
cable_type: SMF
```

> Interface 不是独立的 Instance，而是内嵌在 Instance 的 `interfaces` 列表中，随 Instance 一起解析和管理。

## Catalog 绑定（ADR-011）

Instance 默认通过 `model` 字段隐式绑定到指向该 Model 的 CatalogEntry。也可显式覆盖：

```yaml
# instances/links/core-link-01.yaml
id: core-link-01
family: CableAssemblyFamily
model: sfp28-sr-25g
catalog:
  id: acme-approved-sfp28
  source: enterprise
```

`catalog` 是保留字段，不参与 Family Schema 校验。解析后，生效的 CatalogEntry 数据会注入到 `resolved.catalog`，被引用的 ServiceMethodCatalogEntry 会合并为 `resolved.service_method`。

规则可按 Catalog 字段过滤：

```python
# 查找使用 EOL 器件的实例
eol_parts = ctx.query("instances", catalog__lifecycle="eol")

# 查找需要动火作业的实例
hot_work = ctx.query("instances", service_method__fire_watch_required=True)
```

## 解析后的完整对象

piki 运行时合并 Model 默认值 + Instance 覆盖值 + Layout 部署值 + Catalog 权威层：

```python
resolved = {
    # Model 默认值
    "height_u": 2,
    "tdp_w": 300,
    "psu_count": 1,
    # Instance 覆盖
    "tdp_w": 250,          # 覆盖 Model 的 300
    "status": "installed",
    # Layout 部署值
    "rack_id": "RACK-A01",
    "position_u": 10,
    "pdu_id": "PDU-A",
    # Catalog 权威层（ADR-011）
    "catalog": {
        "manufacturer": "Dell",
        "mpn": "R740-XXX",
        "lifecycle": "active",
    },
}
```

通过 `d.resolved` 访问：

```python
server = ctx.query("instances", id="SRV-01").first()
print(server.resolved.tdp_w)            # 250（Instance 覆盖值）
print(server.resolved.height_u)         # 2（Model 默认值）
print(server.resolved.rack_id)          # RACK-A01（Layout 值）
print(server.resolved.catalog.mpn)      # R740-XXX（Catalog 权威值）
```

## 最佳实践

1. **一实例一文件**：每个物理设备一个 YAML 文件
2. **文件名即 ID**：`SRV-01.yaml` → `id: SRV-01`
3. **只写决策字段**：规格字段（height_u、默认 tdp_w）从 Model 继承，Instance 只写覆盖值
4. **用 tags 表达正交维度**：专业、标段、系统归属用 tags，不用目录结构
5. **状态要准确**：planned / installed / operating / retired 反映真实生命周期
