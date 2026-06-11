"""Registry：Family / Model / Instance 注册和解析。

支持：
- Instance 与 Layout 分离（ADR-008）
- 嵌套项目和跨项目 Instance 引用（ADR-009）
- Tag 机制（ADR-009）
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from ..models.base import Instance, Model, ResolvedInstance, _unflatten
from ..models.diagnostic import Diagnostic, Location, Range, Severity
from ..models.layout import Layout, LayoutEntry
from ..parsing.layout_loader import find_layout_file, load_layout_file
from ..parsing.loaders import load_yaml
from ..parsing.yaml_source import SourceTrackedDict, get_field_location
from .query import QuerySet, _match
from ..models.base import get_non_overridable_fields, NON_OVERRIDABLE_KEY

logger = logging.getLogger(__name__)


def _flatten(
    data: dict[str, Any],
    prefix: str = "",
    preserve_keys: set[str] | None = None,
) -> dict[str, Any]:
    """把嵌套 dict 扁平化，例如 {'physical': {'height_u': 2}} -> {'physical.height_u': 2}。

    Args:
        preserve_keys: 这些键保持嵌套，不扁平化（如 'assets', 'tags'）。
    """
    out: dict[str, Any] = {}
    preserve = preserve_keys or set()
    for key, value in data.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and key not in preserve:
            out.update(_flatten(value, full, preserve))
        else:
            out[full] = value
    return out


# ---------------------------------------------------------------------------
# 跨项目引用解析
# ---------------------------------------------------------------------------

class PathResolver:
    """解析 Instance 引用路径（ADR-009 §5）。

    支持：
    - 当前项目内的 Instance ID
    - $PROJECT_ROOT 变量跨仓库引用
    - 嵌套项目的父/子 Instance 查找
    - piki.toml [external] 注册的外部项目路径
    """

    def __init__(
        self,
        root: Path,
        parent: "Registry | None" = None,
        externals: dict[str, Path] | None = None,
    ):
        self.root = root
        self.parent = parent
        self.externals = externals or {}

    def resolve_instance(self, instance_ref: str) -> ResolvedInstance | None:
        """解析 Instance 引用。

        解析顺序：
        1. 简单 ID：委托给 Registry.find_instance（项目树查找）
        2. $PROJECT_ROOT 前缀：替换为项目根路径后尝试加载
        3. 外部项目别名：prefix/instance_id 格式
        """
        # 1. 简单 ID（无路径分隔符，无变量前缀）
        if "/" not in instance_ref and not instance_ref.startswith("$"):
            return None  # 由 Registry.find_instance 处理

        # 2. $PROJECT_ROOT 变量展开
        if instance_ref.startswith("$PROJECT_ROOT/"):
            rel_path = instance_ref[len("$PROJECT_ROOT/"):]
            target = self.root / rel_path
            if target.exists():
                return self._load_instance_file(target)
            return None

        # 3. 外部项目别名: alias/instance_id
        for alias, ext_path in self.externals.items():
            if instance_ref.startswith(alias + "/"):
                sub_path = instance_ref[len(alias) + 1:]
                # 尝试 instances/sub_path.yaml
                target = ext_path / "instances" / (sub_path + ".yaml")
                if target.exists():
                    return self._load_instance_file(target)
                # 也尝试直接路径
                target2 = ext_path / sub_path
                if target2.exists() and target2.suffix in (".yaml", ".yml"):
                    return self._load_instance_file(target2)
            # 整个 ref 就是一个外部别名（指向外部项目根）
            if instance_ref == alias:
                return None  # 需要加载整个外部项目

        return None

    def _load_instance_file(self, path: Path) -> ResolvedInstance | None:
        """从单个 YAML 文件加载 Instance 为未解析状态。"""
        if not path.exists():
            return None
        from ..parsing.loaders import load_yaml
        data = load_yaml(path)
        inst_id = data.get("id")
        if not inst_id:
            return None
        # 返回未解析的 ResolvedInstance（调用方应由 Registry._resolve 解析）
        return None  # 跨仓库 Instance 需调用方 Registry 处理


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class Registry:
    """运行时中央注册表。"""

    def __init__(self) -> None:
        self._families: dict[str, type[BaseModel]] = {}
        self._models: dict[str, Model] = {}
        self._instances: dict[str, ResolvedInstance] = {}
        # Layout（每个项目一个）
        self._layout: Layout | None = None
        # 按集合名分组，集合名 = 目录名（如 instances, racks, devices）
        self._collections: dict[str, dict[str, ResolvedInstance]] = {}
        # 诊断收集器
        self._diagnostics: list[Diagnostic] = []
        # 嵌套项目支持
        self._parent: Registry | None = None
        self._children: dict[str, Registry] = {}
        # 项目标签约束（piki.toml 中定义的允许 Tag 键）
        self._allowed_tags: set[str] = set()
        # 项目根
        self._root: Path | None = None
        # 项目名称（用于 FQID）
        self._project_name: str = ""

    # ------------------------------------------------------------------
    # Family / Model
    # ------------------------------------------------------------------

    def add_family(self, name: str, cls: type[BaseModel]) -> None:
        self._families[name] = cls

    def get_family(self, name: str) -> type[BaseModel] | None:
        return self._families.get(name)

    def add_model(self, model: Model) -> None:
        self._models[model.id] = model

    def get_model(self, model_id: str) -> Model | None:
        return self._models.get(model_id)

    # ------------------------------------------------------------------
    # 嵌套项目
    # ------------------------------------------------------------------

    def set_parent(self, parent: Registry) -> None:
        """设置父项目的 Registry，用于 Instance 继承查找。"""
        self._parent = parent

    @property
    def parent(self) -> Registry | None:
        return self._parent

    def add_child(self, name: str, child: Registry) -> None:
        """注册子项目 Registry。"""
        self._children[name] = child
        child.set_parent(self)

    @property
    def children(self) -> dict[str, Registry]:
        return dict(self._children)

    def set_project_name(self, name: str) -> None:
        """设置项目名称（用于生成全限定 ID）。"""
        self._project_name = name

    def fqid(self, instance_id: str) -> str:
        """返回 Instance 的全限定 ID（ADR-009 §6.2）。

        格式: parent_name/child_name/.../instance_id
        """
        parts: list[str] = []
        parent_prefix = self._build_parent_prefix()
        if parent_prefix:
            parts.append(parent_prefix)
        if self._project_name:
            parts.append(self._project_name)
        parts.append(instance_id)
        return "/".join(parts)

    def _build_parent_prefix(self) -> str:
        """构建祖先项目前缀（不含当前项目名）。"""
        if self._parent is None:
            return ""
        parts: list[str] = []
        grand_prefix = self._parent._build_parent_prefix()
        if grand_prefix:
            parts.append(grand_prefix)
        if self._parent._project_name:
            parts.append(self._parent._project_name)
        return "/".join(parts)

    def all_instances_with_fqid(self) -> dict[str, ResolvedInstance]:
        """返回所有 Instance 的全限定 ID 映射。"""
        result: dict[str, ResolvedInstance] = {}
        if self._parent:
            result.update(self._parent.all_instances_with_fqid())
        for iid, inst in self._instances.items():
            result[self.fqid(iid)] = inst
        return result

    def find_instance(self, instance_id: str) -> ResolvedInstance | None:
        """在项目树中查找 Instance。

        搜索顺序：当前项目 → 父项目 → 根项目。
        """
        if instance_id in self._instances:
            return self._instances[instance_id]
        if self._parent:
            return self._parent.find_instance(instance_id)
        return None

    def find_model(self, model_id: str) -> Model | None:
        """在项目树中查找 Model。"""
        if model_id in self._models:
            return self._models[model_id]
        if self._parent:
            return self._parent.find_model(model_id)
        return None

    # ------------------------------------------------------------------
    # Tag 机制
    # ------------------------------------------------------------------

    def set_allowed_tags(self, tags: list[str]) -> None:
        """设置项目允许的 Tag 键（从 piki.toml 读取）。"""
        self._allowed_tags = set(tags)

    @property
    def allowed_tags(self) -> set[str]:
        return set(self._allowed_tags)
    def register_external(self, alias: str, path: Path) -> None:
        """注册外部项目路径（ADR-009 §5.3）。"""
        if not hasattr(self, "_externals"):
            self._externals: dict[str, Path] = {}
        self._externals[alias] = Path(path)

    @property
    def externals(self) -> dict[str, Path]:
        if not hasattr(self, "_externals"):
            self._externals = {}
        return dict(self._externals)

    def _make_path_resolver(self, root: Path, externals: dict[str, Path] | None = None) -> "PathResolver":
        """创建 PathResolver 实例。"""
        merged = dict(self.externals)
        if externals:
            merged.update(externals)
        return PathResolver(root=root, parent=self, externals=merged)


    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def load_layout(self, project_root: Path) -> Layout | None:
        """加载项目的 Layout 文件。

        每个项目只有一个 Layout 文件（ADR-008）。
        """
        path = find_layout_file(project_root)
        if path is None:
            return None
        self._layout = load_layout_file(path, name=project_root.name)
        return self._layout

    @property
    def layout(self) -> Layout | None:
        return self._layout

    def get_layout_entry(self, instance_id: str) -> LayoutEntry | None:
        """获取指定 Instance 的 Layout 条目。"""
        if self._layout:
            entry = self._layout.get(instance_id)
            if entry is not None:
                return entry
        # 向上查找
        if self._parent:
            return self._parent.get_layout_entry(instance_id)
        return None

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def diagnostics(self) -> list[Diagnostic]:
        return list(self._diagnostics)

    def clear_diagnostics(self) -> None:
        self._diagnostics.clear()

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------

    def load_library(self, library_dir: Path) -> None:
        """扫描 library/ 下的型号库 YAML。"""
        if not library_dir.exists():
            return
        for path in library_dir.rglob("*.yaml"):
            data = load_yaml(path)
            model_id = data.get("model")
            family = data.get("family")
            if not model_id or not family:
                logger.warning("Skipping model without 'model' or 'family': %s", path)
                continue
            model_data = {k: v for k, v in data.items()
                          if k not in ("model", "family")}
            self.add_model(Model(id=model_id, family=family,
                                 data=model_data, source=path))

    def load_collection(self, collection_dir: Path) -> str:
        """扫描一个数据目录，加载所有 Instance。返回集合名。"""
        collection_name = collection_dir.name
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
            resolved = self._resolve(instance, data)
            if resolved is None:
                flat = _flatten(instance.data)
                flat["id"] = instance.id
                resolved = ResolvedInstance(
                    id=instance.id,
                    family="_invalid",
                    raw=flat,
                    _resolved=flat,
                    source=instance.source,
                )
            loaded[resolved.id] = resolved
            self._instances[resolved.id] = resolved

        self._collections[collection_name] = loaded
        return collection_name

    # ------------------------------------------------------------------
    # 核心：解析合并 Instance + Model + Layout
    # ------------------------------------------------------------------

    def _resolve(
        self,
        instance: Instance,
        source_data: dict[str, Any] | None = None,
    ) -> ResolvedInstance | None:
        """合并 Model 默认值 + Instance 覆盖值 + Layout 部署值，并用 Family 校验。

        解析顺序（ADR-008 定义）：
        1. 加载 Instance → 获取设备属性（model, 覆盖参数）
        2. 加载 Model  → 获取默认值
        3. 加载 Layout  → 获取部署决策
        4. 合并：resolved = Model.defaults + Instance.overrides + Layout

        Args:
            instance: 原始实例数据
            source_data: 带源码追踪的 YAML 数据（用于定位错误行号）
        """
        family_name = instance.family
        model_id = instance.model

        # 0. 确定 Family
        if family_name is None:
            if model_id is not None:
                model = self.find_model(model_id)
                if model is not None:
                    family_name = model.family
            # 如果还找不到，直接调用 get_family 看看
            if family_name is None and instance.data.get("family"):
                family_name = instance.data["family"]

        if family_name is None:
            logger.warning("Instance %s has no family or model", instance.id)
            return None

        family_cls = self.get_family(family_name)
        if family_cls is None:
            if self._parent:
                family_cls = self._parent.get_family(family_name)
            if family_cls is None:
                logger.warning("Unknown family %s for instance %s",
                             family_name, instance.id)
                return None

        # 1. 获取 Model 默认值
        model_defaults: dict[str, Any] = {}
        if model_id:
            model = self.find_model(model_id)
            if model is not None:
                model_defaults = dict(model.data)

        # 2. Instance 覆盖值
        overrides = dict(instance.data)
        overrides.pop("model", None)
        overrides.pop("family", None)

        # 2a. 覆盖白名单：不可覆盖字段被忽略（带诊断，ADR-008 §1.2）
        non_overridable = get_non_overridable_fields(family_cls)
        if non_overridable:
            from ..models.diagnostic import Location
            for field_name in sorted(non_overridable):
                if field_name in overrides:
                    self._diagnostics.append(
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
                            source="piki.schema",
                        )
                    )
                    del overrides[field_name]

        # 3. 合并 Model + Instance（用于 Schema 校验的基值）
        merged = _flatten({**model_defaults, **overrides},
                          preserve_keys={"assets", "tags"})
        merged["id"] = instance.id

        # 4. Schema 校验
        try:
            validated = family_cls.model_validate(merged)
        except ValidationError as exc:
            location = self._build_error_location(
                instance.source, source_data, exc)
            diagnostic = Diagnostic.from_validation_error(
                exc=exc,
                location=location,
                code="SCHEMA-001",
                source="piki.schema",
            )
            if source_data is not None:
                related = self._build_related_info(
                    instance.source, source_data, exc)
                if related:
                    diagnostic = Diagnostic(
                        severity=Severity.ERROR,
                        message=str(exc),
                        location=location,
                        code="SCHEMA-001",
                        source="piki.schema",
                        related_information=related,
                    )
            self._diagnostics.append(diagnostic)

            flat = _flatten(instance.data)
            flat["id"] = instance.id
            return ResolvedInstance(
                id=instance.id,
                family="_invalid",
                raw=flat,
                _resolved=flat,
                source=instance.source,
                _validation_error=str(exc),
            )

        resolved_dict = _flatten(validated.model_dump(),
                                 preserve_keys={"assets", "tags"})

        # 5. Layout 合并（后于 Schema 校验，因为 Layout 字段不参与 Schema）
        layout_entry = self.get_layout_entry(instance.id)
        if layout_entry is not None:
            layout_flat = layout_entry.to_flat()
            resolved_dict.update(layout_flat)

        return ResolvedInstance(
            id=instance.id,
            family=family_name,
            raw=overrides,
            _resolved=resolved_dict,
            source=instance.source,
        )

    # ------------------------------------------------------------------
    # 错误定位辅助
    # ------------------------------------------------------------------

    def _build_error_location(
        self,
        path: Path,
        source_data: dict[str, Any] | None,
        exc: ValidationError,
    ) -> Location:
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

    def _build_related_info(
        self,
        path: Path,
        source_data: SourceTrackedDict,
        exc: ValidationError,
    ) -> list:
        from ..models.diagnostic import RelatedInformation

        related: list[RelatedInformation] = []
        for error in exc.errors():
            loc_parts = error.get("loc", ())
            if not loc_parts:
                continue
            field_path = ".".join(str(p) for p in loc_parts)
            mark = get_field_location(source_data, field_path, path)
            if mark is not None:
                msg = error.get("msg", "校验失败")
                loc = Location(
                    uri=path.as_uri(),
                    range=Range.point(mark.line, mark.column),
                )
                related.append(RelatedInformation(
                    location=loc, message=f"{field_path}: {msg}"))
        return related

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def list_collections(self) -> list[str]:
        return list(self._collections.keys())

    def all_instances(self) -> dict[str, ResolvedInstance]:
        """返回当前项目的所有 Instance（不包括父项目）。"""
        return dict(self._instances)

    def all_instances_tree(self) -> dict[str, ResolvedInstance]:
        """返回项目树中所有 Instance（包括父项目，子覆盖父同名）。"""
        result: dict[str, ResolvedInstance] = {}
        if self._parent:
            result.update(self._parent.all_instances_tree())
        result.update(self._instances)
        return result

    def query(self, collection: str, **filters: Any) -> QuerySet:
        """查询某个集合，支持增强过滤语法。

        支持 Django-style 双下划线后缀：
          __eq, __ne, __gt, __gte, __lt, __lte, __in, __contains,
          __startswith, __endswith

        支持 Tag 过滤：
          tags__discipline=hvac  → 自动按 tags.discipline 过滤
        """
        items = list(self._collections.get(collection, {}).values())
        qs = QuerySet(items)
        if filters:
            qs = qs.filter(**filters)
        return qs
