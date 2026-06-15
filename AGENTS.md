# piki — AGENTS.md

> **piki** 是一个面向工程设计的 Text-Native 声明式系统建模框架（DSMF）。
> 工程师用 YAML 声明设计意图，Python 规则自动校验合理性，Git 追踪每一次变更。

## 项目定位

piki 是**设计意图层 + 规则校验层**，不是 CAD 工具、不是仿真求解器、不是 PLM。

**核心循环：** 写 YAML → `piki check` → 修正违规 → `piki generate` → 交付物。
可以理解为一个工程编译器：YAML 源码 → 语义校验 → 多格式输出。

## 仓库结构

```
piki/                           # monorepo 根目录
├── src/piki/                   # Python 核心（可通过 pip 安装）
│   ├── core/                   #   引擎层：registry、checker、generator、context
│   │   ├── engine/             #   checker.py、registry.py、generator_registry.py
│   │   └── models/             #   diagnostic、interface、query_set
│   ├── extensions/             #   内置插件：telecom、datacenter、keyboard、environments、manufacturing
│   ├── cli.py                  #   CLI 入口（piki init/check/report/generate）
│   └── templates/              #   项目脚手架模板
├── studio/                     # TypeScript 浏览器端 IDE（Piki Studio）
│   ├── src/                    #   Three.js + 自研 USDA 解析器
│   └── ARCHITECTURE.md         #   Studio 专属架构文档
├── samples/                    # 示例项目
├── docs/                       # 全部文档（概念与决策的真相源）
├── tests/                      # Python 测试
└── piki.toml                   # piki 自身的项目配置（自己吃自己的狗粮）
```

## 核心数据模型（五层栈）

写任何代码前必须先理解这五层：

| 层            | 概念                    | 存放位置             | 定义什么                                          |
| ------------- | ----------------------- | -------------------- | ------------------------------------------------- |
| **Family**    | 类型约束（pydantic 类） | 插件代码             | "服务器必须有哪些字段？类型是什么？"              |
| **Model**     | 型号默认值（YAML）      | `models/` 或插件自带 | "通用服务器：tdp_w=300, height_u=2"               |
| **Catalog**   | 真实世界映射与权威来源（YAML） | `catalogs/` 或插件/企业提供 | "通用服务器对应哪个 MPN？生命周期是什么？安装工法需要什么前提？" |
| **Instance**  | 实际部署的实体（YAML）  | `instances/`         | "SRV-01：model=generic-server, tdp_w=250（覆盖）" |
| **Interface** | 可连接点（YAML，内嵌）  | Instance 文件内部    | "SRV-01/eth0：类型 SFP28，双向"                   |

运行时解析：`Model.defaults + Instance.overrides + Layout.placement + Catalog.authority`。

## 五个数据维度 + Catalog 引用层（ADR-001 → ADR-011）

piki 将工程设计拆为五个正交维度建模，Catalog 作为跨维度的引用层：

| 维度                      | 格式                                    | 位置                               | 职责                                                      |
| ------------------------- | --------------------------------------- | ---------------------------------- | --------------------------------------------------------- |
| **Instance**              | YAML 文件                               | `instances/`                       | "这东西是什么？"                                          |
| **Layout**                | 每个子项目一个 YAML 列表                | `layout.yaml`                      | "部署在哪？哪个机柜/哪个 U 位/接哪个 PDU？"               |
| **Connection**（ADR-005） | YAML Instance 文件                      | `instances/connections/`           | "Interface A 和 Interface B 如何连接？"                   |
| **Mating**（ADR-006）     | YAML 文件                               | `mates/`                           | "两个实体怎样耦合？（机械、守恒、同步等）"                |
| **Context**（ADR-010）    | `context` 字段 + `piki.toml` [contexts] | `instances/contexts/{context_id}/` | 归属声明：本次工程 / 既有 / 保密 / 标段 / 概念 / 自然环境 |
| **Catalog**（ADR-011）    | YAML 文件                               | `catalogs/`                        | 跨维度引用层：Model 的真实世界映射与服务工法前提        |

### 关键分离：Instance 与 Layout

**Instance** 定义"是什么"。**Layout** 定义"放哪里"。
两者是独立文件——方案比选 = Git 分支，而不是复制 Instance 文件。

### 关键分离：Connection 与 Mating

- **Connection**（ADR-005）：信号/能量链路（"SRV-01/eth0 到 SW-01/Gi1-0-1 的光纤"）
- **Mating**（ADR-006）：部件耦合关系（"rack-mount-19inch"，"IEC-C14-C13 电源配对"，"mass-conservation"，"clock-sync"）

## 插件架构（ADR-002）

插件是通过 `pip` 安装的 Python 包。每个插件提供：

