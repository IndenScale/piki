# ADR-005: LSP 兼容的诊断格式

> 状态：已接受  
> 日期：2026-06-11  
> 作者：piki 核心团队

## 背景

piki 的规则引擎产生大量诊断信息：Schema 错误、业务规则失败、外键引用无效……这些信息需要被多种消费者使用：终端用户、CI 系统、IDE 插件、报告生成器。
如何设计一个统一的诊断格式，让所有消费者都能高效处理？本 ADR 记录我们选择 LSP（Language Server Protocol）兼容格式的决策。

---

## 1. 问题：诊断信息的消费者多样性

### 1.1 消费者列表

| 消费者              | 需求               | 期望格式                 |
| ------------------- | ------------------ | ------------------------ |
| **终端用户**        | 人类可读的错误列表 | 彩色文本、行号、建议修复 |
| **CI 系统**         | 机器可解析、可统计 | JUnit XML、JSON          |
| **IDE/编辑器**      | 行内高亮、跳转定位 | LSP Diagnostic           |
| **PR 评论**         | 嵌入代码评审       | Markdown                 |
| **报告生成器**      | 结构化数据、可过滤 | JSON / 对象模型          |
| **未来 LSP 服务器** | 实时诊断推送       | LSP PublishDiagnostics   |

### 1.2 如果没有统一格式

```python
# ❌ 反模式：每个消费者单独实现解析
class HumanFormatter:
    def format(self, results: list[RuleResult]):
        # 从 RuleResult 提取信息
        ...

class JunitFormatter:
    def format(self, results: list[RuleResult]):
        # 从 RuleResult 提取信息，但字段不够
        ...

class LspHandler:
    def handle(self, results: list[RuleResult]):
        # RuleResult 没有 range，无法定位到具体字符
        ...
```

问题：

- 每个消费者重复解析逻辑
- 新增消费者时需要修改核心数据结构
- 信息丢失（如 RuleResult 只有 `file` 字符串，没有行/列/范围）

---

## 2. 为什么是 LSP 格式

### 2.1 LSP Diagnostic 的结构

```typescript
// LSP 3.17 Specification
interface Diagnostic {
  range: Range; // 错误位置（精确到字符）
  severity?: DiagnosticSeverity; // 级别：Error/Warning/Info/Hint
  code?: string | integer; // 错误码
  codeDescription?: CodeDescription; // 错误码文档链接
  source?: string; // 产生诊断的组件
  message: string; // 诊断消息
  relatedInformation?: DiagnosticRelatedInformation[]; // 关联信息
  tags?: DiagnosticTag[]; // 标签：Unnecessary/Deprecated
}

interface Range {
  start: Position; // { line: number, character: number }
  end: Position;
}
```

### 2.2 LSP 格式的优势

| 维度           | LSP 格式                                           | 自定义格式              |
| -------------- | -------------------------------------------------- | ----------------------- |
| **编辑器生态** | ✅ VS Code、Vim、Emacs、JetBrains 原生支持         | ❌ 需自行开发插件       |
| **定位精度**   | ✅ 精确到字符范围（Range）                         | ⚠️ 通常只有行号         |
| **关联信息**   | ✅ relatedInformation 支持"错误在这里，原因在那里" | ⚠️ 需自行设计           |
| **错误码体系** | ✅ code + codeDescription 标准化                   | ⚠️ 各项目自行定义       |
| **扩展性**     | ✅ data 字段可携带任意附加信息                     | ⚠️ 修改 schema 破坏兼容 |
| **社区标准**   | ✅ 微软主导，广泛采用                              | ❌ 孤立标准             |

### 2.3 piki 的扩展

LSP 标准只有四级 severity（Error/Warning/Info/Hint），piki 扩展为五级：

```python
class Severity(IntEnum):
    DEBUG = 0       # 调试信息，verbose 模式显示
    INFO = 1        # 一般信息
    WARNING = 2     # 警告
    ERROR = 3       # 错误，当前检查项失败
    FATAL = 4       # 致命错误，系统无法继续
```

映射到 LSP：

- FATAL/ERROR → LSP Error (1)
- WARNING → LSP Warning (2)
- INFO/DEBUG → LSP Information (3)

---

## 3. piki 的诊断系统设计

### 3.1 核心类

```python
# src/piki/core/models/diagnostic.py

@dataclass(frozen=True)
class Position:
    """LSP-compatible 位置：0-based line and character."""
    line: int = 0
    character: int = 0

@dataclass(frozen=True)
class Range:
    """LSP-compatible 范围：[start, end) 半开区间."""
    start: Position = field(default_factory=Position)
    end: Position = field(default_factory=Position)

@dataclass(frozen=True)
class Location:
    """LSP-compatible 位置：文件 URI + 范围."""
    uri: str
    range: Range = field(default_factory=Range)

@dataclass
class Diagnostic:
    """编译器风格的诊断信息，与 LSP Diagnostic 结构对应."""
    severity: Severity
    message: str
    location: Location = field(default_factory=lambda: Location(uri=""))
    code: str = ""                    # 错误码，如 "TELECOM-POWER-001"
    code_description: CodeDescription | None = None  # 文档链接
    source: str = "piki"              # 产生组件，如 "piki.telecom"
    related_information: list[RelatedInformation] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)  # 扩展数据
```

