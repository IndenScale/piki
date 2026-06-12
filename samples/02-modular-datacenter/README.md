# 02-modular-datacenter — 数据中心建设

> 通信 + 建筑耦合：方舱配电 + 液冷管路 + 光纤布线 + 厂区嵌套。
> 证明 piki 声明式范式可跨领域扩展。

## 场景

A1 区模块化数据中心包含 4 个方舱、11 台设备、4 个配电单元。

### 方舱布局

| 方舱 | 类型 | 内容 |
|------|------|------|
| `AI-LIQUID-01` | 智算液冷 | 4×GPU 服务器（12kW）+ 列间液冷空调 |
| `GEN-AIR-01` | 通算风冷 | 2×CPU 服务器 + 存储节点 |
| `POWER-01` | 配电 | HVDC-MAIN + HVDC-BACKUP |
| `BAT-01` | 储能 | 2×锂电电池组（500kW） |

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

## 项目结构

```
02-modular-datacenter/
├── piki.toml
├── instances/
│   ├── containers/           # 方舱
│   │   ├── POWER-01.yaml
│   │   ├── AI-LIQUID-01.yaml
│   │   ├── GEN-AIR-01.yaml
│   │   └── BAT-01.yaml
│   ├── equipment/            # 设备
│   │   ├── GPU-A01-01~04.yaml
│   │   ├── CPU-G01-01~02.yaml
│   │   ├── STOR-G01-01.yaml
│   │   └── COOL-A01-01.yaml
│   └── power/                # 配电
│       ├── HVDC-MAIN.yaml
│       ├── HVDC-BACKUP.yaml
│       ├── BAT-BANK-A.yaml
│       └── BAT-BANK-B.yaml
├── mates/
│   ├── grid-mount/           # L1 配合：设备装进方舱
│   │   ├── AI-LIQUID-01-GPU-A01-01~04.yaml
│   │   ├── AI-LIQUID-01-COOL-A01-01.yaml
│   │   ├── GEN-AIR-01-CPU-G01-01~02.yaml
│   │   ├── GEN-AIR-01-STOR-G01-01.yaml
│   │   ├── BAT-01-BAT-BANK-A~B.yaml
│   │   └── POWER-01-HVDC-MAIN~BACKUP.yaml
│   └── power-cable/          # L2 配合：配电→设备供电
│       ├── HVDC-MAIN-GPU-A01-01~02.yaml
│       ├── HVDC-BACKUP-GPU-A01-03~04.yaml
│       ├── HVDC-MAIN-COOL-A01-01.yaml
│       ├── HVDC-MAIN-CPU-G01-01~02.yaml
│       └── HVDC-BACKUP-STOR-G01-01.yaml
├── layouts/
│   └── layout.yaml
└── rules/
    ├── liquid_loop.py
    └── pue.py
```

## 快速体验

```bash
cd samples/02-modular-datacenter
piki check
```

## 跨领域矩阵

| 领域 | piki 概念 | 本示例体现 |
|------|----------|-----------|
| **通信** | 光纤连接、设备功耗、机柜空间 | （本示例聚焦方舱级，通信设备级见 `01-telecom-expansion`） |
| **电力** | 配电单元、N+M 冗余、容量检查 | HVDC-MAIN/BACKUP、BAT-BANK-A/B、连接容量校验 |
| **暖通** | 液冷环路、冷却容量、供液温度 | COOL-A01-01、液冷管路 |
| **建筑** | 方舱空间、承重限制、防火分区 | ContainerFamily 空间边界 + 3D 碰撞检测 |
| **多领域耦合规则** | 跨 Family 查询 | 液冷连接容量 ≥ 方舱冷却需求；电力连接容量 ≥ 方舱 IT 功耗 |

## 你学到了什么

| 能力 | 说明 |
|------|------|
| 多 Family 类型 | Container / Equipment / PowerUnit 三类（datacenter 插件） |
| **Mate 配合图** | `mates/` 目录：grid-mount（L1 机械）+ power-cable（L2 供电） |
| **约束自动验证** | Mate 的 `constrains` 在加载时自动检查 |
| **双向索引遍历** | `ctx.mated_children("AI-LIQUID-01")` 获取所有子设备 |
| PUE 估算 | IT 功耗 + 制冷功耗 + 配电损耗 → 动态 PUE |
| 液冷匹配 | 冷却液流量、供液温度、供回水温差 |
| 配电冗余 | N+M 冗余配置检查（`redundancy_n`） |
| 嵌套项目 | 支持厂区→子区域目录结构（`piki.toml` 递归发现） |
| BOM 生成 | `piki generate dc-bom` 导出 CSV |

## 关联概念

- [ADR-006: Mating Graph](../../docs/adr/006-mating-graph.md)
- [ADR-001: 嵌套项目 + FQID](../../ROADMAP.md)
- [高级用法：多插件协作](../../docs/concepts/03-advanced.md)
