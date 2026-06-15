"""Registry：piki 运行时的项目数据包装器。

注意：数据加载和 ADL 层验证已经迁移到独立的 ``adl`` 包。
本 Registry 现在是一个薄包装层，把 piki 运行时 API 映射到 ``adl.project.Project``。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adl.diagnostics import Diagnostic
from adl.models import CatalogEntry, MateGraph, MateSpec, MateTypeMeta, Model, ResolvedInstance
from adl.project import Project, ProjectLoader
from adl.types import TypeRegistry
from pydantic import BaseModel

from .query import QuerySet, make_query_set


class Registry:
    """运行时中央注册表（现为 ``adl.project.Project`` 的兼容包装）。"""

    def __init__(self, project: Project | None = None) -> None:
        self._project = project
        self._extra_diagnostics: list[Diagnostic] = []

    # ------------------------------------------------------------------
    # 数据加载（新入口）
    # ------------------------------------------------------------------

    def load_project(
        self,
        root: Path,
        type_registry: TypeRegistry,
        config: dict[str, Any],
        extra_model_dirs: list[Path] | None = None,
        extra_catalog_dirs: list[Path] | None = None,
    ) -> Project:
        """通过 ADL 加载器完整加载项目。"""
        parent_project = self._project.parent if self._project else None
        loader = ProjectLoader(
            root=root,
            type_registry=type_registry,
            config=config,
            parent=parent_project,
            extra_model_dirs=extra_model_dirs or [],
            extra_catalog_dirs=extra_catalog_dirs or [],
        )
        self._project = loader.load()
        return self._project

    @property
    def project(self) -> Project:
        """底层 ADL Project 对象（不存在时自动创建）。"""
        return self._ensure_project()

    # ------------------------------------------------------------------
    # Lazy project creation (for tests and backward compatibility)
    # ------------------------------------------------------------------

    def _ensure_project(self) -> Project:
        """如果当前没有 Project，则创建一个空项目。"""
        if self._project is None:
            self._project = Project(
                root=Path("."),
                config={},
                type_registry=TypeRegistry(),
            )
        return self._project

    # ------------------------------------------------------------------
    # Family / Model
    # ------------------------------------------------------------------

    def add_family(self, name: str, cls: type[BaseModel]) -> None:
        self._ensure_project().type_registry.add_family(name, cls)

    def get_family(self, name: str) -> type[BaseModel] | None:
        if self._project is None:
            return None
        family = self._project.type_registry.get_family(name)
        if family is None and self._project.parent:
            family = self._project.parent.type_registry.get_family(name)
        return family

    def add_model(self, model: Model) -> None:
        self._ensure_project().models[model.id] = model

    def get_model(self, model_id: str) -> Model | None:
        if self._project is None:
            return None
        return self._project.models.get(model_id)

    def find_model(self, model_id: str) -> Model | None:
        if self._project is None:
            return None
        return self._project.find_model(model_id)

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    def add_catalog(self, entry: CatalogEntry) -> None:
        self._ensure_project().catalogs[entry.id] = entry

    def _project_loader(self, root: Path | None = None) -> ProjectLoader:
        """为当前 Project 构造一个 ProjectLoader。"""
        project = self._ensure_project()
        return ProjectLoader(
            root=root if root is not None else project.root,
            type_registry=project.type_registry,
            config=project.config,
            parent=project.parent,
        )

    def load_catalogs(self, root: Path, source: str = "project") -> None:
        """加载 ``root/catalogs`` 下的 Catalog 到当前 Project。"""
        project = self._ensure_project()
        loader = self._project_loader(root=root)
        loader.load_catalogs_into(project, [(Path(root) / "catalogs", source)])

    def find_catalog(
        self,
        model_ref: str | None = None,
        catalog_id: str | None = None,
        source: str | None = None,
    ) -> CatalogEntry | None:
        if self._project is None:
            return None
        if catalog_id:
            entry = self._project.find_catalog(catalog_id)
            if entry is not None and (source is None or entry.source == source):
                return entry
            return None
        if model_ref:
            return self._project.find_catalog_by_model(model_ref)
        return None

    def get_service_methods(self, method_ids: list[str]) -> list[CatalogEntry]:
        if self._project is None:
            return []
        result: list[CatalogEntry] = []
        for mid in method_ids:
            entry = self.find_catalog(catalog_id=mid)
            if entry is not None and entry.family == "ServiceMethodCatalogFamily":
                result.append(entry)
        return result

    # ------------------------------------------------------------------
    # 嵌套项目
    # ------------------------------------------------------------------

    def set_parent(self, parent: "Registry") -> None:
        """设置父 Registry。

        注意：此操作仅在加载前设置父项目引用。加载后请直接访问 project.parent。
        """
        if self._project is None:
            self._project = Project(
                root=Path("."),
                config={},
                type_registry=TypeRegistry(),
                parent=parent.project,
            )
        else:
            self._project.parent = parent.project

    @property
    def parent(self) -> "Registry | None":
        if self._project is None or self._project.parent is None:
            return None
        return Registry(self._project.parent)

    def add_child(self, name: str, child: "Registry") -> None:
        self._ensure_project().children[name] = child.project

    @property
    def children(self) -> dict[str, "Registry"]:
        if self._project is None:
            return {}
        return {name: Registry(proj) for name, proj in self._project.children.items()}

    def set_project_name(self, name: str) -> None:
        if self._project is None:
            self._project = Project(
                root=Path("."),
                config={},
                type_registry=TypeRegistry(),
                project_name=name,
            )
        else:
            self._project.project_name = name

    def fqid(self, instance_id: str) -> str:
        if self._project is None:
            return instance_id
        return self._project.fqid(instance_id)

    def all_instances_with_fqid(self) -> dict[str, ResolvedInstance]:
        if self._project is None:
            return {}
        return self._project.all_instances_with_fqid()

    def all_instances_tree(self) -> dict[str, ResolvedInstance]:
        if self._project is None:
            return {}
        return self._project.all_instances_tree()

    def find_instance(self, instance_id: str) -> ResolvedInstance | None:
        if self._project is None:
            return None
        return self._project.find_instance(instance_id)

    # ------------------------------------------------------------------
    # Instance / Collection
    # ------------------------------------------------------------------

    def all_instances(self) -> dict[str, ResolvedInstance]:
        if self._project is None:
            return {}
        return dict(self._project.instances)

    def query(self, collection: str, **filters: Any) -> QuerySet:
        if self._project is None:
            return make_query_set([])
        items = list(self._project.collections.get(collection, {}).values())
        qs = make_query_set(items)
        if filters:
            qs = qs.filter(**filters)
        return qs

    def load_models(self, models_dir: Path) -> None:
        """加载 ``models_dir`` 下的型号库到当前 Project。"""
        project = self._ensure_project()
        loader = self._project_loader()
        loader.load_models_into(project, [Path(models_dir)])

    def load_collection(self, collection_dir: Path, collection_name: str | None = None) -> str:
        """加载一个 Instance 集合到当前 Project。

        返回实际使用的集合名称。
        """
        project = self._ensure_project()
        loader = self._project_loader()
        name = collection_name or Path(collection_dir).name
        loaded = loader.load_collection_into(project, Path(collection_dir), name)
        project.collections[name] = loaded
        return name

    def list_collections(self) -> list[str]:
        """返回当前 Project 中已加载的集合名称列表。"""
        if self._project is None:
            return []
        return list(self._project.collections.keys())

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def load_layout(self, project_root: Path) -> Any:
        """加载 ``project_root`` 下的 Layout 文件到当前 Project。"""
        project = self._ensure_project()
        loader = self._project_loader(root=project_root)
        loader.load_layout_into(project, Path(project_root))
        return project.layout

    @property
    def layout(self) -> Any:
        if self._project is None:
            return None
        return self._project.layout

    def get_layout_entry(self, instance_id: str) -> Any:
        if self._project is None or self._project.layout is None:
            return None
        entry = self._project.layout.get(instance_id)
        if entry is not None:
            return entry
        if self._project.parent:
            parent_reg = Registry(self._project.parent)
            return parent_reg.get_layout_entry(instance_id)
        return None

    # ------------------------------------------------------------------
    # Mating
    # ------------------------------------------------------------------

    @property
    def mate_types(self) -> dict[str, MateTypeMeta]:
        if self._project is None:
            return {}
        return self._project.type_registry.mate_types

    @property
    def mate_graph(self) -> MateGraph:
        return self._ensure_project().mate_graph

    @property
    def _mate_graph(self) -> MateGraph:
        """向后兼容：旧测试直接访问 registry._mate_graph。"""
        return self.mate_graph

    @property
    def mates(self) -> list[MateSpec]:
        return list(self._ensure_project().mates)

    @property
    def _mates(self) -> list[MateSpec]:
        """向后兼容：旧测试直接修改 registry._mates。"""
        return self._ensure_project().mates

    def add_mate_type(self, type_name: str, meta: MateTypeMeta) -> None:
        self._ensure_project().type_registry.add_mate_type(type_name, meta)

    def load_mates(self, root: Path) -> None:
        """加载 ``root`` 下的 Mate 文件到当前 Project。"""
        project = self._ensure_project()
        loader = self._project_loader(root=root)
        loader.load_mates_into(project, Path(root))

    def validate_mates(self) -> list[Diagnostic]:
        """遗留方法：ADL 层 Mate 验证已迁移到 ``adl.validation.ADLValidator``。"""
        return []

    # ------------------------------------------------------------------
    # Tag / External
    # ------------------------------------------------------------------

    def set_allowed_tags(self, tags: list[str]) -> None:
        self._ensure_project().allowed_tags = set(tags)

    @property
    def allowed_tags(self) -> set[str]:
        if self._project is None:
            return set()
        return set(self._project.allowed_tags)

    def register_external(self, alias: str, path: Path) -> None:
        self._ensure_project().externals[alias] = Path(path)

    @property
    def externals(self) -> dict[str, Path]:
        if self._project is None:
            return {}
        return dict(self._project.externals)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def diagnostics(self) -> list[Diagnostic]:
        result: list[Diagnostic] = []
        if self._project is not None:
            result.extend(self._project.diagnostics)
        result.extend(self._extra_diagnostics)
        return result

    def clear_diagnostics(self) -> None:
        if self._project is not None:
            self._project.diagnostics.clear()
        self._extra_diagnostics.clear()

    def add_diagnostic(self, diagnostic: Diagnostic) -> None:
        self._extra_diagnostics.append(diagnostic)

    # ------------------------------------------------------------------
    # 路径解析（兼容旧测试）
    # ------------------------------------------------------------------

    def _make_path_resolver(
        self,
        project_root: Path,
        externals: dict[str, Path] | None = None,
    ) -> _PathResolver:
        """构造一个用于跨仓库 Instance 引用的路径解析器。"""
        return _PathResolver(Path(project_root), externals or {})


class _PathResolver:
    """轻量级路径解析器。

    用于将 ``$PROJECT_ROOT/...`` 或 ``alias/...`` 形式的引用解析为文件路径。
    当前实现仅做路径存在性检查；真正的跨仓库 Instance 解析需要 Registry
    上下文配合。
    """

    def __init__(
        self,
        project_root: Path,
        externals: dict[str, Path],
    ) -> None:
        self.project_root = Path(project_root)
        self.externals = externals

    def resolve_instance(self, ref: str) -> ResolvedInstance | None:
        """解析 Instance 引用。

        - 简单 ID（无 ``/``）：返回 ``None``，由调用方在 Registry 中查找。
        - ``$PROJECT_ROOT/...``：若目标文件不存在返回 ``None``。
        - ``alias/...``：若 alias 对应的外部项目文件存在返回 ``None``。
        """
        if "/" not in ref:
            return None

        if ref.startswith("$PROJECT_ROOT/"):
            relative = ref[len("$PROJECT_ROOT/") :]
            path = self.project_root / relative
            if not path.exists():
                return None
            # 文件存在，但跨文件 Instance 解析需要 Registry 上下文
            return None

        alias, _, rest = ref.partition("/")
        external_root = self.externals.get(alias)
        if external_root is not None:
            path = Path(external_root) / rest
            if path.exists():
                # 跨仓库解析需要 Registry 上下文
                return None

        return None
