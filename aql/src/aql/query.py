"""QuerySet: lazy, chainable query DSL with Django-style operators.

Operators (double-underscore suffix):
  - __eq         equality (default)
  - __ne         not equal
  - __gt         greater than
  - __gte        greater than or equal
  - __lt         less than
  - __lte        less than or equal
  - __in         in list/tuple/set/dict
  - __contains   substring or element containment
  - __startswith prefix match
  - __endswith   suffix match

Chainable operations:
  - .filter(**kwargs)
  - .exclude(**kwargs)
  - .order_by("field", "-field2")
  - .limit(n)
  - .fields("id", "name")

Terminal operations:
  - .first()
  - .count()
  - .list()
  - .values()
  - .group_by("field")
  - .aggregate(**fn)
  - .join(other_items, local_field, foreign_field="id")

Extensibility:
  - key_resolver: callable(item, key) -> value, for custom key resolution
    (e.g. tags__discipline → item.tags["discipline"])
  - nested_field_prefixes: set of field prefixes treated as nested attr paths
    (e.g. {"catalog", "resolved"} → catalog__lifecycle → catalog.lifecycle)
"""

from __future__ import annotations

from typing import Any, Callable

# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

_OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a is not None and b is not None and a > b,
    "gte": lambda a, b: a is not None and b is not None and a >= b,
    "lt": lambda a, b: a is not None and b is not None and a < b,
    "lte": lambda a, b: a is not None and b is not None and a <= b,
    "in": lambda a, b: (
        any(x in b for x in a)
        if isinstance(a, (list, tuple, set)) and isinstance(b, (list, tuple, set, dict))
        else a in b
        if isinstance(b, (list, tuple, set, dict))
        else False
    ),
    "contains": lambda a, b: b in a if a is not None else False,
    "startswith": lambda a, b: str(a).startswith(str(b)) if a is not None else False,
    "endswith": lambda a, b: str(a).endswith(str(b)) if a is not None else False,
}


# ---------------------------------------------------------------------------
# QuerySet
# ---------------------------------------------------------------------------


