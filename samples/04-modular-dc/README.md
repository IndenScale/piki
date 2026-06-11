# 04-modular-dc — 模块化数据中心示例

> ⭐⭐⭐⭐ 高级示例：集装箱式模块化机房，面向智算/通算/储能/配电全场景。

## 场景

你负责一个模块化数据中心项目，场地部署了 4 个标准集装箱方舱：

| 方舱 | 类型 | 标准 | 配电容量 | 制冷容量 | 状态 |
|------|------|------|----------|----------|------|
| AI-LIQUID-01 | 智算液冷 | 40ft | 500kW | 550kW | 运营中 |
| GEN-AIR-01 | 通算风冷 | 40ft | 300kW | 320kW | 运营中 |
| BAT-01 | 锂电储能 | 20ft | 1000kW | 50kW | 运营中 |
| POWER-01 | 配电 | 20ft | 2000kW | 30kW | 运营中 |

### 设备部署

**智算液冷方舱（AI-LIQUID-01）**：
- 4 台 GPU 服务器（每台 12kW，液冷）
- 1 台列间液冷空调（8kW）

**通算风冷方舱（GEN-AIR-01）**：
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
├── piki.toml                    # 项目配置
├── containers/                  # 方舱数据
│   ├── AI-LIQUID-01.yaml        # 智算液冷方舱
│   ├── GEN-AIR-01.yaml          # 通算风冷方舱
│   ├── BAT-01.yaml              # 锂电储能方舱
│   └── POWER-01.yaml            # 配电方舱
├── power/                       # 配电单元
│   ├── HVDC-MAIN.yaml           # 主路 HVDC
│   ├── HVDC-BACKUP.yaml         # 备路 HVDC
│   ├── BAT-BANK-A.yaml          # 锂电组 A
│   └── BAT-BANK-B.yaml          # 锂电组 B
├── equipment/                   # 设备
│   ├── GPU-A01-01~04.yaml       # GPU 服务器
│   ├── COOL-A01-01.yaml         # 列间空调
│   ├── CPU-G01-01~02.yaml       # CPU 服务器
│   └── STOR-G01-01.yaml         # 存储节点
├── connections/                 # 方舱间连接
│   ├── LIQUID-AI-GEN.yaml       # 液冷管路
│   ├── POWER-P01-AI.yaml        # 供电电缆→智算
│   ├── POWER-P01-GEN.yaml       # 供电电缆→通算
│   └── POWER-BAT-P01.yaml       # 供电电缆→储能
└── rules/                       # 项目自定义规则
    ├── pue.py                   # PUE 估算检查
    └── liquid_loop.py           # 液冷环路流量匹配
```

## 运行检查

```bash
cd samples/04-modular-dc
piki check
```

预期输出：

```
[PASS] DC-POWER-001: 方舱功率预算检查
[PASS] DC-COOLING-001: 液冷方舱制冷容量检查
[PASS] DC-CONN-001: 连接完整性检查
[PASS] DC-FK-001: 外键完整性检查
[PASS] DC-LIQUID-001: 液冷环路流量匹配检查
[PASS] DC-WEIGHT-001: 方舱总重检查
[PASS] DC-CONN-002: 连接容量检查
[PASS] DC-REDUNDANCY-001: 配电冗余检查
[PASS] DC-PUE-001: PUE 估算检查
============================================================
总计: 0 错误, 9 通过
============================================================
```

## 故意触发功率超载

在 AI-LIQUID-01 中添加更多 GPU 服务器，使总功率超过 500kW × 85% = 425kW：

```yaml
# equipment/GPU-A01-05.yaml
id: GPU-A01-05
name: 智算节点-A01-05
model: gpu-server
equipment_type: compute
container_id: AI-LIQUID-01
power_unit_id: HVDC-MAIN
power_kw: 12
...
```

当前 AI-LIQUID-01 已有 5 台 GPU（60kW）+ 1 台空调（8kW）= 68kW，远低于 425kW。要触发超载需要添加约 30 台 GPU。

## 故意触发制冷不足

把 AI-LIQUID-01 的 `cooling_capacity_kw` 改小：

```yaml
# containers/AI-LIQUID-01.yaml
cooling_capacity_kw: 50   # 当前液冷设备热负荷 68kW
```

制冷检查会失败。

## 故意触发冗余不足

把 HVDC-MAIN 的 `redundancy_n` 改成 1：

```yaml
# power/HVDC-MAIN.yaml
redundancy_n: 1   # 项目要求 N+1（即 redundancy_n >= 2）
```

冗余检查会失败。

## 生成 BOM 报告

```bash
piki generate dc-bom-csv --output dc-bom.csv
cat dc-bom.csv
```

## 与 telecom 插件的对比

| 维度 | telecom | datacenter |
|------|---------|------------|
| 管理对象 | 机柜(Rack) | 方舱(Container) |
| 配电单元 | PDU（机柜级） | PowerUnit（方舱级/系统级） |
| 设备 | Server（U位+PDU） | Equipment（功耗+重量+液冷参数） |
| 连接 | 无 | Connection（液冷/电力/光纤） |
| 检查重点 | U位冲突、PDU功率 | 方舱功率预算、制冷容量、重量、连接完整性 |
| 适用场景 | 传统机房、电信设备 | 模块化数据中心、集装箱部署、智算中心 |

## 你学到了什么

| 能力 | 说明 |
|------|------|
| 多插件共存 | `telecom` 和 `datacenter` 可同时启用，管理不同粒度的资源 |
| 方舱级管理 | 集装箱作为部署单元，包含配电、制冷、设备 |
| 连接建模 | 方舱间管线/电缆/光纤用 `ConnectionFamily` 建模 |
| 液冷参数 | `liquid_cooled`、`coolant_flow_lpm` 等字段支持液冷场景 |
| 自定义 PUE | 项目规则可以根据 IT 功耗和制冷功耗估算 PUE |
| 冗余配置 | `redundancy_n` 字段 + 规则检查配电冗余策略 |
