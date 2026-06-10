# API 参考

> piki 公共 API 的完整说明。用户编写规则和生成器时主要使用这些接口。

## 概述

piki 的公共 API 通过顶层包 `piki` 暴露，便于规则文件中直接导入：

```python
from piki import rule, generator, Context, Severity, Project, Plugin
```

---

## 装饰器

### `@rule(rule_id, name, priority=0, severity=Severity.ERROR)`

标记一个函数为 piki 检查规则。

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `rule_id` | `str` | 是 | — | 规则唯一标识，建议格式：`{领域}-{主题}-{序号}`，如 `TELECOM-POWER-001` |
| `name` | `str` | 是 | — | 规则名称（人类可读） |
| `priority` | `int` | 否 | `0` | 优先级，数值越大越先执行 |
| `severity` | `Severity` | 否 | `Severity.ERROR` | 失败时的严重级别 |

**示例：**

```python
from piki import rule, Context

@rule("TELECOM-POWER-001", "PDU 功率预算检查", priority=10)
def check_pdu_budget(ctx: Context):
    pdus = ctx.query("pdus")
    devices = ctx.query("devices")
    for pdu in pdus:
        powered = devices.filter(pdu_id=pdu.id)
        total = sum(d.tdp_w for d in powered)
        assert total <= pdu.rated_w, (
            f"PDU {pdu.id} 负载 {total}W 超过额定 {pdu.rated_w}W"
        )
```

**设计说明：**
- 装饰器将元数据附加到函数对象上，**不写入全局列表**
- `register_module_rules` 会扫描模块中所有带标记的函数并注册到 `Checker` 实例
- 规则通过抛出 `AssertionError` 表示失败，异常消息即为失败原因

---

### `@generator(gen_id, name)`

标记一个函数为 piki 生成器。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `gen_id` | `str` | 是 | 生成器唯一标识 |
| `name` | `str` | 是 | 生成器名称（人类可读） |

**示例：**

```python
from piki import generator, Context

@generator("bom-csv", "BOM 表导出")
def export_bom(ctx: Context, config: dict):
    devices = ctx.query("devices")
    # ... 生成 CSV
```

---

## 核心类

### `Context`

规则函数通过 `Context` 访问数据、配置和查询集合。

**属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `config` | `dict[str, Any]` | 合并后的配置（全局规则配置 + 插件配置），可在 `piki.toml` 中自定义 |

**方法：**

#### `Context.query(collection, **filters) -> QuerySet`

查询指定集合，支持过滤操作符和链式操作。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `collection` | `str` | 集合名称（对应目录名，如 `"devices"`、`"racks"`） |
| `**filters` | — | 过滤条件，支持 Django-style 双下划线操作符 |

**支持的操作符：**

| 操作符 | 说明 | 示例 |
|--------|------|------|
| `__eq` | 等值（默认） | `rack_id="RACK-A01"` |
| `__ne` | 不等 | `status__ne="removed"` |
| `__gt` | 大于 | `tdp_w__gt=300` |
| `__gte` | 大于等于 | `position_u__gte=10` |
| `__lt` | 小于 | `position_u__lt=20` |
| `__lte` | 小于等于 | `height_u__lte=4` |
| `__in` | 在列表中 | `rack_id__in=["A01", "A02"]` |
| `__contains` | 包含 | `tags__contains="critical"` |
| `__startswith` | 前缀匹配 | `id__startswith="SRV-"` |
| `__endswith` | 后缀匹配 | `id__endswith="-01"` |

**链式操作（返回 `QuerySet`）：**

```python
devices = ctx.query("devices")

# 排序
ordered = devices.order_by("position_u")           # 升序
ordered = devices.order_by("-tdp_w")               # 降序
ordered = devices.order_by("rack_id", "-position_u")  # 多字段

# 限制数量
top3 = devices.order_by("-tdp_w").limit(3)

# 字段投影（只保留指定字段）
ids = devices.fields("id", "model")
```

**终结操作：**

```python
devices = ctx.query("devices", rack_id="RACK-A01")

# 遍历
for d in devices:
    print(d.id, d.tdp_w)

# 获取第一个
first = devices.first()

# 计数
count = devices.count()

# 转为列表
items = devices.list()

# 转为 dict 列表
values = devices.values("id", "model", "tdp_w")

# 按字段分组
groups = devices.group_by("rack_id")  # -> {"RACK-A01": [...], "RACK-A02": [...]}

# 聚合计算
stats = devices.aggregate(
    total_power=lambda items: sum(d.tdp_w for d in items),
    count=len,
    avg_power=lambda items: sum(d.tdp_w for d in items) / len(items) if items else 0,
)

# 连接查询
racks = ctx.query("racks")
joined = devices.join(racks.list(), "rack_id")
for d in joined:
    rack = d._join_related  # 关联的 rack 对象
```

---

### `Severity`

诊断严重级别枚举，与 LSP `DiagnosticSeverity` 兼容。

