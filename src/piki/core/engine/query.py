"""Query：增强查询语法，对齐 SQL 核心能力。

支持操作符（Django-style 双下划线后缀）：
  - __eq       等值（默认）
  - __ne       不等
  - __gt       大于
  - __gte      大于等于
  - __lt       小于
  - __lte      小于等于
  - __in       在列表中
  - __contains 包含（子串或元素）
  - __startswith 前缀匹配
  - __endswith   后缀匹配

支持链式操作：
  - .order_by("field", "-field2")
  - .limit(n)
  - .fields(["id", "name"])
  - .first()
  - .count()
  - .group_by("field")
  - .join(other_collection, local_field, foreign_field="id")

用法：
    ctx.query("devices", rack_id="RACK-A01")
    ctx.query("devices", tdp_w__gt=300)
    ctx.query("devices", rack_id__in=["A01", "A02"]).order_by("position_u")
    ctx.query("devices").group_by("rack_id")
"""

from __future__ import annotations

from typing import Any, Callable


class QuerySet:
    """惰性求值的查询结果集。"""

    def __init__(self, items: list[Any]) -> None:
        self._items = list(items)
        self._order: list[tuple[str, bool]] = []  # (field, reverse)
        self._slice: tuple[int, int] | None = None
        self._project: list[str] | None = None

    # ---------- 过滤（链式起点） ----------

    def filter(self, **kwargs: Any) -> "QuerySet":
        """追加过滤条件（AND）。"""
        filtered = [item for item in self._items if _match(item, kwargs)]
        return QuerySet(filtered)

    def exclude(self, **kwargs: Any) -> "QuerySet":
        """排除匹配项。"""
        filtered = [item for item in self._items if not _match(item, kwargs)]
        return QuerySet(filtered)

    # ---------- 链式操作 ----------

    def order_by(self, *fields: str) -> "QuerySet":
        """排序："-field" 表示降序。"""
        qs = self._clone()
        qs._order = []
        for f in fields:
            if f.startswith("-"):
                qs._order.append((f[1:], True))
            else:
                qs._order.append((f, False))
        return qs

    def limit(self, n: int) -> "QuerySet":
        """限制返回数量。"""
        qs = self._clone()
        qs._slice = (0, n)
        return qs

    def fields(self, *names: str) -> "QuerySet":
        """投影：只保留指定字段。"""
        qs = self._clone()
        qs._project = list(names)
        return qs

    # ---------- 终结操作 ----------

    def __iter__(self):
        return iter(self._evaluate())

    def __len__(self) -> int:
        return len(self._evaluate())

    def __getitem__(self, index: int | slice) -> Any | list[Any]:
        evaluated = self._evaluate()
        return evaluated[index]

    def first(self) -> Any | None:
        evaluated = self._evaluate()
        return evaluated[0] if evaluated else None

    def count(self) -> int:
        return len(self._evaluate())

    def list(self) -> list[Any]:
        return list(self._evaluate())

    def values(self, *names: str) -> list[dict[str, Any]]:
        """返回 dict 列表。"""
        evaluated = self._evaluate()
        if not names:
            names = self._project or []
        return [_project_dict(item, names) for item in evaluated]

    def group_by(self, field: str) -> dict[Any, list[Any]]:
        """按字段分组。"""
        from collections import defaultdict

        groups: dict[Any, list[Any]] = defaultdict(list)
        for item in self._evaluate():
            groups[_get_value(item, field)].append(item)
        return dict(groups)

    def aggregate(self, **aggregations: Callable[[list[Any]], Any]) -> dict[str, Any]:
        """聚合计算。

        示例：
            ctx.query("devices").aggregate(
                total_power=lambda items: sum(d.tdp_w for d in items),
                count=len,
            )
        """
        items = self._evaluate()
        return {name: fn(items) for name, fn in aggregations.items()}

    def join(
        self,
        other_items: list[Any],
        local_field: str,
        foreign_field: str = "id",
    ) -> "QuerySet":
        """简单内连接。

        示例：
            devices = ctx.query("devices")
            racks = ctx.query("racks")
            joined = devices.join(racks, "rack_id")
            # joined 中每个 item 有额外属性 _join_rack
        """
        foreign_map = {_get_value(o, foreign_field): o for o in other_items}
        joined = []
        for item in self._evaluate():
            key = _get_value(item, local_field)
            if key in foreign_map:
                # 用动态属性附加关联对象
                item._join_related = foreign_map[key]  # type: ignore[attr-defined]
                joined.append(item)
        return QuerySet(joined)

    # ---------- 内部 ----------

    def _clone(self) -> "QuerySet":
        qs = QuerySet(self._items)
        qs._order = list(self._order)
        qs._slice = self._slice
        qs._project = self._project
        return qs

    def _evaluate(self) -> list[Any]:
        items = list(self._items)
        # 排序
        for field, reverse in reversed(self._order):
            items.sort(key=lambda item: _get_value(item, field), reverse=reverse)
        # 切片
        if self._slice:
            start, end = self._slice
            items = items[start:end]
        # 投影
        if self._project:
            items = [_project(item, self._project) for item in items]
        return items


