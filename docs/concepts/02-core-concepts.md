# 核心概念

> 理解 piki 的五个核心概念：Family（型号族）、Model（型号）、Instance（实例）、Rule（规则）、Plugin（行业插件）。

## 1. Family：型号族

### 问题

同一类设备（如服务器）有共同属性：都有高度、功耗、重量。但不同型号（Dell R740 vs HP DL380）具体数值不同。如何**统一约束、差异取值**？

### 解决方案：Family 定义约束结构

**Family** 是 pydantic 类，定义"这类设备必须有什么字段、什么类型"：

```python
# piki-telecom 插件定义
class ServerFamily(BaseModel):
    height_u: int = Field(..., ge=1, le=48)
    tdp_w: float = Field(..., gt=0)
    psu_count: int = Field(default=1, ge=1)
```

Family 只约束结构，不提供具体数值。具体数值由 Model 提供。

### 嵌套继承

Family 支持嵌套，越往下约束越具体：

```text
DeviceFamily
  └── ServerFamily
        └── StorageServerFamily
              └── NASFamily
```

```python
class DeviceFamily(BaseModel):
    """所有设备的基类"""
    height_u: int = Field(..., ge=1, le=48)
    weight_kg: float = Field(..., gt=0)

class ServerFamily(DeviceFamily):
    """服务器特有"""
    tdp_w: float = Field(..., gt=0)
    psu_count: int = Field(default=1, ge=1)

class StorageServerFamily(ServerFamily):
    """存储服务器"""
    disk_slots: int = Field(..., ge=1)
    raid_levels: list[str]
```

NASFamily 自动继承所有上级约束：height_u、weight_kg、tdp_w、psu_count、disk_slots、raid_levels。

### 为什么不用数据库的表结构？

| 方式           | 问题                         | Family 方案                    |
| -------------- | ---------------------------- | ------------------------------ |
| 纯 YAML 无约束 | 写错字段类型发现不了         | pydantic 自动校验              |
| 数据库 DDL     | 改结构需迁移，不适合设计迭代 | YAML + pydantic，改文件即生效  |
| 硬编码类       | 每新增型号要改代码           | 插件定义 Family，用户只配 YAML |

## 2. Model：型号

### 问题

Family 只定义了"服务器必须有 height_u 和 tdp_w"，但没说具体是多少。Dell R740 是 2U/350W，HP DL380 是 2U/500W。这些**厂商规格**存在哪里？

### 解决方案：型号库

**Model** 是 Family 的一个具体实现，提供默认值：

```yaml
# library/devices/generic-server.yaml
model: generic-server
family: ServerFamily

physical:
  height_u: 2

power:
  tdp_w: 300
  psu_count: 1
```

```yaml
# library/devices/dell-r740.yaml
model: dell-r740
family: ServerFamily

physical:
  height_u: 2

power:
  tdp_w: 350
  psu_count: 2
```

Model 来自两个来源：

1. **插件自带**：`piki-telecom` 安装时附带常用型号
2. **项目本地**：`library/` 目录下项目自己维护的型号

### Model 与 Family 的关系

```text
Family（约束结构）
  └── Model（默认值）
```

- Family 说"必须有 height_u，范围 1-48"
- Model 说"这台具体是 2U"

## 3. Instance：实例

### 问题

Model 提供了默认值，但实际部署时可能需要覆盖。例如 `generic-server` 默认功耗 300W，但某台实际只有 250W。如何**记录实际值**？

### 解决方案：设计记录

**Instance** 是实际部署的设备，可覆盖 Model 的默认值：

```yaml
# devices/SRV-01.yaml
id: SRV-01
model: generic-server
status: installed
rack_id: RACK-A01
position_u: 10
pdu_id: PDU-A

tdp_w: 250  # 覆盖 Model 默认值 300
```

Instance 只写**决策字段**（放哪、接哪个 PDU），规格字段（height_u、默认 tdp_w）从 Model 自动补齐。

### 三层结构总结

```text
Family（约束结构）
  └── Model（默认值）
        └── Instance（实际值，可覆盖）
```

| 层级 | 定义位置 | 内容 | 示例 |
|------|---------|------|------|
| Family | 插件代码 | 字段约束 | `height_u: int = Field(..., ge=1, le=48)` |
| Model | `library/` YAML | 厂商规格默认值 | `height_u: 2` |
| Instance | 数据目录 YAML | 实际部署值 | `position_u: 10`、`tdp_w: 250` |

### 解析过程

piki 加载 Instance 时自动解析：

```python
# 伪代码
family = registry.get_family("ServerFamily")      # 约束校验
model = registry.get_model("generic-server")      # 默认值
instance = load_yaml("devices/SRV-01.yaml")       # 实际值

resolved = {**model, **instance}                  # 实例覆盖默认值
family.validate(resolved)                         # 校验是否合规
```

## 4. Rule：规则

### 问题

Family 的 pydantic 约束只能检查**单条记录**的字段类型和范围。但很多问题需要**跨记录关联**：PDU 总功率、机柜 U 位冲突、线缆长度。

### 解决方案：pytest 风格的规则

```python
# rules/power.py
from piki import rule, Context

@rule("TELECOM-POWER-001", "PDU 功率预算检查")
def check_pdu_budget(ctx: Context):
    """
    检查每个 PDU 的负载率不超过阈值。

    失败示例：
        PDU-A 额定 2000W，已安装 550W，新增 400W 后 950W
        负载率 47.5%，超过项目阈值 40%
    """
    for pdu in ctx.query("pdus"):
        devices = ctx.query("devices", pdu_id=pdu.id)
        total_power = sum(d.resolved.tdp_w for d in devices)
        load_ratio = total_power / pdu.resolved.capacity_w

        threshold = ctx.config.get("power_threshold", 0.8)
        assert load_ratio <= threshold, (
            f"{pdu.id} 负载率 {load_ratio:.1%}，"
            f"超过阈值 {threshold:.1%}"
        )
```