- `register_families(registry)` — pydantic 模型类
- `register_rules(checker)` — `@rule` 装饰的函数
- `register_generators(checker)` — `@generator` 装饰的函数

**显式注册，不使用全局装饰器。** 插件在 `piki.toml` 中启用：

```toml
[plugins]
enabled = ["telecom", "datacenter"]
```

**跨插件查询**使用数据集合名而非插件名：`ctx.query("instances", family="RackFamily")`。

内置插件位于 `src/piki/extensions/`：`telecom`、`datacenter`、`keyboard`、`environments`、`manufacturing`。

## 质量检查分层（ADR-003）

检查按成本和时效分层执行；层级越高成本越大：

| 层     | 类型                       | 执行时机             | 成本     |
| ------ | -------------------------- | -------------------- | -------- |
| **L0** | 文件格式合法性             | 加载时，失败立即终止 | <1ms     |
| **L1** | Schema 校验（pydantic）    | 加载时               | <10ms    |
| **L2** | 单记录完整性（外键、必填） | 加载时               | <10ms    |
| **L3** | 跨记录业务规则             | `piki check` 默认    | 10-100ms |
| **L4** | 几何检查（AABB 碰撞）      | `piki check` 默认    | 100ms-1s |
| **L5** | 物理仿真验证               | `--deep` 标志        | 1s-1min  |
| **L6** | AI 评估                    | `--ai` 标志          | 1-10s    |

诊断信息采用 LSP 兼容格式，以支持 IDE 集成。

## 编写规则

规则是用 `@rule` 装饰的 Python 函数：

```python
from piki import rule, Context

@rule("TELECOM-POWER-001", "PDU 功率预算检查", priority=10)
def check_pdu_budget(ctx: Context):
    threshold = ctx.config.get("power_threshold", 0.8)
    for pdu in ctx.query("instances", family="PduFamily"):
        devices = ctx.query("instances", pdu_id=pdu.id)
        load = sum(d.resolved.tdp_w for d in devices)
        assert load / pdu.resolved.capacity_w <= threshold, \
            f"{pdu.id} 负载率 {load/pdu.resolved.capacity_w:.1%}，超出阈值 {threshold:.1%}"
```

**核心 API：**

- `ctx.query(collection, **filters)` → `QuerySet`，支持 Django 风格双下划线操作符（`__gt`、`__in`、`__contains`、`__startswith` 等）
- 链式操作：`.filter()`、`.exclude()`、`.order_by()`、`.limit()`
- 终结操作：`.first()`、`.count()`、`.list()`、`.values()`、`.group_by()`、`.aggregate()`
- `ctx.config` — 合并后的 `piki.toml` 配置
- `ctx.mate_graph.related_to()`、`ctx.mated_descendants()`、`ctx.mated_ancestors()` — 沿配合图遍历

**规则 ID 规范：** `{领域}-{主题}-{序号}`，如 `TELECOM-POWER-001`。

**生成器**函数使用 `@generator` 装饰器，返回结构化的 `GeneratorResult`。

## 标签系统（ADR-001）

非空间维度（专业、安全分区、标段、系统、建设阶段）通过 Instance YAML 的 `tags` 字段表达——它们与代表物理空间的文件路径正交。规则可按标签过滤：

```python
instances = ctx.query("instances", tags__discipline="hvac", tags__security_zone="containment")
```

## Interface 与 Connection 模型（ADR-005、RFC-001）

- Interface：内嵌在 Instance 的 `interfaces` 列表中。引用格式：`instance_id/interface_id`
- telecom 插件内置 `InterfaceType` 枚举 + 兼容性矩阵 + `INTERFACE_CABLE_MAP`
- Connection 通过 `from_interface` / `to_interface` 引用 Interface

## Mating Graph 配合图（ADR-006）

Mating 在 piki 中被定义为广义的设计耦合（Design Coupling），包括机械配合、接口配对、守恒约束、时序同步等。三级耦合建模：

- **L1 实体级耦合**：rack-mount、thermal-contact、wireless-link、mass-conservation
- **L2 接口级耦合**：IEC-C14-C13 电源配对、SFP28 笼子 → 光模块
- **L3 跨耦合链路**：跨配合组件的 Connection 链

Mate 的 `constrains` 在引擎加载时自动验证。参见 [设计知识成熟曲线](docs/concepts/06-knowledge-maturation.md)。

## 空间可视化（ADR-008、ADR-009）

- 场景格式：**OpenUSD**（非 Three.js JSON）——数字孪生行业标准
- 浏览器渲染：**glTF** 过渡方案（Piki Studio 通过自研 USDA 文本解析器实现）
- 碰撞检测：规则引擎中纯 Python AABB/OBB 算法，无外部物理依赖
- Piki Studio（`studio/`）：TypeScript + Vite + Three.js，通过 File System Access API 读取本地项目目录

