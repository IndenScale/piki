"""SymbolResolvePass — 将 HIR 中的 SymbolRef 消解为 MIR 指针。

这是进入 MIR 的第一道 pass：它建立 ResolvedCompilation，
把 Model / Instance / Catalog / Grid / Layout / Mate 之间的引用解析为直接指针。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adl.diagnostics import Diagnostic, Location, Severity

from ..hir import (
    CatalogUnit,
    Compilation,
    GridUnit,
    InstanceUnit,
    LayoutEntryHIR,
    LayoutUnit,
    MateUnit,
    ModelUnit,
)
from ..mir import (
    MIRValue,
    ResolvedCatalogIR,
    ResolvedCompilation,
    ResolvedGridIR,
    ResolvedInstanceIR,
    ResolvedInterfaceIR,
    ResolvedLayoutEntryIR,
    ResolvedLayoutIR,
    ResolvedMateIR,
    ResolvedModelIR,
)
from ..pass_manager import Pass, PassContext, PassResult, PassStage
from ..symbols import RefKind, SymbolRef, SymbolTable


class SymbolResolvePass(Pass):
    """消解 HIR 引用，生成 MIR 骨架。"""

    name = "symbol-resolve"
    stage = PassStage.MIR
    description = "将 HIR SymbolRef 消解为 MIR 指针"

    def run(self, ctx: PassContext) -> PassResult:
        result = PassResult()
        comp: Compilation | None = ctx.compilation
        if comp is None:
            ctx.emit(
                Diagnostic(
                    severity=Severity.ERROR,
                    message="symbol-resolve: HIR compilation 为空",
                    location=Location(uri=str(ctx.root)),
                    code="MIR-001",
                    source="adl.compiler.symbol_resolve",
                )
            )
            return result

        resolver = _Resolver(comp, ctx.root)
        resolved = resolver.resolve_all()
        ctx.resolved = resolved
        ctx.diagnostics.extend(resolved.diagnostics)
        result.modified = True
        return result


class _Resolver:
    def __init__(self, comp: Compilation, root: Path) -> None:
        self.comp = comp
        self.root = root
        self.resolved = ResolvedCompilation(hir=comp)
        self.diagnostics: list[Diagnostic] = []

        # 中间索引：HIR unit id → Resolved IR
        self._models: dict[str, ResolvedModelIR] = {}
        self._instances: dict[str, ResolvedInstanceIR] = {}
        self._catalogs: dict[str, ResolvedCatalogIR] = {}
        self._grids: dict[str, ResolvedGridIR] = {}

    def resolve_all(self) -> ResolvedCompilation:
        self._resolve_models()
        self._resolve_instances()
        self._resolve_grids()
        self._resolve_catalogs()
        self._resolve_layouts()
        self._resolve_mates()
        self.resolved.diagnostics = self.diagnostics
        return self.resolved

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------

    def _resolve_models(self) -> None:
        for unit in self.comp.models.values():
            family_def = self._resolve_family_ref(unit.family_ref, unit.namespace)
            model = ResolvedModelIR(
                id=unit.id,
                namespace=unit.namespace,
                family=family_def,
                fields=self._hir_fields_to_mir(unit.fields),
                source=unit.ast_source,
                span=unit.span,
            )
            self.resolved.resolved_models[unit.id] = model
            self._models[unit.id] = model

    # ------------------------------------------------------------------
    # Instances
    # ------------------------------------------------------------------

    def _resolve_instances(self) -> None:
        for unit in self.comp.instances.values():
            family_def = self._resolve_family_ref(unit.family_ref, unit.namespace)
            family_name = unit.family_ref.text if unit.family_ref else ""
            model = self._resolve_model_ref(unit.model_ref, unit.namespace)

            inst = ResolvedInstanceIR(
                id=unit.id,
                fqid=self._fqid(unit.namespace, unit.id),
                namespace=unit.namespace,
                family=family_def,
                family_name=family_name,
                model=model,
                fields=self._hir_fields_to_mir(unit.fields),
                source=unit.ast_source,
                span=unit.span,
            )
            # 先登记，便于接口引用回溯 parent
            self.resolved.resolved_instances[unit.id] = inst
            self._instances[unit.id] = inst

        # 第二遍：解析接口（接口可能引用其它实例，但通常只引用自身）
        for unit in self.comp.instances.values():
            inst = self._instances[unit.id]

            # 合并 Model 中声明的接口（Instance 未覆盖时继承）
            merged_interfaces = list(unit.interfaces)
            merged_footprints = list(unit.footprints)
            if unit.model_ref is not None:
                model = self.comp.models.get(unit.model_ref.text)
                if model is not None:
                    existing_iface_ids = {iface.id for iface in merged_interfaces}
                    for iface_hir in model.interfaces:
                        if iface_hir.id not in existing_iface_ids:
                            merged_interfaces.append(iface_hir)
                    existing_fp_ids = {fp.id for fp in merged_footprints}
                    for fp_hir in model.footprints:
                        if fp_hir.id not in existing_fp_ids:
                            merged_footprints.append(fp_hir)

            for iface_hir in merged_interfaces:
                iface = self._make_interface(iface_hir, inst)
                inst.interfaces[iface.id] = iface
            for fp_hir in merged_footprints:
                pins: list[ResolvedInterfaceIR] = []
                for pin_hir in fp_hir.pins:
                    pin = self._make_interface(pin_hir, inst)
                    pin.id = f"{fp_hir.id}/{pin_hir.id}"
                    inst.interfaces[pin.id] = pin
                    pins.append(pin)
                inst.footprints[fp_hir.id] = pins

    # ------------------------------------------------------------------
    # Grids
    # ------------------------------------------------------------------

    def _resolve_grids(self) -> None:
        for unit in self.comp.grids.values():
            fields = self._hir_fields_to_dict(unit.fields)
            grid = ResolvedGridIR(
                id=unit.id,
                namespace=unit.namespace,
                grid_type=fields.get("type", "orthogonal"),
                origin=fields.get("origin"),
                axes=list(unit.axes),
                source=unit.ast_source,
                span=unit.span,
            )
            self.resolved.resolved_grids[unit.id] = grid
            self._grids[unit.id] = grid

    # ------------------------------------------------------------------
    # Catalogs
    # ------------------------------------------------------------------

    def _resolve_catalogs(self) -> None:
        for unit in self.comp.catalogs.values():
            model = self._resolve_model_ref(unit.model_ref, unit.namespace)
            catalog = ResolvedCatalogIR(
                id=unit.id,
                namespace=unit.namespace,
                family=unit.catalog_family,
                model=model,
                source=unit.source,
                fields=self._hir_fields_to_mir(unit.fields),
                service_methods=list(unit.service_methods),
                source_path=unit.ast_source,
                span=unit.span,
            )
            self.resolved.resolved_catalogs[unit.id] = catalog
            self._catalogs[unit.id] = catalog

    # ------------------------------------------------------------------
    # Layouts
    # ------------------------------------------------------------------

    def _resolve_layouts(self) -> None:
        for unit in self.comp.layouts.values():
            layout = ResolvedLayoutIR(
                id=unit.namespace or "root",
                namespace=unit.namespace,
                source=unit.ast_source,
                span=unit.span,
            )
            layout.grids = dict(self._grids)
            for entry_hir in unit.entries:
                entry = self._resolve_layout_entry(entry_hir)
                if entry is not None:
                    layout.entries[entry.instance.id] = entry
            self.resolved.resolved_layouts[layout.id] = layout

    def _resolve_layout_entry(self, entry_hir: LayoutEntryHIR) -> ResolvedLayoutEntryIR | None:
        instance = self._resolve_instance_ref(entry_hir.instance_ref, "layout entry")
        if instance is None:
            return None

        rack = self._resolve_instance_ref(entry_hir.rack_ref, "layout rack") if entry_hir.rack_ref else None
        pdu = self._resolve_instance_ref(entry_hir.pdu_ref, "layout pdu") if entry_hir.pdu_ref else None
        parent = self._resolve_instance_ref(entry_hir.parent_ref, "layout parent") if entry_hir.parent_ref else None
        grid = self._resolve_grid_ref(entry_hir.grid_ref) if entry_hir.grid_ref else None

        return ResolvedLayoutEntryIR(
            instance=instance,
            rack=rack,
            pdu=pdu,
            parent=parent,
            grid=grid,
            position_u=entry_hir.position_u,
            grid_position=entry_hir.grid_position,
            row_id=entry_hir.row_id,
            bay_index=entry_hir.bay_index,
            position_x_mm=entry_hir.position_x_mm,
            position_y_mm=entry_hir.position_y_mm,
            position_z_mm=entry_hir.position_z_mm,
            transform=entry_hir.transform,
            extra=dict(entry_hir.extra),
            span=entry_hir.span,
        )

    # ------------------------------------------------------------------
    # Mates
    # ------------------------------------------------------------------

    def _resolve_mates(self) -> None:
        for unit in self.comp.mates.values():
            parent_inst, parent_iface = self._resolve_mate_endpoint(
                unit.parent_ref, unit.namespace, "parent"
            )
            child_inst, child_iface = self._resolve_mate_endpoint(
                unit.child_ref, unit.namespace, "child"
            )
            if parent_inst is None or child_inst is None:
                continue

            mate = ResolvedMateIR(
                id=unit.id,
                namespace=unit.namespace,
                mate_type=unit.mate_type,
                parent=parent_inst,
                child=child_inst,
                parent_interface=parent_iface,
                child_interface=child_iface,
                constraints=list(unit.constraints),
                interface_pairings=list(unit.interface_pairings),
                at=dict(unit.at),
                span=unit.span,
            )
            self.resolved.resolved_mates[unit.id] = mate

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_interface(self, iface_hir: Any, parent: ResolvedInstanceIR) -> ResolvedInterfaceIR:
        from adl.geometry import Transform
        from adl.geometry.interface_signature import get_signature

        local_transform = None
        if hasattr(iface_hir, "local_transform") and iface_hir.local_transform is not None:
            try:
                local_transform = Transform.model_validate(iface_hir.local_transform)
            except Exception:
                local_transform = None

        signature = None
        if hasattr(iface_hir, "signature") and iface_hir.signature is not None:
            signature = iface_hir.signature
        elif iface_hir.interface_type:
            signature = get_signature(iface_hir.interface_type)

        return ResolvedInterfaceIR(
            id=iface_hir.id,
            parent=parent,
            interface_type=iface_hir.interface_type,
            active_type=getattr(iface_hir, "active_type", None),
            direction=getattr(iface_hir, "direction", "bidirectional"),
            description=getattr(iface_hir, "description", ""),
            specs=dict(getattr(iface_hir, "specs", {}) or {}),
            local_transform=local_transform,
            mating_kind=getattr(iface_hir, "mating_kind", None),
            mating_params=dict(getattr(iface_hir, "mating_params", None) or {}),
            signature=signature,
            span=iface_hir.span,
        )

    def _resolve_family_ref(self, ref: SymbolRef | None, namespace: str) -> Any:
        if ref is None:
            return None
        return self.comp.type_system.get_family(ref.text)

    def _resolve_model_ref(self, ref: SymbolRef | None, namespace: str) -> ResolvedModelIR | None:
        if ref is None:
            return None
        sym = self.comp.symbol_table.resolve(ref, namespace)
        if sym is None or sym.definition_node is None:
            self._unresolved(ref, "model")
            return None
        model = self._models.get(sym.definition_node.id)
        if model is None:
            # 模型可能还未被消解（正常情况下 models 先处理）
            if isinstance(sym.definition_node, ModelUnit):
                family_def = self._resolve_family_ref(sym.definition_node.family_ref, namespace)
                model = ResolvedModelIR(
                    id=sym.definition_node.id,
                    namespace=sym.definition_node.namespace,
                    family=family_def,
                    fields=self._hir_fields_to_mir(sym.definition_node.fields),
                    source=sym.definition_node.ast_source,
                    span=sym.definition_node.span,
                )
                self._models[model.id] = model
                self.resolved.resolved_models[model.id] = model
        return model

    def _resolve_instance_ref(
        self,
        ref: SymbolRef | None,
        context: str,
    ) -> ResolvedInstanceIR | None:
        if ref is None:
            return None
        inst = self._instances.get(ref.text)
        if inst is not None:
            return inst
        sym = self.comp.symbol_table.resolve(ref, ref.text.split("/", 1)[0] or "")
        if sym is None or sym.definition_node is None:
            self._unresolved(ref, context)
            return None
        # 若实例在后续才处理，兜底重新创建（理论上不会发生）
        return self._instances.get(sym.definition_node.id)

    def _resolve_grid_ref(self, ref: SymbolRef | None) -> ResolvedGridIR | None:
        if ref is None:
            return None
        grid = self._grids.get(ref.text)
        if grid is not None:
            return grid
        sym = self.comp.symbol_table.resolve(ref, "")
        if sym is None or sym.definition_node is None:
            self._unresolved(ref, "grid")
            return None
        return self._grids.get(sym.definition_node.id)

    def _resolve_mate_endpoint(
        self,
        ref: SymbolRef | None,
        namespace: str,
        role: str,
    ) -> tuple[ResolvedInstanceIR | None, ResolvedInterfaceIR | None]:
        if ref is None:
            self._error("MATE-001", f"Mate {role} 引用为空", namespace)
            return None, None

        text = ref.text
        if ref.kind == RefKind.INSTANCE_INTERFACE or "/" in text:
            parts = text.split("/")
            inst_ref = SymbolRef(parts[0], RefKind.INSTANCE)
            inst = self._resolve_instance_ref(inst_ref, f"mate {role}")
            if inst is None:
                return None, None
            iface_id = parts[1]
            iface = inst.interfaces.get(iface_id)
            if iface is None and len(parts) == 3:
                iface = inst.interfaces.get(f"{parts[1]}/{parts[2]}")
            if iface is None:
                self._error(
                    "MATE-002",
                    f"Mate {role} 引用中的接口不存在: {text}",
                    ref.text,
                )
                return inst, None
            return inst, iface

        return self._resolve_instance_ref(ref, f"mate {role}"), None

    def _hir_fields_to_mir(self, fields: dict[str, Any]) -> dict[str, MIRValue]:
        return {k: self._hir_value_to_mir(v) for k, v in fields.items()}

    def _hir_value_to_mir(self, hir_val: Any) -> MIRValue:
        from ..hir import HIRValue, HIRValueKind

        if not isinstance(hir_val, HIRValue):
            return MIRValue.literal(hir_val)

        if hir_val.kind == HIRValueKind.LITERAL:
            return MIRValue.literal(hir_val.data, hir_val.span)
        if hir_val.kind == HIRValueKind.LIST:
            return MIRValue.lst(
                [self._hir_value_to_mir(item) for item in (hir_val.data or [])],
                hir_val.span,
            )
        if hir_val.kind == HIRValueKind.MAPPING:
            return MIRValue.mapping(
                {k: self._hir_value_to_mir(v) for k, v in (hir_val.data or {}).items()},
                hir_val.span,
            )
        if hir_val.kind == HIRValueKind.REFERENCE:
            # MIR 中字段引用保持为文本引用，由后续 pass 按语义消解
            return MIRValue.literal(hir_val.data.text if hasattr(hir_val.data, "text") else str(hir_val.data), hir_val.span)

        return MIRValue.literal(str(hir_val.data), hir_val.span)

    def _hir_fields_to_dict(self, fields: dict[str, Any]) -> dict[str, Any]:
        return {k: self._hir_value_to_dict(v) for k, v in fields.items()}

    def _hir_value_to_dict(self, hir_val: Any) -> Any:
        from ..hir import HIRValue, HIRValueKind

        if not isinstance(hir_val, HIRValue):
            return hir_val
        if hir_val.kind == HIRValueKind.LITERAL:
            return hir_val.data
        if hir_val.kind == HIRValueKind.LIST:
            return [self._hir_value_to_dict(item) for item in (hir_val.data or [])]
        if hir_val.kind == HIRValueKind.MAPPING:
            return {k: self._hir_value_to_dict(v) for k, v in (hir_val.data or {}).items()}
        if hir_val.kind == HIRValueKind.REFERENCE:
            return hir_val.data.text if hasattr(hir_val.data, "text") else str(hir_val.data)
        return str(hir_val.data)

    def _fqid(self, namespace: str, id: str) -> str:
        if namespace:
            return f"{namespace}:{id}"
        return id

    def _unresolved(self, ref: SymbolRef, kind: str) -> None:
        self._error(
            "REFS-001",
            f"未解析的 {kind} 引用: {ref.text}",
            ref.text,
        )

    def _error(self, code: str, message: str, target: str) -> None:
        self.diagnostics.append(
            Diagnostic(
                severity=Severity.ERROR,
                message=message,
                location=Location(uri=str(self.root)),
                code=code,
                source="adl.compiler.symbol_resolve",
            )
        )
