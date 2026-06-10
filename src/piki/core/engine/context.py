"""Context：规则运行时数据访问。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .query import QuerySet
from .registry import Registry


class Context:
    """规则函数通过 Context 访问数据和配置。"""

    def __init__(self, registry: Registry, config: dict[str, Any]) -> None:
        self._registry = registry
        self._config = config
        self._current_file: str = ""
        self._files_filter: set[str] | None = None

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
