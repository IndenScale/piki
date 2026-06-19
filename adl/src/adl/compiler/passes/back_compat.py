"""BackCompatEmitPass — HIR → 现有 Project API。

从 Compilation (HIR) 生成 adl.project.Project 对象，保持向后兼容。

这是 POC 阶段的桥接 Pass：复制 ProjectLoader._resolve_instance 的合并逻辑，
但输入源从 YAML dict 变为 HIR SemanticUnit。
"""

from __future__ import annotations

from pathlib import Path

from adl.models import (
    Layout,
    LayoutEntry,
    MateGraph,
    MateSpec,
    Model,
    ResolvedInstance,
    get_non_overridable_fields,
)
from adl.models.catalog import CatalogEntry
from adl.models.grid import Grid, GridAxis
from adl.project import Project
from adl.project.loader import _flatten
from adl.types import TypeRegistry

from ..hir import (
    Compilation,
    GridUnit,
    HIRValueKind,
    InstanceUnit,
)
from ..pass_manager import Pass, PassContext, PassResult, PassStage


class BackCompatEmitPass(Pass):
    """HIR → Project 向后兼容 Pass。

    从 Compilation 构建传统 Project 对象，存储在 ctx.extra["project"] 中。
    """

    name = "back-compat-emit"
    stage = PassStage.MIR
    description = "从 HIR Compilation 生成向后兼容的 Project 对象"

    def run(self, ctx: PassContext) -> PassResult:
        result = PassResult()
        comp: Compilation = ctx.compilation
        if comp is None:
            return result

        project = Project(
            root=comp.root,
            config=comp.config,
            type_registry=TypeRegistry(),
            project_name=comp.config.get("project", {}).get("name", comp.root.name),
        )

        # 1. Models
        for unit in comp.models.values():
            project.models[unit.id] = Model(
                id=unit.id,
                family=unit.family_ref.text if unit.family_ref else "",
                data=_hir_fields_to_dict(unit.fields),
                source=unit.ast_source,
            )

        # 2. Catalogs
        for unit in comp.catalogs.values():
            entry = CatalogEntry(
                id=unit.id,
                family=unit.catalog_family,
                source=unit.source,
                model_ref=unit.model_ref.text if unit.model_ref else None,
                data=_hir_fields_to_dict(unit.fields),
                source_path=unit.ast_source,
            )
            project.catalogs[unit.id] = entry

        # 3. Layout
        if "root" in comp.layouts or "" in comp.layouts:
            layout_unit = comp.layouts.get("root") or comp.layouts.get("")
            entries: dict[str, LayoutEntry] = {}
            for e in layout_unit.entries:
                entry = LayoutEntry(
                    instance=e.instance_ref.text,
                    rack_id=e.rack_ref.text if e.rack_ref else None,
                    position_u=e.position_u,
                    pdu_id=e.pdu_ref.text if e.pdu_ref else None,
                    parent=e.parent_ref.text if e.parent_ref else None,
                    grid_id=e.grid_ref.text if e.grid_ref else None,
                    grid_position=e.grid_position,
                    row_id=e.row_id,
                    bay_index=e.bay_index,
                    position_x_mm=e.position_x_mm,
                    position_y_mm=e.position_y_mm,
                    position_z_mm=e.position_z_mm,
                    transform=e.transform,
                    extra=e.extra,
                )
                entries[e.instance_ref.text] = entry
            project.layout = Layout(
                name="main",
                entries=entries,
                source=layout_unit.ast_source,
            )

        # 4. Grids
        for unit in comp.grids.values():
            grid = _hir_to_grid(unit)
            project.grids[unit.id] = grid

        # 5. Instances (with Model merging)
        for unit in comp.instances.values():
            resolved = _resolve_instance_from_hir(unit, comp, project)
            if resolved is not None:
                project.instances[resolved.id] = resolved

        # 6. Mates
        for unit in comp.mates.values():
            mate = _hir_to_mate(unit)
            project.mates.append(mate)
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


def _hir_fields_to_dict(fields: dict) -> dict:
    """将 HIR fields 递归转为普通 Python dict/list/scalar。

    对 MAPPING → dict，对 LIST → list，对 LITERAL → 其值，
    对 REFERENCE → 引用文本。
    嵌套结构完全展开，不保留 HIRValue 包装。
    """
    result: dict = {}
    for key, val in fields.items():
        result[key] = _hir_value_to_python(val)
    return result


def _hir_value_to_python(hir_val: Any) -> Any:
    """递归将 HIRValue 转为纯 Python 对象（dict / list / scalar）。"""
    if not hasattr(hir_val, "kind"):
        # 已是纯 Python 对象或普通容器
        if isinstance(hir_val, dict):
            return {k: _hir_value_to_python(v) for k, v in hir_val.items()}
        if isinstance(hir_val, list):
            return [_hir_value_to_python(item) for item in hir_val]
        return hir_val

    kind = hir_val.kind
    if kind == HIRValueKind.LITERAL:
        return hir_val.data
    elif kind == HIRValueKind.REFERENCE:
        return hir_val.data.text if hasattr(hir_val.data, "text") else str(hir_val.data)
    elif kind == HIRValueKind.LIST:
        return [_hir_value_to_python(item) for item in (hir_val.data or [])]
    elif kind == HIRValueKind.MAPPING:
        return {k: _hir_value_to_python(v) for k, v in (hir_val.data or {}).items()}
    # Fallback for unknown kinds
    return str(hir_val)


