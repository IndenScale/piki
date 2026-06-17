"""LoweringPass — AST → HIR。

将 SourceFile 转换为 Compilation，建立符号表，分类语义单元。
"""

from __future__ import annotations

from ..ast_ import (
    ASTValue,
    DeclKind,
    Field,
    FileKind,
    SourceFile,
    ValueKind,
)
from ..hir import (
    CatalogUnit,
    Compilation,
    FootprintHIR,
    GridUnit,
    HIRValue,
    HIRValueKind,
    InstanceUnit,
    InterfaceHIR,
    LayoutEntryHIR,
    LayoutUnit,
    MateUnit,
    ModelUnit,
)
from ..pass_manager import Pass, PassContext, PassResult, PassStage
from ..span import Span
from ..symbols import RefKind, Symbol, SymbolKind, SymbolRef
from ..type_system import TypeSystem


def _ast_value_to_hir(value: ASTValue) -> HIRValue:
    """递归转换 ASTValue → HIRValue。"""
    if value.kind == ValueKind.MAPPING:
        assert isinstance(value.data, dict)
        return HIRValue(
            kind=HIRValueKind.MAPPING,
            data={k: _ast_value_to_hir(v) for k, v in value.data.items()},
            span=value.span,
        )
    elif value.kind == ValueKind.LIST:
        assert isinstance(value.data, list)
        return HIRValue(
            kind=HIRValueKind.LIST,
            data=[_ast_value_to_hir(item) for item in value.data],
            span=value.span,
        )
    else:
        return HIRValue(kind=HIRValueKind.LITERAL, data=value.data, span=value.span)


def _is_ref_field(key: str) -> RefKind | None:
    """判断字段是否可能包含引用。"""
    _REF_FIELDS: dict[str, RefKind] = {
        "family": RefKind.FAMILY,
        "model": RefKind.MODEL,
        "rack_id": RefKind.RACK,
        "pdu_id": RefKind.PDU,
        "parent": RefKind.INSTANCE,
        "child": RefKind.INSTANCE,
        "catalog": RefKind.CATALOG,
        "grid_id": RefKind.GRID,
        "mate_type": RefKind.MATE_TYPE,
        "instance": RefKind.INSTANCE,
    }
    return _REF_FIELDS.get(key)


def _fields_to_hir(
    fields: list[Field],
    root_path: Any,
) -> dict[str, HIRValue]:
    """将 AST Field 列表转换为 HIR 字段字典。

    对已知引用字段生成 HIRValue(kind=REFERENCE)，
    其他字段生成 HIRValue(kind=LITERAL)。
    """
    result: dict[str, HIRValue] = {}
    for f in fields:
        ref_kind = _is_ref_field(f.key)
        if ref_kind is not None and f.value.kind == ValueKind.STR:
            result[f.key] = HIRValue.ref(f.value.data, ref_kind, f.value.span)
        else:
            result[f.key] = _ast_value_to_hir(f.value)
    return result


