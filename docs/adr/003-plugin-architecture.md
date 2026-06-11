# ADR-003: 插件架构——用插件管理领域知识

> 状态：已接受  
> 日期：2026-06-11  
> 作者：piki 核心团队  

## 背景

工程设计涉及众多专业领域：电信、数据中心、建筑、电力、暖通、结构……每个领域有自己的术语、规范、约束和检查规则。如何在同一个框架内支持这些差异巨大的领域，而不让核心变得臃肿？本 ADR 记录我们选择插件架构的决策过程。

---

## 1. 问题：领域知识的爆炸性差异

### 1.1 不同领域的"对象"完全不同

| 领域 | 核心对象 | 关键属性 |
|------|----------|----------|
| **电信** | 机柜、PDU、服务器、交换机 | U 位、功耗、端口数、速率 |
| **数据中心** | 方舱、配电单元、液冷管路 | 承重、制冷量、流量、PUE |
| **建筑** | 房间、楼层、梁、柱 | 跨度、荷载、配筋、防火等级 |
| **电力** | 变压器、开关柜、电缆 | 容量、电压等级、载流量、短路电流 |
| **暖通** | 空调、风管、冷却塔 | 风量、冷量、风速、噪声 |

这些对象的属性集合几乎没有交集。如果全部硬编码到核心框架中：

```python
# ❌ 反模式：核心框架硬编码所有领域的 Family
class UniversalFamily(BaseModel):
    # 电信属性
    rack_id: str = ""
    position_u: int = 0
    pdu_id: str = ""
    
    # 数据中心属性
    container_id: str = ""
    coolant_flow_lpm: float = 0
    
    # 建筑属性
    floor_id: str = ""
    span_m: float = 0
    reinforcement: str = ""
    
    # ... 100+ 个字段，绝大多数对任何给定实例都是空的
```

结果：

- 核心代码膨胀到无法控制
- 任何领域的变更都需要修改核心
- 新领域贡献者需要理解整个核心代码
- 测试矩阵爆炸（每个字段的组合都要测）

### 1.2 不同领域的规则完全不同

电信领域关心"PDU 功率预算"，建筑领域关心"楼板承重"。这些规则：

- 使用的数据不同
- 计算的公式不同
- 引用的规范不同（国标 GB、企标、IEC、TIA）
- 严重级别不同（电信过载 = 宕机，建筑超载 = 结构安全）

如果规则也硬编码到核心：

```python
# ❌ 反模式：核心框架包含所有领域的规则
def check_everything(ctx):
    # 电信规则
    check_pdu_budget(ctx)
    check_rack_space(ctx)
    
    # 数据中心规则
    check_container_weight(ctx)
    check_liquid_cooling(ctx)
    
    # 建筑规则
    check_floor_load(ctx)
    check_fire_rating(ctx)
    
    # ... 每次新增领域都要改这里
```

结果：

- 核心发布频率被迫与最慢的领域同步
- 领域专家无法独立迭代规则
- 规则之间的命名冲突（不同领域可能有同名概念）

---

## 2. 方案对比

### 2.1 方案 A：单体核心（硬编码所有领域）

| 维度 | 评价 |
|------|------|
| **核心复杂度** | ❌ 极高，所有领域代码混在一起 |
| **领域迭代速度** | ❌ 受核心发布周期约束 |
| **新领域接入** | ❌ 需要修改核心代码 |
| **测试隔离** | ❌ 一个领域的 bug 可能影响其他领域 |
| **社区贡献** | ❌ 贡献门槛高 |

### 2.2 方案 B：配置文件驱动（JSON Schema 定义 Family）

核心只提供通用引擎，Family 和规则通过配置文件定义：

```json
// ❌ 配置文件定义 Family —— 表达能力不足
{
  "family": "ServerFamily",
  "fields": [
    {"name": "height_u", "type": "int", "min": 1, "max": 48},
    {"name": "tdp_w", "type": "float", "min": 0}
  ]
}
```

