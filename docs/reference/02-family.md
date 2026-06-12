# Family 定义格式

> Family 是 piki 的**约束层**——定义"这类设备必须有什么字段、什么类型"。
>
> Family 只能用 **Python pydantic 类**定义，通过插件注册到 piki。不支持 YAML 或其他配置文件方式。

## 为什么必须用 pydantic

Family 定义的是**领域模型的约束结构**，不是数据：

| 需求 | YAML 能否表达 | pydantic 能否表达 |
|------|--------------|------------------|
| 字段类型（int/str/float） | ✅ | ✅ |
| 数值范围（ge/le/gt/lt） | ✅ | ✅ |
| 正则匹配 | ⚠️ 有限 | ✅ 完整 |
| 条件约束（if A then B） | ❌ | ✅ `model_validator` |
| 跨字段校验 | ❌ | ✅ 自定义校验器 |
| 嵌套模型 | ❌ 复杂 | ✅ `BaseModel` 嵌套 |
| IDE 类型提示 | ❌ | ✅ |
| 调试堆栈跟踪 | ❌ | ✅ |

**Family 是代码，不是配置。** 像 Kubernetes CRD 那样的 YAML Schema 需要完整的 OpenAPI 生态和运行时校验器，piki 不重新发明这套基础设施。

## 基本结构

```python
# src/piki/extensions/telecom/plugin.py
from pydantic import BaseModel, Field

class ServerFamily(BaseModel):
    id: str = Field(...)
    name: str = Field(default="")
    model: str = Field(default="")
    status: str = Field(default="planned")

    # 物理规格
    height_u: int = Field(default=2, ge=1, le=48)
    depth_mm: float = Field(default=0, ge=0)
    width_mm: float = Field(default=0, ge=0)
    height_mm: float = Field(default=0, ge=0)
    weight_kg: float = Field(default=0, ge=0)

    # 电源规格
    tdp_w: float = Field(default=300, gt=0)
    psu_count: int = Field(default=1, ge=1)
    psu_redundancy: bool = Field(default=False)
```

## 字段约束

pydantic `Field()` 支持的常用约束：

| 参数 | 说明 | 示例 |
|------|------|------|
| `default` | 默认值 | `Field(default="planned")` |
| `default_factory` | 动态默认值 | `Field(default_factory=list)` |
| `ge` | ≥ 最小值 | `Field(ge=1)` |
| `gt` | > 最小值 | `Field(gt=0)` |
| `le` | ≤ 最大值 | `Field(le=48)` |
| `lt` | < 最大值 | `Field(lt=1000)` |
| `min_length` | 最小长度 | `Field(min_length=1)` |
| `max_length` | 最大长度 | `Field(max_length=64)` |
| `pattern` | 正则匹配 | `Field(pattern=r"^SRV-[A-Z0-9]+")` |
| `json_schema_extra` | 额外元数据 | 见下文"不可覆盖字段" |

## 不可覆盖字段

物理尺寸字段应标记为 `non_overridable`，防止 Instance 覆盖导致几何碰撞失效：

```python
from pydantic import BaseModel, Field

class ServerFamily(BaseModel):
    # ... 其他字段 ...

    height_u: int = Field(
        default=2, ge=1, le=48,
        json_schema_extra={"piki_non_overridable": True}
    )
    depth_mm: float = Field(
        default=0, ge=0,
        json_schema_extra={"piki_non_overridable": True}
    )
    width_mm: float = Field(
        default=0, ge=0,
        json_schema_extra={"piki_non_overridable": True}
    )
    weight_kg: float = Field(
        default=0, ge=0,
        json_schema_extra={"piki_non_overridable": True}
    )
```

当 Instance 试图覆盖这些字段时，piki 报错：

```
[ERROR] SCHEMA-002: Instance 'SRV-01' 试图覆盖不可覆盖字段 'height_u'（值=4）。
        物理尺寸字段不允许 Instance 覆盖，请在 Model 中设置或保持默认值。
```

## 条件约束（model_validator）

用 pydantic `model_validator` 表达字段间的条件关系：

```python
from pydantic import BaseModel, Field, model_validator

class ServerFamily(BaseModel):
    psu_count: int = Field(default=1, ge=1)
    psu_redundancy: bool = Field(default=False)

    @model_validator(mode="after")
    def check_redundancy(self):
        if self.psu_redundancy and self.psu_count < 2:
            raise ValueError(
                f"启用 PSU 冗余时 psu_count 必须 >= 2，当前为 {self.psu_count}"
            )
        return self
```

