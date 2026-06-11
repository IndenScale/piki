# 04-modular-dc — 模块化数据中心

> 智算液冷方舱 + 通算风冷方舱 + 锂电储能 + 配电，演示复杂部署场景。
> 演示 ADR-008 Instance/Layout 分离 + 多 family 类型管理。

## 场景

A1区模块化数据中心包含 4 个方舱、7 台设备、4 个配电单元和 4 条连接。

### 智算液冷方舱（AI-LIQUID-01）
- 4 台 GPU 服务器（每台 12kW，液冷）
- 1 台列间液冷空调（8kW）

### 通算风冷方舱（GEN-AIR-01）
- 2 台 CPU 服务器（每台 3kW）
- 1 台存储节点（1.5kW）

### 配电架构

```
市电 → POWER-01（配电方舱）
         ├── HVDC-MAIN（主路 500kW）
         ├── HVDC-BACKUP（备路 500kW）
         └── 储能接入
                  └── BAT-01（锂电 500kW）
                           ├── BAT-BANK-A（250kW）
                           └── BAT-BANK-B（250kW）
```

### 方舱间连接

```
POWER-01 ──power──→ AI-LIQUID-01   (600kW)
POWER-01 ──power──→ GEN-AIR-01     (400kW)
BAT-01   ──power──→ POWER-01       (1000kW)
AI-LIQUID-01 ──liquid──→ GEN-AIR-01  (120L/min, 规划中)
```

## 项目结构

```
04-modular-dc/
├── piki.toml                          # 项目配置
├── instances/                         # 所有设备身份（ADR-008）
│   ├── containers/                    #   方舱
│   │   ├── AI-LIQUID-01.yaml
│   │   ├── GEN-AIR-01.yaml
│   │   ├── BAT-01.yaml
│   │   └── POWER-01.yaml
│   ├── equipment/                     #   设备
│   │   ├── GPU-A01-01~04.yaml
│   │   ├── COOL-A01-01.yaml
│   │   ├── CPU-G01-01~02.yaml
│   │   └── STOR-G01-01.yaml
│   ├── power/                         #   配电单元
│   │   ├── HVDC-MAIN.yaml
│   │   ├── HVDC-BACKUP.yaml
│   │   ├── BAT-BANK-A.yaml
│   │   └── BAT-BANK-B.yaml
│   └── connections/                   #   方舱间连接
│       ├── LIQUID-AI-GEN.yaml
│       ├── POWER-P01-AI.yaml
│       ├── POWER-P01-GEN.yaml
│       └── POWER-BAT-P01.yaml
├── library/                           # 型号库
│   ├── containers/
│   ├── equipment/
│   └── power/
├── layouts/
│   └── layout.yaml                    # 部署决策（ADR-008）
└── rules/                             # 自定义规则
    ├── pue.py
    └── liquid_loop.py
```

## 运行检查

```bash
cd samples/04-modular-dc
piki check
```

## 你学到了什么

| 能力 | 说明 |
|------|------|
| Instance/Layout 分离 | `instances/` 统一存放所有设备身份，`layouts/` 管理部署 |
| 多 Family 类型 | EquipmentFamily / ContainerFamily / PowerUnitFamily / ConnectionFamily |
| 方舱级管理 | 集装箱作为部署单元，包含配电、制冷、设备 |
| 连接建模 | 方舱间管线/电缆/光纤用 ConnectionFamily 建模 |
| 液冷参数 | `liquid_cooled`、`coolant_flow_lpm` 等字段支持液冷场景 |
| 自定义 PUE | 项目规则根据 IT 功耗和制冷功耗估算 PUE |
| 冗余配置 | `redundancy_n` 字段 + 规则检查配电冗余策略 |
