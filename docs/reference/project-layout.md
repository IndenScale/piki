# piki 项目目录结构

> 一个 piki 项目初始化后包含哪些目录和文件，以及各自的用途。

## 概览

```text
my-project/
├── piki.toml                 # 项目元数据（根目录标记、插件、配置）
├── .gitignore                # 忽略缓存和生成产物
├── .piki_cache/              # 解析缓存（可选，gitignore）
│
├── library/                  # 项目本地型号库
│   └── devices/
│       └── generic-server.yaml
│
├── racks/                    # 机柜实例
│   └── RACK-A01.yaml
│
├── devices/                  # 设备实例
│   ├── SRV-01.yaml
│   ├── SRV-02.yaml
│   └── SRV-03.yaml
│
├── cables/                   # 线缆实例（可选，取决于插件）
│   └── CAB-01.yaml
│
├── rules/                    # 项目自定义规则
│   ├── __init__.py
│   ├── power.py
│   └── rack_space.py
│
└── generators/               # 项目自定义生成器（可选）
    └── my_report.py
```

## 核心文件

### `piki.toml`

项目根标记文件。piki 通过向上扫描 `piki.toml` 确定项目边界。

```toml
[project]
name = "my-datacenter"
version = "1.0.0"

[plugins]
enabled = ["telecom"]

[plugins.telecom]
power_threshold = 0.4
rack_usage_threshold = 0.8
```

| 字段 | 说明 |
|------|------|
| `project.name` | 项目名称 |
| `project.version` | 项目版本 |
| `plugins.enabled` | 启用的插件列表 |
| `plugins.<name>` | 插件专属配置，可在规则中通过 `ctx.config` 读取 |
| `rules` | 全局规则配置 |
| `performance` | 性能相关配置（缓存、并行） |
| `output` | 输出格式配置 |

## 资产目录

### `library/`

项目本地型号库。每个 YAML 文件是一个 **Model**，必须包含：

- `model`: 型号 ID
- `family`: 所属 Family 名称
- 各字段默认值

```yaml
# library/devices/generic-server.yaml
model: generic-server
family: ServerFamily

height_u: 2
tdp_w: 300
psu_count: 1
psu_redundancy: false
```

来源优先级：**项目本地 `library/` > 插件自带型号库**。

### 数据目录（`racks/`、`devices/`、`cables/` 等）

目录名即集合名。每个 YAML 文件是一条 **Instance**。

```yaml
# devices/SRV-01.yaml
id: SRV-01
model: generic-server
status: installed
rack_id: RACK-A01
position_u: 10
pdu_id: PDU-A
```

必须包含 `id`。如果未指定 `family`，piki 会尝试从 `model` 推导。

Instance 字段会覆盖 Model 的默认值。例如 `SRV-02.yaml` 中 `tdp_w: 250` 会覆盖型号库的 `300`。

### `rules/`

项目自定义规则，按主题分组。

```python
# rules/power.py
from piki import rule, Context

@rule("PROJECT-POWER-001", "项目功率检查")
def check_project_power(ctx: Context):
    threshold = ctx.config.get("power_threshold", 0.8)
    # ...
```

规则 ID 建议格式：`{领域}-{主题}-{序号}`，如 `TELECOM-POWER-001`。

### `generators/`（可选）

项目自定义生成器，通过 `piki generate` 调用。

## 字段命名空间约定

- **Model** 中推荐使用嵌套命名空间，如 `physical.height_u`、`power.tdp_w`
- **Instance** 中可以直接写扁平字段，如 `height_u: 2`、`tdp_w: 250`，piki 会自动覆盖对应 Model 字段
- 解析后的完整对象可通过 `d.resolved.height_u` 或 `d.height_u` 访问

## 缓存与生成产物

以下目录建议加入 `.gitignore`：

```gitignore
.piki_cache/
reports/
```

- `.piki_cache/`: 解析缓存，加速增量检查
- `reports/`: `piki check` 或 `piki generate` 的输出目录

## 与 folder-db 的关系

| 层级 | 负责 | 说明 |
|------|------|------|
| folder-db | 目录结构、YAML 读写、基础 CRUD | piki 可以读写，但不依赖 |
| piki-core | Family 注册、Model 解析、Rule 引擎、报告生成 | 框架层 |
| piki-plugin-{行业} | Family 定义、行业规则、默认型号库 | 扩展层 |
