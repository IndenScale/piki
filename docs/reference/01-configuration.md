# 项目配置参考

> `piki.toml` 的完整字段说明与配置示例。

## 概述

`piki.toml` 是 piki 项目的根标记文件，必须位于项目根目录。piki 通过向上扫描 `piki.toml` 确定项目边界。

## 完整示例

```toml
# piki.toml

[project]
name = "my-datacenter"
version = "1.0.0"

[plugins]
enabled = ["telecom"]

[plugins.telecom]
power_threshold = 0.4          # PDU 负载阈值（0.0 ~ 1.0）
rack_usage_threshold = 0.8     # 机柜使用率阈值（0.0 ~ 1.0）

[rules]
# 全局规则配置
default_priority = 0

[rules.TELECOM-POWER-001]
warning_only = true            # true 则只警告不报错

[rules.TELECOM-RACK-001]
warning_only = false

[generators]
enabled = ["bom-csv", "panel-diagram"]

[generators.bom-csv]
format = "csv"                 # csv | excel | json
columns = ["id", "model", "rack_id", "position_u", "tdp_w"]

[generators.panel-diagram]
format = "svg"                 # svg | pdf | png
rack_ids = ["RACK-A01", "RACK-A02"]

[output]
format = "human"               # human | json | junit | markdown
verbose = false

[performance]
cache_parsed = true            # 缓存解析后的实例
cache_dir = ".piki_cache"
parallel = 4
```

---

## 配置段详解

### `[project]` — 项目元数据

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `name` | `str` | 是 | — | 项目名称 |
| `version` | `str` | 否 | `"1.0.0"` | 项目版本 |

**示例：**

```toml
[project]
name = "shanghai-dc-phase-1"
version = "2.1.0"
```

---

### `[plugins]` — 插件配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `enabled` | `list[str] \| str` | 是 | — | 启用的插件列表。单插件可写字符串，多插件用列表 |

**示例：**

```toml
# 单插件
[plugins]
enabled = "telecom"

# 多插件
[plugins]
enabled = ["telecom", "construction"]
```

---

### `[plugins.<name>]` — 插件专属配置

每个插件可以定义自己的配置字段，在规则中通过 `ctx.config` 读取。

**telecom 插件配置：**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `power_threshold` | `float` | `0.4` | PDU 负载告警阈值（0.0 ~ 1.0），超过此比例触发检查 |
| `rack_usage_threshold` | `float` | `0.8` | 机柜使用率告警阈值（0.0 ~ 1.0） |

**示例：**

```toml
[plugins.telecom]
power_threshold = 0.4
rack_usage_threshold = 0.8
```

**在规则中读取：**

```python
@rule("TELECOM-POWER-001", "PDU 功率预算检查")
def check_pdu_budget(ctx: Context):
    threshold = ctx.config.get("power_threshold", 0.8)
    # ...
```

---

### `[rules]` — 全局规则配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `default_priority` | `int` | `0` | 默认规则优先级 |
| `skip` | `list[str]` | `[]` | 默认跳过的规则 ID 列表 |

**示例：**

```toml
[rules]
default_priority = 0
skip = ["TELECOM-DEPRECATED-001"]
```

---

### `[rules.<rule_id>]` — 单条规则配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `warning_only` | `bool` | `false` | `true` 时规则失败只产生警告，不影响整体通过状态 |

**示例：**

```toml
[rules.TELECOM-POWER-001]
warning_only = true            # PDU 过载只警告，不阻止提交

[rules.TELECOM-RACK-001]
warning_only = false           # 机柜空间不足视为错误
```

---

### `[generators]` — 生成器全局配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | `list[str] \| str` | `[]` | `piki generate` 无参数时运行的生成器列表 |

**示例：**

```toml
[generators]
enabled = ["bom-csv", "panel-diagram", "cable-labels"]
```

---

### `[generators.<gen_id>]` — 单个生成器配置

生成器参数由插件定义，常见配置：

**bom-csv 生成器：**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `format` | `str` | `"csv"` | 输出格式：`csv`、`excel`、`json` |
| `columns` | `list[str]` | 插件默认 | 输出列列表 |

**panel-diagram 生成器：**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `format` | `str` | `"svg"` | 输出格式：`svg`、`pdf`、`png` |
| `rack_ids` | `list[str]` | 全部机柜 | 要生成的机柜 ID 列表 |

**cable-labels 生成器：**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `format` | `str` | `"pdf"` | 输出格式：`pdf`、`png` |
| `page_size` | `str` | `"A4"` | 页面尺寸 |
| `labels_per_page` | `int` | `24` | 每页标签数 |

**示例：**

```toml
[generators.bom-csv]
format = "csv"
columns = ["id", "model", "rack_id", "position_u", "tdp_w"]

[generators.panel-diagram]
format = "svg"
rack_ids = ["RACK-A01", "RACK-A02"]

[generators.cable-labels]
format = "pdf"
page_size = "A4"
labels_per_page = 24
```

---

### `[output]` — 输出配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `format` | `str` | `"human"` | 默认输出格式：`human`、`json`、`junit`、`markdown` |
| `verbose` | `bool` | `false` | 是否显示调试信息 |

**示例：**

```toml
[output]
format = "human"
verbose = false
```

---

### `[performance]` — 性能配置

> 以下配置为规划特性，当前版本尚未完全实现。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `cache_parsed` | `bool` | `true` | 是否缓存解析后的实例 |
| `cache_dir` | `str` | `".piki_cache"` | 缓存目录 |
| `parallel` | `int` | `4` | 并行检查的工作进程数 |

**示例：**

```toml
[performance]
cache_parsed = true
cache_dir = ".piki_cache"
parallel = 4
```

---

### `[security]` — 安全配置

> 以下配置为规划特性，当前版本尚未实现。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `encryption_key_file` | `str` | — | 加密密钥文件路径 |

**示例：**

```toml
[security]
encryption_key_file = ".piki_key"
```

---

## 配置优先级

当同一配置在多处定义时，优先级从高到低：

1. **命令行参数**（如 `--format json`）
2. **单条规则配置**（`[rules.<rule_id>]`）
3. **全局配置**（`[rules]`、`[output]` 等）
4. **插件默认值**

---

## 配置验证

piki 在加载项目时会验证 `piki.toml` 的基本结构：

- `[project]` 段必须存在
- `project.name` 必须设置
- `plugins.enabled` 中的插件必须已安装

验证失败时会输出明确的错误信息，并终止执行。
