# 01-telecom-expansion — 设备扩容

> 通信工程师最日常的场景：新增服务器前，自动检查功率、空间、接口兼容性。
> 从 `piki init --plugin telecom` 开始，一步步添加设备直到触发规则。

## 场景

你管理一个小型机房，机柜 `RACK-A01` 里已有 2 台服务器 + 1 台交换机：

| 设备 | 型号 | 位置 | 接口 |
|------|------|------|------|
| `SRV-01` | generic-server (300W) | U10-U11 | SFP28×1, SFP+×1, IEC-C14×2 |
| `SRV-02` | generic-server (250W) | U14-U15 | SFP28×1, QSFP28×1, IEC-C14×1 |
| `SW-01` | access-switch (150W) | U20 | SFP28×2, OSFP×1, IEC-C14×1 |

双路 PDU（各 2000W）。piki 帮你：**在提交设计前，自动发现功率、空间、配合三大类问题。**

## 项目结构

```
01-telecom-expansion/
├── piki.toml
├── models/
│   ├── devices/
│   │   ├── generic-server.yaml
│   │   └── access-switch.yaml
│   └── racks/
│       └── standard-rack.yaml
├── instances/
│   ├── devices/
│   │   ├── SRV-01.yaml
│   │   ├── SRV-02.yaml
│   │   └── SW-01.yaml
│   ├── pdus/
│   │   ├── PDU-A.yaml
│   │   └── PDU-B.yaml
│   └── racks/
│       └── RACK-A01.yaml
├── instances/
│   ├── devices/            # 服务器/交换机设备
│   ├── pdus/               # PDU 实例
│   ├── racks/              # 机柜实例
│   ├── ports/              # 设备端口（PortFamily）
│   └── port_connections/   # 端口到端口连接（PortConnectionFamily）
├── mates/
│   ├── rack-mount/         # L1 机械配合：设备装进机柜
│   │   ├── RACK-A01-SRV-01.yaml
│   │   ├── RACK-A01-SRV-02.yaml
│   │   ├── RACK-A01-SW-01.yaml
│   │   ├── RACK-A01-PDU-A.yaml
│   │   └── RACK-A01-PDU-B.yaml
│   ├── power-iec/          # L2 接口配合：电源口配对
│   │   ├── PDU-A-SRV-01-A.yaml
│   │   ├── PDU-A-SRV-02-A.yaml
│   │   ├── PDU-B-SRV-01-B.yaml
│   │   └── PDU-B-SW-01-A.yaml
│   ├── sfp28-cage/         # L2 接口配合：光模块插入笼子
│   └── lc-connector/       # L2 接口配合：光纤接入光模块
├── layouts/
│   └── layout.yaml
└── rules/
    └── power.py
```

## 快速体验

```bash
cd samples/01-telecom-expansion
piki check
```

## 你学到了什么

| 能力 | 对应位置 |
|------|---------|
| **Mate 配合图** | `mates/` 目录：rack-mount（L1 机械）+ power-iec（L2 接口） |
| **约束自动验证** | Mate 的 `constrains` 在加载时自动检查 depth/width/weight |
| **Interface 类型枚举** | SRV-01/SRV-02/SW-01 使用 SFP28/SFP+/QSFP28/OSFP/IEC-C14 |
| **端口级建模** | `instances/ports/`：PortFamily 定义设备端口 |
| **端口连接建模** | `instances/port_connections/`：PortConnectionFamily 定义端口到端口连接 |
| **端口占用冲突** | TELECOM-PORT-001 检查同一设备内端口重复定义 |
| **连接完整性** | TELECOM-CONN-001/002/003 检查端点、类型兼容、线缆匹配 |
| **PDU 功率预算** | 累加 PDU 下所有设备功耗，与额定容量对比 |
| **U 位冲突** | 同机柜内设备位置重叠检测 |
| **3D 碰撞检测** | AABB 包围盒空间冲突 |
| **端口分配表** | `piki generate port-map` 输出每设备端口占用与对端连接 |
| **Instance/Layout 分离** | 设备身份在 `instances/`，部署位置在 `layouts/` |
| **型号库复用** | `models/` 定义默认规格，Instance 可覆盖 |

## 关联概念

- [ADR-006: Mating Graph](../../docs/adr/006-mating-graph.md)
- [ADR-005: Connection 与 Interface](../../docs/adr/005-connection-as-instance.md)
- [编写检查规则](../../docs/concepts/02-writing-rules.md)
