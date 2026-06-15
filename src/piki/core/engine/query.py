"""piki query adapter — wraps QuerySet with piki-specific semantics.

Adds:
- tags__discipline → resolved.tags[discipline] key resolution
- catalog__lifecycle → nested field path resolution for ADR-011
- service_method__* → nested field path resolution
"""

from __future__ import annotations

from typing import Any

from ._query_engine import QuerySet as _BaseQuerySet

# Nested field prefixes for ADR-011 Catalog queries
_PIKI_NESTED_FIELD_PREFIXES = {"catalog", "service_method", "service_methods", "resolved"}

# Sentinel: "I don't handle this key" — must be a unique object for identity check
_UNRESOLVED = object()


def _piki_key_resolver(item: Any, key: str) -> Any:
    """Resolve piki-specific keys.

    Handles:
    - tags__<tag_key>  →  item.tags[tag_key] or resolved.tags[tag_key]
    """
    if key.startswith("tags__"):
        tag_key = key[6:]  # strip "tags__" prefix
        actual_tags = _get_value(item, "tags")
        if isinstance(actual_tags, dict):
            return actual_tags.get(tag_key, _UNRESOLVED)
        # ResolvedInstance may have tags in resolved.tags
        tag_value = _get_value(item, "resolved.tags." + tag_key)
        if tag_value is not None:
            return tag_value
        return _UNRESOLVED

    return _UNRESOLVED


def _get_value(item: Any, field: str) -> Any:
    """Extract field value, with nested attr support."""
    if hasattr(item, field):
        return getattr(item, field)
    if isinstance(item, dict):
        return item.get(field)
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


def make_query_set(items: list[Any]) -> _BaseQuerySet:
    """Create a QuerySet pre-configured with piki semantics."""
    return _BaseQuerySet(
        items,
        key_resolver=_piki_key_resolver,
        nested_field_prefixes=_PIKI_NESTED_FIELD_PREFIXES,
        unresolved_sentinel=_UNRESOLVED,
    )


# Re-export for backward compatibility
QuerySet = _BaseQuerySet
