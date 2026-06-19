"""BackCompatEmitPass — MIR → 现有 Project API。

从 ResolvedCompilation（MIR）生成 adl.project.Project 对象，保持向后兼容。
本 pass 不再复刻 Model/Instance 合并逻辑，只把 MIR 结果映射到旧模型。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adl.diagnostics import Diagnostic, Location, Severity
from adl.models import (
    Layout,
    LayoutEntry,
    MateConstraint,
    MateConstraintOperator,
    MateGraph,
    MateSpec,
    MateTypeMeta,
    Model,
    ResolvedInstance,
)
from adl.models.catalog import CatalogEntry
from adl.models.grid import Grid, GridAxis
from adl.project import Project
from adl.types import TypeRegistry

from ..hir import Compilation
from ..mir import (
    MIRValue,
    ResolvedCatalogIR,
    ResolvedCompilation,
    ResolvedGridIR,
    ResolvedInstanceIR,
    ResolvedLayoutEntryIR,
    ResolvedMateIR,
    ResolvedModelIR,
)
from ..pass_manager import Pass, PassContext, PassResult, PassStage


class BackCompatEmitPass(Pass):
    """MIR → Project 向后兼容 Pass。

    从 ResolvedCompilation 构建传统 Project 对象，存储在 ctx.extra["project"] 中。
    """

    name = "back-compat-emit"
    stage = PassStage.MIR
    description = "从 MIR ResolvedCompilation 生成向后兼容的 Project 对象"

    def run(self, ctx: PassContext) -> PassResult:
        result = PassResult()
        resolved: ResolvedCompilation | None = ctx.resolved
        comp: Compilation | None = ctx.compilation

        if resolved is None or comp is None:
            ctx.emit(
                Diagnostic(
                    severity=Severity.ERROR,
                    message="back-compat-emit: MIR 为空",
                    location=Location(uri=str(ctx.root)),
                    code="MIR-003",
                    source="adl.compiler.back_compat",
                )
            )
            return result

        project = Project(
            root=comp.root,
            config=comp.config,
            type_registry=_type_registry_from_type_system(comp.type_system),
            project_name=comp.config.get("project", {}).get("name", comp.root.name),
        )

        # 1. Models
        for model in resolved.resolved_models.values():
            project.models[model.id] = Model(
                id=model.id,
                family=model.family.name if model.family else "",
                data=_mir_fields_to_dict(model.fields),
                source=model.source,
            )

        # 2. Catalogs
        for catalog in resolved.resolved_catalogs.values():
            project.catalogs[catalog.id] = CatalogEntry(
                id=catalog.id,
                family=catalog.family,
                source=catalog.source,
                model_ref=catalog.model.id if catalog.model else None,
                data=_mir_fields_to_dict(catalog.fields),
                source_path=catalog.source_path,
            )

        # 3. Layout
        layout = _build_layout(resolved.resolved_layouts.get("root"))
        if layout is not None:
            project.layout = layout

        # 4. Grids
        for grid in resolved.resolved_grids.values():
            project.grids[grid.id] = _build_grid(grid)

        # 5. Instances
        for inst in resolved.resolved_instances.values():
            project.instances[inst.id] = _build_resolved_instance(inst, project)

        # 5a. Collections: 按 instances/<subdir>/ 路径分组（兼容旧 Registry API）
        _group_instances_into_collections(project)

        # 6. Mates
        for mate in resolved.resolved_mates.values():
            project.mates.append(_build_mate(mate))
        project.mate_graph = MateGraph()
        for mate in project.mates:
            project.mate_graph.add(mate)

        # 7. 递归子项目
        self._load_children(project)

        ctx.extra["project"] = project
        result.modified = True
        result.artifacts["project"] = project
        return result

    def _load_children(self, project: Project) -> None:
        """递归发现子项目目录（简化版）。"""
        for entry in sorted(project.root.iterdir()):
            if not entry.is_dir():
                continue
            child_toml = entry / "piki.toml"
            if not child_toml.exists():
                continue
            if entry.name in (
                "models", "instances", "layouts", "rules", "mates",
                ".git", "__pycache__", ".piki", "dist",
            ):
                continue
            try:
                from adl.parsing.loaders import load_toml

                child_config = load_toml(child_toml)
                child_project = Project(
                    root=entry,
                    config=child_config,
                    type_registry=project.type_registry,
                    parent=project,
                    project_name=child_config.get("project", {}).get("name", entry.name),
                )
                project.children[entry.name] = child_project
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _group_instances_into_collections(project: Project) -> None:
    """把 instances/ 下按子目录存放的实例分组到 project.collections。"""
    for inst in project.instances.values():
        source = inst.source
        if source is None:
            continue
        try:
            rel = source.relative_to(project.root)
        except ValueError:
            continue
        parts = rel.parts
        if len(parts) >= 3 and parts[0] == "instances":
            collection_name = parts[1]
            project.collections.setdefault(collection_name, {})[inst.id] = inst


def _mir_fields_to_dict(fields: dict[str, MIRValue]) -> dict[str, Any]:
    return {k: _mir_value_to_python(v) for k, v in fields.items()}


def _mir_value_to_python(val: MIRValue) -> Any:
    if val.kind.value == "literal":
        return val.data
    if val.kind.value == "list":
        return [_mir_value_to_python(item) for item in (val.data or [])]
    if val.kind.value == "mapping":
        return {k: _mir_value_to_python(v) for k, v in (val.data or {}).items()}
    if val.kind.value.endswith("_ptr"):
        return val.data
    return val.data


def _type_registry_from_type_system(ts: Any) -> TypeRegistry:
    """从编译器 TypeSystem 构建旧 API 使用的 TypeRegistry。"""
    reg = TypeRegistry()
    if ts is None:
        return reg

    for family_def in getattr(ts, "families", {}).values():
        if family_def.pydantic_model is not None:
            reg.add_family(family_def.name, family_def.pydantic_model)

    for mate_def in getattr(ts, "mate_types", {}).values():
        constraints: list[MateConstraint] = []
        for c in mate_def.default_constraints:
            try:
                op = MateConstraintOperator(c.get("operator", "<="))
            except ValueError:
                op = MateConstraintOperator.LTE
            constraints.append(
                MateConstraint(
                    field=c.get("field", ""),
                    operator=op,
                    value_ref=c.get("value_ref", ""),
                    message=c.get("message", ""),
                )
            )
        reg.add_mate_type(
            mate_def.name,
            MateTypeMeta(
                type=mate_def.name,
                description=mate_def.description,
                default_constrains=constraints,
                applicable_parent_families=set(mate_def.applicable_parents),
                applicable_child_families=set(mate_def.applicable_children),
            ),
        )

    return reg


def _build_layout(layout) -> Layout | None:
    if layout is None:
        return None
    entries: dict[str, LayoutEntry] = {}
    for entry in layout.entries.values():
        entries[entry.instance.id] = _build_layout_entry(entry)
    grids = {grid_id: _build_grid(grid) for grid_id, grid in layout.grids.items()}
    return Layout(
        name=layout.id or "main",
        entries=entries,
        source=layout.source,
        grids=grids,
    )


def _build_layout_entry(entry: ResolvedLayoutEntryIR) -> LayoutEntry:
    return LayoutEntry(
        instance=entry.instance.id,
        rack_id=entry.rack.id if entry.rack else None,
        position_u=entry.position_u,
        pdu_id=entry.pdu.id if entry.pdu else None,
        row_id=entry.row_id,
        bay_index=entry.bay_index,
        grid_id=entry.grid.id if entry.grid else None,
        grid_position=entry.grid_position,
        position_x_mm=entry.position_x_mm,
        position_y_mm=entry.position_y_mm,
        position_z_mm=entry.position_z_mm,
        parent=entry.parent.id if entry.parent else None,
        transform=entry.transform,
        extra=dict(entry.extra),
    )


def _build_grid(grid: ResolvedGridIR) -> Grid:
    data: dict[str, Any] = {
        "id": grid.id,
        "type": grid.grid_type,
        "axes": grid.axes,
    }
    if grid.origin is not None:
        data["origin"] = grid.origin
    try:
        return Grid.model_validate(data)
    except Exception:
        return Grid(id=grid.id, axes=[])


def _build_resolved_instance(inst: ResolvedInstanceIR, project: Project) -> ResolvedInstance:
    family_name = inst.family.name if inst.family else inst.family_name
    if inst.validation_error:
        family_name = "_invalid"

    raw = _mir_fields_to_dict(inst.overrides)
    resolved = dict(inst.resolved_data) if inst.resolved_data else {}

    # Layout 合并（保持与旧 ProjectLoader 相同行为）
    if project.layout is not None:
        layout_entry = project.layout.get(inst.id)
        if layout_entry is not None:
            resolved.update(layout_entry.to_flat())

    # Catalog 合并
    if inst.catalog is not None:
        resolved["catalog"] = _mir_fields_to_dict(inst.catalog.fields)

    return ResolvedInstance(
        id=inst.id,
        family=family_name,
        raw=raw,
        _resolved=resolved,
        source=inst.source or Path("."),
        model_id=inst.model.id if inst.model else None,
        _validation_error=inst.validation_error,
        _catalog=_mir_fields_to_dict(inst.catalog.fields) if inst.catalog else None,
    )


def _build_mate(mate: ResolvedMateIR) -> MateSpec:
    parent_ref = mate.parent_interface.qualified_id if mate.parent_interface else mate.parent.id
    child_ref = mate.child_interface.qualified_id if mate.child_interface else mate.child.id

    constraints: list[MateConstraint] = []
    for c in mate.constraints:
        try:
            constraints.append(MateConstraint.model_validate(c))
        except Exception:
            pass

    pairings = []
    for p in mate.interface_pairings:
        from adl.models.mating import InterfacePairing

        try:
            pairings.append(InterfacePairing.model_validate(p))
        except Exception:
            pass

    return MateSpec(
        type=mate.mate_type,
        parent=parent_ref,
        child=child_ref,
        constrains=constraints,
        interface_pairings=pairings,
        at=dict(mate.at),
    )

