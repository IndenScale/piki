# 04-modular-dc — 模块化数据中心

> 智算液冷方舱 + 通算风冷方舱 + 锂电储能 + 配电，演示复杂部署场景。
> 演示 ADR-008 Instance/Layout 分离 + 多 family 类型管理。

## 场景

A1区模块化数据中心包含 4 个方舱、11 台设备、4 个配电单元和 4 条连接。

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

| 连接 | 类型 | 源 | 目标 | 容量 |
|------|------|----|------|------|
| LIQUID-AI-GEN | 液冷 | AI-LIQUID-01 | GEN-AIR-01 | 150 L/min |
| POWER-P01-AI | 电力 | POWER-01 | AI-LIQUID-01 | 200 kW |
| POWER-P01-GEN | 电力 | POWER-01 | GEN-AIR-01 | 160 kW |
| POWER-BAT-P01 | 电力 | BAT-01 | POWER-01 | 500 kW |

## 项目结构

```
04-modular-dc/
├── piki.toml                    # 项目配置 + datacenter 插件
├── instances/                   # 设备身份（按类型分目录）
│   ├── containers/              # 方舱
│   │   ├── POWER-01.yaml
│   │   ├── AI-LIQUID-01.yaml
│   │   ├── GEN-AIR-01.yaml
│   │   └── BAT-01.yaml
│   ├── equipment/               # 设备
│   │   ├── GPU-A01-01.yaml
│   │   ├── GPU-A01-02.yaml
│   │   ├── GPU-A01-03.yaml
│   │   ├── GPU-A01-04.yaml
│   │   ├── CPU-G01-01.yaml
│   │   ├── CPU-G01-02.yaml
│   │   ├── STOR-G01-01.yaml
│   │   └── COOL-A01-01.yaml
│   ├── power/                   # 配电
│   │   ├── HVDC-MAIN.yaml
│   │   ├── HVDC-BACKUP.yaml
│   │   ├── BAT-BANK-A.yaml
│   │   └── BAT-BANK-B.yaml
│   └── connections/             # 方舱间连接
│       ├── LIQUID-AI-GEN.yaml
│       ├── POWER-P01-AI.yaml
│       ├── POWER-P01-GEN.yaml
│       └── POWER-BAT-P01.yaml
├── layouts/
│   └── layout.yaml              # 部署决策
└── rules/
    ├── pue.py                   # PUE 估算
    └── liquid_loop.py           # 液冷环路匹配
```

## 运行

```bash
cd samples/04-modular-dc
piki check
```

预期输出：全部通过。

```
============================================================
总计: 0 错误, 11 通过
============================================================
```

## 你学到了什么

| 能力 | 说明 |
|------|------|
| 多 Family 类型 | Container / Equipment / PowerUnit / Connection 四类 |
| 分层 instances/ | 按类型子目录组织大量实例 |
| 液冷管理 | 流量匹配、制冷容量、温度区间检查 |
| PUE 估算 | 动态估算数据中心能效比 |
| 配电冗余 | N+M 冗余配置检查 |
| 空间边界 | 方舱内设备空间容量检查 + 3D 碰撞检测 |
| BOM 生成 | `piki generate dc-bom` 导出 CSV |