def _lower_instance(
    sf: SourceFile,
    decl: Any,
    hir_unit_id: str,
    namespace: str,
) -> InstanceUnit:
    """将单个 Instance AST 节点 Lower 为 InstanceUnit。"""
    fields = _fields_to_hir(decl.fields, sf.path)

    unit = InstanceUnit(
        id=hir_unit_id,
        namespace=namespace,
        span=decl.span,
        ast_source=sf.path,
        fields=fields,
    )

    # Family 引用
    family_val = fields.get("family")
    if family_val and family_val.kind == HIRValueKind.REFERENCE:
        unit.family_ref = family_val.as_ref()

    # Model 引用
    model_val = fields.get("model")
    if model_val and model_val.kind == HIRValueKind.REFERENCE:
        unit.model_ref = model_val.as_ref()

    # Interfaces
    ifaces_val = fields.get("interfaces")
    if ifaces_val and ifaces_val.kind == HIRValueKind.LIST:
        for item in ifaces_val.data:
            if isinstance(item, HIRValue) and item.kind == HIRValueKind.MAPPING:
                unit.interfaces.append(_hir_to_interface(item))

    # Footprints
    fps_val = fields.get("footprints")
    if fps_val and fps_val.kind == HIRValueKind.LIST:
        for item in fps_val.data:
            if isinstance(item, HIRValue) and item.kind == HIRValueKind.MAPPING:
                unit.footprints.append(_hir_to_footprint(item))

    # Tags
    tags_val = fields.get("tags")
    if tags_val and tags_val.kind == HIRValueKind.MAPPING:
        data = tags_val.data
        if isinstance(data, dict):
            unit.tags = {
                k: v.data
                for k, v in data.items()
                if isinstance(v, HIRValue) and v.kind == HIRValueKind.LITERAL
            }

    # Catalog raw
    catalog_val = fields.get("catalog")
    if catalog_val:
        if catalog_val.kind == HIRValueKind.LITERAL:
            unit.catalog_raw = {"id": catalog_val.data}
        elif catalog_val.kind == HIRValueKind.MAPPING and isinstance(catalog_val.data, dict):
            unit.catalog_raw = {
                k: v.data
                for k, v in catalog_val.data.items()
                if isinstance(v, HIRValue) and v.kind == HIRValueKind.LITERAL
            }

    return unit


def _hir_to_interface(item: HIRValue) -> InterfaceHIR:
    """从 HIR MAPPING 值提取 InterfaceHIR。"""
    data = item.data
    if not isinstance(data, dict):
        return InterfaceHIR(id="unknown", interface_type="unknown")

    def _get_str(key: str) -> str:
        v = data.get(key)
        if isinstance(v, HIRValue) and v.kind == HIRValueKind.LITERAL:
            return str(v.data) if v.data is not None else ""
        return ""

    def _get_specs() -> dict[str, Any]:
        specs_val = data.get("specs")
        if isinstance(specs_val, HIRValue) and specs_val.kind == HIRValueKind.MAPPING:
            sd = specs_val.data
            if isinstance(sd, dict):
                return {
                    k: v.data
                    for k, v in sd.items()
                    if isinstance(v, HIRValue) and v.kind == HIRValueKind.LITERAL
                }
        return {}

    return InterfaceHIR(
        id=_get_str("id"),
        interface_type=_get_str("interface_type"),
        active_type=_get_str("active_type") or None,
        direction=_get_str("direction") or "bidirectional",
        description=_get_str("description"),
        specs=_get_specs(),
    )


def _hir_to_footprint(item: HIRValue) -> FootprintHIR:
    """从 HIR MAPPING 值提取 FootprintHIR。"""
    data = item.data
    if not isinstance(data, dict):
        return FootprintHIR(id="unknown", footprint_type="unknown")

    def _get_str(key: str) -> str:
        v = data.get(key)
        if isinstance(v, HIRValue) and v.kind == HIRValueKind.LITERAL:
            return str(v.data) if v.data is not None else ""
        return ""

    pins: list[InterfaceHIR] = []
    pins_val = data.get("pins")
    if isinstance(pins_val, HIRValue) and pins_val.kind == HIRValueKind.LIST:
        for pin_item in pins_val.data:
            if isinstance(pin_item, HIRValue) and pin_item.kind == HIRValueKind.MAPPING:
                pins.append(_hir_to_interface(pin_item))

    return FootprintHIR(
        id=_get_str("id"),
        footprint_type=_get_str("footprint_type"),
        description=_get_str("description"),
        pins=pins,
    )


def _lower_model(
    sf: SourceFile,
    decl: Any,
    hir_unit_id: str,
    namespace: str,
) -> ModelUnit:
    fields = _fields_to_hir(decl.fields, sf.path)
    unit = ModelUnit(
        id=hir_unit_id,
        namespace=namespace,
        span=decl.span,
        ast_source=sf.path,
        fields=fields,
    )
    family_val = fields.get("family")
    if family_val and family_val.kind == HIRValueKind.REFERENCE:
        unit.family_ref = family_val.as_ref()
    return unit


