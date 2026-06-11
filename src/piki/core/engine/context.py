"""Context：规则运行时数据访问。"""

from __future__ import annotations

from typing import Any

from ..models.diagnostic import Location, RelatedInformation
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

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    def query(self, collection: str, **filters: Any) -> QuerySet:
        qs = self._registry.query(collection, **filters)
        if self._files_filter is not None:
            # _files_filter 已在 Project.run_check 中解析为绝对路径
            allowed = self._files_filter
            items = [
                item for item in qs
                if str(getattr(item, "source", "")) in allowed
            ]
            qs = QuerySet(items)
        return qs

    def set_files_filter(self, files: list[str] | None) -> None:
        """设置文件过滤列表，只检查指定文件相关的实例。"""
        if files:
            self._files_filter = set(files)
        else:
            self._files_filter = None

    def set_current_file(self, path: str) -> None:
        """设置当前正在检查的文件路径，用于报告定位。"""
        self._current_file = path

    def clear_current_file(self) -> None:
        """清除当前文件路径。"""
        self._current_file = ""
        self._related_info.clear()
        self._suggestion = ""

    def add_related_info(self, location: Location, message: str) -> None:
        """添加关联诊断信息。

        规则函数可以在 assert 之前调用此方法，将关联信息附加到诊断报告中。
        例如："错误发生在这里，但原因是那里的那个值"。
        """
        self._related_info.append(RelatedInformation(location=location, message=message))

    def set_suggestion(self, suggestion: str) -> None:
        """设置修复建议。

        规则函数可以在 assert 之前调用此方法，为用户提供修复指导。
        """
        self._suggestion = suggestion

    def pop_related_info(self) -> list[RelatedInformation]:
        """取出并清空当前累积的关联信息（供 Checker 调用）。"""
        info = list(self._related_info)
        self._related_info.clear()
        return info

    def pop_suggestion(self) -> str:
        """取出并清空当前修复建议（供 Checker 调用）。"""
        suggestion = self._suggestion
        self._suggestion = ""
        return suggestion
