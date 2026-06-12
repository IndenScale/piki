# 06-nested-project — 嵌套项目

> 厂区级项目 → 安全壳内 / 安全壳外 子项目。
> 演示 ADR-009 核心特性：嵌套项目、继承、Tag、FQID。

## 场景

一个厂区包含两个物理安全分区：

- **安全壳内**：抗震等级 9 度，需屏蔽保护
- **安全壳外**：抗震等级 7 度，标准办公环境

两台通用服务器（SRV-01、SRV-02）在根项目定义，可在子项目中引用部署。

## 项目结构（ADR-009 §2.3）

```
厂区/                              ← 根项目
├── piki.toml                      ← 全厂配置 + Tag 声明
├── models/                       ← 全厂共享型号
│   └── devices/
│       ├── generic-server.yaml
│       └── pump.yaml
├── instances/                     ← 全厂共享设备身份
│   ├── SRV-01.yaml
│   └── SRV-02.yaml
│
├── 安全壳内/                      ← 子项目（抗震 9 度）
│   ├── piki.toml                  ← 覆盖参数
│   ├── instances/                 ← 壳内特有设备
│   │   └── PUMP-01.yaml
│   └── layouts/
│       └── building-a/
│           └── floor-2/
│               └── layout.yaml    ← 引用根项目 SRV-01 + 自有 PUMP-01
│
└── 安全壳外/                      ← 子项目（抗震 7 度）
    ├── piki.toml                  ← 覆盖参数
    ├── instances/                 ← 壳外特有设备
    │   └── SRV-03.yaml
    └── layouts/
        └── layout.yaml            ← 引用根项目 SRV-02 + 自有 SRV-03
```

## 关键设计

### 继承（ADR-009 §1.2）

子项目自动可见父项目的所有型号和 Instance：

```yaml
# 安全壳内/layouts/building-a/floor-2/layout.yaml
- instance: SRV-01          # SRV-01 在根项目 instances/ 中定义
  rack_id: RACK-C01
  position_u: 10
  pdu_id: PDU-C1

- instance: PUMP-01         # PUMP-01 在安全壳内/instances/ 中定义
  grid_id: B-3
  position_x_mm: 1500
  position_y_mm: 3000
```

### Tag 机制（ADR-009 §3）

Instance 使用 Tag 表示正交维度：

```yaml
# 安全壳内/instances/PUMP-01.yaml
id: PUMP-01
name: 安全壳冷却泵-01
model: pump
tdp_w: 180
tags:
  discipline: hvac               # 暖通设备
  security_zone: containment     # 安全壳内
  system: cooling                # 冷却系统
```

### FQID（ADR-009 §6.2）

全限定 ID 自动生成：

```
SRV-01  → 厂区/SRV-01
PUMP-01 → 厂区/安全壳内/PUMP-01
SRV-03  → 厂区/安全壳外/SRV-03
```

## 运行

```bash
cd samples/06-nested-project
piki check
```

## 你学到了什么

| 能力 | 说明 |
|------|------|
| 嵌套项目 | 根项目 → 子项目的层级关系 |
| 继承 | 子项目可见父项目型号和 Instance |
| 参数覆盖 | 子项目 `piki.toml` 覆盖父项目配置 |
| Tag 机制 | `discipline`, `security_zone`, `system` 正交维度标签 |
| FQID | 全限定 ID 避免跨层级命名冲突 |
| Layout 不继承 | 每个子项目有独立的 Layout 文件 |
