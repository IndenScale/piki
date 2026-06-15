"""AQL QuerySet unit tests — pure AQL, no piki dependency."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from piki.core.engine._query_engine import _KEY_UNRESOLVED, QuerySet


def _make_items() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(id="A", age=30, name="Alice", tags=["dev", "ops"]),
        SimpleNamespace(id="B", age=25, name="Bob", tags=["dev"]),
        SimpleNamespace(id="C", age=35, name="Charlie", tags=["ops"]),
        SimpleNamespace(id="D", age=30, name="Diana", tags=["qa", "dev"]),
    ]


class TestOperators:
    def test_eq_default(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(age=30)
        assert qs.count() == 2
        assert {i.id for i in qs} == {"A", "D"}

    def test_ne(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(age__ne=30)
        assert qs.count() == 2
        assert {i.id for i in qs} == {"B", "C"}

    def test_gt(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(age__gt=30)
        assert qs.count() == 1
        assert qs.first().id == "C"

    def test_in(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(id__in=["A", "C"])
        assert qs.count() == 2

    def test_contains_string(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(name__contains="li")
        assert qs.count() == 2

    def test_startswith(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(name__startswith="C")
        assert qs.count() == 1
        assert qs.first().id == "C"

    def test_unknown_operator_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown query operator: 'unknown' in 'age__unknown'"):
            QuerySet([{"age": 30}]).filter(age__unknown=1)


class TestChaining:
    def test_filter_then_order_by(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(age=30).order_by("name")
        result = qs.list()
        assert [i.id for i in result] == ["A", "D"]

    def test_limit(self) -> None:
        items = _make_items()
        qs = QuerySet(items).limit(2)
        assert qs.count() == 2

    def test_exclude(self) -> None:
        items = _make_items()
        qs = QuerySet(items).exclude(age=30)
        assert qs.count() == 2

    def test_fields_projection(self) -> None:
        items = _make_items()
        qs = QuerySet(items).fields("id", "age")
        first = qs.first()
        assert first.id == "A"
        assert first.age == 30

    def test_first_empty(self) -> None:
        qs = QuerySet([]).filter(age=999)
        assert qs.first() is None


class TestAggregation:
    def test_group_by(self) -> None:
        items = _make_items()
        groups = QuerySet(items).group_by("age")
        assert set(groups.keys()) == {25, 30, 35}
        assert len(groups[30]) == 2

    def test_count(self) -> None:
        assert QuerySet(_make_items()).count() == 4
        assert QuerySet(_make_items()).filter(age__gt=30).count() == 1

    def test_aggregate(self) -> None:
        items = _make_items()
        result = QuerySet(items).aggregate(
            total_age=lambda items: sum(i.age for i in items),
            count=len,
        )
        assert result["total_age"] == 120
        assert result["count"] == 4

    def test_values(self) -> None:
        items = _make_items()
        vals = QuerySet(items).values("id", "age")
        assert vals[0] == {"id": "A", "age": 30}


class TestExtensibility:
    def test_key_resolver_tags(self) -> None:
        """Custom key_resolver for tags__ prefix."""

        def resolver(item, key):
            if key.startswith("tags__"):
                return item.get("tags", {}).get(key[6:], _KEY_UNRESOLVED)
            return _KEY_UNRESOLVED

        items = [
            {"tags": {"color": "red"}, "id": "x"},
            {"tags": {"color": "blue"}, "id": "y"},
        ]
        qs = QuerySet(items, key_resolver=resolver).filter(tags__color="red")
        assert qs.count() == 1
        assert qs.first()["id"] == "x"

    def test_nested_field_prefixes(self) -> None:
        """Custom nested_field_prefixes for catalog__ style paths."""
        items = [
            {"catalog": {"lifecycle": "active"}, "id": "x"},
            {"catalog": {"lifecycle": "eol"}, "id": "y"},
        ]
        qs = QuerySet(items, nested_field_prefixes={"catalog"}).filter(catalog__lifecycle="active")
        assert qs.count() == 1
        assert qs.first()["id"] == "x"

    def test_combined_resolver_and_prefixes(self) -> None:
        """Both key_resolver and nested_field_prefixes work together."""

        def resolver(item, key):
            if key.startswith("tags__"):
                return item.get("tags", {}).get(key[6:], _KEY_UNRESOLVED)
            return _KEY_UNRESOLVED

        items = [
            {"tags": {"zone": "a"}, "catalog": {"lifecycle": "active"}, "id": "x"},
            {"tags": {"zone": "b"}, "catalog": {"lifecycle": "eol"}, "id": "y"},
        ]
        qs = (
            QuerySet(items, key_resolver=resolver, nested_field_prefixes={"catalog"})
            .filter(tags__zone="a")
            .filter(catalog__lifecycle="active")
        )
        assert qs.count() == 1
        assert qs.first()["id"] == "x"
