# 编写检查规则

> 从实际问题出发，学习如何为声明式设计编写校验规则。
>
> 规则是声明式建模的"守卫"：你声明设计意图，规则确保意图合理。

## 规则的本质

规则是**用代码表达的业务知识**。例如：

- "PDU 负载不能超过 80%" → 功率规则
- "同一 U 位不能放两台设备" → 空间规则
- "光纤跳线长度不能超过 50 米" → 线缆规则

piki 的规则用 Python 编写，pytest 风格。你不需要学习新语法，只要会写 Python 函数。

## 示例 1：PDU 功率预算

### 问题

机柜 `RACK-A01` 有两路 PDU：PDU-A（2000W）和 PDU-B（2000W）。已有设备：

| 设备   | PDU   | 功耗 |
| ------ | ----- | ---- |
| SRV-01 | PDU-A | 300W |
| SRV-02 | PDU-A | 250W |

新增 `SRV-03`（400W）接 PDU-A，总负载 950W，负载率 47.5%。虽然物理上安全，但项目规定预留 60% 余量（即负载率不超过 40%）。

### 规则代码

```python
# rules/power.py
from piki import rule, Context

@rule("TELECOM-POWER-001", "PDU 功率预算检查")
def check_pdu_budget(ctx: Context):
    """
    检查每个 PDU 的负载率不超过项目阈值。

    遍历所有 PDU，统计接入该 PDU 的设备总功耗，
    计算负载率并与阈值比较。
    """
    threshold = ctx.config.get("power_threshold", 0.8)

    for pdu in ctx.query("pdus"):
        # 找到所有接入该 PDU 的设备
        devices = ctx.query("devices", pdu_id=pdu.id)

        # 计算总功耗（使用 resolved 值，含 Model 默认值）
        total_power = sum(d.resolved.tdp_w for d in devices)
        load_ratio = total_power / pdu.resolved.capacity_w

        assert load_ratio <= threshold, (
            f"{pdu.id} 负载率 {load_ratio:.1%}（{total_power}W / {pdu.resolved.capacity_w}W），"
            f"超过项目阈值 {threshold:.1%}。"
            f"已接入设备: {', '.join(d.id for d in devices)}"
        )
```

### 运行结果

```bash
$ piki check
[FAIL] TELECOM-POWER-001: PDU 功率预算检查
       PDU-A 负载率 47.5%（950W / 2000W），超过项目阈值 40%。
       已接入设备: SRV-01, SRV-02, SRV-03
       文件: devices/SRV-03.yaml
       建议: 考虑分配到 PDU-B，或申请扩容 PDU 容量
```

### 关键技巧

1. **用 `ctx.query` 获取数据**：支持按条件过滤和链式操作
2. **用 `resolved` 访问解析后的值**：自动包含 Model 默认值
3. **用 `assert` 表达断言**：失败时自动输出详细信息
4. **用 `ctx.config` 读取配置**：阈值等参数可配置

## 查询语法速查

`ctx.query(collection, **filters)` 支持 Django-style 双下划线操作符：

| 操作符 | 含义 | 示例 |
|--------|------|------|
| （默认） | 等值 | `ctx.query("devices", rack_id="RACK-A01")` |
| `__ne` | 不等 | `ctx.query("devices", status__ne="retired")` |
| `__gt` | 大于 | `ctx.query("devices", tdp_w__gt=300)` |
| `__gte` | 大于等于 | `ctx.query("devices", tdp_w__gte=100)` |
| `__lt` | 小于 | `ctx.query("devices", position_u__lt=20)` |
| `__lte` | 小于等于 | `ctx.query("devices", height_u__lte=4)` |
| `__in` | 在列表中 | `ctx.query("devices", rack_id__in=["A01","A02"])` |
| `__contains` | 包含 | `ctx.query("devices", name__contains="DB")` |
| `__startswith` | 前缀 | `ctx.query("devices", id__startswith="SRV-")` |
| `__endswith` | 后缀 | `ctx.query("devices", id__endswith="-PROD")` |

链式操作（返回 QuerySet）：

```python
devices = (
    ctx.query("devices", rack_id__in=["A01", "A02"])
    .filter(tdp_w__gt=200)
    .exclude(status="retired")
    .order_by("position_u")
    .limit(10)
)
```

终结操作：

```python
ctx.query("devices").count()                    # 数量
ctx.query("devices", rack_id="A01").first()     # 第一条
ctx.query("devices").values("id", "tdp_w")      # dict 列表
ctx.query("devices").group_by("rack_id")        # 按机柜分组
ctx.query("devices").aggregate(                 # 聚合计算
    total_power=lambda items: sum(d.tdp_w for d in items),
    count=len,
)
```

## 示例 2：U 位冲突检查

### 问题

