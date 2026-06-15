"""AQL — Abstract Query Language.

A lazy, chainable, Django-style query DSL for Python collections.

Usage::

    from aql import QuerySet

    items = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
    qs = QuerySet(items).filter(age__gt=25).order_by("name")
    print(qs.list())  # [{"name": "Alice", "age": 30}]

Features:
- Django-style double-underscore operators (__gt, __in, __contains, ...)
- Chainable: filter, exclude, order_by, limit, fields
- Terminal: first, count, list, values, group_by, aggregate
- Extensible: custom key resolvers and nested field prefixes
"""

from .query import QuerySet

__all__ = ["QuerySet"]
__version__ = "0.1.0"
