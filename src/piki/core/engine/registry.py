"""Registry：Family / Model / Instance 注册和解析。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from ..models.base import Instance, Model, ResolvedInstance, _unflatten
from ..models.diagnostic import Diagnostic, Location, Range, Severity
from ..parsing.loaders import load_yaml
from ..parsing.yaml_source import SourceTrackedDict, get_field_location
from .query import QuerySet, _match

logger = logging.getLogger(__name__)


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """把嵌套 dict 扁平化，例如 {'physical': {'height_u': 2}} -> {'physical.height_u': 2}。"""
    out: dict[str, Any] = {}
    for key, value in data.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(_flatten(value, full))
        else:
            out[full] = value
    return out


class Registry:
    """运行时中央注册表。"""

    def __init__(self) -> None:
        self._families: dict[str, type[BaseModel]] = {}
        self._models: dict[str, Model] = {}
        self._instances: dict[str, ResolvedInstance] = {}
        # 按集合名分组，集合名 = 目录名（如 racks, devices）
        self._collections: dict[str, dict[str, ResolvedInstance]] = {}
        # 诊断收集器：Schema 校验失败等诊断信息
        self._diagnostics: list[Diagnostic] = []

    def add_family(self, name: str, cls: type[BaseModel]) -> None:
        self._families[name] = cls

    def get_family(self, name: str) -> type[BaseModel] | None:
        return self._families.get(name)

    def add_model(self, model: Model) -> None:
        self._models[model.id] = model

    def get_model(self, model_id: str) -> Model | None:
        return self._models.get(model_id)

    @property
    def diagnostics(self) -> list[Diagnostic]:
        """获取收集到的所有诊断信息。"""
        return list(self._diagnostics)

    def clear_diagnostics(self) -> None:
        """清空诊断收集器。"""
        self._diagnostics.clear()

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
            # 去掉 metadata 字段，其余作为型号数据
            model_data = {k: v for k, v in data.items() if k not in ("model", "family")}
            self.add_model(Model(id=model_id, family=family, data=model_data, source=path))

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

            model_id = data.get("model")
            family_name = data.get("family")

            instance = Instance(
                id=inst_id,
                model=model_id,
                family=family_name,
                data={k: v for k, v in data.items() if k != "id"},
                source=path,
            )
            resolved = self._resolve(instance, data)
            if resolved is None:
                # 不应再到达这里：_resolve 现在在校验失败时直接返回 ResolvedInstance
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

    def _resolve(self, instance: Instance, source_data: dict[str, Any] | None = None) -> ResolvedInstance | None:
        """合并 Model 默认值 + Instance 覆盖值，并用 Family 校验。

        Args:
            instance: 原始实例数据
            source_data: 带源码追踪的 YAML 数据（用于定位错误行号）
        """
        family_name = instance.family
        model_id = instance.model

        # 如果没显式指定 family，尝试从 model 推导
        if not family_name and model_id:
            model = self.get_model(model_id)
            if model:
                family_name = model.family

        if not family_name:
            logger.warning(
                "Instance %s has no family and cannot infer from model: %s",
                instance.id,
                instance.source,
            )
            # 退化为无校验的纯数据
            flat = _flatten(instance.data)
            return ResolvedInstance(
                id=instance.id,
                family="",
                raw=flat,
                _resolved=flat,
                source=instance.source,
            )

        family_cls = self.get_family(family_name)
        if family_cls is None:
            logger.warning(
                "Unknown family '%s' for instance %s in %s",
                family_name,
                instance.id,
                instance.source,
            )
            flat = _flatten(instance.data)
            return ResolvedInstance(
                id=instance.id,
                family=family_name,
                raw=flat,
                _resolved=flat,
                source=instance.source,
            )

        # 合并 model 默认值
        base: dict[str, Any] = {}
        if model_id:
            model = self.get_model(model_id)
            if model:
                base = _flatten(model.data)

        overrides = _flatten(instance.data)
        merged = {**base, **overrides}
        # 确保 id 在合并数据中
        merged["id"] = instance.id

        # 用 pydantic 校验
        try:
            validated = family_cls(**_unflatten(merged))
        except ValidationError as exc:
            logger.error(
                "Validation failed for %s (%s): %s",
                instance.id,
                instance.source,
                exc,
            )
            # 构建带行号定位的 Diagnostic
            location = self._build_error_location(instance.source, source_data, exc)
            diagnostic = Diagnostic.from_validation_error(
                exc=exc,
                location=location,
                code="SCHEMA-001",
                source="piki.schema",
            )
            # 为每个错误字段添加 related_information
            if source_data is not None:
                related = self._build_related_info(instance.source, source_data, exc)
                if related:
                    # 创建新的 Diagnostic，包含 related_information
                    diagnostic = Diagnostic(
                        severity=Severity.ERROR,
                        message=str(exc),
                        location=location,
                        code="SCHEMA-001",
                        source="piki.schema",
                        related_information=related,
                    )
            self._diagnostics.append(diagnostic)

            # 返回带错误详情的 ResolvedInstance，family 标记为 _invalid
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

        resolved_dict = _flatten(validated.model_dump())
        return ResolvedInstance(
            id=instance.id,
            family=family_name,
            raw=overrides,
            _resolved=resolved_dict,
            source=instance.source,
        )

    def _build_error_location(
        self,
        path: Path,
        source_data: dict[str, Any] | None,
        exc: ValidationError,
    ) -> Location:
        """从 ValidationError 和源码数据构建 Location。"""
        # 默认定位到文件开头
        location = Location.from_path(path, line=0)

        if source_data is None or not isinstance(source_data, SourceTrackedDict):
            return location

        # 尝试从第一个错误定位到具体字段
        errors = exc.errors()
        if errors:
            first_error = errors[0]
            loc_parts = first_error.get("loc", ())
            if loc_parts:
                # 构建字段路径，如 ("total_u",) 或 ("physical", "height_u")
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
        """为 ValidationError 的每个错误字段构建 RelatedInformation。"""
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
                related.append(RelatedInformation(location=loc, message=f"{field_path}: {msg}"))
        return related

    def list_collections(self) -> list[str]:
        return list(self._collections.keys())

    def query(self, collection: str, **filters: Any) -> QuerySet:
        """查询某个集合，支持增强过滤语法。

        过滤操作符（Django-style 双下划线后缀）：
          __eq, __ne, __gt, __gte, __lt, __lte, __in, __contains,
          __startswith, __endswith

        链式操作（返回 QuerySet）：
          .filter(**kwargs)  .exclude(**kwargs)
          .order_by("field", "-field2")
          .limit(n)  .fields("id", "name")

        终结操作：
          .first()  .count()  .list()  .values("id", "name")
          .group_by("field")  .aggregate(sum=lambda items: ...)
          .join(other_items, "local_field", "foreign_field")

        示例：
            ctx.query("devices", rack_id="RACK-A01")
            ctx.query("devices", tdp_w__gt=300)
            ctx.query("devices", rack_id__in=["A01", "A02"]).order_by("position_u")
        """
        items = list(self._collections.get(collection, {}).values())
        qs = QuerySet(items)
        if filters:
            qs = qs.filter(**filters)
        return qs

    def all_instances(self) -> dict[str, ResolvedInstance]:
        return dict(self._instances)