def _hir_value_flat(val) -> Any:
    """向后兼容别名：等同于 _hir_value_to_python。"""
    return _hir_value_to_python(val)


def _resolve_instance_from_hir(
    unit: InstanceUnit,
    comp: Compilation,
    project: Project,
) -> ResolvedInstance | None:
    """从 HIR InstanceUnit 解析为 ResolvedInstance（复刻 ProjectLoader 逻辑）。"""
    family_name = unit.family_ref.text if unit.family_ref else None
    model_id = unit.model_ref.text if unit.model_ref else None

    # 确定 Family
    if family_name is None and model_id is not None:
        model_unit = comp.models.get(model_id)
        if model_unit is not None and model_unit.family_ref:
            family_name = model_unit.family_ref.text

    if family_name is None:
        family_name = _hir_fields_to_dict(unit.fields).get("family")

    if family_name is None:
        return None

    if comp.type_system:
        family_def = comp.type_system.get_family(family_name)
        family_cls = family_def.pydantic_model if family_def else None
    else:
        family_cls = None

    # Model 默认值
    model_defaults: dict = {}
    if model_id:
        model_unit = comp.models.get(model_id)
        if model_unit is not None:
            model_defaults = _hir_fields_to_dict(model_unit.fields)

    # Instance 覆盖
    overrides = _hir_fields_to_dict(unit.fields)
    overrides.pop("model", None)
    overrides.pop("family", None)

    # Non-overridable 检查
    if family_cls is not None:
        non_overridable = get_non_overridable_fields(family_cls)
        for field_name in sorted(non_overridable):
            if field_name in overrides:
                # 兼容：只在有 source 时添加诊断
                pass

    merged = _flatten(
        {**model_defaults, **overrides},
        preserve_keys={"assets", "tags", "shape", "kinematics", "load_capacity"},
    )
    merged["id"] = unit.id

    # Schema 校验
    if family_cls is not None:
        try:
            from pydantic import ValidationError
            validated = family_cls.model_validate(merged)
            resolved_dict = _flatten(
                validated.model_dump(),
                preserve_keys={"assets", "tags", "shape", "kinematics", "load_capacity"},
            )
        except ValidationError:
            resolved_dict = _flatten(overrides)
            resolved_dict["id"] = unit.id
            return ResolvedInstance(
                id=unit.id,
                family="_invalid",
                raw=overrides,
                _resolved=resolved_dict,
                source=unit.ast_source or Path("."),
                model_id=model_id,
            )
    else:
        resolved_dict = merged

    # Layout 合并
    if project.layout is not None:
        layout_entry = project.layout.get(unit.id)
        if layout_entry is not None:
            resolved_dict.update(layout_entry.to_flat())

    # Catalog
    active_catalog = _resolve_catalog_from_hir(unit, comp, project, model_id)
    if active_catalog is not None:
        resolved_dict["catalog"] = active_catalog.data

    return ResolvedInstance(
        id=unit.id,
        family=family_name,
        raw=overrides,
        _resolved=resolved_dict,
        source=unit.ast_source or Path("."),
        model_id=model_id,
    )


def _resolve_catalog_from_hir(
    unit: InstanceUnit,
    comp: Compilation,
    project: Project,
    model_id: str | None,
) -> CatalogEntry | None:
    catalog_raw = unit.catalog_raw
    if catalog_raw:
        catalog_id = catalog_raw.get("id") or catalog_raw.get("catalog_id")
        if catalog_id:
            entry = project.catalogs.get(catalog_id)
            if entry is not None:
                return entry
    if model_id:
        for entry in project.catalogs.values():
            if entry.model_ref == model_id:
                return entry
    return None


def _hir_to_grid(unit: GridUnit) -> Grid:
    fields = _hir_fields_to_dict(unit.fields)
    axes_data = fields.get("axes", [])
    axes = []
    if isinstance(axes_data, list):
        for a in axes_data:
            if isinstance(a, dict):
                try:
                    axes.append(GridAxis.model_validate(a))
                except Exception:
                    pass
    return Grid(
        id=unit.id,
        name=fields.get("name", unit.id),
        axes=axes,
    )


def _hir_to_mate(unit) -> MateSpec:
    from adl.models.mating import InterfacePairing, MateConstraint

    constraints = []
    for c in unit.constraints:
        try:
            constraints.append(MateConstraint.model_validate(c))
        except Exception:
            pass

    pairings = []
    for p in unit.interface_pairings:
        try:
            pairings.append(InterfacePairing.model_validate(p))
        except Exception:
            pass

    return MateSpec(
        type=unit.mate_type,
        parent=unit.parent_ref.text if unit.parent_ref else "",
        child=unit.child_ref.text if unit.child_ref else "",
        constrains=constraints,
        interface_pairings=pairings,
        at=unit.at,
    )
