"""MIR — 中级中间表示。

所有引用已消解为直接指针；Model/Instance 已合并；类型已检查。
MIR 是编译器后端（Project 生成、几何构建、诊断报告）的输入层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from adl.geometry import Transform

from .span import Span
from .type_system import FamilyDef


class MIRValueKind(Enum):
    LITERAL = "literal"
    INSTANCE_PTR = "instance_ptr"
    INTERFACE_PTR = "interface_ptr"
    MODEL_PTR = "model_ptr"
    CATALOG_PTR = "catalog_ptr"
    GRID_PTR = "grid_ptr"
    MATE_PTR = "mate_ptr"
    LIST = "list"
    MAPPING = "mapping"


@dataclass
class MIRValue:
    """MIR 中的值：引用已消解为指针或字面量。"""

    data: Any
    kind: MIRValueKind
    span: Span = field(default_factory=Span.synthetic)

    @classmethod
    def literal(cls, value: Any, span: Span | None = None) -> "MIRValue":
        return cls(kind=MIRValueKind.LITERAL, data=value, span=span or Span.synthetic())

    @classmethod
    def instance_ptr(cls, inst: "ResolvedInstanceIR", span: Span | None = None) -> "MIRValue":
        return cls(kind=MIRValueKind.INSTANCE_PTR, data=inst, span=span or Span.synthetic())

    @classmethod
    def interface_ptr(cls, iface: "ResolvedInterfaceIR", span: Span | None = None) -> "MIRValue":
        return cls(kind=MIRValueKind.INTERFACE_PTR, data=iface, span=span or Span.synthetic())

    @classmethod
    def model_ptr(cls, model: "ResolvedModelIR", span: Span | None = None) -> "MIRValue":
        return cls(kind=MIRValueKind.MODEL_PTR, data=model, span=span or Span.synthetic())

    @classmethod
    def catalog_ptr(cls, catalog: "ResolvedCatalogIR", span: Span | None = None) -> "MIRValue":
        return cls(kind=MIRValueKind.CATALOG_PTR, data=catalog, span=span or Span.synthetic())

    @classmethod
    def grid_ptr(cls, grid: "ResolvedGridIR", span: Span | None = None) -> "MIRValue":
        return cls(kind=MIRValueKind.GRID_PTR, data=grid, span=span or Span.synthetic())

    @classmethod
    def mate_ptr(cls, mate: "ResolvedMateIR", span: Span | None = None) -> "MIRValue":
        return cls(kind=MIRValueKind.MATE_PTR, data=mate, span=span or Span.synthetic())

    @classmethod
    def lst(cls, data: list["MIRValue"], span: Span | None = None) -> "MIRValue":
        return cls(kind=MIRValueKind.LIST, data=data, span=span or Span.synthetic())

    @classmethod
    def mapping(cls, data: dict[str, "MIRValue"], span: Span | None = None) -> "MIRValue":
        return cls(kind=MIRValueKind.MAPPING, data=data, span=span or Span.synthetic())


@dataclass
class ResolvedInterfaceIR:
    """消解后的 Interface：指向所属 Instance。"""

    id: str
    parent: "ResolvedInstanceIR"
    interface_type: str
    active_type: str | None = None
    direction: str = "bidirectional"
    description: str = ""
    specs: dict[str, Any] = field(default_factory=dict)
    local_transform: Transform | None = None
    mating_kind: str | None = None
    mating_params: dict[str, Any] = field(default_factory=dict)
    signature: Any = None
    span: Span = field(default_factory=Span.synthetic)

    @property
    def qualified_id(self) -> str:
        return f"{self.parent.id}/{self.id}"


@dataclass
class ResolvedModelIR:
    """消解后的 Model。"""

    id: str
    namespace: str
    family: FamilyDef | None
    fields: dict[str, MIRValue] = field(default_factory=dict)
    source: Path | None = None
    span: Span = field(default_factory=Span.synthetic)


@dataclass
class ResolvedCatalogIR:
    """消解后的 Catalog Entry。"""

    id: str
    namespace: str
    family: str
    model: ResolvedModelIR | None = None
    source: str = "project"
    fields: dict[str, MIRValue] = field(default_factory=dict)
    service_methods: list[str] = field(default_factory=list)
    source_path: Path | None = None
    span: Span = field(default_factory=Span.synthetic)


@dataclass
class ResolvedGridIR:
    """消解后的 Grid。"""

    id: str
    namespace: str
    grid_type: str = "orthogonal"
    origin: Any = None
    axes: list[Any] = field(default_factory=list)
    source: Path | None = None
    span: Span = field(default_factory=Span.synthetic)


@dataclass
class ResolvedLayoutEntryIR:
    """消解后的 LayoutEntry：指向 Instance/Grid。"""

    instance: ResolvedInstanceIR
    rack: ResolvedInstanceIR | None = None
    pdu: ResolvedInstanceIR | None = None
    position_u: int | None = None
    parent: ResolvedInstanceIR | None = None
    grid: ResolvedGridIR | None = None
    grid_position: tuple[str, str] | None = None
    row_id: str | None = None
    bay_index: int | None = None
    position_x_mm: float | None = None
    position_y_mm: float | None = None
    position_z_mm: float | None = None
    transform: Transform | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    span: Span = field(default_factory=Span.synthetic)


@dataclass
class ResolvedLayoutIR:
    """消解后的 Layout。"""

    id: str
    namespace: str
    entries: dict[str, ResolvedLayoutEntryIR] = field(default_factory=dict)
    grids: dict[str, ResolvedGridIR] = field(default_factory=dict)
    source: Path | None = None
    span: Span = field(default_factory=Span.synthetic)


@dataclass
class ResolvedMateIR:
    """消解后的 Mate：parent/child 已消解为 Instance 指针。"""

    id: str
    namespace: str
    mate_type: str
    parent: ResolvedInstanceIR
    child: ResolvedInstanceIR
    parent_interface: ResolvedInterfaceIR | None = None
    child_interface: ResolvedInterfaceIR | None = None
    constraints: list[Any] = field(default_factory=list)
    interface_pairings: list[Any] = field(default_factory=list)
    at: dict[str, Any] = field(default_factory=dict)
    span: Span = field(default_factory=Span.synthetic)


@dataclass
class ResolvedInstanceIR:
    """消解后的 Instance：合并 Model 默认值与 Instance 覆盖值。"""

    id: str
    fqid: str
    namespace: str
    family: FamilyDef | None = None
    family_name: str = ""
    model: ResolvedModelIR | None = None
    fields: dict[str, MIRValue] = field(default_factory=dict)
    overrides: dict[str, MIRValue] = field(default_factory=dict)
    interfaces: dict[str, ResolvedInterfaceIR] = field(default_factory=dict)
    footprints: dict[str, list[ResolvedInterfaceIR]] = field(default_factory=dict)
    catalog: ResolvedCatalogIR | None = None
    tags: dict[str, str] = field(default_factory=dict)
    bbox: Any = None
    source: Path | None = None
    span: Span = field(default_factory=Span.synthetic)
    resolved_data: dict[str, Any] = field(default_factory=dict)
    validation_error: str = ""


@dataclass
class ResolvedCompilation:
    """MIR 根节点。"""

    hir: Any  # Compilation
    resolved_instances: dict[str, ResolvedInstanceIR] = field(default_factory=dict)
    resolved_models: dict[str, ResolvedModelIR] = field(default_factory=dict)
    resolved_catalogs: dict[str, ResolvedCatalogIR] = field(default_factory=dict)
    resolved_layouts: dict[str, ResolvedLayoutIR] = field(default_factory=dict)
    resolved_mates: dict[str, ResolvedMateIR] = field(default_factory=dict)
    resolved_grids: dict[str, ResolvedGridIR] = field(default_factory=dict)
    diagnostics: list[Any] = field(default_factory=list)
