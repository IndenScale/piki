"""AST — 抽象语法树。

YAML 源文件的直接结构化表示。每个 YAML 文件对应一个 SourceFile 节点。
不做语义分析，仅做结构解析。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .span import Span

# ---------------------------------------------------------------------------
# 文件类型
# ---------------------------------------------------------------------------


class FileKind(Enum):
    INSTANCE = "instance"
    MODEL = "model"
    CATALOG = "catalog"
    LAYOUT = "layout"
    MATE = "mate"
    CONFIG = "config"  # piki.toml
    CONNECTION = "connection"
    GRID = "grid"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# 值类型
# ---------------------------------------------------------------------------


class ValueKind(Enum):
    NULL = "null"
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STR = "str"
    LIST = "list"
    MAPPING = "mapping"


@dataclass
class ASTValue:
    """AST 中的值节点。"""
    kind: ValueKind
    data: Any  # None | bool | int | float | str | list[ASTValue] | dict[str, ASTValue]
    span: Span


@dataclass
class Field:
    """一个键值对。"""
    key: str
    value: ASTValue
    span: Span


# ---------------------------------------------------------------------------
# 声明类型
# ---------------------------------------------------------------------------


class DeclKind(Enum):
    INSTANCE = "instance"
    MODEL = "model"
    CATALOG_ENTRY = "catalog_entry"
    LAYOUT_ENTRY = "layout_entry"
    MATE_SPEC = "mate_spec"
    CONNECTION = "connection"
    GRID_DEF = "grid_def"
    CONTEXT_DEF = "context_def"
    SECTION_HEADER = "section_header"  # layout.yaml 中的 [...] section


@dataclass
class Declaration:
    """AST 中的一条顶层声明。"""
    kind: DeclKind
    name: str  # 标识符（instance id, model id 等）
    fields: list[Field] = field(default_factory=list)
    span: Span = field(default_factory=Span.synthetic)


# ---------------------------------------------------------------------------
# SourceFile
# ---------------------------------------------------------------------------


@dataclass
class SourceFile:
    """一个 YAML 源文件的 AST 根节点。"""
    path: Path
    kind: FileKind
    declarations: list[Declaration] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)  # 原始 YAML 数据
    span: Span = field(default_factory=Span.synthetic)

    @property
    def name(self) -> str:
        return self.path.name
