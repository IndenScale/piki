# 01-telecom-expansion — 真实机房扩容场景

> 通信工程师最日常的场景：在已有设备不可动的前提下，新增核心/汇聚/接入交换机和服务器，自动检查功率、空间、接口、线缆、冗余、承重、散热。
>
> 本 sample 从 `piki init --plugin telecom` 的骨架升级为一个**贴近真实工程需求**的完整样板间。

## 场景

你管理一个主机房 `ROOM-01`（10m × 8m）：

- **RACK-A01**（A 列第 1 机柜，核心/汇聚机柜）
  - 既有核心交换机 `CORE-SW-01`：H3C S6520X-30QC-EI，U40，已安装
  - 新增汇聚交换机 `AGG-SW-01`：H3C S6520X-30QC-EI，U37，计划部署
- **RACK-A02**（A 列第 2 机柜，接入/服务器机柜）
  - 既有接入交换机 `ACCESS-SW-01`：华为 CE6881-48S6CQ，U20，已安装
  - 新增业务服务器 `SRV-01` / `SRV-02`：Dell PowerEdge R750，U10-U11 / U14-U15，计划部署

机柜编号采用 `RACK-{列}{行}`，A 列沿东墙南北布置、正面朝北，A01（南侧）与 A02（北侧）之间保持 600mm 维护间距。
每台机柜配置双路 PDU（A/B 路，各 3000W，分相 L1/L2），核心/汇聚/接入/服务器均要求双路供电冗余。

网络连接：

- `CORE-SW-01/Ten1/0/1` ↔ `AGG-SW-01/Ten1/0/1`（QSFP28，OM4 MPO-MPO，5m）
- `AGG-SW-01/Gi1/0/1` ↔ `ACCESS-SW-01/10GE1/0/49`（SFP28，OM4 LC-LC，10m，跨机柜）
- `ACCESS-SW-01/10GE1/0/1` ↔ `SRV-01/eth0`（SFP28，OM4 LC-LC，3m）
- `ACCESS-SW-01/10GE1/0/2` ↔ `SRV-02/eth0`（SFP28，OM4 LC-LC，3m）

piki 帮你：**在提交设计前，自动发现功率、空间、配合、冗余、承重、散热、线缆规格七大类问题。**

## 项目结构

```
01-telecom-expansion/
├── piki.toml                 # 项目配置：阈值、启用规则与生成器
├── .gitignore                # 忽略 dist/ 生成物
├── catalogs/                 # Catalog 权威层：厂商、料号、价格、生命周期
│   └── components/
│       ├── h3c-s6520x-30qc.yaml
│       ├── hw-ce6881-48s6cq.yaml
│       ├── dell-r750.yaml
│       ├── qsfp28-sr-100g.yaml
│       ├── sfp28-sr-25g.yaml
│       └── om4-*.yaml
├── models/                   # 型号默认值层
│   ├── devices/
│   │   ├── generic-server.yaml      # 保留作为 fallback
│   │   ├── access-switch.yaml       # 保留作为 fallback
│   │   ├── h3c-s6520x-30qc.yaml     # H3C 核心/汇聚交换机
│   │   ├── hw-ce6881-48s6cq.yaml    # 华为接入交换机
│   │   └── dell-r750.yaml           # Dell 2U 服务器
│   ├── racks/
│   │   └── standard-rack.yaml       # 42U 标准机柜（含承重/散热/维护空间）
│   ├── transceivers/
│   │   ├── qsfp28-sr-100g.yaml
│   │   └── sfp28-sr-25g.yaml
│   └── fibers/
│       ├── om4-mpo-mpo-5m.yaml
│       ├── om4-lc-lc-3m.yaml
│       └── om4-lc-lc-10m.yaml
├── instances/                # 实际部署实体
│   ├── devices/              # 交换机 / 服务器
│   ├── pdus/                 # 双路 PDU
│   ├── racks/                # 两个机柜
│   ├── rooms/                # 机房平面（RoomFamily）
│   ├── ports/                # 设备端口（PortFamily）
│   ├── port_connections/     # 端口到端口连接（PortConnectionFamily）
│   ├── transceivers/         # 光模块实例
│   └── fibers/               # 光纤跳线实例
├── mates/                    # 配合图（Mating Graph）
│   ├── rack-mount/           # L1 机械配合
│   ├── power-iec/            # L2 电源配合（双路冗余）
│   ├── sfp28-cage/           # L2 SFP28 光模块插入笼子
│   ├── qsfp28-cage/          # L2 QSFP28 光模块插入笼子
│   └── lc-connector/         # L2 LC 光纤跳线接入光模块
├── layouts/
│   └── layout.yaml           # 设备部署位置与主 PDU
└── rules/
    └── power.py              # 项目自定义规则占位文件
```