## Generator 交付物管线（ADR-004）

生成器从文本真相源派生产出交付物：

- `GeneratorResult` 结构：`{generator_id, content, file_path, content_type, success}`
- 输出约定：`dist/` 根目录，按受众分子目录（施工图、采购清单、设计评审）
- 默认策略：`dist/` 进 gitignore；里程碑版本可提交快照

## 核心 CLI 命令

| 命令                                                     | 用途         |
| -------------------------------------------------------- | ------------ |
| `piki init [PATH] [--plugin]`                            | 初始化新项目 |
| `piki check [--format] [--skip] [--only] [--files] [-o]` | 运行设计校验 |
| `piki generate [GENERATOR] [-o]`                         | 导出交付物   |
| `piki report [--format] [-o]`                            | 生成检查报告 |
| `piki plugins list`                                      | 列出可用插件 |

## 配置（`piki.toml`）

关键配置段：`[project]`、`[plugins]`、`[plugins.<name>]`、`[rules]`、`[rules.<id>]`、`[generators]`、`[tags]`、`[output]`、`[performance]`。

配置优先级：命令行参数 > 单条规则配置 > 全局配置 > 插件默认值。

## 编码规范

### Python

- **Family 定义**：只能用 pydantic `BaseModel` 类，通过插件 `register_families()` 注册
- **物理尺寸字段**（height_u、depth_mm、weight_kg 等）：在 Field 的 `json_schema_extra` 中标记 `piki_non_overridable`
- **`family` 字段**：Model YAML 中必填；Instance 可直接指定 `family` 或通过 `model` 推导
- **Instance ID = 文件名**（如 `SRV-01.yaml` → `id: SRV-01`）
- **解析后的值**：通过 `d.resolved.field_name` 访问——这是 Model+Instance+Layout 合并后的完整值
- **目录名即语义**：`instances/`、`models/`、`catalogs/`、`rules/`、`generators/`、`mates/`、`modules/` 都是固定约定

### TypeScript（Studio）

- Studio 是 `studio/` 目录下的独立 Vite 项目
- 自研 USDA 文本解析器（当前阶段不依赖 WASM）
- 详见 `studio/ARCHITECTURE.md`

### YAML

- Instance 文件：必须有 `id`。可选 `family` 或 `model` 推导 Family。
- Model 文件：必须有 `model` 和 `family`。
- Catalog 文件：必须有 `catalog_id` 和 `family`（`ComponentCatalogFamily` 或 `ServiceMethodCatalogFamily`）。
- 嵌套命名空间（`physical.`、`power.`、`assets.`）在解析时被扁平化合并。
- Interface 引用语法：`instance_id/interface_id`。

## 嵌套项目（ADR-001）

子项目继承父项目的 `piki.toml`、`models/`、`instances/`（同名字段覆盖）。Layout **不继承**——每个子项目有独立的 `layout.yaml`。物理空间是文件组织的主维度。

## CAD 资产策略（ADR-007）

**引用而非嵌入。** piki YAML 声明 `assets.mesh` 路径和可选的 `asset_hash`。不做 mesh 加工、不做格式转换。白牌型号（`generic-1u-server`）用于占位几何。

## 设计哲学

- **Text-Native & Agent-Oriented**（concepts/04, 05）：文本是机器协作协议；Agent 写 YAML，人类审阅；GUI 是可视化消费层
- **不是 CAD 工具**：不加交互式 3D 编辑——真相源永远是文本
- **不是仿真求解器**：不加物理求解器——留给 Ansys/Synopsys
- **不是项目管理工具**：不加甘特图、成本追踪
- **插件边界清晰**：核心不知道电信概念；插件之间不互相导入

## 关键文档导航

| 文档                                 | 何时阅读                               |
| ------------------------------------ | -------------------------------------- |
| `docs/concepts/01-core-concepts.md`  | 理解数据模型                           |
| `docs/concepts/02-writing-rules.md`  | 编写校验规则                           |
| `docs/reference/06-api.md`           | 完整 API 参考                          |
| `docs/reference/07-cli.md`           | CLI 命令                               |
| `docs/reference/01-configuration.md` | piki.toml 配置                         |
| `docs/reference/08-catalog.md`       | Catalog 格式与来源优先级               |
| `docs/adr/`                          | 架构决策记录（修改架构前先读相关 ADR） |
| `docs/rfcs/`                         | 功能需求提案                           |
| `studio/ARCHITECTURE.md`             | Studio（TypeScript）架构               |
| `ROADMAP.md`                         | 当前进展与未来计划                     |