| 维度 | 评价 |
|------|------|
| **表达能力** | ❌ JSON Schema 无法表达复杂约束（如"如果 liquid_cooled=true，则 coolant_flow_lpm > 0"） |
| **规则编写** | ❌ 规则需要 DSL，DSL 的设计和维护成本极高 |
| **调试体验** | ❌ 配置文件错误难以定位 |
| **IDE 支持** | ❌ 无类型提示、无自动补全 |

### 2.3 方案 C：插件架构（Python 包）

每个领域是一个独立的 Python 包，通过标准接口注册到核心：

```python
# piki-telecom/plugin.py —— 插件独立维护
class TelecomPlugin(Plugin):
    name = "telecom"
    
    def register_families(self, registry):
        registry.add_family("ServerFamily", ServerFamily)
        registry.add_family("RackFamily", RackFamily)
    
    def register_rules(self, checker):
        checker.add_rule("TELECOM-POWER-001", check_pdu_budget)
        checker.add_rule("TELECOM-RACK-001", check_rack_space)
    
    def register_generators(self, checker):
        checker.add_generator("bom-csv", generate_bom_csv)
```

| 维度 | 评价 |
|------|------|
| **表达能力** | ✅ Python 的完整表达能力，复杂约束随意写 |
| **规则编写** | ✅ pytest 风格，工程师已经会写 |
| **调试体验** | ✅ 标准 Python 堆栈跟踪 |
| **IDE 支持** | ✅ 类型提示、自动补全、跳转定义 |
| **核心复杂度** | ✅ 核心只提供框架，领域代码分离 |
| **领域迭代** | ✅ 独立版本号、独立发布 |
| **新领域接入** | ✅ 新建一个 Python 包即可 |
| **测试隔离** | ✅ 领域测试不依赖核心 |
| **社区贡献** | ✅ 领域专家只需懂自己的领域 |

---

## 3. piki 的插件架构设计

### 3.1 三层结构

```
piki-core（框架层）
  ├── CLI 入口
  ├── 项目发现（piki.toml 扫描）
  ├── Registry（Family/Model/Instance 注册表）
  ├── Checker（规则引擎）
  ├── Context（数据访问 + 配置）
  ├── QuerySet（过滤/排序/聚合）
  ├── Diagnostic（诊断系统）
  └── Reporting（报告格式：human/json/junit/markdown）
        ↑
        │ 标准接口
        ↓
piki-telecom（领域插件）
  ├── Family：RackFamily, PduFamily, ServerFamily
  ├── Rules：功率预算、U 位冲突、外键完整性
  ├── Generators：bom-csv
  └── Library：generic-server.yaml 等型号
        ↑
        │ 相同接口
        ↓
piki-datacenter（领域插件）
  ├── Family：ContainerFamily, PowerUnitFamily, EquipmentFamily
  ├── Rules：方舱承重、液冷容量、连接完整性
  ├── Generators：dc-bom-csv
  └── Library：标准方舱型号
```

### 3.2 插件发现机制

piki 通过两种途径发现插件：

1. **内置扩展**：`src/piki/extensions/` 目录下的插件（随 piki 核心发布）
2. **外部插件**：`piki.plugins.*` 命名空间下的第三方包（独立 pip 安装）

```python
# src/piki/core/plugin.py
def discover_plugins() -> dict[str, type[Plugin]]:
    # 1. 扫描内置 extensions
    for _, name, _ in iter_modules(ext_pkg.__path__, ...):
        ...
    
    # 2. 扫描外部 piki.plugins 包
    for _, name, _ in iter_modules(plugins_pkg.__path__, ...):
        ...
```

**设计原则**：

- 核心不依赖任何特定插件
- 插件通过标准 `Plugin` 基类接口注册
- 项目通过 `piki.toml` 选择启用哪些插件
- 未启用的插件代码不会被加载

### 3.3 插件接口

