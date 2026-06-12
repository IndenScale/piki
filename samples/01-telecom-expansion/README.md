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

双路 PDU（各 2000W），现有 3 根光纤连接。现在新增 `SRV-03`（400W）。

piki 帮你：**在提交设计前，自动发现功率、空间、接口三大类问题。**

## 项目结构

```
01-telecom-expansion/
├── piki.toml                         # 项目配置（功率阈值 40%）
├── models/devices/
│   ├── generic-server.yaml           # 服务器型号（2U, 300W）
│   └── access-switch.yaml            # 交换机型号（1U, 150W）
├── instances/
│   ├── devices/
│   │   ├── SRV-01.yaml               # 服务器-01（含 4 个 Interface）
│   │   ├── SRV-02.yaml               # 服务器-02（含 3 个 Interface）
│   │   └── SW-01.yaml                # 交换机（含 4 个 Interface）
│   ├── pdus/
│   │   ├── PDU-A.yaml                # 主路 PDU（IEC-C14×2）
│   │   └── PDU-B.yaml                # 备路 PDU（IEC-C14×2）
│   ├── racks/
│   │   └── RACK-A01.yaml             # 42U 机柜
│   └── connections/
│       ├── FIBER-S01-S02.yaml        # SFP28 ↔ SFP28（同类型，通过）
│       ├── FIBER-S01-SW01.yaml       # SFP+ ↔ SFP28（兼容矩阵判定通过）
│       └── FIBER-S02-SW01.yaml       # QSFP28 ↔ SFP28（故意不兼容）
├── layouts/
│   └── layout.yaml                   # 部署决策（Instance/Layout 分离）
└── rules/
    └── power.py                      # 项目自定义规则（预留）
```

## 快速体验

```bash
cd samples/01-telecom-expansion
piki check
```

预期输出（2 个预期错误——接口不兼容 + 线缆类型不匹配）：

```
[PASS] REFS-001: Layout-Instance 引用完整性
[PASS] FK-001: 通用外键引用完整性
[FAIL] INTERFACE-COMPAT-001: 接口类型兼容性检查
       QSFP28 ↔ SFP28 不兼容
[FAIL] INTERFACE-CABLE-001: 线缆-接口类型匹配检查
       QSFP28 口不支持 OM4-LC-LC
[PASS] TELECOM-POWER-001: PDU 功率预算检查
[PASS] TELECOM-RACK-001: U 位冲突检查
...
```

## 你学到了什么

| 能力 | 对应文件 |
|------|---------|
| **Interface 类型枚举** | SRV-01/SRV-02/SW-01 使用 SFP28/SFP+/QSFP28/OSFP/IEC-C14 |
| **兼容性矩阵** | FIBER-S01-SW01：SFP+ ↔ SFP28 通过（SFP28 笼子兼容 SFP+ 模块） |
| **不兼容检测** | FIBER-S02-SW01：QSFP28 ↔ SFP28 失败（物理尺寸不同） |
| **线缆类型校验** | QSFP28 口配 LC 跳线 → INTERFACE-CABLE-001 报错 |
| **PDU 功率预算** | 累加 PDU 下所有设备功耗，与额定容量对比 |
| **U 位冲突** | 同机柜内设备位置重叠检测 |
| **3D 碰撞检测** | AABB 包围盒空间冲突 |
| **Instance/Layout 分离** | 设备身份在 `instances/`，部署位置在 `layouts/` |
| **型号库复用** | `models/` 定义默认规格，Instance 可覆盖（如 tdp_w） |

## 关联概念

- [ADR-007: Connection 与 Interface](../../docs/adr/007-connection-as-instance.md)
- [RFC-001: Telecom 接口类型体系](../../docs/rfcs/001-telecom-interface-types.md)
- [ADR-008: Instance/Layout 分离](../../docs/adr/001-project-organization.md)
- [编写检查规则](../../docs/concepts/02-writing-rules.md)