class QuerySet:
    """Lazy-evaluated query result set over an iterable of items.

    Parameters
    ----------
    items:
        The underlying collection (list of dicts, objects, etc.).
    key_resolver:
        Optional callable ``(item, key) -> value``.  When set, it is tried
        *before* the built-in attribute/dict/nested-attr resolution.  Useful
        for domain-specific key mappings (e.g. ``tags__discipline``).
    nested_field_prefixes:
        Field prefixes that should be treated as nested attribute paths.
        For example ``{"catalog"}`` causes ``catalog__lifecycle`` to be
        resolved as ``catalog.lifecycle`` rather than ``catalog`` with
        operator ``lifecycle``.
    """

    def __init__(
        self,
        items: list[Any],
        key_resolver: Callable[[Any, str], Any] | None = None,
        nested_field_prefixes: set[str] | None = None,
        unresolved_sentinel: Any = None,
    ) -> None:
        self._items = list(items)
        self._key_resolver = key_resolver
        self._nested_field_prefixes = nested_field_prefixes or set()
        self._unresolved_sentinel = (
            unresolved_sentinel if unresolved_sentinel is not None else _KEY_UNRESOLVED
        )
        self._order: list[tuple[str, bool]] = []  # (field, reverse)
        self._slice: tuple[int, int] | None = None
        self._project: list[str] | None = None

    # ---------- Filtering (chain start) ----------

    def filter(self, **kwargs: Any) -> "QuerySet":
        """Add filter conditions (AND)."""
        filtered = [item for item in self._items if self._match(item, kwargs)]
        return self._clone_with(filtered)

    def exclude(self, **kwargs: Any) -> "QuerySet":
        """Exclude matching items."""
        filtered = [item for item in self._items if not self._match(item, kwargs)]
        return self._clone_with(filtered)

    # ---------- Chainable ----------

    def order_by(self, *fields: str) -> "QuerySet":
        """Sort; ``"-field"`` means descending."""
        qs = self._clone()
        qs._order = []
        for f in fields:
            if f.startswith("-"):
                qs._order.append((f[1:], True))
            else:
                qs._order.append((f, False))
        return qs

    def limit(self, n: int) -> "QuerySet":
        """Limit result count."""
        qs = self._clone()
        qs._slice = (0, n)
        return qs

    def fields(self, *names: str) -> "QuerySet":
        """Project only named fields."""
        qs = self._clone()
        qs._project = list(names)
        return qs

    # ---------- Terminal ----------

    def __iter__(self):
        return iter(self._evaluate())

    def __len__(self) -> int:
        return len(self._evaluate())

    def __getitem__(self, index: int | slice) -> Any | list[Any]:
        return self._evaluate()[index]

    def first(self) -> Any | None:
        evaluated = self._evaluate()
        return evaluated[0] if evaluated else None

    def count(self) -> int:
        return len(self._evaluate())

    def list(self) -> list[Any]:
        return list(self._evaluate())

    def values(self, *names: str) -> list[dict[str, Any]]:
        """Return list of dicts."""
        evaluated = self._evaluate()
        if not names:
            names = self._project or []
        return [self._project_dict(item, names) for item in evaluated]

    def group_by(self, field: str) -> dict[Any, list[Any]]:
        """Group items by field value."""
        from collections import defaultdict

        groups: dict[Any, list[Any]] = defaultdict(list)
        for item in self._evaluate():
            groups[self._get_value(item, field)].append(item)
        return dict(groups)

    def aggregate(self, **aggregations: Callable[[list[Any]], Any]) -> dict[str, Any]:
        """Run aggregation functions over the result set.

        Example::

            qs.aggregate(
                total=lambda items: sum(i.age for i in items),
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
        """Simple inner join.

        Attaches the matched foreign item as ``_join_related`` on each result.
        """
        foreign_map = {self._get_value(o, foreign_field): o for o in other_items}
        joined = []
        for item in self._evaluate():
            key = self._get_value(item, local_field)
            if key in foreign_map:
                item._join_related = foreign_map[key]  # type: ignore[attr-defined]
                joined.append(item)
        return QuerySet(joined)

    # ---------- Internal ----------

    def _clone(self) -> "QuerySet":
        qs = QuerySet(
            self._items,
            key_resolver=self._key_resolver,
            nested_field_prefixes=self._nested_field_prefixes,
        )
        qs._order = list(self._order)
        qs._slice = self._slice
        qs._project = self._project
        return qs

    def _clone_with(self, items: list[Any]) -> "QuerySet":
        qs = QuerySet(
            items,
            key_resolver=self._key_resolver,
            nested_field_prefixes=self._nested_field_prefixes,
        )
        qs._order = list(self._order)
        qs._slice = self._slice
        qs._project = self._project
        return qs

    def _evaluate(self) -> list[Any]:
        items = list(self._items)
        for field, reverse in reversed(self._order):
            items.sort(key=lambda item: self._get_value(item, field), reverse=reverse)
        if self._slice:
            start, end = self._slice
            items = items[start:end]
        if self._project:
            items = [self._project_item(item, self._project) for item in items]
        return items

    # ---------- Matching ----------

    def _match(self, item: Any, filters: dict[str, Any]) -> bool:
        """Return True if item satisfies all filter conditions."""
        for key, expected in filters.items():
            # Let key_resolver handle domain-specific keys first
            if self._key_resolver is not None:
                resolved = self._key_resolver(item, key)
                if resolved is not self._unresolved_sentinel:
                    if resolved != expected:
                        return False
                    continue

            # Parse field__operator
            field, op = self._parse_key(key)

            actual = self._get_value(item, field)
            op_fn = _OPERATORS.get(op)
            if op_fn is None:
                raise ValueError(f"Unknown query operator: {op!r} in {key!r}")
            if not op_fn(actual, expected):
                return False
        return True

    def _parse_key(self, key: str) -> tuple[str, str]:
        """Parse a filter key into (field_path, operator)."""
        if "__" not in key:
            return key, "eq"

        parts = key.rsplit("__", 1)
        maybe_field, maybe_op = parts[0], parts[1]

        if maybe_op in _OPERATORS:
            field = maybe_field.replace("__", ".")
            return field, maybe_op

        # Check nested field prefixes (e.g. catalog__lifecycle)
        prefix = key.split("__", 1)[0]
        if prefix in self._nested_field_prefixes:
            return key.replace("__", "."), "eq"

        raise ValueError(f"Unknown query operator: {maybe_op!r} in {key!r}")

    def _get_value(self, item: Any, field: str) -> Any:
        """Extract a field value from an item (attribute, dict, or nested path)."""
        # 1. Direct attribute (including @property)
        if hasattr(item, field):
            return getattr(item, field)

        # 2. Dict key (exact match first, then dotted path)
        if isinstance(item, dict):
            if field in item:
                return item[field]
            # Try dotted path on dict: "catalog.lifecycle" → item["catalog"]["lifecycle"]
            parts = field.split(".")
            obj: Any = item
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

        # 3. Nested attribute path (a.b.c)
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

    @staticmethod
    def _project_item(item: Any, names: list[str]) -> Any:
        from types import SimpleNamespace

        qs = QuerySet([])
        return SimpleNamespace(**{name: qs._get_value(item, name) for name in names})

    @staticmethod
    def _project_dict(item: Any, names: list[str]) -> dict[str, Any]:
        qs = QuerySet([])
        return {name: qs._get_value(item, name) for name in names}


# ---------------------------------------------------------------------------
# Sentinel for key_resolver
# ---------------------------------------------------------------------------


class _KeyUnresolved:
    """Sentinel returned by key_resolver when it does not handle a key."""

    _instance: "_KeyUnresolved | None" = None

    def __new__(cls) -> "_KeyUnresolved":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


_KEY_UNRESOLVED = _KeyUnresolved()