### 规则的四层分类

| 层级 | 检查内容       | 示例                        | 实现方式           |
| ---- | -------------- | --------------------------- | ------------------ |
| L0   | 文件格式合法性 | 输入必须是合法的 YAML/JSON  | 解析器异常         |
| L1   | 字段类型/范围  | height_u 必须是 1-48 的整数 | pydantic Field     |
| L2   | 单记录完整性   | rack_id 引用的机柜必须存在  | pydantic validator |
| L3   | 跨记录业务规则 | PDU 总功率不超阈值          | pytest 函数        |

### Context 对象

规则通过 `Context` 访问数据和配置：

```python
@rule("TELECOM-RACK-001", "U 位冲突检查")
def check_rack_space(ctx: Context):
    # 查询数据
    racks = ctx.query("racks")
    devices = ctx.query("devices")

    # 读取配置
    threshold = ctx.config.get("rack_usage_threshold", 0.8)

    # 访问已解析的实例（含 Model 默认值）
    for device in devices:
        height = device.resolved.height_u    # 从 Model 解析的值
```

## 5. Plugin：行业插件

### 问题

不同行业需要不同的 Family 和规则。电信/数据中心需要机柜、PDU、光纤；建筑需要房间、楼层、暖通。如何**扩展而不修改核心**？

### 解决方案：插件机制

```text
piki-core（框架）
  └── piki-telecom（电信插件）
        ├── families/          # Family 定义
        │   ├── device.py
        │   ├── rack.py
        │   └── cable.py
        ├── rules/             # 行业通用规则
        │   ├── power.py
        │   ├── rack_space.py
        │   └── cable_length.py
        └── library/           # 默认型号库
            └── devices/
                └── generic-server.yaml
```

插件就是一个 Python 包，安装后自动注册：

```python
# piki_telecom/plugin.py
from piki import Plugin

class TelecomPlugin(Plugin):
    name = "telecom"
    version = "1.0.0"

    def register_families(self, registry):
        registry.add("ServerFamily", ServerFamily)
        registry.add("RackFamily", RackFamily)
        registry.add("CableFamily", CableFamily)

    def register_rules(self, checker):
        checker.add("TELECOM-POWER-001", check_pdu_budget)
        checker.add("TELECOM-RACK-001", check_rack_space)
        checker.add("TELECOM-CABLE-001", check_cable_length)

    def register_generators(self, checker):
        """注册导出器：BOM、面板图、标签等"""
        checker.add_generator("bom", "BOM 导出", export_bom)
        checker.add_generator("panel-diagram", "面板图导出", export_panel)
        checker.add_generator("cable-labels", "线缆标签导出", export_cable_labels)
```

### 插件发现

piki 自动发现已安装的插件：

```bash
pip install piki-telecom piki-construction
piki plugins list
# telecom      1.0.0    电信/数据中心
# construction 0.5.0    建筑工程
```

项目配置选择启用哪些：

```toml
# piki.toml — 项目元数据文件
[project]
name = "my-datacenter"
version = "1.0.0"

[plugins]
enabled = ["telecom"]
```

`piki.toml` 的核心作用：

| 声明项 | 说明 | 示例 |
|--------|------|------|
| 项目根目录 | piki 从该文件位置开始扫描 | `piki.toml` 所在目录 |
| 行业插件 | 启用哪些插件，加载对应的 Family 和 Rule | `enabled = ["telecom"]` |
| 型号库 | 插件自带 + 本地 `library/` 的型号 | 自动扫描，无需显式列出 |
| 项目配置 | 阈值、格式等参数 | `power_threshold = 0.4`，`rack_usage_threshold = 0.8` |

## 概念关系图

```text
┌─────────────────────────────────────────────────────────────┐
│                    Plugin（行业插件）                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Family    │  │    Rule     │  │      Library        │  │
│  │  （约束结构） │  │ （业务检查） │  │    （型号默认值）    │  │
│  │  ServerFamily│  │PDU功率检查  │  │ generic-server.yaml │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         └────────────────┼─────────────────────┘             │
│                          │                                   │
│                          ▼                                   │
│                   ┌─────────────┐                            │
│                   │   Registry  │  ← 运行时录入和查找机制      │
│                   │  （中央目录） │                            │
│                   └──────┬──────┘                            │
│                          │                                   │
│         ┌────────────────┼────────────────┐                  │
│         │                │                │                  │
│         ▼                ▼                ▼                  │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Instance  │  │   Generator  │  │    Report    │         │
│  │  设计记录   │  │  BOM/面板图/标签│  │   检查报告    │         │
│  │ SRV-01.yaml│  │  export_bom() │  │  piki check  │         │
│  └────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

Registry 是内部机制：负责加载 Model、注册 Family、解析 Instance。用户不直接操作 Registry，只写 Instance YAML 和 Rule Python。

Generator 是插件注册的导出函数，通过 `piki generate` 调用。

## 加载顺序

```text
1. 加载插件 → 注册 Family 和 Rule
2. 扫描 library/ → 注册 Model
3. 扫描数据目录 → 加载 Instance
4. 解析 Instance 时：
   - 用 family 找到 Family 类（约束）
   - 用 model 找到 Model 数据（默认值）
   - 实例字段覆盖默认值
```

## 下一步

- [学习写规则 →](03-writing-rules.md)