## 嵌套模型

复杂结构用嵌套 `BaseModel`：

```python
from pydantic import BaseModel, Field

class NetworkPort(BaseModel):
    name: str
    speed_gbps: int = Field(ge=1)
    port_type: str = Field(default="RJ45")  # RJ45 / SFP+ / QSFP28

class NetworkFamily(BaseModel):
    id: str
    name: str = ""
    port_count: int = Field(default=24, ge=1, le=128)
    ports: list[NetworkPort] = Field(default_factory=list)
```

## 注册到插件

Family 通过插件的 `register_families` 方法注册：

```python
from piki.core.plugin import Plugin
from piki.core.engine.registry import Registry

class TelecomPlugin(Plugin):
    name = "telecom"
    version = "0.1.0"

    def register_families(self, registry: Registry) -> None:
        registry.add_family("RackFamily", RackFamily)
        registry.add_family("PduFamily", PduFamily)
        registry.add_family("ServerFamily", ServerFamily)
```

## 项目需要扩展 Family 怎么办

**Family 是领域共识，不应被单个项目随意扩展。**

| 场景 | 正确做法 |
|------|---------|
| 该字段是**领域通用需求**（如所有服务器都有 BMC） | 提 Issue / PR 修改插件，或 fork 插件 |
| 该字段是**项目特有需求**（只有这个项目用） | 用 `tags` 或 `extra` 字段表达，不改 Family |
| 需要全新的设备类型 | 开发新插件，或扩展现有插件 |

用 tags 表达项目特有信息：

```yaml
# instances/SRV-01.yaml
id: SRV-01
family: ServerFamily
model: generic-server

tags:
  bmc_ip: "192.168.1.100"
  bmc_user: "admin"
```

## 最佳实践

1. **每个 Family 一个独立的 pydantic 类**：不要在一个类里混合不同设备类型
2. **物理尺寸标记 `piki_non_overridable`**：防止 Instance 覆盖导致几何碰撞失效
3. **写 docstring**：帮助其他开发者理解 Family 的用途
4. **用 `model_validator` 表达条件约束**：如"冗余时必须 >=2 个 PSU"
5. **嵌套模型组织复杂结构**：如网络端口的列表
6. **字段命名一致**：同一概念在不同 Family 中用相同字段名（如都用 `weight_kg` 不用 `mass_kg`）

## 完整示例

```python
"""piki-telecom 插件的 Family 定义。"""

from pydantic import BaseModel, Field


class RackFamily(BaseModel):
    """机柜 Family：标准 19 英寸机柜。"""

    id: str = Field(...)
    name: str = Field(default="")
    location: str = Field(default="")
    total_u: int = Field(..., ge=1, le=48)
    power_capacity_w: float = Field(default=0, ge=0)

    # 物理尺寸（毫米）
    depth_mm: float = Field(default=0, ge=0)
    width_mm: float = Field(default=0, ge=0)
    height_mm: float = Field(default=0, ge=0)


class PduFamily(BaseModel):
    """PDU Family：电源分配单元。"""

    id: str = Field(...)
    name: str = Field(default="")
    rack_id: str = Field(default="")
    phase: str = Field(default="L1")
    capacity_w: float = Field(..., gt=0)


class ServerFamily(BaseModel):
    """服务器 Family：通用机架式服务器。"""

    id: str = Field(...)
    name: str = Field(default="")
    model: str = Field(default="")
    status: str = Field(default="planned")
    rack_id: str = Field(default="")
    position_u: int = Field(default=1, ge=1, le=48)
    pdu_id: str = Field(default="")

    # 物理规格（不可覆盖）
    height_u: int = Field(
        default=2, ge=1, le=48,
        json_schema_extra={"piki_non_overridable": True}
    )
    depth_mm: float = Field(
        default=0, ge=0,
        json_schema_extra={"piki_non_overridable": True}
    )
    width_mm: float = Field(
        default=0, ge=0,
        json_schema_extra={"piki_non_overridable": True}
    )
    weight_kg: float = Field(
        default=0, ge=0,
        json_schema_extra={"piki_non_overridable": True}
    )

    # 电源规格
    tdp_w: float = Field(default=300, gt=0)
    psu_count: int = Field(default=1, ge=1)
    psu_redundancy: bool = Field(default=False)
```
