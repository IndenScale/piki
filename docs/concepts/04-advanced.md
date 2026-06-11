# 高级用法

> CI/CD 集成、多插件协作、性能优化、以及常见问题解答。

## 1. CI/CD 集成

### Git 预提交钩子

在 `.git/hooks/pre-commit` 中添加：

```bash
#!/bin/bash
# 只检查新增或修改的 YAML 文件
changed_yaml=$(git diff --cached --name-only --diff-filter=ACM | grep '\.yaml$')

if [ -n "$changed_yaml" ]; then
    echo "Running piki check on changed files..."
    piki check --files $changed_yaml
    if [ $? -ne 0 ]; then
        echo "piki check failed. Commit aborted."
        exit 1
    fi
fi
```

### GitHub Actions

```yaml
# .github/workflows/piki.yml
name: Piki Check

on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install piki
        run: |
          pip install piki

      - name: Run piki check
        run: piki check --format junit -o report.xml

      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: piki-report
          path: report.xml
```

### 报告格式

```bash
# 人类可读（默认）
piki check

# JSON（供脚本解析）
piki check --format json

# JUnit XML（供 CI 系统解析）
piki check --format junit -o report.xml

# Markdown（供 PR 评论）
piki check --format markdown -o check-report.md

# 生成独立报告文件
piki report --format markdown -o report.md
```

## 2. 多插件协作

### 场景：电信 + 建筑

数据中心项目同时涉及电信设备和建筑空间：

```toml
# piki.toml
[plugins]
enabled = ["telecom", "construction"]

[plugins.construction]
floor_height_m = 4.5
```

目录结构：

```text
project/
├── piki.toml
├── rooms/              # construction 插件
│   ├── schema.yaml
│   └── ROOM-101.yaml
├── racks/              # telecom 插件
│   ├── schema.yaml
│   └── RACK-A01.yaml
├── devices/
│   └── ...
└── rules/
    ├── telecom/        # 电信规则
    └── construction/   # 建筑规则
```

### 跨插件规则

```python
# rules/cross_plugin.py
from piki import rule, Context

@rule("CROSS-001", "机房承重检查")
def check_floor_load(ctx: Context):
    """
    建筑插件提供房间信息，电信插件提供设备重量。
    检查设备总重不超过楼板承重。
    """
    for room in ctx.query("rooms"):
        racks = ctx.query("racks", room_id=room.id)
        total_weight = 0

        for rack in racks:
            devices = ctx.query("devices", rack_id=rack.id)
            rack_weight = sum(d.resolved.weight_kg for d in devices)
            total_weight += rack_weight

        assert total_weight <= room.floor_load_kg, (
            f"房间 {room.id} 设备总重 {total_weight}kg "
            f"超过楼板承重 {room.floor_load_kg}kg"
        )
```

## 3. 生成器（Generator）

> 像 npm 脚本一样，通过配置文件引入导出功能。

### 问题

设计验证通过后，还需要：

- 导出 BOM 表给采购
- 导出面板图给施工
- 导出设备标签和线缆标签给现场

这些功能每个项目需求不同，如何**按需引入、配置启用**？

### 解决方案：插件注册 + 配置启用

插件在代码里注册生成器：

```python
# piki_telecom/plugin.py
def register_generators(self, generator):
    generator.add("bom", export_bom)
    generator.add("panel-diagram", export_panel)
    generator.add("cable-labels", export_cable_labels)
    generator.add("port-map", export_port_map)
```

项目在 `piki.toml` 里选择启用哪些、配置参数：

```toml
# piki.toml
[plugins.telecom.generators]
enabled = ["bom", "panel-diagram", "cable-labels"]

[plugins.telecom.generators.bom]
format = "csv"                 # csv | excel | json
columns = ["id", "model", "rack_id", "position_u", "tdp_w"]

[plugins.telecom.generators.panel-diagram]
format = "svg"                 # svg | pdf | png
rack_ids = ["RACK-A01", "RACK-A02"]

[plugins.telecom.generators.cable-labels]
format = "pdf"                 # pdf 直接打印
page_size = "A4"
labels_per_page = 24
```

### 使用

```bash
# 生成所有启用的（需在 piki.toml [generators] enabled 中配置）
piki generate

# 生成单个
piki generate bom-csv
piki generate bom-csv --output ./bom.csv
```

### 与 npm scripts 的对比

| npm | piki |
|-----|------|
| `package.json` 的 `scripts` 字段 | `piki.toml` 的 `[plugins.*.generators]` |
| `npm run build` | `piki generate` |
| 脚本逻辑在 `node_modules/` 里 | 生成器逻辑在插件包里 |
| 项目只配置启用哪些 | 项目只配置启用哪些 |

### 自定义生成器

项目也可以写自己的生成器：

```python
# generators/my_report.py
from piki import generator, Context

@generator("my-report", "自定义报告")
def export_my_report(ctx: Context, config: dict):
    devices = ctx.query("devices")
    with open("my-report.md", "w") as f:
        f.write(f"# 设备清单\n\n")
        for d in devices:
            f.write(f"- {d.id}: {d.model}\n")
```