## 快速体验

```bash
cd samples/01-telecom-expansion
piki check
piki generate
```

生成物会输出到 `dist/` 目录：

| 生成物 | 路径 | 用途 |
|--------|------|------|
| BOM 清单 | `dist/采购清单/bom.csv` | 采购/施工队 |
| 机柜面板图 | `dist/施工图/rack-panel.txt` / `rack-panels.svg` | 施工上架 |
| 功率预算 | `dist/设计评审/power-budget.csv` | 设计评审 |
| 线缆清单 | `dist/采购清单/cable-list.csv` | 采购光模块/光纤 |
| 端口分配表 | `dist/设计评审/port-map.csv` | 端口管理 |
| 线缆排期表 | `dist/施工清单/cable-schedule.csv` | 施工队按顺序布线（含平面路由） |
| 线缆标签 | `dist/施工清单/cable-labels.svg` | 打印贴标 |
| 端口互连图 | `dist/设计评审/port-diagram.svg` | 可视化接线关系 |
| 机房平面图 | `dist/施工图/floor-plan.svg` | 机柜在机房中的位置与朝向 |

按机柜过滤面板图：

```bash
piki generate rack-face-panel-svg --rack RACK-A01
```

## 你学到了什么

| 能力 | 对应位置 |
|------|---------|
| **真实设备型号库** | `models/devices/`：H3C / 华为 / Dell 真实型号 |
| **Catalog 权威层** | `catalogs/components/`：厂商、MPN、单价、生命周期 |
| **多机柜 brownfield 场景** | `RACK-A01/A02` + `status: installed` 既有设备 |
| **双路 PDU 冗余** | `mates/power-iec/` + `TELECOM-REDUNDANCY-001` |
| **相线平衡检查** | `TELECOM-POWER-002` |
| **机柜承重检查** | `TELECOM-WEIGHT-001` |
| **机柜散热检查** | `TELECOM-COOL-001` |
| **线缆长度规格检查** | `TELECOM-CABLE-001` |
| **维护空间检查** | `TELECOM-MAINTENANCE-001` |
| **机柜平面碰撞检查** | `TELECOM-FLOOR-001` |
| **机房通道宽度检查** | `TELECOM-FLOOR-002` |
| **机柜编号规范检查** | `TELECOM-FLOOR-003` |
| **机房平面图生成** | `piki generate floor-plan` |
| **Mate 配合图** | `mates/` 目录：rack-mount / power-iec / sfp28-cage / qsfp28-cage / lc-connector |
| **端口级建模** | `instances/ports/`：PortFamily 定义设备端口 |
| **端口连接建模** | `instances/port_connections/`：PortConnectionFamily 定义端口到端口连接 |
| **连接完整性** | TELECOM-CONN-001/002/003 检查端点、类型兼容、线缆匹配 |
| **3D 碰撞检测** | `TELECOM-COLLISION-001` |
| **线缆标签** | `piki generate cable-labels` |
| **线缆排期表** | `piki generate cable-schedule` |
| **端口互连图** | `piki generate port-diagram` |
| **Instance/Layout 分离** | 设备身份在 `instances/`，部署位置在 `layouts/` |

## 关联概念

- [ADR-006: Mating Graph](../../docs/adr/006-mating-graph.md)
- [ADR-005: Connection 与 Interface](../../docs/adr/005-connection-as-instance.md)
- [ADR-011: Catalog 权威层](../../docs/adr/011-catalog-as-authority-layer.md)
- [编写检查规则](../../docs/concepts/02-writing-rules.md)
