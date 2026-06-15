"""piki QuerySet adapter tests — tags__ resolution and nested field prefixes via make_query_set."""

from __future__ import annotations

from types import SimpleNamespace

from piki.core.engine.query import make_query_set


class FakeResolvedInstance:
    """Minimal fake that behaves like piki's ResolvedInstance for tags/attrs."""

    def __init__(self, id: str, tags: dict | None = None, **kwargs):
        self.id = id
        self.tags = tags or {}
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.resolved = SimpleNamespace(
            tags=self.tags,
            tdp_w=getattr(self, "tdp_w", 0),
        )


class TestTagsResolution:
    def test_tags_discipline_filter(self) -> None:
        items = [
            FakeResolvedInstance("A", tags={"discipline": "hvac"}),
            FakeResolvedInstance("B", tags={"discipline": "electrical"}),
        ]
        qs = make_query_set(items).filter(tags__discipline="hvac")
        assert qs.count() == 1
        assert qs.first().id == "A"

    def test_tags_security_zone_filter(self) -> None:
        items = [
            FakeResolvedInstance("A", tags={"security_zone": "containment"}),
            FakeResolvedInstance("B", tags={"security_zone": "public"}),
        ]
        qs = make_query_set(items).filter(tags__security_zone="public")
        assert qs.count() == 1
        assert qs.first().id == "B"

    def test_tags_on_plain_dict(self) -> None:
        items = [
            {"tags": {"discipline": "hvac"}, "id": "x"},
            {"tags": {"discipline": "electrical"}, "id": "y"},
        ]
        qs = make_query_set(items).filter(tags__discipline="electrical")
        assert qs.count() == 1
        assert qs.first()["id"] == "y"


class TestNestedFieldPrefixes:
    def test_catalog_lifecycle(self) -> None:
        items = [
            FakeResolvedInstance("A", catalog=SimpleNamespace(lifecycle="active")),
            FakeResolvedInstance("B", catalog=SimpleNamespace(lifecycle="eol")),
        ]
        qs = make_query_set(items).filter(catalog__lifecycle="active")
        assert qs.count() == 1
        assert qs.first().id == "A"

    def test_resolved_tdp_w(self) -> None:
        items = [
            FakeResolvedInstance("A", tdp_w=300),
            FakeResolvedInstance("B", tdp_w=500),
        ]
        qs = make_query_set(items).filter(resolved__tdp_w__gt=400)
        assert qs.count() == 1
        assert qs.first().id == "B"
