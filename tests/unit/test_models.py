"""Models 单元测试 —— 覆盖 ResolvedInstance 属性访问、嵌套解析。"""

from __future__ import annotations

from pathlib import Path

import pytest

from piki.core.models.base import (
    Instance,
    Model,
    ResolvedInstance,
    _make_namespace,
    _unflatten,
)


class TestMakeNamespace:
    """测试 _make_namespace 嵌套对象构造。"""

    def test_flat_dict(self) -> None:
        ns = _make_namespace({"a": 1, "b": "hello"})
        assert ns.a == 1
        assert ns.b == "hello"

    def test_nested_dict(self) -> None:
        ns = _make_namespace({"a": {"b": {"c": 42}}})
        assert ns.a.b.c == 42

    def test_list_of_dicts(self) -> None:
        ns = _make_namespace({"items": [{"id": "x"}, {"id": "y"}]})
        assert len(ns.items) == 2
        assert ns.items[0].id == "x"
        assert ns.items[1].id == "y"

    def test_mixed(self) -> None:
        ns = _make_namespace(
            {
                "name": "test",
                "tags": ["a", "b"],
                "config": {"timeout": 30},
            }
        )
        assert ns.name == "test"
        assert ns.tags == ["a", "b"]
        assert ns.config.timeout == 30


class TestUnflatten:
    """测试 _unflatten 扁平化还原。"""

    def test_simple(self) -> None:
        assert _unflatten({"a": 1, "b": 2}) == {"a": 1, "b": 2}

    def test_nested(self) -> None:
        flat = {"a.b.c": 42, "a.d": "hello"}
        assert _unflatten(flat) == {"a": {"b": {"c": 42}, "d": "hello"}}

    def test_overlapping_prefix(self) -> None:
        """a 既是叶子又是前缀时，当前实现会抛出 TypeError（已知限制）。"""
        flat = {"a": 1, "a.b": 2}
        with pytest.raises(TypeError):
            _unflatten(flat)


class TestResolvedInstance:
    """测试 ResolvedInstance 的属性访问。"""

    def test_getattr_resolved(self) -> None:
        r = ResolvedInstance(
            id="test",
            family="ServerFamily",
            raw={"rack_id": "R1"},
            _resolved={"id": "test", "rack_id": "R1", "tdp_w": 300},
            source=Path("test.yaml"),
        )
        assert r.id == "test"
        assert r.rack_id == "R1"
        assert r.tdp_w == 300

    def test_getattr_missing_raises(self) -> None:
        r = ResolvedInstance(
            id="test",
            family="ServerFamily",
            raw={},
            _resolved={"id": "test"},
            source=Path("test.yaml"),
        )
        with pytest.raises(AttributeError, match="nonexistent"):
            _ = r.nonexistent

    def test_resolved_property(self) -> None:
        r = ResolvedInstance(
            id="test",
            family="ServerFamily",
            raw={"power": {"pdu": "A"}},
            _resolved={"id": "test", "power.pdu": "A", "power.phase": "L1"},
            source=Path("test.yaml"),
        )
        assert r.resolved.power.pdu == "A"
        assert r.resolved.power.phase == "L1"

    def test_resolved_flat_access(self) -> None:
        """直接属性访问扁平字段。"""
        r = ResolvedInstance(
            id="test",
            family="ServerFamily",
            raw={},
            _resolved={"id": "test", "height_u": 2},
            source=Path("test.yaml"),
        )
        assert r.height_u == 2


class TestModel:
    """测试 Model 数据类。"""

    def test_basic(self) -> None:
        m = Model(
            id="generic-server",
            family="ServerFamily",
            data={"height_u": 2, "tdp_w": 300},
            source=Path("lib/generic-server.yaml"),
        )
        assert m.id == "generic-server"
        assert m.family == "ServerFamily"
        assert m.data["height_u"] == 2

    def test_optional_source(self) -> None:
        m = Model(id="x", family="F", data={})
        assert m.source is None


class TestInstance:
    """测试 Instance 数据类。"""

    def test_basic(self) -> None:
        i = Instance(
            id="SRV-01",
            model="generic-server",
            family="ServerFamily",
            data={"rack_id": "R1"},
            source=Path("devices/SRV-01.yaml"),
        )
        assert i.id == "SRV-01"
        assert i.model == "generic-server"
        assert i.data["rack_id"] == "R1"
