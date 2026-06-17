"""ADL 层验证器。

对已经加载的 ``Project`` 执行声明层验证，生成 ``Diagnostic`` 列表。
这些验证不依赖任何领域插件知识，只检查 ADL 自身的约束：
引用完整性、Mate 约束、Catalog 引用、FQID 冲突等。
"""

from __future__ import annotations

from typing import Any

from adl.diagnostics import Diagnostic, Location, Severity
from adl.models import (
    InterfaceSpec,
    get_interfaces_from_resolved,
    parse_mate_ref,
    resolve_interface_ref,
)
from adl.project import Project

_ABS_LAYOUT_FIELDS = frozenset(
    {
        "rack_id",
        "position_u",
        "pdu_id",
        "row_id",
        "bay_index",
        "grid_id",
        "grid_position",
        "position_x_mm",
        "position_y_mm",
        "position_z_mm",
    }
)


class ADLValidator:
    """ADL 声明层验证器。"""

    def __init__(self, project: Project) -> None:
        self.project = project

    def validate(self) -> list[Diagnostic]:
        """运行所有 ADL 层验证，返回 Diagnostic 列表。"""
        diagnostics: list[Diagnostic] = []
        diagnostics.extend(self._validate_layout_references())
        diagnostics.extend(self._validate_relative_layout())
        diagnostics.extend(self._validate_grid_layout())
        diagnostics.extend(self._validate_foreign_keys())
        diagnostics.extend(self._validate_mate_references())
        diagnostics.extend(self._validate_mate_family_compat())
        diagnostics.extend(self._validate_mate_constraints())
        diagnostics.extend(self._validate_catalog_references())
        diagnostics.extend(self._validate_catalog_service_methods())
        diagnostics.extend(self._validate_fqid_duplicates())
        diagnostics.extend(self._validate_tag_schema())
        return diagnostics

    # ------------------------------------------------------------------
    # Layout → Instance 引用
    # ------------------------------------------------------------------

    def _validate_layout_references(self) -> list[Diagnostic]:
        """检查 Layout 中引用的 Instance 都存在且 Schema 有效。"""
        diagnostics: list[Diagnostic] = []
        layout = self.project.layout
        if layout is None:
            return diagnostics

        all_instances = self.project.all_instances_tree()
        valid_ids = {iid for iid, inst in all_instances.items() if inst.family != "_invalid"}

        for entry_id, entry in layout.entries.items():
            if entry_id not in all_instances:
                diagnostics.append(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=(
                            f"Layout 引用的 Instance '{entry_id}' 在项目树中不存在。"
                            f" 请检查 instances/ 目录是否包含该 Instance 文件。"
                        ),
                        location=Location.from_path(layout.source)
                        if layout.source
                        else Location(uri=""),
                        code="REFS-001",
                        source="adl.validation",
                    )
                )
            elif entry_id not in valid_ids:
                diagnostics.append(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=(
                            f"Layout 引用的 Instance '{entry_id}' Schema 校验失败，"
                            f"无法用于部署。请先修复该 Instance 的错误。"
                        ),
                        location=Location.from_path(layout.source)
                        if layout.source
                        else Location(uri=""),
                        code="REFS-001",
                        source="adl.validation",
                    )
                )
        return diagnostics

    def _validate_relative_layout(self) -> list[Diagnostic]:
        """校验 Layout 中相对坐标条目的 ADR-013 约束。

        - ``parent`` 与任意绝对坐标字段互斥。
        - ``parent`` 指向的实例必须在同一 Layout 中存在。
        - ``parent`` 不能形成环。
        """
        diagnostics: list[Diagnostic] = []
        layout = self.project.layout
        if layout is None:
            return diagnostics

        for entry in layout.entries.values():
            if entry.parent is None:
                continue

            if entry.parent == entry.instance:
                diagnostics.append(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=(f"Layout 条目 '{entry.instance}' 的 parent 不能指向自身。"),
                        location=Location.from_path(layout.source)
                        if layout.source
                        else Location(uri=""),
                        code="LAYOUT-003",
                        source="adl.validation",
                    )
                )

            absolute_fields = entry.absolute_fields
            if absolute_fields:
                diagnostics.append(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=(
                            f"Layout 条目 '{entry.instance}' 使用相对坐标时，"
                            f"不能同时填写绝对坐标字段: {', '.join(sorted(absolute_fields))}。"
                        ),
                        location=Location.from_path(layout.source)
                        if layout.source
                        else Location(uri=""),
                        code="LAYOUT-001",
                        source="adl.validation",
                    )
                )

            if entry.parent not in layout.entries:
                diagnostics.append(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=(
                            f"Layout 条目 '{entry.instance}' 的 parent "
                            f"'{entry.parent}' 在 Layout 中不存在。"
                        ),
                        location=Location.from_path(layout.source)
                        if layout.source
                        else Location(uri=""),
                        code="LAYOUT-002",
                        source="adl.validation",
                    )
                )

        for cycle in layout.detect_cycles():
            diagnostics.append(
                Diagnostic(
                    severity=Severity.ERROR,
                    message=(f"Layout parent 引用存在环: {' -> '.join(cycle)} -> {cycle[0]}。"),
                    location=Location.from_path(layout.source)
                    if layout.source
                    else Location(uri=""),
                    code="LAYOUT-004",
                    source="adl.validation",
                )
            )

        return diagnostics

    # ------------------------------------------------------------------
    # Grid 轴网部署校验
    # ------------------------------------------------------------------

    def _validate_grid_layout(self) -> list[Diagnostic]:
        """校验 Layout 中 Grid 轴网引用的合法性。"""
        diagnostics: list[Diagnostic] = []
        layout = self.project.layout
        if layout is None:
            return diagnostics

        for entry in layout.entries.values():
            grid_id = entry.grid_id
            grid_position = entry.grid_position
            has_row_bay = entry.row_id is not None and entry.bay_index is not None

            if grid_id is None:
                if grid_position is not None:
                    diagnostics.append(
                        Diagnostic(
                            severity=Severity.ERROR,
                            message=(
                                f"Layout 条目 '{entry.instance}' 填写了 grid_position "
                                f"但未指定 grid_id。"
                            ),
                            location=Location.from_path(layout.source)
                            if layout.source
                            else Location(uri=""),
                            code="GRID-003",
                            source="adl.validation",
                        )
                    )
                continue

            grid = self.project.find_grid(grid_id)
            if grid is None:
                diagnostics.append(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=(
                            f"Layout 条目 '{entry.instance}' 引用的 Grid "
                            f"'{grid_id}' 不存在。"
                        ),
                        location=Location.from_path(layout.source)
                        if layout.source
                        else Location(uri=""),
                        code="GRID-001",
                        source="adl.validation",
                    )
                )
                continue

            if grid_position is None and not has_row_bay:
                diagnostics.append(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=(
                            f"Layout 条目 '{entry.instance}' 引用了 Grid '{grid_id}'，"
                            f"但未提供 grid_position 或 row_id + bay_index。"
                        ),
                        location=Location.from_path(layout.source)
                        if layout.source
                        else Location(uri=""),
                        code="GRID-004",
                        source="adl.validation",
                    )
                )
                continue

            effective_position = grid_position
            if effective_position is None and has_row_bay:
                effective_position = (entry.row_id, str(entry.bay_index))

            if effective_position is not None:
                axis_a_id, axis_b_id = effective_position
                if not grid.has_line(0, axis_a_id):
                    diagnostics.append(
                        Diagnostic(
                            severity=Severity.ERROR,
                            message=(
                                f"Layout 条目 '{entry.instance}' 的 grid_position "
                                f"'{axis_a_id}' 不在 Grid '{grid_id}' 的第一组轴线中。"
                            ),
                            location=Location.from_path(layout.source)
                            if layout.source
                            else Location(uri=""),
                            code="GRID-002",
                            source="adl.validation",
                        )
                    )
                if not grid.has_line(1, axis_b_id):
                    diagnostics.append(
                        Diagnostic(
                            severity=Severity.ERROR,
                            message=(
                                f"Layout 条目 '{entry.instance}' 的 grid_position "
                                f"'{axis_b_id}' 不在 Grid '{grid_id}' 的第二组轴线中。"
                            ),
                            location=Location.from_path(layout.source)
                            if layout.source
                            else Location(uri=""),
                            code="GRID-002",
                            source="adl.validation",
                        )
                    )

        return diagnostics

    # ------------------------------------------------------------------
    # 通用外键引用
    # ------------------------------------------------------------------

    def _validate_foreign_keys(self) -> list[Diagnostic]:
        """检查 Instance 字段中的外键引用。"""
        diagnostics: list[Diagnostic] = []
        all_ids = set(self.project.all_instances_tree().keys())

        for inst in self.project.instances.values():
            for field_name, field_value in inst._resolved.items():
                if not isinstance(field_value, str) or not field_value:
                    continue

                # 接口引用：from_interface / to_interface
                if field_name.endswith("_interface") and "/" in field_value:
                    try:
                        instance_id, interface_id = resolve_interface_ref(field_value)
                    except ValueError as exc:
                        diagnostics.append(
                            Diagnostic(
                                severity=Severity.ERROR,
                                message=(
                                    f"Instance '{inst.id}' 的字段 '{field_name}' 接口引用格式无效: {exc}"
                                ),
                                location=Location.from_path(inst.source),
                                code="FK-001",
                                source="adl.validation",
                            )
                        )
                        continue

                    target = self.project.find_instance(instance_id)
                    if target is None:
                        diagnostics.append(
                            Diagnostic(
                                severity=Severity.ERROR,
                                message=(
                                    f"Instance '{inst.id}' 的字段 '{field_name}' 引用了 "
                                    f"不存在的 Instance '{instance_id}'。"
                                ),
                                location=Location.from_path(inst.source),
                                code="FK-001",
                                source="adl.validation",
                            )
                        )
                        continue

                    interfaces = get_interfaces_from_resolved(target)
                    if interface_id not in {i.id for i in interfaces}:
                        diagnostics.append(
                            Diagnostic(
                                severity=Severity.ERROR,
                                message=(
                                    f"Instance '{inst.id}' 的字段 '{field_name}' 引用了 "
                                    f"Interface '{field_value}'，但 Instance '{instance_id}' "
                                    f"未声明该接口。"
                                ),
                                location=Location.from_path(inst.source),
                                code="FK-001",
                                source="adl.validation",
                            )
                        )
                    continue

                # 普通外键引用：以 _id 结尾
                if not field_name.endswith("_id"):
                    continue

                if field_value not in all_ids:
                    diagnostics.append(
                        Diagnostic(
                            severity=Severity.ERROR,
                            message=(
                                f"Instance '{inst.id}' 的字段 '{field_name}' 引用了 "
                                f"不存在的 Instance '{field_value}'。"
                            ),
                            location=Location.from_path(inst.source),
                            code="FK-001",
                            source="adl.validation",
                        )
                    )

        return diagnostics

    # ------------------------------------------------------------------
    # Mate 引用与约束
    # ------------------------------------------------------------------

    def _validate_mate_references(self) -> list[Diagnostic]:
        """检查 Mate 的 parent/child 引用是否存在。"""
        diagnostics: list[Diagnostic] = []
        for mate in self.project.mates:
            parent_inst_id, _ = parse_mate_ref(mate.parent)
            child_inst_id, _ = parse_mate_ref(mate.child)

            if self.project.find_instance(parent_inst_id) is None:
                diagnostics.append(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=f"Mate '{mate.type}' parent instance '{parent_inst_id}' not found",
                        location=Location(uri=""),
                        code="MATE-001",
                        source="adl.validation",
                    )
                )
            if self.project.find_instance(child_inst_id) is None:
                diagnostics.append(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=f"Mate '{mate.type}' child instance '{child_inst_id}' not found",
                        location=Location(uri=""),
                        code="MATE-001",
                        source="adl.validation",
                    )
                )
        return diagnostics

    def _validate_mate_family_compat(self) -> list[Diagnostic]:
        """检查 Mate 类型对 parent/child Family 的限制。"""
        diagnostics: list[Diagnostic] = []
        for mate in self.project.mates:
            type_meta = self.project.type_registry.get_mate_type(mate.type)
            if not type_meta:
                continue

            parent_inst_id, _ = parse_mate_ref(mate.parent)
            child_inst_id, _ = parse_mate_ref(mate.child)
            parent_inst = self.project.find_instance(parent_inst_id)
            child_inst = self.project.find_instance(child_inst_id)

            if not parent_inst or not child_inst:
                continue

            if type_meta.applicable_parent_families:
                if parent_inst.family not in type_meta.applicable_parent_families:
                    diagnostics.append(
                        Diagnostic(
                            severity=Severity.ERROR,
                            message=(
                                f"Mate '{mate.type}' does not accept parent family "
                                f"'{parent_inst.family}'. Allowed: {type_meta.applicable_parent_families}"
                            ),
                            location=Location(uri=""),
                            code="MATE-002",
                            source="adl.validation",
                        )
                    )

            if type_meta.applicable_child_families:
                if child_inst.family not in type_meta.applicable_child_families:
                    diagnostics.append(
                        Diagnostic(
                            severity=Severity.ERROR,
                            message=(
                                f"Mate '{mate.type}' does not accept child family "
                                f"'{child_inst.family}'. Allowed: {type_meta.applicable_child_families}"
                            ),
                            location=Location(uri=""),
                            code="MATE-002",
                            source="adl.validation",
                        )
                    )
        return diagnostics

    def _validate_mate_constraints(self) -> list[Diagnostic]:
        """检查 Mate 的固有约束。"""
        diagnostics: list[Diagnostic] = []
        for mate in self.project.mates:
            type_meta = self.project.type_registry.get_mate_type(mate.type)
            constrains = (
                mate.constrains
                if mate.constrains
                else (type_meta.default_constrains if type_meta else [])
            )
            if not constrains:
                continue

            parent_inst_id, parent_iface_id = parse_mate_ref(mate.parent)
            child_inst_id, child_iface_id = parse_mate_ref(mate.child)
            parent_inst = self.project.find_instance(parent_inst_id)
            child_inst = self.project.find_instance(child_inst_id)

            if parent_inst is None or child_inst is None:
                continue

            parent_iface = self._find_interface(parent_inst, parent_iface_id)
            child_iface = self._find_interface(child_inst, child_iface_id)

            for constraint in constrains:
                child_val = self._resolve_constraint_value(
                    child_inst, child_iface, constraint.field
                )
                parent_val = self._resolve_constraint_value(
                    parent_inst, parent_iface, constraint.value_ref
                )

                if child_val is None or parent_val is None:
                    continue

                if not self._evaluate_constraint(child_val, constraint, parent_val):
                    msg = constraint.message or (
                        f"Mate constraint violated: {child_inst.id}.{constraint.field} "
                        f"{constraint.operator.value} {constraint.value_ref} "
                        f"(got {child_val} vs {parent_val})"
                    )
                    diagnostics.append(
                        Diagnostic(
                            severity=Severity.ERROR,
                            message=msg,
                            location=Location(uri=""),
                            code="MATE-003",
                            source="adl.validation",
                        )
                    )

        return diagnostics

    def _find_interface(self, inst: Any, iface_id: str | None) -> InterfaceSpec | None:
        """从 ResolvedInstance 中查找指定 Interface。"""
        if iface_id is None:
            return None
        interfaces = get_interfaces_from_resolved(inst)
        for iface in interfaces:
            if iface.id == iface_id:
                return iface
        return None

    def _resolve_constraint_value(
        self,
        inst: Any,
        iface: InterfaceSpec | None,
        field: str,
    ) -> Any:
        """解析约束字段值：L2 接口优先，其次 Instance resolved 字段。"""
        if iface is not None and hasattr(iface, "specs"):
            val = iface.specs.get(field)
            if val is not None:
                return val
        try:
            return inst.resolved.__getattr__(field)
        except AttributeError:
            pass
        try:
            return getattr(inst.resolved, field, None)
        except Exception:
            pass
        return None

    def _evaluate_constraint(self, left: Any, constraint: Any, right: Any) -> bool:
        """评估约束。"""
        from adl.models.mating import evaluate_operator

        return evaluate_operator(left, constraint.operator, right)

    # ------------------------------------------------------------------
    # Catalog 引用
    # ------------------------------------------------------------------

    def _validate_catalog_references(self) -> list[Diagnostic]:
        """检查 Instance 显式 catalog 引用是否存在。"""
        diagnostics: list[Diagnostic] = []
        for inst in self.project.instances.values():
            raw_catalog = inst._catalog
            if not isinstance(raw_catalog, dict):
                continue
            catalog_id = raw_catalog.get("id") or raw_catalog.get("catalog_id")
            if not catalog_id:
                continue
            if not inst._resolved.get("catalog"):
                source = raw_catalog.get("source")
                diagnostics.append(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=(
                            f"Instance '{inst.id}' 显式指定的 Catalog "
                            f"'{catalog_id}'（source={source or 'any'}）不存在。"
                        ),
                        location=Location.from_path(inst.source),
                        code="CATALOG-001",
                        source="adl.validation",
                    )
                )
        return diagnostics

    def _validate_catalog_service_methods(self) -> list[Diagnostic]:
        """检查 ComponentCatalogEntry 引用的 service_methods 是否存在。"""
        diagnostics: list[Diagnostic] = []
        for entry in self.project.catalogs.values():
            if entry.family != "ComponentCatalogFamily":
                continue
            for method_id in entry.service_methods:
                method = self.project.find_catalog(method_id)
                if method is None:
                    diagnostics.append(
                        Diagnostic(
                            severity=Severity.ERROR,
                            message=(
                                f"Catalog '{entry.id}' 引用的 service method '{method_id}' 不存在。"
                            ),
                            location=Location.from_path(entry.source_path)
                            if entry.source_path
                            else Location(uri=""),
                            code="CATALOG-002",
                            source="adl.validation",
                        )
                    )
        return diagnostics

    # ------------------------------------------------------------------
    # FQID 冲突
    # ------------------------------------------------------------------

    def _validate_fqid_duplicates(self) -> list[Diagnostic]:
        """检查同一项目树中是否存在简单 ID 冲突。"""
        diagnostics: list[Diagnostic] = []
        all_instances = self.project.all_instances_with_fqid()
        all_simple = self.project.all_instances_tree()

        id_counts: dict[str, list[str]] = {}
        for fqid_val, inst in all_instances.items():
            simple_id = inst.id
            id_counts.setdefault(simple_id, []).append(fqid_val)

        for simple_id, fqids in id_counts.items():
            if len(fqids) > 1:
                inst = all_simple.get(simple_id)
                diagnostics.append(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=(
                            f"Instance ID '{simple_id}' 在项目树中出现 {len(fqids)} 次: "
                            f"{', '.join(fqids)}。请使用全限定 ID 引用。"
                        ),
                        location=Location.from_path(inst.source) if inst else Location(uri=""),
                        code="REFS-002",
                        source="adl.validation",
                    )
                )
        return diagnostics

    # ------------------------------------------------------------------
    # Tag Schema
    # ------------------------------------------------------------------

    def _validate_tag_schema(self) -> list[Diagnostic]:
        """检查 Instance 的 Tag 键是否在允许集合内。"""
        diagnostics: list[Diagnostic] = []
        allowed_tags = self.project.allowed_tags
        if not allowed_tags:
            return diagnostics

        for inst in self.project.instances.values():
            tags_raw = inst._resolved.get("tags")
            if not isinstance(tags_raw, dict):
                continue

            active_keys: set[str] = set()
            for k, v in tags_raw.items():
                if k == "extra":
                    if isinstance(v, dict):
                        active_keys.update(ek for ek, ev in v.items() if ev)
                    continue
                if v:
                    active_keys.add(k)

            unknown_keys = active_keys - allowed_tags
            if unknown_keys:
                diagnostics.append(
                    Diagnostic(
                        severity=Severity.WARNING,
                        message=(
                            f"Instance '{inst.id}' 使用了未在配置中声明的 Tag 键: "
                            f"{', '.join(sorted(unknown_keys))}。"
                            f" 允许的键: {', '.join(sorted(allowed_tags))}。"
                        ),
                        location=Location.from_path(inst.source),
                        code="TAGS-001",
                        source="adl.validation",
                    )
                )
        return diagnostics
