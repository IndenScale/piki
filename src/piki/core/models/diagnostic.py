"""Diagnostic 系统 —— 编译器风格的多级诊断报告。

设计目标：
1. 支持 fatal/error/warning/info/debug 五级 severity
2. 支持定位到具体 line/span（文件 + 行号 + 列号 + 长度）
3. 与 LSP (Language Server Protocol) 兼容的 Location/Range/Position 模型
4. 支持 related_information（关联诊断，如"错误发生在这里，但原因在那里"）
5. 支持 code + code_description（错误码 + 链接到文档）

LSP 参考：
- https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#diagnostic
- https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#position
- https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specifications/lsp/3.17/specification/#range
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any


class Severity(IntEnum):
    """诊断严重级别，数值越大越严重。

    与 LSP DiagnosticSeverity 对齐：
    - Error = 1, Warning = 2, Information = 3, Hint = 4
    我们扩展为五级，并增加 FATAL（系统无法继续）。
    """

    DEBUG = 0       # 调试信息，仅在 verbose 模式显示
    INFO = 1        # 一般信息
    WARNING = 2     # 警告，不影响继续执行
    ERROR = 3       # 错误，当前检查项失败，但系统可继续其他检查
    FATAL = 4       # 致命错误，系统无法继续（如配置损坏、核心依赖缺失）

    def __str__(self) -> str:
        return self.name

    @property
    def label(self) -> str:
        """人类可读标签。"""
        return {
            Severity.DEBUG: "DEBUG",
            Severity.INFO: "INFO",
            Severity.WARNING: "WARNING",
            Severity.ERROR: "ERROR",
            Severity.FATAL: "FATAL",
        }[self]

    @property
    def lsp_value(self) -> int | None:
        """映射到 LSP DiagnosticSeverity。

        LSP: Error=1, Warning=2, Info=3, Hint=4
        我们的 DEBUG/INFO 都映射到 Info，FATAL/ERROR 映射到 Error。
        """
        return {
            Severity.DEBUG: 3,      # Information
            Severity.INFO: 3,       # Information
            Severity.WARNING: 2,    # Warning
            Severity.ERROR: 1,      # Error
            Severity.FATAL: 1,      # Error
        }.get(self)


@dataclass(frozen=True)
class Position:
    """LSP-compatible 位置：0-based line and character.

    Args:
        line: 0-based 行号
        character: 0-based 列号（UTF-16 code unit，与 LSP 一致）
    """

    line: int = 0
    character: int = 0

    def __post_init__(self) -> None:
        if self.line < 0:
            object.__setattr__(self, "line", 0)
        if self.character < 0:
            object.__setattr__(self, "character", 0)

    def to_lsp(self) -> dict[str, int]:
        return {"line": self.line, "character": self.character}

    def __str__(self) -> str:
        return f"{self.line + 1}:{self.character + 1}"


@dataclass(frozen=True)
class Range:
    """LSP-compatible 范围：从 start 到 end（半开区间 [start, end)）。"""

    start: Position = field(default_factory=Position)
    end: Position = field(default_factory=Position)

    def to_lsp(self) -> dict[str, dict[str, int]]:
        return {"start": self.start.to_lsp(), "end": self.end.to_lsp()}

    def __str__(self) -> str:
        if self.start == self.end:
            return str(self.start)
        return f"{self.start}-{self.end}"

    @classmethod
    def from_line(cls, line: int, start_col: int = 0, end_col: int | None = None) -> "Range":
        """从单行创建 Range。

        如果 end_col 为 None，则使用 start_col 作为点位置（start == end）。
        """
        end = end_col if end_col is not None else start_col
        return cls(
            start=Position(line=line, character=start_col),
            end=Position(line=line, character=end),
        )

    @classmethod
    def point(cls, line: int, character: int = 0) -> "Range":
        """创建一个点范围（start == end）。"""
        p = Position(line=line, character=character)
        return cls(start=p, end=p)


@dataclass(frozen=True)
class Location:
    """LSP-compatible 位置：文件 URI + 范围。"""

    uri: str  # 文件路径或 URI，如 "file:///path/to/file.yaml"
    range: Range = field(default_factory=Range)

    def to_lsp(self) -> dict[str, Any]:
        return {"uri": self.uri, "range": self.range.to_lsp()}

    @property
    def path(self) -> Path:
        """从 URI 提取路径。"""
        if self.uri.startswith("file://"):
            return Path(self.uri[7:])
        return Path(self.uri)

    @classmethod
    def from_path(
        cls,
        path: Path | str,
        line: int = 0,
        start_col: int = 0,
        end_col: int | None = None,
        character: int | None = None,
    ) -> "Location":
        """从文件路径创建 Location。

        Args:
            path: 文件路径
            line: 0-based 行号
            start_col: 0-based 起始列号
            end_col: 0-based 结束列号（None 则与 start_col 相同）
            character: start_col 的别名（与 Position 参数名一致）
        """
        p = Path(path)
        uri = p.as_uri() if p.is_absolute() else str(p)
        col = character if character is not None else start_col
        return cls(
            uri=uri,
            range=Range.point(line, col) if end_col is None else Range.from_line(line, col, end_col),
        )

    def __str__(self) -> str:
        return f"{self.path}:{self.range}"


@dataclass(frozen=True)
class RelatedInformation:
    """关联诊断信息 —— "错误在这里，但原因是那里的那个值"。

    对应 LSP DiagnosticRelatedInformation。
    """

    location: Location
    message: str

    def to_lsp(self) -> dict[str, Any]:
        return {
            "location": self.location.to_lsp(),
            "message": self.message,
        }


@dataclass(frozen=True)
class CodeDescription:
    """错误码的文档链接。"""

    href: str

    def to_lsp(self) -> dict[str, str]:
        return {"href": self.href}


@dataclass
class Diagnostic:
    """编译器风格的诊断信息。

    对应 LSP Diagnostic 结构，但扩展了 severity 级别和更多元数据。

    Attributes:
        severity: 严重级别
        message: 诊断消息
        location: 发生位置
        code: 错误码（如 "SCHEMA-001", "TELECOM-POWER-001"）
        code_description: 错误码文档链接
        source: 产生诊断的组件（如 "piki.schema", "piki.telecom"）
        related_information: 关联诊断信息列表
        tags: 诊断标签（如 "deprecated", "unnecessary"）
        data: 扩展数据（供下游工具使用）
    """

    severity: Severity
    message: str
    location: Location = field(default_factory=lambda: Location(uri=""))
    code: str = ""
    code_description: CodeDescription | None = None
    source: str = "piki"
    related_information: list[RelatedInformation] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    # 向后兼容：保留 name 属性（用于规则名称）
    name: str = ""

    @property
    def passed(self) -> bool:
        """是否通过（无错误）。DEBUG/INFO/WARNING 视为通过。"""
        return self.severity < Severity.ERROR

    @property
    def is_fatal(self) -> bool:
        return self.severity == Severity.FATAL

    @property
    def is_error(self) -> bool:
        return self.severity == Severity.ERROR

    @property
    def is_warning(self) -> bool:
        return self.severity == Severity.WARNING

    @property
    def file(self) -> str:
        """向后兼容：返回文件路径字符串。"""
        return str(self.location.path) if self.location.uri else ""

    def to_lsp(self) -> dict[str, Any]:
        """转换为 LSP Diagnostic 格式。"""
        result: dict[str, Any] = {
            "range": self.location.range.to_lsp(),
            "message": self.message,
            "severity": self.severity.lsp_value,
            "source": self.source,
        }
        if self.code:
            result["code"] = self.code
        if self.code_description:
            result["codeDescription"] = self.code_description.to_lsp()
        if self.related_information:
            result["relatedInformation"] = [ri.to_lsp() for ri in self.related_information]
        if self.tags:
            result["tags"] = self.tags
        return result

    def to_dict(self) -> dict[str, Any]:
        """转换为 JSON 可序列化的 dict。"""
        return {
            "severity": self.severity.name,
            "message": self.message,
            "location": {
                "uri": self.location.uri,
                "range": {
                    "start": {"line": self.location.range.start.line, "character": self.location.range.start.character},
                    "end": {"line": self.location.range.end.line, "character": self.location.range.end.character},
                },
            },
            "code": self.code,
            "source": self.source,
            "name": self.name,
            "related_information": [
                {"location": {"uri": ri.location.uri, "range": ri.location.range.to_lsp()}, "message": ri.message}
                for ri in self.related_information
            ],
            "tags": self.tags,
        }

    @classmethod
    def from_validation_error(
        cls,
        exc: Exception,
        location: Location,
        code: str = "SCHEMA-001",
        source: str = "piki.schema",
    ) -> "Diagnostic":
        """从 pydantic ValidationError 创建 Diagnostic。"""
        return cls(
            severity=Severity.ERROR,
            message=str(exc),
            location=location,
            code=code,
            source=source,
        )

    @classmethod
    def fatal(
        cls,
        message: str,
        location: Location | None = None,
        code: str = "FATAL-001",
        source: str = "piki",
        name: str = "",
    ) -> "Diagnostic":
        """快速创建 FATAL 诊断。"""
        return cls(
            severity=Severity.FATAL,
            message=message,
            location=location or Location(uri=""),
            code=code,
            source=source,
            name=name,
        )

    @classmethod
    def error(
        cls,
        message: str,
        location: Location | None = None,
        code: str = "",
        source: str = "piki",
        name: str = "",
    ) -> "Diagnostic":
        """快速创建 ERROR 诊断。"""
        return cls(
            severity=Severity.ERROR,
            message=message,
            location=location or Location(uri=""),
            code=code,
            source=source,
            name=name,
        )

    @classmethod
    def warning(
        cls,
        message: str,
        location: Location | None = None,
        code: str = "",
        source: str = "piki",
        name: str = "",
    ) -> "Diagnostic":
        """快速创建 WARNING 诊断。"""
        return cls(
            severity=Severity.WARNING,
            message=message,
            location=location or Location(uri=""),
            code=code,
            source=source,
            name=name,
        )

    @classmethod
    def info(
        cls,
        message: str,
        location: Location | None = None,
        code: str = "",
        source: str = "piki",
        name: str = "",
    ) -> "Diagnostic":
        """快速创建 INFO 诊断。"""
        return cls(
            severity=Severity.INFO,
            message=message,
            location=location or Location(uri=""),
            code=code,
            source=source,
            name=name,
        )

    @classmethod
    def debug(
        cls,
        message: str,
        location: Location | None = None,
        code: str = "",
        source: str = "piki",
        name: str = "",
    ) -> "Diagnostic":
        """快速创建 DEBUG 诊断。"""
        return cls(
            severity=Severity.DEBUG,
            message=message,
            location=location or Location(uri=""),
            code=code,
            source=source,
            name=name,
        )


@dataclass
class DiagnosticReport:
    """诊断报告：一组 Diagnostic 的集合。"""

    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """是否全部通过（无 ERROR/FATAL）。"""
        return all(d.passed for d in self.diagnostics)

    @property
    def fatal_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == Severity.FATAL)

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == Severity.INFO)

    @property
    def debug_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.severity == Severity.DEBUG)

    @property
    def pass_count(self) -> int:
        """通过的数量（severity < ERROR）。"""
        return sum(1 for d in self.diagnostics if d.passed)

    def add(self, diagnostic: Diagnostic) -> None:
        self.diagnostics.append(diagnostic)

    def extend(self, diagnostics: list[Diagnostic]) -> None:
        self.diagnostics.extend(diagnostics)

    def by_severity(self, severity: Severity) -> list[Diagnostic]:
        """按严重级别过滤。"""
        return [d for d in self.diagnostics if d.severity == severity]

    def by_file(self, path: Path | str) -> list[Diagnostic]:
        """按文件路径过滤。"""
        target = Path(path)
        return [d for d in self.diagnostics if d.location.path == target]

    def by_code(self, code: str) -> list[Diagnostic]:
        """按错误码过滤。"""
        return [d for d in self.diagnostics if d.code == code]

    def has_fatal(self) -> bool:
        return self.fatal_count > 0

    def to_lsp(self) -> list[dict[str, Any]]:
        """转换为 LSP Diagnostic 列表。"""
        return [d.to_lsp() for d in self.diagnostics]

    def to_dict(self) -> dict[str, Any]:
        """转换为 JSON 可序列化的 dict。"""
        return {
            "passed": self.passed,
            "fatal_count": self.fatal_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "debug_count": self.debug_count,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }
