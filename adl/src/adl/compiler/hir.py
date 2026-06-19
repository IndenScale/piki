"""HIR — 高级中间表示。

AST 经过 Lowering 后得到 HIR：
- 命名空间已建立
- 符号表已填充（定义端）
- 语义单元已分类（InstanceUnit / ModelUnit / etc.）
- 引用记录为 SymbolRef（未消解）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .span import Span
from .symbols import RefKind, SymbolRef, SymbolTable
from .type_system import TypeSystem

# ---------------------------------------------------------------------------
# HIR 值
# ---------------------------------------------------------------------------


class HIRValueKind(Enum):
    LITERAL = "literal"
    REFERENCE = "reference"
    LIST = "list"
    MAPPING = "mapping"


@dataclass
class HIRValue:
    kind: HIRValueKind
    data: Any
    span: Span = field(default_factory=Span.synthetic)

    @classmethod
    def literal(cls, value: Any, span: Span | None = None) -> "HIRValue":
        return cls(kind=HIRValueKind.LITERAL, data=value, span=span or Span.synthetic())

    @classmethod
    def ref(cls, text: str, kind: RefKind, span: Span | None = None) -> "HIRValue":
        return cls(
            kind=HIRValueKind.REFERENCE,
            data=SymbolRef(text=text, kind=kind, span=span or Span.synthetic()),
            span=span or Span.synthetic(),
        )

    @classmethod
    def mapping(cls, data: dict[str, "HIRValue"], span: Span | None = None) -> "HIRValue":
        return cls(kind=HIRValueKind.MAPPING, data=data, span=span or Span.synthetic())

    @classmethod
    def lst(cls, data: list["HIRValue"], span: Span | None = None) -> "HIRValue":
        return cls(kind=HIRValueKind.LIST, data=data, span=span or Span.synthetic())

    def as_ref(self) -> SymbolRef | None:
        if self.kind == HIRValueKind.REFERENCE and isinstance(self.data, SymbolRef):
            return self.data
        return None

    def as_str(self) -> str | None:
        if self.kind == HIRValueKind.LITERAL and isinstance(self.data, str):
            return self.data
        return None


# ---------------------------------------------------------------------------
# 语义单元
# ---------------------------------------------------------------------------


class UnitKind(Enum):
    INSTANCE = "instance"
    MODEL = "model"
    CATALOG = "catalog"
    LAYOUT = "layout"
    MATE = "mate"
    GRID = "grid"


@dataclass
class InterfaceHIR:
    id: str
    interface_type: str
    active_type: str | None = None
    direction: str = "bidirectional"
    description: str = ""
    specs: dict[str, Any] = field(default_factory=dict)
    local_transform: dict[str, Any] | None = None
    mating_params: dict[str, Any] = None
    span: Span = field(default_factory=Span.synthetic)


@dataclass
class FootprintHIR:
    id: str
    footprint_type: str
    description: str = ""
    pins: list[InterfaceHIR] = field(default_factory=list)
    span: Span = field(default_factory=Span.synthetic)


# ── HIR 语义单元 ──


@dataclass
class InstanceUnit:
    id: str
    namespace: str = ""
    kind: UnitKind = UnitKind.INSTANCE
    span: Span = field(default_factory=Span.synthetic)
    ast_source: Path | None = None
    family_ref: SymbolRef | None = None
    model_ref: SymbolRef | None = None
    fields: dict[str, HIRValue] = field(default_factory=dict)
    interfaces: list[InterfaceHIR] = field(default_factory=list)
    footprints: list[FootprintHIR] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    catalog_raw: dict[str, Any] | None = None


@dataclass
class ModelUnit:
    id: str
    namespace: str = ""
    kind: UnitKind = UnitKind.MODEL
    span: Span = field(default_factory=Span.synthetic)
    ast_source: Path | None = None
    family_ref: SymbolRef | None = None
    fields: dict[str, HIRValue] = field(default_factory=dict)
    interfaces: list[InterfaceHIR] = field(default_factory=list)
    footprints: list[FootprintHIR] = field(default_factory=list)


@dataclass
class CatalogUnit:
    id: str
    namespace: str = ""
    kind: UnitKind = UnitKind.CATALOG
    span: Span = field(default_factory=Span.synthetic)
    ast_source: Path | None = None
    catalog_family: str = "ComponentCatalogFamily"
    model_ref: SymbolRef | None = None
    source: str = "project"
    fields: dict[str, HIRValue] = field(default_factory=dict)
    service_methods: list[str] = field(default_factory=list)


@dataclass
class LayoutEntryHIR:
    instance_ref: SymbolRef
    rack_ref: SymbolRef | None = None
    position_u: int | None = None
    pdu_ref: SymbolRef | None = None
    parent_ref: SymbolRef | None = None
    grid_ref: SymbolRef | None = None
    grid_position: tuple[str, str] | None = None
    row_id: str | None = None
    bay_index: int | None = None
    position_x_mm: float | None = None
    position_y_mm: float | None = None
    position_z_mm: float | None = None
    transform: Any = None
    span: Span = field(default_factory=Span.synthetic)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class LayoutUnit:
    id: str = "layout"
    namespace: str = ""
    kind: UnitKind = UnitKind.LAYOUT
    span: Span = field(default_factory=Span.synthetic)
    ast_source: Path | None = None
    entries: list[LayoutEntryHIR] = field(default_factory=list)


@dataclass
class MateUnit:
    id: str
    namespace: str = ""
    kind: UnitKind = UnitKind.MATE
    span: Span = field(default_factory=Span.synthetic)
    ast_source: Path | None = None
    mate_type: str = ""
    parent_ref: SymbolRef | None = None
    child_ref: SymbolRef | None = None
    constraints: list[dict[str, Any]] = field(default_factory=list)
    interface_pairings: list[Any] = field(default_factory=list)
    at: dict[str, Any] = field(default_factory=dict)


@dataclass
class GridUnit:
    id: str
    namespace: str = ""
    kind: UnitKind = UnitKind.GRID
    span: Span = field(default_factory=Span.synthetic)
    ast_source: Path | None = None
    axes: list[dict[str, Any]] = field(default_factory=list)
    fields: dict[str, HIRValue] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Compilation (HIR 根)
# ---------------------------------------------------------------------------


@dataclass
class Compilation:
    """HIR 根节点：一次编译的完整语义表示。"""
    root: Path
    config: dict[str, Any] = field(default_factory=dict)
    symbol_table: SymbolTable = field(default_factory=SymbolTable)
    type_system: TypeSystem = field(default_factory=TypeSystem)
    units: dict[str, Any] = field(default_factory=dict)

    # 按类型索引
    instances: dict[str, InstanceUnit] = field(default_factory=dict)
    models: dict[str, ModelUnit] = field(default_factory=dict)
    catalogs: dict[str, CatalogUnit] = field(default_factory=dict)
    layouts: dict[str, LayoutUnit] = field(default_factory=dict)
    mates: dict[str, MateUnit] = field(default_factory=dict)
    grids: dict[str, GridUnit] = field(default_factory=dict)

    def add_unit(self, unit: Any) -> None:
        key = f"{unit.namespace}:{unit.id}" if unit.namespace else unit.id
        self.units[key] = unit
        if isinstance(unit, InstanceUnit):
            self.instances[unit.id] = unit
        elif isinstance(unit, ModelUnit):
            self.models[unit.id] = unit
        elif isinstance(unit, CatalogUnit):
            self.catalogs[unit.id] = unit
        elif isinstance(unit, LayoutUnit):
            self.layouts[unit.namespace or "root"] = unit
        elif isinstance(unit, MateUnit):
            self.mates[unit.id] = unit
        elif isinstance(unit, GridUnit):
            self.grids[unit.id] = unit