```python
class Plugin:
    """行业插件基类。"""
    
    name: str = ""           # 插件标识符
    version: str = "0.1.0"   # 语义化版本
    
    def register_families(self, registry: Registry) -> None:
        """注册 Family 定义（pydantic 模型）。"""
        pass
    
    def register_rules(self, checker: Checker) -> None:
        """注册检查规则（pytest 风格函数）。"""
        pass
    
    def register_generators(self, checker: Checker) -> None:
        """注册生成器（导出函数）。"""
        pass
```

### 3.4 跨插件协作

多个插件可以同时启用，规则可以跨插件查询数据：

```python
# rules/cross_plugin.py
@rule("CROSS-001", "机房承重检查")
def check_floor_load(ctx: Context):
    """建筑插件提供房间信息，电信插件提供设备重量。"""
    for room in ctx.query("rooms"):           # construction 插件的数据
        racks = ctx.query("racks", room_id=room.id)  # telecom 插件的数据
        total_weight = sum(
            d.resolved.weight_kg 
            for rack in racks 
            for d in ctx.query("devices", rack_id=rack.id)
        )
        assert total_weight <= room.floor_load_kg
```

**关键设计**：`ctx.query()` 通过**数据目录名**（如 `"racks"`、`"rooms"`）而非插件名来查询，实现松耦合。

---

## 4. 插件 vs 其他扩展机制

### 4.1 为什么不用 Python 装饰器全局注册

有些框架使用全局装饰器：

```python
# ❌ 全局装饰器 —— 有全局状态污染风险
@global_rule("TELECOM-POWER-001")
def check_pdu_budget(ctx):
    ...
```

piki 选择**显式注册**：

```python
# ✅ 显式注册 —— 无全局状态，测试友好
class TelecomPlugin(Plugin):
    def register_rules(self, checker):
        checker.add_rule("TELECOM-POWER-001", check_pdu_budget)
```

理由：

- 全局装饰器在导入时副作用难以控制
- 显式注册让测试可以构造隔离的 Checker 实例
- 插件启用/禁用由 `piki.toml` 控制，而非导入副作用

### 4.2 为什么不用动态加载（exec/import_string）

有些框架允许用户通过配置字符串动态加载规则：

```toml
# ❌ 动态加载 —— 安全风险、调试困难
[rules]
custom = "my_module:my_rule"
```

piki 选择**包管理**：

```bash
# ✅ pip 安装插件 —— 标准 Python 生态
pip install piki-telecom
```

理由：

- pip 有依赖解析、版本锁定、虚拟环境
- 插件代码在 IDE 中可跳转、可调试
- 不引入 `exec()` 的安全风险

---

## 5. 决策总结

| 决策 | 选择 | 核心理由 |
|------|------|----------|
| **扩展机制** | Python 插件包 | 完整表达能力、标准调试、IDE 支持 |
| **注册方式** | 显式接口方法 | 无全局状态、测试隔离、配置驱动 |
| **发现机制** | 内置 + 外部命名空间扫描 | 核心内置常用插件，社区可独立发布 |
| **启用控制** | `piki.toml` 配置 | 项目按需启用，未启用不加载 |
| **跨插件协作** | `ctx.query()` 数据目录名 | 松耦合，插件不直接依赖彼此 |

---

## 6. 未来演进

| 方向 | 说明 |
|------|------|
| **插件市场** | 未来可能有 `piki plugins install telecom` 命令，类似 npm |
| **插件模板** | `piki plugin init` 脚手架，快速创建新插件 |
| **插件依赖** | 插件之间声明依赖（如 `piki-datacenter` 依赖 `piki-telecom`） |
| **插件版本兼容** | 核心框架声明支持的插件 API 版本 |

---

## 参考

- [piki 核心概念：Plugin](https://github.com/indenscale/piki/blob/main/docs/concepts/02-core-concepts.md#5-plugin%E8%A1%8C%E4%B8%9A%E6%8F%92%E4%BB%B6)
- [pytest 插件系统](https://docs.pytest.org/en/stable/how-to/writing_plugins.html) — 参考设计
- [Kubernetes 插件生态](https://kubernetes.io/docs/concepts/extend-kubernetes/) — 领域扩展的标杆
