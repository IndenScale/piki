"""YAML 源码定位 —— 追踪每个字段在源文件中的行号。

使用 PyYAML 的 compose() 获取 AST，从中提取每个节点的行号信息。
比自定义 Constructor 更可靠，因为 AST 节点天然携带 start_mark。

设计：
- load_yaml_with_source(path) 返回一个 SourceTrackedDict
- 每个值可以通过 _get_source(key) 获取 SourceMark（含行号、列号）
- 对于嵌套 dict，递归包装
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SourceMark:
    """YAML 节点在源文件中的位置。"""

    path: Path
    line: int  # 0-based 行号
    column: int  # 0-based 列号

    def __str__(self) -> str:
        return f"{self.path}:{self.line + 1}:{self.column + 1}"


class SourceTrackedDict(dict):
    """带源码位置追踪的 dict。"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._source_marks: dict[str, SourceMark] = {}

    def _set_source(self, key: str, mark: SourceMark) -> None:
        self._source_marks[key] = mark

    def _get_source(self, key: str) -> SourceMark | None:
        return self._source_marks.get(key)

    def _get_source_recursive(self, key_path: str) -> SourceMark | None:
        """通过点分隔路径获取源码位置，如 'physical.height_u'。"""
        parts = key_path.split(".")
        current: Any = self
        for part in parts:
            if isinstance(current, SourceTrackedDict):
                mark = current._get_source(part)
                if mark is not None and part == parts[-1]:
                    return mark
                current = current.get(part)
            elif isinstance(current, SourceTrackedList):
                try:
                    idx = int(part)
                    current = current[idx]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return None


class SourceTrackedList(list):
    """带源码位置追踪的 list。"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._source_marks: dict[int, SourceMark] = {}

    def _set_source(self, index: int, mark: SourceMark) -> None:
        self._source_marks[index] = mark

    def _get_source(self, index: int) -> SourceMark | None:
        return self._source_marks.get(index)


def _compose_to_tracked(node: yaml.Node, path: Path) -> Any:
    """将 PyYAML 的 AST 节点转换为带源码追踪的 Python 对象。"""
    SourceMark(path=path, line=node.start_mark.line, column=node.start_mark.column)

    if isinstance(node, yaml.MappingNode):
        tracked = SourceTrackedDict()
        for key_node, value_node in node.value:
            key = _compose_to_tracked(key_node, path)
            if not isinstance(key, str):
                key = str(key)
            value = _compose_to_tracked(value_node, path)
            tracked[key] = value
            tracked._set_source(
                key,
                SourceMark(
                    path=path,
                    line=value_node.start_mark.line,
                    column=value_node.start_mark.column,
                ),
            )
        return tracked

    elif isinstance(node, yaml.SequenceNode):
        tracked = SourceTrackedList()
        for i, item_node in enumerate(node.value):
            tracked.append(_compose_to_tracked(item_node, path))
            tracked._set_source(
                i,
                SourceMark(
                    path=path,
                    line=item_node.start_mark.line,
                    column=item_node.start_mark.column,
                ),
            )
        return tracked

    elif isinstance(node, yaml.ScalarNode):
        # 使用 SafeConstructor 解析标量
        from yaml.constructor import SafeConstructor

        constructor = SafeConstructor()
        return constructor.construct_scalar(node)  # type: ignore[no-any-return]

    else:
        raise ValueError(f"Unknown YAML node type: {type(node)}")


def load_yaml_with_source(path: Path) -> dict[str, Any]:
    """加载 YAML 文件，返回带源码位置追踪的 dict。

    返回的 dict 是 SourceTrackedDict，可以通过 _get_source(key) 获取每个字段的行号。
    """
    with open(path, "r", encoding="utf-8") as f:
        node = yaml.compose(f)

    if node is None:
        return SourceTrackedDict()

    if not isinstance(node, yaml.MappingNode):
        raise ValueError(f"YAML file must contain a mapping: {path}")

    result = _compose_to_tracked(node, path)
    if not isinstance(result, SourceTrackedDict):
        raise ValueError(f"YAML file must contain a mapping: {path}")
    return result


def get_field_line(data: dict[str, Any], field: str) -> int:
    """获取字段在 YAML 中的行号（0-based），如果无法获取则返回 0。"""
    if isinstance(data, SourceTrackedDict):
        mark = data._get_source(field)
        if mark is not None:
            return mark.line
        # 尝试递归查找
        mark = data._get_source_recursive(field)
        if mark is not None:
            return mark.line
    return 0


def get_field_location(data: dict[str, Any], field: str, path: Path) -> SourceMark | None:
    """获取字段在 YAML 中的完整位置信息。"""
    if isinstance(data, SourceTrackedDict):
        mark = data._get_source(field)
        if mark is not None:
            return mark
        mark = data._get_source_recursive(field)
        if mark is not None:
            return mark
    return None