```toml
# piki.toml
[generators]
enabled = ["my-report"]
```

## 4. 性能优化

> 以下功能为规划特性，当前版本尚未实现。

### 大数据量场景

当设备数量超过 10,000 台时：

```bash
# 增量检查（只检查变更）—— 规划中
piki check --incremental

# 并行检查（利用多核）—— 规划中
piki check --parallel 8

# 只检查特定目录 —— 规划中
piki check racks/ devices/
```

### 缓存解析结果

```toml
# piki.toml
[performance]
cache_parsed = true      # 缓存解析后的实例 —— 规划中
cache_dir = ".piki_cache"
```

### 选择性加载

```python
# 规则中只加载需要的数据
@rule("TELECOM-POWER-001")
def check_pdu_budget(ctx: Context):
    # 只查询 PDU 和设备，不加载线缆、端口等
    pdus = ctx.query("pdus")
    devices = ctx.query("devices").fields("id", "pdu_id", "tdp_w")
```

## 5. 项目配置详解

`piki.toml` 是项目元数据文件，必须位于项目根目录。piki 通过扫描 `piki.toml` 确定项目边界：

```toml
# piki.toml
[project]
name = "my-datacenter"
version = "1.0.0"

[plugins]
enabled = ["telecom"]

[plugins.telecom]
# 插件特定配置
power_threshold = 0.4          # PDU 负载阈值
rack_usage_threshold = 0.8     # 机柜使用率阈值
```

> 以下配置段当前版本已支持：
>
> ```toml
> [rules.TELECOM-POWER-001]
> warning_only = true            # true 则只警告不报错（不影响整体通过状态）
>
> [generators]
> enabled = ["bom-csv", "my-report"]  # piki generate 无参数时运行这些生成器
> ```
>
> 以下配置段为规划特性，当前版本尚未解析：
>
> ```toml
> [project]
> root = true                    # 声明项目根目录 —— 规划中
>
> [rules]
> # 全局规则配置 —— 规划中
> default_priority = 0
> skip = []                      # 默认跳过的规则
>
> [performance]
> # 性能配置 —— 规划中
> cache_parsed = true
> parallel = 4
>
> [output]
> # 输出配置 —— 规划中
> format = "human"
> verbose = false
> ```

### 为什么需要项目元数据？

| 场景 | 没有 `piki.toml` | 有 `piki.toml` |
|------|-----------------|----------------|
| 子目录执行 `piki check` | 找不到数据，报错 | 向上找到根目录，自动扫描 |
| 多项目仓库 | 不知道哪些目录属于哪个项目 | 每个子项目有自己的 `piki.toml` |
| 插件加载 | 手动指定 `--plugin telecom` | 自动读取 `enabled` 列表 |
| 型号引用 | 手动指定型号路径 | 自动扫描 `library/` 和插件自带型号 |

## 6. 常见问题

### Q: piki 和 folder-db 的关系？

**A:** piki 早期设计曾计划使用 folder-db 作为数据访问层，但当前版本已独立实现 YAML 加载和查询。piki 负责：

- 定义 Family 和约束（pydantic）
- 提供插件机制和规则引擎
- 生成报告和 CI 集成
- YAML 文件的读写和查询

### Q: 已有数据在数据库里，能用 piki 吗？

**A:** 可以。编写适配器将数据库数据导出为 YAML（`import_from_database` 为规划特性）：

```python
# scripts/export_from_db.py
# 规划中：from piki import Project
#
# project = Project(".")
# project.import_from_database(
#     connection_string="postgresql://...",
#     tables=["racks", "devices", "cables"]
# )
```

### Q: 如何扩展 Family？

**A:** 两种方式：

1. **插件内扩展**（推荐，已实现）：开发插件，定义新 Family
2. **项目内扩展**：在 `families/` 目录下定义 —— 规划中：

```python
# families/custom.py —— 规划中
# from piki import Family, Field
#
# class MyDeviceFamily(Family):
#     custom_field: str = Field(...)
```

### Q: 规则可以访问外部 API 吗？

**A:** 可以，但不推荐在检查阶段做。建议在 `piki sync` 阶段拉取外部数据（`piki sync` 为规划特性）：

```bash
# 同步外部数据到本地 YAML —— 规划中
# piki sync --source vendor_api

# 然后检查
piki check
```

### Q: 如何处理敏感数据？

**A:** 敏感字段（如密码、IP）可以加密存储（加密功能为规划特性）：

```yaml
# devices/SRV-01.yaml
id: SRV-01
# 加密字段，前缀 enc: 表示加密 —— 规划中
# ip_address: "enc:AES256:..."
```

```toml
# piki.toml
[security]
encryption_key_file = ".piki_key"  # —— 规划中
```

## 7. 扩展阅读

> 以下文档为规划内容，尚未编写：
>
> - [AI Readiness](05-ai-readiness.md) — Text-Native + 开源如何为 AI 参与工程设计奠定基础
> - [Family 设计指南](../reference/family-design.md)
> - [插件开发指南](../reference/plugin-development.md)
> - [API 参考](../reference/api.md)
> - [电信行业最佳实践](../reference/telecom-best-practices.md)
