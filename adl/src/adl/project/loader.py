"""ADL 项目加载器。

负责扫描项目目录、解析 YAML、合并 Model/Instance/Layout、构建 MateGraph，
最终返回一个 ``Project`` 对象。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from adl.diagnostics import Diagnostic, Location, Severity
from adl.models import (
    CatalogEntry,
    ComponentCatalogFamily,
    Instance,
    MateGraph,
    Model,
    ResolvedInstance,
    ServiceMethodCatalogFamily,
    get_non_overridable_fields,
    merge_service_methods,
)
from adl.parsing import find_layout_file, load_grids, load_layout_file, load_mates, load_yaml
from adl.types import TypeRegistry

from .project import Project

logger = logging.getLogger(__name__)

_CATALOG_SOURCE_PRIORITY = {
    "project": 0,
    "parent": 1,
    "enterprise": 2,
    "public": 3,
}


def _flatten(
    data: dict[str, Any],
    prefix: str = "",
    preserve_keys: set[str] | None = None,
) -> dict[str, Any]:
    """把嵌套 dict 扁平化，例如 {'physical': {'height_u': 2}} -> {'physical.height_u': 2}。"""
    out: dict[str, Any] = {}
    preserve = preserve_keys or {"assets", "tags"}
    for key, value in data.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and key not in preserve:
            out.update(_flatten(value, full, preserve))
        else:
            out[full] = value
    return out


class ProjectLoader:
    """ADL 项目加载器。

    Args:
        root: 项目根目录。
        type_registry: 类型注册表（Family / MateType / InterfaceType）。
        config: 项目配置；为 None 时自动加载 ``piki.toml``。
        parent: 父项目（用于嵌套项目）。
        extra_model_dirs: 额外的型号库目录（如插件自带型号库）。
        extra_catalog_dirs: 额外的 Catalog 目录（如插件自带 Catalog）。
    """

    def __init__(
        self,
        root: Path,
        type_registry: TypeRegistry,
        config: dict[str, Any] | None = None,
        parent: Project | None = None,
        extra_model_dirs: list[Path] | None = None,
        extra_catalog_dirs: list[Path] | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.type_registry = type_registry
        self.config = config if config is not None else self._load_config(self.root)
        self.parent = parent
        self.extra_model_dirs = extra_model_dirs or []
        self.extra_catalog_dirs = extra_catalog_dirs or []

    @staticmethod
    def _load_config(root: Path) -> dict[str, Any]:
        """加载 ``piki.toml`` 配置。"""
        from adl.parsing import load_toml

        path = root / "piki.toml"
        if path.exists():
            return load_toml(path)
        return {}

    def load(self) -> Project:
        """加载项目并返回 ``Project`` 对象。"""
        project = Project(
            root=self.root,
            config=self.config,
            type_registry=self.type_registry,
            parent=self.parent,
            project_name=self.config.get("project", {}).get("name", self.root.name),
            allowed_tags=set(self.config.get("tags", {}).get("allowed", [])),
        )
        self._load_externals(project)

        # 加载顺序很重要：Model -> Catalog -> Layout -> Grid -> Instance -> Mate
        self.load_models_into(project, [self.root / "models"] + self.extra_model_dirs)
        self.load_catalogs_into(
            project,
            [(self.root / "catalogs", "project")]
            + self._enterprise_catalog_dirs()
            + [(extra_dir, "public") for extra_dir in self.extra_catalog_dirs],
        )
        self.load_layout_into(project, self.root)
        self.load_grids_into(project, self.root)
        self._load_instances(project)
        self.load_mates_into(project, self.root)

        # 嵌套子项目
        self._load_children(project)

        return project

    def _enterprise_catalog_dirs(self) -> list[tuple[Path, str]]:
        """返回企业 Catalog 目录配置。"""
        enterprise_path = self.config.get("catalogs", {}).get("enterprise")
        if isinstance(enterprise_path, str):
            return [(Path(enterprise_path), "enterprise")]
        return []

    # ------------------------------------------------------------------
    # Model
    # ------------------------------------------------------------------

    def load_models_into(self, project: Project, models_dirs: list[Path]) -> None:
        """加载型号库到已有 ``Project`` 对象。"""
        for models_dir in models_dirs:
            if not models_dir.exists():
                continue
            for path in sorted(models_dir.rglob("*.yaml")):
                data = load_yaml(path)
                model_id = data.get("model")
                family = data.get("family")
                if not model_id or not family:
                    logger.warning("Skipping model without 'model' or 'family': %s", path)
                    continue
                model_data = {k: v for k, v in data.items() if k not in ("model", "family")}
                project.models[model_id] = Model(
                    id=model_id,
                    family=family,
                    data=model_data,
                    source=path,
                )

    def _load_models(self, project: Project) -> None:
        """加载型号库：项目本地 + 额外目录（插件）。"""
        self.load_models_into(project, [self.root / "models"] + self.extra_model_dirs)

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    def load_catalogs_into(self, project: Project, catalog_dirs: list[tuple[Path, str]]) -> None:
        """加载 Catalog 到已有 ``Project`` 对象。"""
        family_map = {
            "ComponentCatalogFamily": ComponentCatalogFamily,
            "ServiceMethodCatalogFamily": ServiceMethodCatalogFamily,
        }

        for catalogs_dir, source in catalog_dirs:
            if not catalogs_dir.exists():
                continue
            for path in sorted(catalogs_dir.rglob("*.yaml")):
                data = load_yaml(path)
                if not isinstance(data, dict):
                    logger.warning("Skipping non-mapping catalog file: %s", path)
                    continue

                catalog_id = data.get("catalog_id")
                family_name = data.get("family")
                if not catalog_id or not family_name:
                    logger.warning("Skipping catalog without 'catalog_id' or 'family': %s", path)
                    continue

                family_cls = family_map.get(family_name)
                if family_cls is None:
                    logger.warning("Unknown catalog family %s in %s", family_name, path)
                    continue

                try:
                    validated = family_cls.model_validate(data)
                except Exception as exc:
                    project.diagnostics.append(
                        Diagnostic(
                            severity=Severity.ERROR,
                            message=f"Catalog '{catalog_id}' Schema 校验失败: {exc}",
                            location=Location.from_path(path),
                            code="SCHEMA-001",
                            source="adl.schema",
                        )
                    )
                    continue

                entry_data = validated.model_dump()
                project.catalogs[catalog_id] = CatalogEntry(
                    id=catalog_id,
                    family=family_name,
                    source=source,
                    model_ref=entry_data.get("model_ref"),
                    data=entry_data,
                    source_path=path,
                )

    def _load_catalogs(self, project: Project) -> None:
        """加载 Catalog：项目本地 + 企业 + 插件公共 Catalog。"""
        catalog_dirs: list[tuple[Path, str]] = [(self.root / "catalogs", "project")]
        catalog_dirs.extend(self._enterprise_catalog_dirs())
        for extra_dir in self.extra_catalog_dirs:
            catalog_dirs.append((extra_dir, "public"))
        self.load_catalogs_into(project, catalog_dirs)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def load_layout_into(self, project: Project, root: Path) -> None:
        """加载 Layout 文件到已有 ``Project`` 对象。"""
        path = find_layout_file(root)
        if path is None:
            return
        project.layout = load_layout_file(path, name=root.name)

    def load_grids_into(self, project: Project, root: Path) -> None:
        """加载 Grid 资源到已有 ``Project`` 对象，并注入 Layout。"""
        grids = load_grids(root)
        project.grids.update(grids)
        if project.layout is not None:
            project.layout.grids.update(grids)

    def _load_layout(self, project: Project) -> None:
        """加载项目 Layout 文件。"""
        self.load_layout_into(project, self.root)

    # ------------------------------------------------------------------
    # Instance
    # ------------------------------------------------------------------

    def _load_instances(self, project: Project) -> None:
        """扫描 instances/ 目录，子目录作为独立集合加载。"""
        instances_dir = self.root / "instances"
        if not instances_dir.exists():
            return

        has_subdirs = False
        for entry in sorted(instances_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                if any(entry.rglob("*.yaml")):
                    loaded = self.load_collection_into(project, entry, entry.name)
                    project.collections[entry.name] = loaded
                    has_subdirs = True

        if not has_subdirs:
            raise FileNotFoundError(
                "instances/ 目录下没有子目录。请按类型创建子目录，"
                "例如 instances/devices/、instances/racks/、instances/pdus/"
            )

    def load_collection_into(
        self,
        project: Project,
        collection_dir: Path,
        collection_name: str,
    ) -> dict[str, ResolvedInstance]:
        """加载一个 Instance 子目录到已有 ``Project`` 对象。

        返回加载的实例字典；调用方负责将其存入 ``project.collections``。
        """
        loaded: dict[str, ResolvedInstance] = {}
        for path in sorted(collection_dir.rglob("*.yaml")):
            data = load_yaml(path)
            inst_id = data.get("id")
            if not inst_id:
                logger.warning("Skipping instance without 'id': %s", path)
                continue

            instance = Instance(
                id=inst_id,
                model=data.get("model"),
                family=data.get("family"),
                data={k: v for k, v in data.items() if k != "id"},
                source=path,
            )
            resolved = self._resolve_instance(project, instance, data)
            if resolved is None:
                flat = _flatten(instance.data)
                flat["id"] = instance.id
                resolved = ResolvedInstance(
                    id=instance.id,
                    family="_invalid",
                    raw=flat,
                    _resolved=flat,
                    source=instance.source,
                    model_id=instance.model,
                )
            loaded[resolved.id] = resolved
            project.instances[resolved.id] = resolved
        return loaded

    def _load_collection(
        self, project: Project, collection_dir: Path
    ) -> dict[str, ResolvedInstance]:
        """兼容旧签名的内部方法。"""
        return self.load_collection_into(project, collection_dir, collection_dir.name)

    def _resolve_instance(
        self,
        project: Project,
        instance: Instance,
        source_data: dict[str, Any] | None = None,
    ) -> ResolvedInstance | None:
        """合并 Model + Instance + Layout + Catalog，并用 Family 校验。"""
        family_name = instance.family
        model_id = instance.model

        # 确定 Family
        if family_name is None:
            if model_id is not None:
                model = project.find_model(model_id)
                if model is not None:
                    family_name = model.family
            if family_name is None and instance.data.get("family"):
                family_name = instance.data["family"]

        if family_name is None:
            logger.warning("Instance %s has no family or model", instance.id)
            return None

        family_cls = self.type_registry.get_family(family_name)
        if family_cls is None:
            if project.parent:
                family_cls = project.parent.type_registry.get_family(family_name)
            if family_cls is None:
                logger.warning("Unknown family %s for instance %s", family_name, instance.id)
                return None

        # Model 默认值
        model_defaults: dict[str, Any] = {}
        if model_id:
            model = project.find_model(model_id)
            if model is not None:
                model_defaults = dict(model.data)

        # Instance 覆盖值
        overrides = dict(instance.data)
        overrides.pop("model", None)
        overrides.pop("family", None)

        catalog_override = overrides.pop("catalog", None)
        if isinstance(catalog_override, dict):
            catalog_override = dict(catalog_override)

        # 不可覆盖字段
        non_overridable = get_non_overridable_fields(family_cls)
        if non_overridable:
            for field_name in sorted(non_overridable):
                if field_name in overrides:
                    project.diagnostics.append(
                        Diagnostic(
                            severity=Severity.ERROR,
                            message=(
                                f"Instance '{instance.id}' 试图覆盖不可覆盖字段 "
                                f"'{field_name}'（值={overrides[field_name]!r}）。"
                                f" 物理尺寸字段不允许 Instance 覆盖，"
                                f" 请在 Model 中设置或保持默认值。"
                            ),
                            location=Location.from_path(instance.source),
                            code="SCHEMA-002",
                            source="adl.schema",
                        )
                    )
                    del overrides[field_name]

        merged = _flatten(
            {**model_defaults, **overrides},
            preserve_keys={"assets", "tags", "shape", "kinematics", "load_capacity"},
        )
        merged["id"] = instance.id

        # Schema 校验
        try:
            validated = family_cls.model_validate(merged)
        except ValidationError as exc:
            location = self._build_error_location(instance.source, source_data, exc)
            project.diagnostics.append(
                Diagnostic.from_validation_error(
                    exc=exc,
                    location=location,
                    code="SCHEMA-001",
                    source="adl.schema",
                )
            )
            flat = _flatten(instance.data)
            flat["id"] = instance.id
            return ResolvedInstance(
                id=instance.id,
                family="_invalid",
                raw=flat,
                _resolved=flat,
                source=instance.source,
                model_id=instance.model,
                _validation_error=str(exc),
            )

        resolved_dict = _flatten(
            validated.model_dump(),
            preserve_keys={"assets", "tags", "shape", "kinematics", "load_capacity"},
        )

        # Layout 合并
        if project.layout is not None:
            layout_entry = project.layout.get(instance.id)
            if layout_entry is not None:
                resolved_dict.update(layout_entry.to_flat())

        # Catalog 权威层注入
        active_catalog = self._resolve_catalog(project, instance, model_id, catalog_override)
        if active_catalog is not None:
            resolved_dict["catalog"] = active_catalog.data
            methods = self._get_service_methods(project, active_catalog.service_methods)
            if methods:
                resolved_dict["service_method"] = merge_service_methods(methods)

        return ResolvedInstance(
            id=instance.id,
            family=family_name,
            raw=overrides,
            _resolved=resolved_dict,
            source=instance.source,
            model_id=model_id,
            _catalog=catalog_override,
        )

    def _resolve_catalog(
        self,
        project: Project,
        instance: Instance,
        model_id: str | None,
        catalog_override: dict[str, Any] | None,
    ) -> CatalogEntry | None:
        """解析 Instance 生效的 CatalogEntry。"""
        catalog_id: str | None = None
        source: str | None = None
        if isinstance(catalog_override, dict):
            catalog_id = catalog_override.get("id") or catalog_override.get("catalog_id")
            source = catalog_override.get("source")

        if catalog_id:
            return self._find_catalog_by_id_and_source(project, catalog_id, source)

        if model_id:
            return self._find_catalog_by_model(project, model_id)

        return None

    def _find_catalog_by_id_and_source(
        self, project: Project, catalog_id: str, source: str | None
    ) -> CatalogEntry | None:
        """按 ID + source 查找 CatalogEntry。"""
        if source == "parent":
            current = project.parent
            while current is not None:
                entry = current.catalogs.get(catalog_id)
                if entry is not None:
                    return CatalogEntry(
                        id=entry.id,
                        family=entry.family,
                        source="parent",
                        model_ref=entry.model_ref,
                        data=entry.data,
                        source_path=entry.source_path,
                    )
                current = current.parent
            return None

        entry = project.catalogs.get(catalog_id)
        if entry is not None and (source is None or entry.source == source):
            return entry
        return None

    def _find_catalog_by_model(self, project: Project, model_ref: str) -> CatalogEntry | None:
        """按 model_ref 优先级查找 CatalogEntry。"""
        candidates: list[tuple[CatalogEntry, int]] = []
        current: Project | None = project
        distance = 0
        while current is not None:
            for entry in current.catalogs.values():
                if entry.model_ref == model_ref:
                    if distance == 0:
                        candidates.append((entry, distance))
                    else:
                        candidates.append(
                            (
                                CatalogEntry(
                                    id=entry.id,
                                    family=entry.family,
                                    source="parent",
                                    model_ref=entry.model_ref,
                                    data=entry.data,
                                    source_path=entry.source_path,
                                ),
                                distance,
                            )
                        )
            current = current.parent
            distance += 1

        if not candidates:
            return None

        candidates.sort(
            key=lambda x: (
                _CATALOG_SOURCE_PRIORITY.get(x[0].source, 99),
                x[1],
            )
        )
        return candidates[0][0]

    def _get_service_methods(self, project: Project, method_ids: list[str]) -> list[CatalogEntry]:
        """按 ID 列表查找 ServiceMethodCatalogEntry。"""
        result: list[CatalogEntry] = []
        for mid in method_ids:
            entry = self._find_catalog_by_id_and_source(project, mid, None)
            if entry is not None and entry.family == "ServiceMethodCatalogFamily":
                result.append(entry)
        return result

    def _build_error_location(
        self,
        path: Path,
        source_data: dict[str, Any] | None,
        exc: ValidationError,
    ) -> Location:
        """从 ValidationError 定位到源文件行号。"""
        from adl.diagnostics import Range
        from adl.parsing import SourceTrackedDict, get_field_location

        location = Location.from_path(path, line=0)
        if source_data is None or not isinstance(source_data, SourceTrackedDict):
            return location
        errors = exc.errors()
        if errors:
            first_error = errors[0]
            loc_parts = first_error.get("loc", ())
            if loc_parts:
                field_path = ".".join(str(p) for p in loc_parts)
                mark = get_field_location(source_data, field_path, path)
                if mark is not None:
                    location = Location(
                        uri=path.as_uri(),
                        range=Range.point(mark.line, mark.column),
                    )
        return location

    # ------------------------------------------------------------------
    # Mate
    # ------------------------------------------------------------------

    def load_mates_into(self, project: Project, root: Path) -> None:
        """加载 Mate 文件并构建 MateGraph 到已有 ``Project`` 对象。"""
        project.mates = load_mates(root)
        project.mate_graph = MateGraph()
        for mate in project.mates:
            project.mate_graph.add(mate)

    def _load_mates(self, project: Project) -> None:
        """加载 Mate 文件并构建 MateGraph。"""
        self.load_mates_into(project, self.root)

    # ------------------------------------------------------------------
    # 嵌套项目
    # ------------------------------------------------------------------

    def _load_children(self, project: Project) -> None:
        """递归发现子项目目录。"""
        for entry in sorted(self.root.iterdir()):
            if not entry.is_dir():
                continue
            child_toml = entry / "piki.toml"
            if not child_toml.exists():
                continue
            if entry.name in (
                "models",
                "instances",
                "layouts",
                "rules",
                "mates",
                ".git",
                "__pycache__",
                ".piki",
            ):
                continue
            try:
                child_config = self._load_config(entry)
                child_loader = ProjectLoader(
                    root=entry,
                    type_registry=self.type_registry,
                    config=child_config,
                    parent=project,
                    extra_model_dirs=self.extra_model_dirs,
                    extra_catalog_dirs=self.extra_catalog_dirs,
                )
                child_project = child_loader.load()
                project.children[entry.name] = child_project
            except Exception as exc:
                logger.warning("Failed to load sub-project %s: %s", entry.name, exc)

    # ------------------------------------------------------------------
    # 外部项目
    # ------------------------------------------------------------------

    def _load_externals(self, project: Project) -> None:
        """从配置加载外部项目注册，并将其 instances/models/layout/mates 合并到主项目。"""
        externals_config = self.config.get("external", {})
        if not isinstance(externals_config, dict):
            return
        for alias, path_str in externals_config.items():
            if not isinstance(path_str, str):
                continue
            ext_path = (self.root / Path(path_str)).resolve()
            if not ext_path.exists():
                logger.warning("External project not found: %s -> %s", alias, ext_path)
                continue
            project.externals[alias] = ext_path
            try:
                ext_config = self._load_config(ext_path)
                ext_loader = ProjectLoader(
                    root=ext_path,
                    type_registry=self.type_registry,
                    config=ext_config,
                    parent=None,
                    extra_model_dirs=self.extra_model_dirs,
                    extra_catalog_dirs=self.extra_catalog_dirs,
                )
                ext_project = ext_loader.load()
                # Merge instances: prefix with alias/ to avoid ID conflicts
                for iid, inst in ext_project.instances.items():
                    fqid = f"{alias}/{iid}"
                    project.instances[fqid] = inst
                    # Also register simple ID for convenience (external is read-only)
                    if iid not in project.instances:
                        project.instances[iid] = inst
                # Merge models
                for mid, model in ext_project.models.items():
                    if mid not in project.models:
                        project.models[mid] = model
                # Merge mates
                ext_mates = list(ext_project.mates)
                logger.info("External %s has %d mates", alias, len(ext_mates))
                for mate in ext_mates:
                    try:
                        project.mates.append(mate)
                        project.mate_graph.add(mate)
                    except Exception as exc:
                        logger.warning("Failed to merge mate %s: %s", mate.type, exc)
                # Merge layouts — entries prefixed with alias/
                if ext_project.layout:
                    for eid, entry in ext_project.layout.entries.items():
                        fqid = f"{alias}/{eid}"
                        if fqid not in project.layout.entries:
                            project.layout.entries[fqid] = entry
                logger.info("Loaded external project '%s' from %s (%d instances)", alias, ext_path, len(ext_project.instances))
            except Exception as exc:
                logger.warning("Failed to load external project %s: %s", alias, exc)
