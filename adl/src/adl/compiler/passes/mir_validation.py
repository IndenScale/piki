"""MIR 阶段验证 Pass：Layout 环、Mate 约束、接口兼容性、Catalog、FQID 去重。

这些 pass 在 SymbolResolve / ModelMerge 之后运行，只产出诊断，不修改 MIR 结构。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adl.diagnostics import Diagnostic, Location, Severity
from adl.models.mating import MateConstraint, evaluate_operator

from ..mir import (
    ResolvedCompilation,
    ResolvedInstanceIR,
    ResolvedInterfaceIR,
    ResolvedLayoutEntryIR,
    ResolvedLayoutIR,
    ResolvedMateIR,
)
from ..pass_manager import Pass, PassContext, PassResult, PassStage


# ---------------------------------------------------------------------------
# LayoutCycleCheckPass
# ---------------------------------------------------------------------------


class LayoutCycleCheckPass(Pass):
    """检测 Layout parent 链中的环。"""

    name = "layout-cycle-check"
    stage = PassStage.MIR
    description = "检测 Layout parent 链中的环"

    def run(self, ctx: PassContext) -> PassResult:
        result = PassResult()
        resolved = ctx.resolved
        if resolved is None:
            return result

        for layout in resolved.resolved_layouts.values():
            cycles = self._detect_cycles(layout)
            for cycle in cycles:
                ctx.emit(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=(
                            f"Layout parent 引用存在环: {' -> '.join(cycle)} -> {cycle[0]}"
                        ),
                        location=_layout_location(layout),
                        code="LAYOUT-004",
                        source="adl.compiler.layout_cycle_check",
                    )
                )
        result.modified = True
        return result

    def _detect_cycles(self, layout: ResolvedLayoutIR) -> list[list[str]]:
        cycles: list[list[str]] = []
        visited: set[str] = set()
        for instance_id in layout.entries:
            if instance_id in visited:
                continue
            path: list[str] = []
            current: str | None = instance_id
            while current is not None:
                if current in path:
                    cycle_start = path.index(current)
                    cycles.append(path[cycle_start:])
                    break
                if current in visited:
                    break
                path.append(current)
                visited.add(current)
                entry = layout.entries.get(current)
                current = entry.parent.id if entry and entry.parent else None
        return cycles


# ---------------------------------------------------------------------------
# MateConstraintPass
# ---------------------------------------------------------------------------


class MateConstraintPass(Pass):
    """检查 Mate 的固有约束。"""

    name = "mate-constraint"
    stage = PassStage.MIR
    description = "检查 Mate 的固有约束"

    def run(self, ctx: PassContext) -> PassResult:
        result = PassResult()
        resolved = ctx.resolved
        if resolved is None:
            return result

        for mate in resolved.resolved_mates.values():
            self._check_mate(ctx, mate, resolved)

        result.modified = True
        return result

    def _check_mate(
        self,
        ctx: PassContext,
        mate: ResolvedMateIR,
        resolved: ResolvedCompilation,
    ) -> None:
        type_system = resolved.hir.type_system if resolved.hir else None
        type_meta = type_system.get_mate_type(mate.mate_type) if type_system else None
        constraints: list[MateConstraint] = []
        for c in mate.constraints:
            try:
                constraints.append(MateConstraint.model_validate(c))
            except Exception:
                pass
        if not constraints and type_meta is not None:
            constraints = type_meta.default_constraints or []

        for constraint in constraints:
            child_val = self._resolve_value(mate.child, mate.child_interface, constraint.field)
            parent_val = self._resolve_value(mate.parent, mate.parent_interface, constraint.value_ref)
            if child_val is None or parent_val is None:
                continue
            if not evaluate_operator(child_val, constraint.operator, parent_val):
                msg = constraint.message or (
                    f"Mate '{mate.id}' 约束违反: {mate.child.id}.{constraint.field} "
                    f"{constraint.operator.value} {constraint.value_ref} "
                    f"(实际值 {child_val} vs {parent_val})"
                )
                ctx.emit(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=msg,
                        location=_mate_location(mate),
                        code="MATE-003",
                        source="adl.compiler.mate_constraint",
                    )
                )

    def _resolve_value(
        self,
        inst: ResolvedInstanceIR,
        iface: ResolvedInterfaceIR | None,
        field: str,
    ) -> Any:
        if iface is not None and field in iface.specs:
            return iface.specs[field]
        return _mir_dict_get(inst.resolved_data, field)


# ---------------------------------------------------------------------------
# InterfaceCompatPass
# ---------------------------------------------------------------------------


class InterfaceCompatPass(Pass):
    """检查 Mate 两端接口的类型与 mating_kind 兼容性。"""

    name = "interface-compat"
    stage = PassStage.MIR
    description = "检查 Mate 两端接口的兼容性"

    def run(self, ctx: PassContext) -> PassResult:
        result = PassResult()
        resolved = ctx.resolved
        if resolved is None:
            return result

        type_system = resolved.hir.type_system if resolved.hir else None
        for mate in resolved.resolved_mates.values():
            if mate.parent_interface is None or mate.child_interface is None:
                continue
            p_type = mate.parent_interface.interface_type
            c_type = mate.child_interface.interface_type
            if type_system is not None and not type_system.is_compatible_interface(p_type, c_type):
                ctx.emit(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=(
                            f"Mate '{mate.id}' 两端接口类型不兼容: "
                            f"parent={p_type}, child={c_type}"
                        ),
                        location=_mate_location(mate),
                        code="MATE-005",
                        source="adl.compiler.interface_compat",
                    )
                )

            p_kind = mate.parent_interface.mating_kind
            c_kind = mate.child_interface.mating_kind
            if p_kind is not None and c_kind is not None and p_kind != c_kind:
                ctx.emit(
                    Diagnostic(
                        severity=Severity.WARNING,
                        message=(
                            f"Mate '{mate.id}' 两端 mating_kind 不一致: "
                            f"parent={p_kind}, child={c_kind}"
                        ),
                        location=_mate_location(mate),
                        code="MATE-006",
                        source="adl.compiler.interface_compat",
                    )
                )

        result.modified = True
        return result


# ---------------------------------------------------------------------------
# CatalogResolvePass
# ---------------------------------------------------------------------------


class CatalogResolvePass(Pass):
    """解析每个 Instance 的 Catalog 引用，并校验 service_method。"""

    name = "catalog-resolve"
    stage = PassStage.MIR
    description = "解析 Instance Catalog 引用并校验 service_method"

    def run(self, ctx: PassContext) -> PassResult:
        result = PassResult()
        resolved = ctx.resolved
        if resolved is None:
            return result

        for inst in resolved.resolved_instances.values():
            self._resolve_instance_catalog(ctx, inst, resolved)

        result.modified = True
        return result

    def _resolve_instance_catalog(
        self,
        ctx: PassContext,
        inst: ResolvedInstanceIR,
        resolved: ResolvedCompilation,
    ) -> None:
        hir_inst = resolved.hir.instances.get(inst.id) if resolved.hir else None
        catalog_raw = getattr(hir_inst, "catalog_raw", None) if hir_inst else None
        active_catalog = None

        if catalog_raw:
            catalog_id = catalog_raw.get("id") or catalog_raw.get("catalog_id")
            if catalog_id:
                active_catalog = resolved.resolved_catalogs.get(catalog_id)
                if active_catalog is None:
                    ctx.emit(
                        Diagnostic(
                            severity=Severity.ERROR,
                            message=f"Instance '{inst.id}' 指定的 Catalog '{catalog_id}' 不存在",
                            location=_inst_location(inst),
                            code="CATALOG-001",
                            source="adl.compiler.catalog_resolve",
                        )
                    )

        if active_catalog is None and inst.model is not None:
            for catalog in resolved.resolved_catalogs.values():
                if catalog.model is not None and catalog.model.id == inst.model.id:
                    active_catalog = catalog
                    break

        if active_catalog is not None:
            inst.catalog = active_catalog
            for method_id in active_catalog.service_methods:
                if method_id not in resolved.resolved_catalogs:
                    ctx.emit(
                        Diagnostic(
                            severity=Severity.ERROR,
                            message=(
                                f"Catalog '{active_catalog.id}' 引用的 service method "
                                f"'{method_id}' 不存在"
                            ),
                            location=_catalog_location(active_catalog),
                            code="CATALOG-002",
                            source="adl.compiler.catalog_resolve",
                        )
                    )


# ---------------------------------------------------------------------------
# FQIDDedupPass
# ---------------------------------------------------------------------------


class FQIDDedupPass(Pass):
    """检查项目树中是否存在简单 Instance ID 冲突。"""

    name = "fqid-dedup"
    stage = PassStage.MIR
    description = "检查 Instance ID 冲突"

    def run(self, ctx: PassContext) -> PassResult:
        result = PassResult()
        resolved = ctx.resolved
        if resolved is None:
            return result

        counts: dict[str, list[str]] = {}
        for inst in resolved.resolved_instances.values():
            counts.setdefault(inst.id, []).append(inst.fqid)

        for simple_id, fqids in counts.items():
            if len(fqids) > 1:
                ctx.emit(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=(
                            f"Instance ID '{simple_id}' 在项目树中出现 {len(fqids)} 次: "
                            f"{', '.join(fqids)}。请使用全限定 ID 引用。"
                        ),
                        location=Location(uri=str(ctx.root)),
                        code="REFS-002",
                        source="adl.compiler.fqid_dedup",
                    )
                )

        result.modified = True
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _layout_location(layout: ResolvedLayoutIR) -> Location:
    if layout.source:
        return Location.from_path(layout.source)
    return Location(uri="")


def _mate_location(mate: ResolvedMateIR) -> Location:
    if mate.span and mate.span.source:
        return Location.from_path(mate.span.source)
    return Location(uri="")


def _inst_location(inst: ResolvedInstanceIR) -> Location:
    if inst.source:
        return Location.from_path(inst.source)
    return Location(uri="")


def _catalog_location(catalog) -> Location:
    if catalog.source_path:
        return Location.from_path(catalog.source_path)
    return Location(uri="")


def _mir_dict_get(data: dict[str, Any], key: str) -> Any:
    """从扁平/嵌套 dict 中取值（优先扁平键，再支持嵌套）。"""
    if key in data:
        return data[key]
    parts = key.split(".")
    node = data
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node