| 级别 | 数值 | LSP 映射 | 说明 |
|------|------|----------|------|
| `DEBUG` | `0` | `Information` | 调试信息，仅在 verbose 模式显示 |
| `INFO` | `1` | `Information` | 一般信息 |
| `WARNING` | `2` | `Warning` | 警告，不影响继续执行 |
| `ERROR` | `3` | `Error` | 错误，当前检查项失败 |
| `FATAL` | `4` | `Error` | 致命错误，系统无法继续 |

**用法：**

```python
from piki import Severity

@rule("TELECOM-RACK-001", "机柜空间检查", severity=Severity.WARNING)
def check_rack_space(ctx: Context):
    # 失败时产生 WARNING 而非 ERROR
    ...
```

---

### `Project`

项目类，负责加载配置、扫描目录、运行检查。

**类方法：**

#### `Project.discover(start=None) -> Project`

从指定目录向上查找 `piki.toml`，返回 `Project` 实例。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `start` | `Path \| str \| None` | 否 | `Path.cwd()` | 起始目录 |

**示例：**

```python
from piki import Project

project = Project.discover("./my-datacenter")
project.load()
report = project.run_check()
print(f"Passed: {report.passed}")
```

**实例方法：**

| 方法 | 说明 |
|------|------|
| `load()` | 加载插件、型号库、实例数据、项目规则 |
| `run_check(skip=None, only=None, files=None) -> CheckReport` | 运行检查 |
| `make_context() -> Context` | 创建规则运行时的 Context |
| `plugin_config(name) -> dict` | 获取指定插件的配置 |
| `enabled_generators() -> list[str]` | 获取启用的生成器列表 |

---

### `Plugin`

行业插件基类，开发插件时继承此类。

**类属性：**

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | `str` | `""` | 插件名称（必须设置） |
| `version` | `str` | `"0.1.0"` | 插件版本 |

**方法：**

| 方法 | 说明 |
|------|------|
| `register_families(registry)` | 注册 Family（pydantic 模型类） |
| `register_rules(checker)` | 注册检查规则 |
| `register_generators(checker)` | 注册生成器 |

**示例：**

```python
from piki import Plugin
from piki.core.engine.registry import Registry
from piki.core.engine.checker import Checker

class TelecomPlugin(Plugin):
    name = "telecom"
    version = "0.1.0"

    def register_families(self, registry: Registry) -> None:
        from .families import ServerFamily, RackFamily, PDUFamily
        registry.add_family("ServerFamily", ServerFamily)
        registry.add_family("RackFamily", RackFamily)
        registry.add_family("PDUFamily", PDUFamily)

    def register_rules(self, checker: Checker) -> None:
        from . import rules
        from piki.core.engine.checker import register_module_rules
        register_module_rules(checker, rules)

    def register_generators(self, checker: Checker) -> None:
        from . import generators
        from piki.core.engine.checker import register_module_rules
        register_module_rules(checker, generators)
```

---

## 辅助函数

### `register_module_rules(checker, module)`

扫描模块中的 `@rule` / `@generator` 装饰器并注册到 `Checker`。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `checker` | `Checker` | 规则引擎实例 |
| `module` | `ModuleType` | 要扫描的 Python 模块 |

**说明：**
- 通过 `inspect.getmembers` 遍历模块成员
- 查找带有 `__piki_rule_meta__` 或 `__piki_gen_meta__` 属性的函数
- 兼容旧版 3 元组和新版 4 元组规则元数据

---

## 数据模型

### `QuerySet`

惰性求值的查询结果集。所有过滤和链式操作都不立即执行，直到调用终结操作（`first()`、`list()`、迭代等）时才求值。

**特性：**
- 每次链式操作返回新的 `QuerySet`，原对象不变
- 支持嵌套属性访问（如 `d.resolved.height_u`）
- 支持 dict 和对象两种数据类型的统一访问

---

### `Diagnostic`

编译器风格的诊断信息，对应 LSP `Diagnostic` 结构。

**属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `severity` | `Severity` | 严重级别 |
| `message` | `str` | 诊断消息 |
| `location` | `Location` | 发生位置（文件 + 行号 + 列号） |
| `code` | `str` | 错误码 |
| `source` | `str` | 产生诊断的组件 |
| `name` | `str` | 规则名称 |
| `related_information` | `list[RelatedInformation]` | 关联诊断信息 |

**快捷构造方法：**

```python
from piki.core.models.diagnostic import Diagnostic

d = Diagnostic.error("PDU 过载", code="TELECOM-POWER-001")
d = Diagnostic.warning("机柜空间紧张", code="TELECOM-RACK-001")
d = Diagnostic.fatal("配置文件损坏", code="FATAL-001")
```

---

## 类型提示参考

编写规则时推荐使用的类型注解：

```python
from piki import rule, Context, Severity
from piki.core.models.diagnostic import Diagnostic

@rule("EXAMPLE-001", "示例规则")
def example_rule(ctx: Context) -> None:
    """规则函数不接受返回值，通过 AssertionError 表示失败。"""
    devices = ctx.query("devices")
    for d in devices:
        assert d.tdp_w > 0, f"设备 {d.id} 功率必须大于 0"
```