### 3.2 源码位置追踪

诊断的精确位置来自 YAML 源码追踪：

```python
# src/piki/core/parsing/yaml_source.py

class SourceTrackedDict(dict):
    """带源码位置追踪的 dict。"""
    def _set_source(self, key: str, mark: SourceMark) -> None:
        self._source_marks[key] = mark

    def _get_source(self, key: str) -> SourceMark | None:
        return self._source_marks.get(key)

# 加载 YAML 时自动追踪
node = yaml.compose(f)
tracked = _compose_to_tracked(node, path)
# tracked._get_source("rack_id") → SourceMark(path, line=5, column=0)
```

当 pydantic 校验失败时：

```python
# 从 ValidationError 定位到具体字段的行号
field_line = get_field_line(data, error["loc"][-1])
location = Location.from_path(path, line=field_line)
```

### 3.3 关联信息（Related Information）

工程诊断经常需要"跨文件引用"：

```
错误：设备 SRV-03 引用的机柜 RACK-A01 不存在
      ↑
      发生在 devices/SRV-03.yaml 第 4 行

      原因：机柜列表中没有 RACK-A01
      ↑
      关联到 racks/ 目录为空
```

```python
diagnostic = Diagnostic.error(
    message="设备 SRV-03 引用的机柜 RACK-A01 不存在",
    location=Location.from_path("devices/SRV-03.yaml", line=4),
    code="TELECOM-FK-001",
    related_information=[
        RelatedInformation(
            location=Location.from_path("racks/"),
            message="机柜目录为空，未定义任何机柜",
        )
    ],
)
```

在 IDE 中显示为：

- 主错误：devices/SRV-03.yaml 第 4 行红色波浪线
- 关联信息：racks/ 目录黄色提示"机柜目录为空"

---

## 4. 报告格式实现

所有报告格式都基于同一 Diagnostic 模型：

```python
# src/piki/core/reporting/formats.py

def format_human(report: DiagnosticReport) -> str:
    """终端友好的彩色文本。"""
    ...

def format_json(report: DiagnosticReport) -> str:
    """JSON 格式，供脚本解析。"""
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)

def format_junit(report: DiagnosticReport) -> str:
    """JUnit XML，供 CI 系统解析。"""
    ...

def format_markdown(report: DiagnosticReport) -> str:
    """Markdown 格式，供 PR 评论。"""
    ...
```

**关键设计**：不是"每种格式从原始结果解析"，而是"所有结果先统一为 Diagnostic，再序列化为不同格式"。

---

## 5. 未来：LSP 服务器

Diagnostic 的 LSP 兼容性为未来实现 `piki-lsp` 奠定了基础：

```python
# 未来可能的 piki-lsp 实现
from lsprotocol.types import *

class PikiLanguageServer:
    def on_document_change(self, uri: str, content: str):
        # 1. 解析 YAML
        # 2. 运行 L0-L3 检查
        # 3. 转换为 LSP Diagnostic
        diagnostics = [d.to_lsp() for d in report.diagnostics]

        # 4. 推送给客户端
        self.publish_diagnostics(uri, diagnostics)
```

用户安装 VS Code 插件后：

- 编辑 YAML 时实时看到错误波浪线
- 鼠标悬停显示详细错误信息
- 点击关联信息跳转到引用位置
- 错误码链接到在线文档

---

## 6. 决策总结

| 决策         | 选择                                   | 核心理由                               |
| ------------ | -------------------------------------- | -------------------------------------- |
| **诊断模型** | LSP-compatible Diagnostic              | 编辑器生态原生支持、定位精确、扩展性强 |
| **位置追踪** | PyYAML AST + SourceTrackedDict         | 零额外解析开销、精确到字段级别         |
| **Severity** | 五级（DEBUG/INFO/WARNING/ERROR/FATAL） | 比 LSP 标准更细，映射简单              |
| **关联信息** | RelatedInformation                     | 工程诊断天然需要跨文件引用             |
| **报告格式** | 统一 Diagnostic → 多格式序列化         | 避免重复解析、新增格式成本低           |
| **未来兼容** | 预留 LSP 服务器接口                    | 今天的设计为明天的 IDE 插件铺路        |

---

## 参考

- [LSP 3.17 Specification — Diagnostic](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#diagnostic)
- [LSP 3.17 Specification — Position](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#position)
- [piki 诊断系统源码](https://github.com/indenscale/piki/blob/main/src/piki/core/models/diagnostic.py)
- [piki YAML 源码追踪](https://github.com/indenscale/piki/blob/main/src/piki/core/parsing/yaml_source.py)
- [ADR-004: 多级质量检查](004-multi-level-quality-checks.md) — 诊断信息的分层产生
