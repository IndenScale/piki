"""Context：规则运行时数据访问。

支持：
- 集合查询（query）
- Layout 查询（layout）
- Tag 过滤（tags__discipline=hvac）
- 跨项目 Instance 查找
"""

from __future__ import annotations

from typing import Any

from ..models.diagnostic import Location, RelatedInformation
from ..models.layout import Layout, LayoutEntry
from .query import QuerySet
from .registry import Registry


class Context:
    """规则函数通过 Context 访问数据和配置。"""

    def __init__(self, registry: Registry, config: dict[str, Any]) -> None:
        self._registry = registry
        self._config = config
        self._current_file: str = ""
        self._files_filter: set[str] | None = None
        self._related_info: list[RelatedInformation] = []
        self._suggestion: str = ""

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    # ------------------------------------------------------------------
    # 集合查询
    # ------------------------------------------------------------------

    def query(self, collection: str, **filters: Any) -> QuerySet:
        """查询某个集合，支持增强过滤语法和 Tag 过滤。

        支持 Django-style 双下划线后缀：
          __eq, __ne, __gt, __gte, __lt, __lte, __in, __contains,
          __startswith, __endswith

        支持 Tag 过滤：
          tags__discipline=hvac  → 自动查找 Instance 的 tags 字段
        """
        qs = self._registry.query(collection, **filters)
        if self._files_filter is not None:
            allowed = self._files_filter
            items = [item for item in qs if str(getattr(item, "source", "")) in allowed]
            qs = QuerySet(items)
        return qs

    def instances(self) -> QuerySet:
        """返回所有 Instance（项目树范围）。

        返回 QuerySet，支持链式操作。
        """
        items = list(self._registry.all_instances_tree().values())
        qs = QuerySet(items)
        if self._files_filter is not None:
            allowed = self._files_filter
            items = [item for item in qs if str(getattr(item, "source", "")) in allowed]
            qs = QuerySet(items)
        return qs

    # ------------------------------------------------------------------
    # Layout 查询（ADR-008）
    # ------------------------------------------------------------------

    @property
    def layout(self) -> Layout | None:
        """获取当前项目的 Layout。"""
        return self._registry.layout

    def layout_entry(self, instance_id: str) -> LayoutEntry | None:
        """获取指定 Instance 的 Layout 条目。"""
        return self._registry.get_layout_entry(instance_id)

    # ------------------------------------------------------------------
    # Instance 查找（跨项目，ADR-009）
    # ------------------------------------------------------------------

    def find_instance(self, instance_id: str):
        """在项目树中查找 Instance。"""
        return self._registry.find_instance(instance_id)

    # ------------------------------------------------------------------
    # 文件过滤
    # ------------------------------------------------------------------

    def set_files_filter(self, files: list[str] | None) -> None:
        if files:
            self._files_filter = set(files)
        else:
            self._files_filter = None

    def set_current_file(self, path: str) -> None:
        self._current_file = path

    def clear_current_file(self) -> None:
        self._current_file = ""
        self._related_info.clear()
        self._suggestion = ""

    # ------------------------------------------------------------------
    # 关联信息与建议
    # ------------------------------------------------------------------

    def add_related_info(self, location: Location, message: str) -> None:
        self._related_info.append(RelatedInformation(location=location, message=message))

    def set_suggestion(self, suggestion: str) -> None:
        self._suggestion = suggestion

    def pop_related_info(self) -> list[RelatedInformation]:
        info = list(self._related_info)
        self._related_info.clear()
        return info

    def pop_suggestion(self) -> str:
        suggestion = self._suggestion
        self._suggestion = ""
        return suggestion
