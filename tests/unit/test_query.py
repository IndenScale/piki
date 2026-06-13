"""QuerySet 单元测试 —— 覆盖所有操作符和链式操作。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from piki.core.engine.query import QuerySet, _get_value, _match, _project


def _make_items() -> list[SimpleNamespace]:
    """构造测试数据。"""
    return [
        SimpleNamespace(id="A", age=30, name="Alice", tags=["dev", "ops"]),
        SimpleNamespace(id="B", age=25, name="Bob", tags=["dev"]),
        SimpleNamespace(id="C", age=35, name="Charlie", tags=["ops"]),
        SimpleNamespace(id="D", age=30, name="Diana", tags=["qa", "dev"]),
    ]


class TestOperators:
    """测试所有过滤操作符。"""

    def test_eq_default(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(age=30)
        assert qs.count() == 2
        assert {i.id for i in qs} == {"A", "D"}

    def test_eq_explicit(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(age__eq=30)
        assert qs.count() == 2

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

    def test_gte(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(age__gte=30)
        assert qs.count() == 3

    def test_lt(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(age__lt=30)
        assert qs.count() == 1
        assert qs.first().id == "B"

    def test_lte(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(age__lte=30)
        assert qs.count() == 3

    def test_in(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(id__in=["A", "C"])
        assert qs.count() == 2
        assert {i.id for i in qs} == {"A", "C"}

    def test_contains_string(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(name__contains="li")
        assert qs.count() == 2
        assert {i.id for i in qs} == {"A", "C"}  # Alice, Charlie

    def test_contains_list(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(tags__contains="dev")
        assert qs.count() == 3
        assert {i.id for i in qs} == {"A", "B", "D"}

    def test_in_list_field(self) -> None:
        """list 字段的 __in：字段中任一元素在期望集合中即匹配。"""
        items = _make_items()
        qs = QuerySet(items).filter(tags__in=["dev", "ops"])
        assert qs.count() == 4
        assert {i.id for i in qs} == {"A", "B", "C", "D"}

    def test_in_list_field_no_overlap(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(tags__in=["qa"])
        assert qs.count() == 1
        assert qs.first().id == "D"

    def test_in_scalar_field_unchanged(self) -> None:
        """标量字段的 __in 保持原有语义：字段值在期望集合中。"""
        items = _make_items()
        qs = QuerySet(items).filter(age__in=[25, 35])
        assert qs.count() == 2
        assert {i.id for i in qs} == {"B", "C"}

    def test_startswith(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(name__startswith="C")
        assert qs.count() == 1
        assert qs.first().id == "C"

    def test_endswith(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(name__endswith="a")
        assert qs.count() == 1
        assert qs.first().id == "D"  # Diana

    def test_unknown_operator_raises(self) -> None:
        items = _make_items()
        with pytest.raises(ValueError, match="Unknown query operator"):
            QuerySet(items).filter(age__unknown=1)

    def test_nested_field_path_via_double_underscore(self) -> None:
        """ADR-011: catalog__lifecycle 等嵌套字段查询应被识别为字段路径。"""
        from types import SimpleNamespace

        items = [SimpleNamespace(catalog={"lifecycle": "eol"})]
        qs = QuerySet(items).filter(catalog__lifecycle="eol")
        assert qs.count() == 1

    def test_nested_field_path_with_operator(self) -> None:
        """ADR-011: catalog__enterprise__price_cny__gt 应能工作。"""
        from types import SimpleNamespace

        items = [
            SimpleNamespace(catalog={"enterprise": {"price_cny": 1200}}),
            SimpleNamespace(catalog={"enterprise": {"price_cny": 800}}),
        ]
        qs = QuerySet(items).filter(catalog__enterprise__price_cny__gt=1000)
        assert qs.count() == 1


class TestChaining:
    """测试链式操作。"""

    def test_filter_then_order_by(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(age=30).order_by("name")
        result = qs.list()
        assert [i.id for i in result] == ["A", "D"]

    def test_order_by_desc(self) -> None:
        items = _make_items()
        qs = QuerySet(items).order_by("-age")
        result = qs.list()
        assert [i.id for i in result] == ["C", "A", "D", "B"]

    def test_limit(self) -> None:
        items = _make_items()
        qs = QuerySet(items).limit(2)
        assert qs.count() == 2

    def test_filter_limit_order(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(age__gte=25).order_by("-age").limit(2)
        result = qs.list()
        assert [i.id for i in result] == ["C", "A"]

    def test_exclude(self) -> None:
        items = _make_items()
        qs = QuerySet(items).exclude(age=30)
        assert qs.count() == 2
        assert {i.id for i in qs} == {"B", "C"}

    def test_filter_exclude_chain(self) -> None:
        items = _make_items()
        qs = QuerySet(items).filter(age__gte=25).exclude(id="C")
        assert qs.count() == 3
        assert "C" not in {i.id for i in qs}

    def test_fields_projection(self) -> None:
        items = _make_items()
        qs = QuerySet(items).fields("id", "age")
        first = qs.first()
        assert first.id == "A"
        assert first.age == 30
        # name 不在投影中，但 SimpleNamespace 会设为 None（因为构造函数传了）
        # 实际行为取决于 _project 实现

    def test_first_empty(self) -> None:
        qs = QuerySet([]).filter(age=999)
        assert qs.first() is None

    def test_getitem_index(self) -> None:
        items = _make_items()
        qs = QuerySet(items).order_by("age")
        assert qs[0].id == "B"
        assert qs[-1].id == "C"

    def test_getitem_slice(self) -> None:
        items = _make_items()
        qs = QuerySet(items).order_by("age")
        sliced = qs[1:3]
        assert len(sliced) == 2
        assert sliced[0].id == "A"


class TestAggregation:
    """测试聚合和分组。"""

    def test_group_by(self) -> None:
        items = _make_items()
        groups = QuerySet(items).group_by("age")
        assert set(groups.keys()) == {25, 30, 35}
        assert len(groups[30]) == 2

    def test_count(self) -> None:
        items = _make_items()
        assert QuerySet(items).count() == 4
        assert QuerySet(items).filter(age__gt=30).count() == 1

    def test_aggregate(self) -> None:
        items = _make_items()
        result = QuerySet(items).aggregate(
            total_age=lambda items: sum(i.age for i in items),
            avg_age=lambda items: sum(i.age for i in items) / len(items),
            count=len,
        )
        assert result["total_age"] == 120
        assert result["avg_age"] == 30.0
        assert result["count"] == 4

    def test_values(self) -> None:
        items = _make_items()
        vals = QuerySet(items).values("id", "age")
        assert vals[0] == {"id": "A", "age": 30}
        assert len(vals) == 4


class TestJoin:
    """测试跨表连接。"""

    def test_join_basic(self) -> None:
        devices = [
            SimpleNamespace(id="D1", rack_id="R1"),
            SimpleNamespace(id="D2", rack_id="R2"),
            SimpleNamespace(id="D3", rack_id="R1"),
        ]
        racks = [
            SimpleNamespace(id="R1", location="A"),
            SimpleNamespace(id="R2", location="B"),
        ]
        joined = QuerySet(devices).join(racks, "rack_id").list()
        assert len(joined) == 3
        assert joined[0]._join_related.location == "A"
        assert joined[1]._join_related.location == "B"

    def test_join_missing_foreign(self) -> None:
        devices = [
            SimpleNamespace(id="D1", rack_id="R1"),
            SimpleNamespace(id="D2", rack_id="R99"),  # 不存在
        ]
        racks = [SimpleNamespace(id="R1", location="A")]
        joined = QuerySet(devices).join(racks, "rack_id").list()
        assert len(joined) == 1
        assert joined[0].id == "D1"


class TestHelpers:
    """测试内部辅助函数。"""

    def test_get_value_dict(self) -> None:
        d = {"a": {"b": 1}}
        assert _get_value(d, "a") == {"b": 1}
        # dict 不支持嵌套属性访问（a.b），_get_value 先尝试 getattr 再 dict.get
        # 对于 dict，"a.b" 不会自动拆分，因为 dict 有 "a.b" 这个 key 吗？没有
        # 实际上 _get_value 对 dict 会走 dict.get("a.b") -> None
        # 嵌套 dict 访问应通过属性路径方式，但 _get_value 的实现是：
        # 先 hasattr/getattr，对 dict 来说 hasattr(d, "a.b") 为 False
        # 然后 isinstance(obj, dict) -> obj.get("a.b") -> None
        # 所以 dict 不支持 a.b 路径访问
        assert _get_value(d, "a.b") is None
        assert _get_value(d, "x") is None

    def test_get_value_nested_attr(self) -> None:
        obj = SimpleNamespace(a=SimpleNamespace(b=2))
        assert _get_value(obj, "a.b") == 2

    def test_match_multiple_filters(self) -> None:
        item = SimpleNamespace(id="A", age=30)
        assert _match(item, {"id": "A", "age": 30}) is True
        assert _match(item, {"id": "A", "age": 25}) is False

    def test_project(self) -> None:
        item = SimpleNamespace(id="A", age=30, name="X")
        projected = _project(item, ["id", "age"])
        assert projected.id == "A"
        assert projected.age == 30
