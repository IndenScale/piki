# 03-data-center — 多机柜数据中心示例

> 进阶示例：多机柜、多型号、自定义规则、报告生成。

## 场景

你管理一个中型数据中心，有 3 个机柜分布在 A/B 两列：

| 机柜 | 位置 | 配电容量 | 设备数 |
|------|------|----------|--------|
| RACK-A01 | 机房A-A列 | 5000W | 3 台 |
| RACK-A02 | 机房A-A列 | 5000W | 1 台 |
| RACK-B01 | 机房A-B列 | 5000W | 1 台 |

每个机柜配两路 PDU（主路 L1 + 备路 L2），容量各 3000W。

设备型号：
- `generic-server`：2U，300W，双 PSU 冗余
- `high-density-server`：4U，800W，双 PSU 冗余（存储节点）

## 项目结构

```
03-data-center/
├── piki.toml                    # 项目配置 + 自定义规则开关
├── library/
│   └── devices/
│       ├── generic-server.yaml      # 通用服务器型号
│       └── high-density-server.yaml # 高密度服务器型号
├── racks/
│   ├── RACK-A01.yaml
│   ├── RACK-A02.yaml
│   └── RACK-B01.yaml
├── pdus/
│   ├── PDU-A01-L1.yaml          # A01 主路
│   ├── PDU-A01-L2.yaml          # A01 备路
│   ├── PDU-A02-L1.yaml          # A02 主路
│   ├── PDU-A02-L2.yaml          # A02 备路
│   ├── PDU-B01-L1.yaml          # B01 主路
│   └── PDU-B01-L2.yaml          # B01 备路
├── devices/
│   ├── SRV-A01-01.yaml          # A01 计算节点
│   ├── SRV-A01-02.yaml          # A01 计算节点
│   ├── SRV-A01-03.yaml          # A01 存储节点（高密度）
│   ├── SRV-A02-01.yaml          # A02 计算节点
│   └── SRV-B01-01.yaml          # B01 计算节点（计划中）
└── rules/
    ├── naming.py                # 自定义规则：命名规范
    ├── redundancy.py            # 自定义规则：冗余策略
    └── cross_rack.py            # 自定义规则：跨机柜负载均衡
```

## 运行检查

```bash
cd samples/03-data-center
piki check
```

预期输出：

```
[PASS] TELECOM-POWER-001: PDU 功率预算检查
[PASS] TELECOM-RACK-001: U 位冲突检查
[PASS] TELECOM-RACK-002: 机柜容量检查
[PASS] TELECOM-FK-001: 外键完整性检查
[PASS] DC-NAMING-001: 设备命名规范检查
[PASS] DC-REDUNDANCY-001: 关键设备冗余检查
[WARN] DC-BALANCE-001: 机柜负载均衡检查
       A 列机柜负载不均衡：最多 3 台，最少 1 台，差异超过 2 台
============================================================
总计: 0 错误, 1 警告, 6 通过
============================================================
```

## 自定义规则详解

### 1. 命名规范（naming.py）

检查设备 ID 是否符合 `SRV-<机柜>-<序号>` 格式：

```python
@rule("DC-NAMING-001", "设备命名规范检查")
def check_device_naming(ctx: Context) -> None:
    pattern = re.compile(r"^SRV-[A-Z]\d{2}-\d{2}$")
    for device in ctx.query("devices"):
        assert pattern.match(device.id), "..."
```

**故意触发**：把某个设备的 `id` 改成 `server-01`，命名检查会失败。

### 2. 冗余策略（redundancy.py）

检查关键设备（`high-density-server`）是否具备 PSU 冗余：

```python
@rule("DC-REDUNDANCY-001", "关键设备冗余检查")
def check_critical_device_redundancy(ctx: Context) -> None:
    if not ctx.config.get("min_pdu_redundancy", False):
        return  # 配置关闭时跳过
    # ...
```

**注意**：此规则受 `piki.toml` 中的 `min_pdu_redundancy` 配置控制。设为 `false` 则跳过检查。

### 3. 跨机柜负载均衡（cross_rack.py）

检查同一列机柜的设备数量差异：

```python
@rule("DC-BALANCE-001", "机柜负载均衡检查")
def check_rack_load_balance(ctx: Context) -> None:
    # A 列有 RACK-A01(3台) 和 RACK-A02(1台)，差异 = 2
    # 当前差异 = 2，刚好等于阈值，所以通过
```

**故意触发**：在 A02 再添加 2 台设备，差异变成 3，检查会失败。

## 生成报告

```bash
# Markdown 格式
piki report --format markdown

# JSON 格式
piki check --format json

# BOM CSV
piki generate bom-csv --output bom.csv
```

## 你学到了什么

| 能力 | 说明 |
|------|------|
| 多型号库 | `library/` 可定义多个型号，不同设备引用不同型号 |
| 自定义规则 | `rules/` 下的 Python 文件自动加载，使用 `@rule` 装饰器 |
| 规则配置 | `piki.toml [rules]` 节可配置规则的开关和参数 |
| 跨集合查询 | `ctx.query()` 支持按条件过滤和跨集合关联 |
| 报告生成 | 内置多种输出格式，支持自定义生成器 |
