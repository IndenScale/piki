# ADR-002: 插件架构——领域知识的封装边界

> 状态：已实现
> 日期：2026-06-12
> 作者：piki 核心团队

## 背景

工程设计涉及众多专业领域：电信、数据中心、建筑、电力、暖通……每个领域有自己的对象类型、约束规则和导出需求。如何在同一框架内支持差异巨大的领域，而不让核心膨胀？

本 ADR 记录我们选择插件架构的决策过程：为什么不用硬编码、为什么不用配置文件、为什么选择显式注册。

---

## 1. 备选方案对比

### 方案 A：单体核心（硬编码所有领域）

将所有领域的 Family、规则、生成器直接写在 piki 核心代码中。

| 维度 | 评价 |
|------|------|
| 核心复杂度 | ❌ 极高，所有领域代码混在一起 |
| 领域迭代速度 | ❌ 受核心发布周期约束 |
| 新领域接入 | ❌ 需要修改核心代码 |
| 测试隔离 | ❌ 一个领域的 bug 可能影响其他领域 |
| 社区贡献 | ❌ 贡献门槛高 |

### 方案 B：配置文件驱动（JSON Schema 定义 Family）

核心只提供通用引擎，Family 和规则通过 JSON Schema 等配置文件定义。

| 维度 | 评价 |
|------|------|
| 表达能力 | ❌ JSON Schema 无法表达复杂约束（如条件依赖） |
| 规则编写 | ❌ 需要 DSL，DSL 的设计和维护成本极高 |
| 调试体验 | ❌ 配置文件错误难以定位 |
| IDE 支持 | ❌ 无类型提示、无自动补全 |

### 方案 C：Python 插件包（选择方案）

每个领域是独立的 Python 包，通过标准接口注册到核心。

```python
class TelecomPlugin(Plugin):
    name = "telecom"

    def register_families(self, registry):
        registry.add_family("ServerFamily", ServerFamily)

    def register_rules(self, checker):
        checker.add_rule("TELECOM-POWER-001", check_pdu_budget)

    def register_generators(self, checker):
        checker.add_generator("bom-csv", generate_bom_csv)
```

| 维度 | 评价 |
|------|------|
| 表达能力 | ✅ Python 的完整表达能力 |
| 规则编写 | ✅ pytest 风格，工程师已会写 |
| 调试体验 | ✅ 标准 Python 堆栈跟踪 |
| IDE 支持 | ✅ 类型提示、自动补全、跳转定义 |
| 核心复杂度 | ✅ 核心只提供框架，领域代码分离 |

---

## 2. 关键设计决策

### 2.1 显式注册而非全局装饰器

```python
# ❌ 全局装饰器 —— 导入时有副作用，难以测试
@global_rule("TELECOM-POWER-001")
def check_pdu_budget(ctx): ...

# ✅ 显式注册 —— 无全局状态，测试可构造隔离实例
class TelecomPlugin(Plugin):
    def register_rules(self, checker):
        checker.add_rule("TELECOM-POWER-001", check_pdu_budget)
```

理由：全局装饰器在导入时产生副作用难以控制。显式注册让插件启用/禁用由 `piki.toml` 控制，而非导入副作用。

### 2.2 pip 包管理而非动态加载

```bash
# ✅ pip 安装插件 —— 标准 Python 生态
pip install piki-telecom
```

不使用配置字符串动态加载（`my_module:my_rule`），理由：pip 有依赖解析、版本锁定、虚拟环境；插件代码在 IDE 中可跳转、可调试；不引入 `exec()` 的安全风险。

### 2.3 跨插件协作：数据目录名而非插件名

```python
@rule("CROSS-001", "机房承重检查")
def check_floor_load(ctx: Context):
    for room in ctx.query("rooms"):  # construction 插件的数据
        racks = ctx.query("racks", room_id=room.id)  # telecom 插件的数据
```

`ctx.query()` 通过数据目录名（`"rooms"`、`"racks"`）而非插件名查询，实现松耦合。插件之间不直接依赖彼此。

---

## 3. 决策总结

| 决策 | 选择 | 核心理由 |
|------|------|----------|
| 扩展机制 | Python 插件包 | 完整表达能力、标准调试、IDE 支持 |
| 注册方式 | 显式接口方法 | 无全局状态、测试隔离、配置驱动 |
| 分发方式 | pip 包管理 | 依赖解析、版本锁定、无安全风险 |
| 跨插件协作 | `ctx.query()` 数据目录名 | 松耦合，插件不直接依赖彼此 |

---

## 参考

- [核心概念 § Plugin](../concepts/01-core-concepts.md#7-plugin行业插件)
- [Plugin API 参考](../reference/06-api.md#plugin)
- [telecom 插件源码](../../src/piki/extensions/telecom/plugin.py)