def _lower_catalog(
    sf: SourceFile,
    decl: Any,
    hir_unit_id: str,
    namespace: str,
) -> CatalogUnit:
    fields = _fields_to_hir(decl.fields, sf.path)
    unit = CatalogUnit(
        id=hir_unit_id,
        namespace=namespace,
        span=decl.span,
        ast_source=sf.path,
        fields=fields,
    )
    family_val = fields.get("family")
    if family_val:
        raw_family = (
            family_val.data.text
            if family_val.kind == HIRValueKind.REFERENCE
            else str(family_val.data)
        )
        unit.catalog_family = raw_family
    model_val = fields.get("model_ref") or fields.get("model")
    if model_val and model_val.kind == HIRValueKind.REFERENCE:
        unit.model_ref = model_val.as_ref()
    return unit


def _lower_layout(
    sf: SourceFile,
    namespace: str,
) -> LayoutUnit:
    unit = LayoutUnit(namespace=namespace, span=Span.point(sf.path, 0, 0))
    for decl in sf.declarations:
        if decl.kind != DeclKind.LAYOUT_ENTRY:
            continue
        fields = _fields_to_hir(decl.fields, sf.path)

        inst_ref = fields.get("instance")
        instance_ref = (
            inst_ref.as_ref()
            if inst_ref and inst_ref.kind == HIRValueKind.REFERENCE
            else SymbolRef(text="", kind=RefKind.INSTANCE)
        )

        rack_val = fields.get("rack_id")
        rack_ref = rack_val.as_ref() if rack_val and rack_val.kind == HIRValueKind.REFERENCE else None

        pdu_val = fields.get("pdu_id")
        pdu_ref = pdu_val.as_ref() if pdu_val and pdu_val.kind == HIRValueKind.REFERENCE else None

        parent_val = fields.get("parent")
        parent_ref = parent_val.as_ref() if parent_val and parent_val.kind == HIRValueKind.REFERENCE else None

        grid_val = fields.get("grid_id")
        grid_ref = grid_val.as_ref() if grid_val and grid_val.kind == HIRValueKind.REFERENCE else None

        entry = LayoutEntryHIR(
            instance_ref=instance_ref,
            rack_ref=rack_ref,
            position_u=_get_int_field(fields, "position_u"),
            pdu_ref=pdu_ref,
            parent_ref=parent_ref,
            grid_ref=grid_ref,
            grid_position=_get_grid_pos(fields),
            row_id=_get_str_field(fields, "row_id"),
            bay_index=_get_int_field(fields, "bay_index"),
            position_x_mm=_get_float_field(fields, "position_x_mm"),
            position_y_mm=_get_float_field(fields, "position_y_mm"),
            position_z_mm=_get_float_field(fields, "position_z_mm"),
            span=decl.span,
        )
        unit.entries.append(entry)
    return unit


def _lower_mate(
    sf: SourceFile,
    decl: Any,
    namespace: str,
) -> MateUnit:
    fields = _fields_to_hir(decl.fields, sf.path)
    unit = MateUnit(
        id=decl.name,
        namespace=namespace,
        span=decl.span,
        ast_source=sf.path,
        mate_type=_get_str_field(fields, "type"),
    )
    parent_val = fields.get("parent")
    if parent_val and parent_val.kind == HIRValueKind.REFERENCE:
        unit.parent_ref = parent_val.as_ref()
    child_val = fields.get("child")
    if child_val and child_val.kind == HIRValueKind.REFERENCE:
        unit.child_ref = child_val.as_ref()
    return unit


def _lower_grid(sf: SourceFile, decl: Any, namespace: str) -> GridUnit:
    fields = _fields_to_hir(decl.fields, sf.path)
    return GridUnit(
        id=decl.name,
        namespace=namespace,
        span=decl.span,
        ast_source=sf.path,
        fields=fields,
    )


# Helpers

def _get_str_field(fields: dict[str, HIRValue], key: str) -> str:
    v = fields.get(key)
    if v and v.kind == HIRValueKind.LITERAL and v.data is not None:
        return str(v.data)
    return ""


def _get_int_field(fields: dict[str, HIRValue], key: str) -> int | None:
    v = fields.get(key)
    if v and v.kind == HIRValueKind.LITERAL and isinstance(v.data, int):
        return v.data
    return None


