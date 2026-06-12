# CLI 命令参考

> 所有 `piki` 命令行接口的完整说明。

## 全局选项

```bash
piki --version        # 显示版本号
piki --help           # 显示帮助信息
```

---

## `piki init`

初始化一个新的 piki 项目。

```bash
piki init [PATH] [--plugin PLUGIN]
```

### 参数

| 参数       | 必填 | 默认值    | 说明                       |
| ---------- | ---- | --------- | -------------------------- |
| `PATH`     | 否   | `.`       | 目标目录，不存在则自动创建 |
| `--plugin` | 否   | `telecom` | 要启用的插件               |

### 示例

```bash
# 在当前目录初始化，使用默认 telecom 插件
piki init

# 在指定目录初始化
piki init ./my-datacenter

# 使用建筑插件
piki init --plugin construction
```

### 执行内容

1. 创建 `piki.toml` 项目配置文件
2. 创建 `.gitignore`（忽略 `.piki_cache/` 和 `reports/`）
3. 安装 Git pre-commit hook（如果目录是 git 仓库）
4. 复制插件模板文件到项目目录

---

## `piki check`

运行设计检查，输出到终端或文件。

```bash
piki check [PATH] [OPTIONS]
```

### 参数

| 参数              | 必填 | 默认值  | 说明                                              |
| ----------------- | ---- | ------- | ------------------------------------------------- |
| `PATH`            | 否   | `.`     | 项目目录（向上扫描 `piki.toml` 确定根目录）       |
| `--format`        | 否   | `human` | 输出格式：`human` / `json` / `junit` / `markdown` |
| `--skip`          | 否   | —       | 跳过指定规则 ID（可多次使用）                     |
| `--only`          | 否   | —       | 只运行指定规则 ID（可多次使用）                   |
| `--files`         | 否   | —       | 只检查指定文件（相对项目根目录的路径）            |
| `--output` / `-o` | 否   | stdout  | 输出到文件而非终端                                |

### 示例

```bash
# 默认人类可读格式
piki check

# JSON 格式，供脚本解析
piki check --format json

# JUnit XML，供 CI 系统解析
piki check --format junit -o report.xml

# Markdown 格式，供 PR 评论
piki check --format markdown -o check-report.md

# 跳过特定规则
piki check --skip TELECOM-POWER-001 --skip TELECOM-RACK-001

# 只检查特定规则
piki check --only TELECOM-POWER-001

# 只检查变更的文件
piki check --files devices/SRV-03.yaml racks/RACK-A01.yaml
```

### 退出码

| 退出码 | 含义                     |
| ------ | ------------------------ |
| `0`    | 所有检查通过             |
| `1`    | 有检查未通过，或发生错误 |

---

## `piki report`

生成设计检查报告文件（默认 markdown 格式）。

```bash
piki report [PATH] [OPTIONS]
```

### 参数

| 参数              | 必填 | 默认值           | 说明                                              |
| ----------------- | ---- | ---------------- | ------------------------------------------------- |
| `PATH`            | 否   | `.`              | 项目目录                                          |
| `--format`        | 否   | `markdown`       | 输出格式：`human` / `json` / `junit` / `markdown` |
| `--skip`          | 否   | —                | 跳过指定规则 ID                                   |
| `--only`          | 否   | —                | 只运行指定规则 ID                                 |
| `--output` / `-o` | 否   | `piki-report.md` | 输出文件路径                                      |

### 示例

```bash
# 生成默认 markdown 报告
piki report

# 指定输出路径
piki report -o ./reports/design-check.md

# JSON 格式报告
piki report --format json -o report.json
```

### 与 `piki check` 的区别

|          | `piki check` | `piki report`    |
| -------- | ------------ | ---------------- |
| 默认输出 | 终端         | 文件             |
| 默认格式 | `human`      | `markdown`       |
| 用途     | 交互式检查   | 生成可分享的报告 |

---

## `piki generate`

运行生成器，导出 BOM、面板图、标签等产物。

```bash
piki generate [GENERATOR] [PATH] [OPTIONS]
```

### 参数

| 参数              | 必填 | 默认值 | 说明                                  |
| ----------------- | ---- | ------ | ------------------------------------- |
| `GENERATOR`       | 否   | —      | 生成器 ID，省略则运行所有启用的生成器 |
| `PATH`            | 否   | `.`    | 项目目录                              |
| `--output` / `-o` | 否   | —      | 输出文件路径                          |

### 示例

```bash
# 运行所有启用的生成器（需在 piki.toml 中配置）
piki generate

# 运行指定生成器
piki generate bom-csv

# 指定输出路径
piki generate bom-csv --output ./bom.csv

# 查看可用生成器
piki generate
# → 未配置时提示：No generators enabled. Available generators: ...
```

### 配置示例

在 `piki.toml` 中启用生成器：

```toml
[generators]
enabled = ["bom-csv", "panel-diagram"]
```

---

## `piki plugins`

插件管理。

### `piki plugins list`

列出所有可用的插件。

```bash
piki plugins list
```

### 示例

```bash
$ piki plugins list
Available plugins:
  telecom              0.1.0
  construction         0.2.0
```

---

## 格式说明

### `human`

适合终端阅读的彩色文本输出，包含：

- 检查概览（通过/失败/警告数）
- 每个失败项的详细说明
- 建议修复方案

### `json`

机器可解析的结构化数据：

```json
{
  "passed": false,
  "summary": { "passed": 8, "failed": 2, "warning": 1 },
  "results": [
    {
      "rule_id": "TELECOM-POWER-001",
      "title": "PDU 功率预算检查",
      "severity": "error",
      "message": "PDU-A 负载 4200W 超过额定 4000W"
    }
  ]
}
```

### `junit`

标准 JUnit XML 格式，兼容 Jenkins、GitLab CI、GitHub Actions 等。

### `markdown`

适合嵌入 PR 评论或文档的报告格式。