# ---------- 操作符实现 ----------

_OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a is not None and b is not None and a > b,
    "gte": lambda a, b: a is not None and b is not None and a >= b,
    "lt": lambda a, b: a is not None and b is not None and a < b,
    "lte": lambda a, b: a is not None and b is not None and a <= b,
    "in": lambda a, b: a in b if isinstance(b, (list, tuple, set, dict)) else False,
    "contains": lambda a, b: b in a if a is not None else False,
    "startswith": lambda a, b: str(a).startswith(str(b)) if a is not None else False,
    "endswith": lambda a, b: str(a).endswith(str(b)) if a is not None else False,
}


def _match(item: Any, filters: dict[str, Any]) -> bool:
    """判断 item 是否满足所有过滤条件。"""
    for key, expected in filters.items():
        # 支持 tags__ 前缀过滤（ADR-009）: tags__discipline=hvac
        # tags__ 后面跟的如果是已知操作符（如 tags__contains），
        # 则走正常操作符路径，否则作为标签键查找
        if key.startswith("tags__"):
            tag_key = key[6:]  # 去掉 "tags__" 前缀
            if tag_key not in _OPERATORS:
                actual_tags = _get_value(item, "tags")
                if isinstance(actual_tags, dict):
                    tag_value = actual_tags.get(tag_key)
                else:
                    # ResolvedInstance 的 tags 也可在 resolved.tags 中
                    tag_value = _get_value(item, f"resolved.tags.{tag_key}")
                if tag_value != expected:
                    return False
                continue
            # fall through to normal operator handling

        # 解析 field__operator
        if "__" in key:
            parts = key.rsplit("__", 1)
            field, op = parts[0], parts[1]
        else:
            field, op = key, "eq"

        actual = _get_value(item, field)
        op_fn = _OPERATORS.get(op)
        if op_fn is None:
            raise ValueError(f"Unknown query operator: {op!r} in {key!r}")
        if not op_fn(actual, expected):
            return False
    return True


def _get_value(item: Any, field: str) -> Any:
    """从 item 中提取字段值，支持嵌套属性（如 resolved.height_u）。"""
    # 1. 尝试属性访问（含 @property）
    if hasattr(item, field):
        return getattr(item, field)
    # 2. 尝试 dict 访问
    if isinstance(item, dict):
        return item.get(field)
    # 3. 尝试嵌套属性（a.b.c）
    parts = field.split(".")
    obj = item
    for part in parts:
        if obj is None:
            return None
        if isinstance(obj, dict):
            obj = obj.get(part)
        elif hasattr(obj, part):
            obj = getattr(obj, part)
        else:
            return None
    return obj


def _project(item: Any, names: list[str]) -> Any:
    """将 item 投影为只含指定字段的 SimpleNamespace。"""
    from types import SimpleNamespace

    return SimpleNamespace(**{name: _get_value(item, name) for name in names})


def _project_dict(item: Any, names: list[str]) -> dict[str, Any]:
    return {name: _get_value(item, name) for name in names}