def _get_float_field(fields: dict[str, HIRValue], key: str) -> float | None:
    v = fields.get(key)
    if v and v.kind == HIRValueKind.LITERAL and isinstance(v.data, (int, float)):
        return float(v.data)
    return None


def _get_grid_pos(fields: dict[str, HIRValue]) -> tuple[str, str] | None:
    v = fields.get("grid_position")
    if v and v.kind == HIRValueKind.LIST:
        items = v.data
        if isinstance(items, list) and len(items) >= 2:
            a = items[0]
            b = items[1]
            if (
                isinstance(a, HIRValue) and a.kind == HIRValueKind.LITERAL
                and isinstance(b, HIRValue) and b.kind == HIRValueKind.LITERAL
            ):
                return (str(a.data), str(b.data))
    return None


# ---------------------------------------------------------------------------
# Pass
# ---------------------------------------------------------------------------


class LoweringPass(Pass):
    """AST → HIR Lowering Pass。

    遍历所有 SourceFile，按文件类型 Lower 为对应的 SemanticUnit，
    同时填充 SymbolTable 的定义端。
    """

    name = "lowering"
    stage = PassStage.HIR
    description = "AST SourceFile → HIR SemanticUnit 转换，建立符号表"

    def run(self, ctx: PassContext) -> PassResult:
        result = PassResult()
        compilation = Compilation(
            root=ctx.root,
            config=ctx.config,
            symbol_table=ctx.symbol_table,
            type_system=ctx.type_system or TypeSystem(),
        )
        namespace = ""  # root namespace

        # 确保根命名空间存在
        ctx.symbol_table.ensure_namespace(namespace)

        for fpath, sf in sorted(ctx.source_files.items()):
            self._lower_file(sf, compilation, namespace, ctx)

        ctx.compilation = compilation
        result.modified = True
        return result

    def _lower_file(
        self,
        sf: SourceFile,
        comp: Compilation,
        namespace: str,
        ctx: PassContext,
    ) -> None:
        if sf.kind == FileKind.LAYOUT:
            unit = _lower_layout(sf, namespace)
            comp.add_unit(unit)
            return

        for decl in sf.declarations:
            hir_unit_id = decl.name

            if sf.kind == FileKind.MODEL:
                unit = _lower_model(sf, decl, hir_unit_id, namespace)
                comp.add_unit(unit)
                ctx.symbol_table.define(
                    Symbol(
                        name=unit.id,
                        kind=SymbolKind.MODEL,
                        namespace=namespace,
                        definition_node=unit,
                        span=unit.span,
                    )
                )

            elif sf.kind == FileKind.CATALOG:
                unit = _lower_catalog(sf, decl, hir_unit_id, namespace)
                comp.add_unit(unit)
                ctx.symbol_table.define(
                    Symbol(
                        name=unit.id,
                        kind=SymbolKind.CATALOG,
                        namespace=namespace,
                        definition_node=unit,
                        span=unit.span,
                    )
                )

            elif sf.kind == FileKind.INSTANCE:
                unit = _lower_instance(sf, decl, hir_unit_id, namespace)
                comp.add_unit(unit)
                ctx.symbol_table.define(
                    Symbol(
                        name=unit.id,
                        kind=SymbolKind.INSTANCE,
                        namespace=namespace,
                        definition_node=unit,
                        span=unit.span,
                    )
                )

            elif sf.kind == FileKind.MATE:
                unit = _lower_mate(sf, decl, namespace)
                comp.add_unit(unit)
                ctx.symbol_table.define(
                    Symbol(
                        name=unit.id,
                        kind=SymbolKind.MATE,
                        namespace=namespace,
                        definition_node=unit,
                        span=unit.span,
                    )
                )

            elif sf.kind == FileKind.GRID:
                unit = _lower_grid(sf, decl, namespace)
                comp.add_unit(unit)
                ctx.symbol_table.define(
                    Symbol(
                        name=unit.id,
                        kind=SymbolKind.GRID,
                        namespace=namespace,
                        definition_node=unit,
                        span=unit.span,
                    )
                )