两台设备不能占用同一个 U 位。例如 `SRV-01`（2U，U10-U11）和 `SRV-02`（2U，U8-U9）不冲突，但如果 `SRV-03` 也放在 U10，就冲突了。

### 规则代码

```python
# rules/rack_space.py
from piki import rule, Context

@rule("TELECOM-RACK-001", "U 位冲突检查")
def check_rack_space(ctx: Context):
    """
    检查同一机柜内没有 U 位重叠的设备。
    """
    for rack in ctx.query("racks"):
        devices = ctx.query("devices", rack_id=rack.id)

        # 计算每个设备占用的 U 位范围
        occupied = []  # [(start_u, end_u, device_id), ...]
        for d in devices:
            height = d.resolved.height_u
            start = d.position_u
            end = start + height - 1
            occupied.append((start, end, d.id))

        # 检查重叠
        for i, (s1, e1, id1) in enumerate(occupied):
            for s2, e2, id2 in occupied[i+1:]:
                if not (e1 < s2 or e2 < s1):  # 有重叠
                    overlap_start = max(s1, s2)
                    overlap_end = min(e1, e2)
                    assert False, (
                        f"机柜 {rack.id} U{overlap_start}-U{overlap_end} 冲突: "
                        f"{id1}（U{s1}-U{e1}）与 {id2}（U{s2}-U{e2}）"
                    )
```

### 运行结果

```bash
[FAIL] TELECOM-RACK-001: U 位冲突检查
       机柜 RACK-A01 U10-U11 冲突: SRV-01（U10-U11）与 SRV-03（U10-U11）
       文件: devices/SRV-03.yaml
```

## 示例 3：线缆长度检查

### 问题

光纤跳线有最大长度限制。例如 OM3 多模光纤在 10Gbps 下最大传输距离 300 米。如果设计中的线缆长度超过限制，需要报错。

### 规则代码

```python
# rules/cable.py
from piki import rule, Context

@rule("TELECOM-CABLE-001", "线缆长度检查")
def check_cable_length(ctx: Context):
    """
    检查线缆长度不超过该类型/速率下的最大传输距离。
    """
    # 类型-速率-最大距离映射（可从配置或标准库加载）
    max_distance = {
        ("OM3", "10G"): 300,
        ("OM4", "10G"): 400,
        ("OM4", "40G"): 150,
        ("SM", "100G"): 10000,
    }

    for cable in ctx.query("cables"):
        cable_type = cable.resolved.cable_type
        speed = cable.resolved.speed
        length = cable.length_m

        key = (cable_type, speed)
        if key in max_distance:
            max_len = max_distance[key]
            assert length <= max_len, (
                f"线缆 {cable.id} 长度 {length}m 超过 {cable_type}@{speed} "
                f"最大距离 {max_len}m"
            )
```

## 示例 4：跨表引用完整性

### 问题

设备的 `rack_id` 必须引用一个真实存在的机柜，`pdu_id` 必须引用一个真实存在的 PDU。

### 规则代码

```python
# rules/integrity.py
from piki import rule, Context

@rule("TELECOM-INTG-001", "外键完整性检查")
def check_foreign_keys(ctx: Context):
    """
    检查所有外键引用有效。
    """
    racks = {r.id for r in ctx.query("racks")}
    pdus = {p.id for p in ctx.query("pdus")}

    for device in ctx.query("devices"):
        assert device.rack_id in racks, (
            f"设备 {device.id} 引用的机柜 {device.rack_id} 不存在"
        )
        assert device.pdu_id in pdus, (
            f"设备 {device.id} 引用的 PDU {device.pdu_id} 不存在"
        )
```

## 规则的组织

### 按主题分组

```text
rules/
├── __init__.py
├── power.py          # 功率相关
├── rack_space.py     # 机柜空间
├── cable.py          # 线缆
├── integrity.py      # 数据完整性
└── custom/           # 项目特有规则
    └── __init__.py
```

### 规则优先级

```python
@rule("TELECOM-POWER-001", "PDU 功率预算检查", priority=1)
def check_pdu_budget(ctx: Context):
    """priority 越高越先执行"""
    ...
```

### 跳过规则

```bash
# 跳过特定规则（功能待实现）
piki check --skip TELECOM-POWER-001

# 只运行特定规则（功能待实现）
piki check --only TELECOM-RACK-001
```

## 规则最佳实践

1. **一条规则只做一件事**：不要一个函数检查功率又检查 U 位
2. **错误信息要具体**：指出具体设备、具体数值、具体建议
3. **用配置代替硬编码**：阈值、映射表放到 `piki.toml`
4. **给规则写文档**：docstring 说明检查什么、什么情况下失败
5. **规则 ID 要有规律**：`{行业}-{主题}-{序号}`，如 `TELECOM-POWER-001`

## 下一步

- [高级用法 →](04-advanced.md)
