"""单元测试：Mate 数据模型 (ADR-008)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from piki.core.models.mating import (
    InterfacePairing,
    MateConstraint,
    MateConstraintOperator,
    MateGraph,
    MateSpec,
    MateTypeMeta,
    evaluate_operator,
    is_interface_ref,
    parse_mate_ref,
)

# ============================================================================
# parse_mate_ref
# ============================================================================


class TestParseMateRef:
    def test_bare_instance(self) -> None:
        inst, iface = parse_mate_ref("RACK-A01")
        assert inst == "RACK-A01"
        assert iface is None

    def test_interface_ref(self) -> None:
        inst, iface = parse_mate_ref("SRV-01/power-a")
        assert inst == "SRV-01"
        assert iface == "power-a"

    def test_interface_ref_with_trailing_slash(self) -> None:
        inst, iface = parse_mate_ref("PDU-A/out-3")
        assert inst == "PDU-A"
        assert iface == "out-3"

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_mate_ref("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_mate_ref("   ")

    def test_whitespace_around_instance(self) -> None:
        inst, iface = parse_mate_ref("  RACK-A01  ")
        assert inst == "RACK-A01"
        assert iface is None

    def test_multiple_slashes(self) -> None:
        """只按第一个 / 分割。"""
        inst, iface = parse_mate_ref("DEV-01/a/b/c")
        assert inst == "DEV-01"
        assert iface == "a/b/c"


class TestIsInterfaceRef:
    def test_bare_instance(self) -> None:
        assert is_interface_ref("RACK-A01") is False

    def test_interface_ref(self) -> None:
        assert is_interface_ref("SRV-01/eth0") is True

    def test_empty(self) -> None:
        assert is_interface_ref("") is False


# ============================================================================
# MateConstraintOperator & evaluate_operator
# ============================================================================


class TestConstraintOperator:
    def test_lte(self) -> None:
        assert evaluate_operator(10, MateConstraintOperator.LTE, 20) is True
        assert evaluate_operator(20, MateConstraintOperator.LTE, 20) is True
        assert evaluate_operator(30, MateConstraintOperator.LTE, 20) is False

    def test_gte(self) -> None:
        assert evaluate_operator(30, MateConstraintOperator.GTE, 20) is True
        assert evaluate_operator(10, MateConstraintOperator.GTE, 20) is False

    def test_eq(self) -> None:
        assert evaluate_operator("SFP28", MateConstraintOperator.EQ, "SFP28") is True
        assert evaluate_operator("SFP28", MateConstraintOperator.EQ, "SFP+") is False

    def test_ne(self) -> None:
        assert evaluate_operator("SFP28", MateConstraintOperator.NE, "SFP+") is True
        assert evaluate_operator("SFP28", MateConstraintOperator.NE, "SFP28") is False

    def test_in(self) -> None:
        assert evaluate_operator(2, MateConstraintOperator.IN, [1, 2, 3]) is True
        assert evaluate_operator(4, MateConstraintOperator.IN, [1, 2, 3]) is False

    def test_contains(self) -> None:
        assert evaluate_operator("hello world", MateConstraintOperator.CONTAINS, "world") is True
        assert evaluate_operator("hello", MateConstraintOperator.CONTAINS, "z") is False

    def test_none_operands(self) -> None:
        """任意 operand 为 None 时返回 False（in/contains 有特殊处理）。"""
        assert evaluate_operator(None, MateConstraintOperator.LTE, 20) is False
        assert evaluate_operator(10, MateConstraintOperator.LTE, None) is False

    def test_type_mismatch(self) -> None:
        """类型不匹配时返回 False。"""
        assert evaluate_operator("abc", MateConstraintOperator.LTE, 20) is False


# ============================================================================
# MateConstraint
# ============================================================================


class TestMateConstraint:
    def test_minimal(self) -> None:
        c = MateConstraint(field="depth_mm", value_ref="depth_mm")
        assert c.field == "depth_mm"
        assert c.operator == MateConstraintOperator.LTE
        assert c.value_ref == "depth_mm"
        assert c.message == ""

    def test_with_message(self) -> None:
        c = MateConstraint(
            field="weight_kg",
            operator=MateConstraintOperator.LTE,
            value_ref="rail_capacity_kg_per_pair",
            message="重量超限",
        )
        assert c.message == "重量超限"

    def test_all_operator_values(self) -> None:
        """确保所有 operator 均可通过 Pydantic 解析。"""
        for op_str in ("<=", ">=", "<", ">", "==", "!=", "in", "contains"):
            c = MateConstraint(field="f", operator=op_str, value_ref="v")  # type: ignore[arg-type]
            assert c.operator.value == op_str


# ============================================================================
# InterfacePairing
# ============================================================================


class TestInterfacePairing:
    def test_valid_pairing(self) -> None:
        p = InterfacePairing(
            **{"from": "SRV-01/power-a", "to": "PDU-A/out-3", "pairing_type": "power-iec-c14-c13"}
        )
        assert p.from_ref == "SRV-01/power-a"
        assert p.to_ref == "PDU-A/out-3"
        assert p.pairing_type == "power-iec-c14-c13"

    def test_missing_slash_on_from(self) -> None:
        with pytest.raises(ValidationError, match="必须包含 '/'"):
            InterfacePairing(**{"from": "SRV-01", "to": "PDU-A/out-3"})

    def test_missing_slash_on_to(self) -> None:
        with pytest.raises(ValidationError, match="必须包含 '/'"):
            InterfacePairing(**{"from": "SRV-01/eth0", "to": "SW-01"})

    def test_both_missing_slash(self) -> None:
        with pytest.raises(ValidationError):
            InterfacePairing(**{"from": "SRV-01", "to": "SW-01"})


# ============================================================================
# MateSpec
# ============================================================================


class TestMateSpec:
    def test_minimal_l1_mate(self) -> None:
        m = MateSpec(type="rack-mount-19inch", parent="RACK-A01", child="SRV-01")
        assert m.type == "rack-mount-19inch"
        assert m.parent == "RACK-A01"
        assert m.child == "SRV-01"
        assert m.at == {}
        assert m.constrains == []
        assert m.pairings == []
        assert m.media == ""
        assert m.length_m == 0.0

    def test_l1_with_constrains(self) -> None:
        m = MateSpec(
            type="rack-mount-19inch",
            parent="RACK-A01",
            child="SRV-01",
            constrains=[
                MateConstraint(field="depth_mm", value_ref="depth_mm"),
                MateConstraint(
                    field="weight_kg",
                    operator=MateConstraintOperator.LTE,
                    value_ref="rail_capacity_kg_per_pair",
                ),
            ],
        )
        assert len(m.constrains) == 2

    def test_l2_interface_mate(self) -> None:
        """L2 配合：parent/child 都是 Interface 引用。"""
        m = MateSpec(
            type="power-iec-c14-c13",
            parent="PDU-A/out-3",
            child="SRV-01/power-a",
        )
        assert parse_mate_ref(m.parent) == ("PDU-A", "out-3")
        assert parse_mate_ref(m.child) == ("SRV-01", "power-a")

    def test_l1_with_pairings(self) -> None:
        m = MateSpec(
            type="rack-mount-19inch",
            parent="RACK-A01",
            child="SRV-01",
            at={"u_start": 10, "u_span": 2},
            pairings=[
                InterfacePairing(**{"from": "SRV-01/power-a", "to": "PDU-A/out-3"}),
            ],
        )
        assert len(m.pairings) == 1
        assert m.pairings[0].from_ref == "SRV-01/power-a"

    def test_self_reference_rejected(self) -> None:
        with pytest.raises(ValidationError, match="两端不能相同"):
            MateSpec(type="self", parent="X", child="X")

    def test_l3_link_mate(self) -> None:
        """L3 跨配合链链路 Mate。"""
        m = MateSpec(
            type="optical-link",
            parent="SW-01/Gi1/0/1",
            child="SRV-01/eth1",
            media="OM4-LC-LC",
            length_m=3.0,
            constrains=[
                MateConstraint(
                    field="interface_type",
                    operator=MateConstraintOperator.EQ,
                    value_ref="interface_type",
                ),
            ],
        )
        assert m.media == "OM4-LC-LC"
        assert m.length_m == 3.0
        assert len(m.constrains) == 1


# ============================================================================
# MateTypeMeta
# ============================================================================


class TestMateTypeMeta:
    def test_empty_meta(self) -> None:
        meta = MateTypeMeta(type="custom-type")
        assert meta.type == "custom-type"
        assert meta.description == ""
        assert meta.default_constrains == []
        assert meta.applicable_parent_families == set()
        assert meta.applicable_child_families == set()

    def test_with_family_restrictions(self) -> None:
        meta = MateTypeMeta(
            type="rack-mount-19inch",
            applicable_parent_families={"RackFamily"},
            applicable_child_families={"ServerFamily", "PduFamily"},
        )
        assert "RackFamily" in meta.applicable_parent_families
        assert "ServerFamily" in meta.applicable_child_families

    def test_with_default_constrains(self) -> None:
        meta = MateTypeMeta(
            type="rack-mount-19inch",
            default_constrains=[
                MateConstraint(field="depth_mm", value_ref="depth_mm"),
            ],
        )
        assert len(meta.default_constrains) == 1


# ============================================================================
# MateGraph
# ============================================================================


class TestMateGraph:
    @staticmethod
    def _make_mate(type_name: str, parent: str, child: str) -> MateSpec:
        return MateSpec(type=type_name, parent=parent, child=child)

    def test_empty_graph(self) -> None:
        g = MateGraph()
        assert len(g) == 0
        assert g.list() == []

    def test_add_and_query(self) -> None:
        g = MateGraph()
        m = self._make_mate("rack-mount-19inch", "RACK-A01", "SRV-01")
        g.add(m)

        assert len(g) == 1
        assert g.parents_of("SRV-01") == [m]
        assert g.children_of("RACK-A01") == [m]
        assert g.related_to("RACK-A01") == [m]
        assert g.related_to("SRV-01") == [m]

    def test_parents_of_nonexistent(self) -> None:
        g = MateGraph()
        assert g.parents_of("NONEXISTENT") == []

    def test_children_of_nonexistent(self) -> None:
        g = MateGraph()
        assert g.children_of("NONEXISTENT") == []

    def test_multiple_mates(self) -> None:
        g = MateGraph()
        m1 = self._make_mate("rack-mount-19inch", "RACK-A01", "SRV-01")
        m2 = self._make_mate("rack-mount-19inch", "RACK-A01", "SRV-02")
        m3 = self._make_mate("rack-mount-19inch", "RACK-B01", "SW-01")
        g.add(m1)
        g.add(m2)
        g.add(m3)

        # RACK-A01 承载了两个设备
        assert len(g.children_of("RACK-A01")) == 2
        assert set(m.child for m in g.children_of("RACK-A01")) == {"SRV-01", "SRV-02"}

        # SRV-01 只有一个承载者
        assert len(g.parents_of("SRV-01")) == 1
        assert g.parents_of("SRV-01")[0].parent == "RACK-A01"

    def test_interface_ref_indexing(self) -> None:
        """Interface 引用在双向索引中应正常解析。"""
        g = MateGraph()
        m = MateSpec(type="power-iec-c14-c13", parent="PDU-A/out-3", child="SRV-01/power-a")
        g.add(m)

        # 按完整引用查找
        assert g.parents_of("SRV-01/power-a") == [m]
        assert g.children_of("PDU-A/out-3") == [m]

        # 按 Instance ID 查找
        assert m in g.related_to("SRV-01")
        assert m in g.related_to("PDU-A")

    def test_chain_single_level(self) -> None:
        g = MateGraph()
        g.add(self._make_mate("rack-mount-19inch", "RACK-A01", "SRV-01"))
        chains = g.chain("SRV-01")
        assert len(chains) == 1
        assert len(chains[0]) == 1
        assert chains[0][0].parent == "RACK-A01"

    def test_chain_multi_level(self) -> None:
        """机柜→服务器→GPU 三级配合链。"""
        g = MateGraph()
        g.add(self._make_mate("rack-mount-19inch", "RACK-A01", "SRV-01"))
        g.add(self._make_mate("pcie-slot", "SRV-01/slot-3", "GPU-01"))

        chains = g.chain("GPU-01")
        assert len(chains) == 1
        assert len(chains[0]) == 2
        assert chains[0][0].child == "GPU-01"
        assert chains[0][1].child == "SRV-01"

    def test_chain_no_parents(self) -> None:
        g = MateGraph()
        assert g.chain("RACK-A01") == []

    def test_chain_multiple_branches(self) -> None:
        """一个 Instance 有两个 parent Mate (如双路电源)。"""
        g = MateGraph()
        g.add(MateSpec(type="power-iec-c14-c13", parent="PDU-A/out-3", child="SRV-01/power-a"))
        g.add(MateSpec(type="power-iec-c14-c13", parent="PDU-B/out-5", child="SRV-01/power-b"))
        g.add(self._make_mate("rack-mount-19inch", "RACK-A01", "PDU-A"))
        g.add(self._make_mate("rack-mount-19inch", "RACK-A01", "PDU-B"))

        chains = g.chain("SRV-01/power-a")
        assert len(chains) == 1
        # chain: SRV-01/power-a → PDU-A/out-3 (L2 mate) → PDU-A (rack-mount) → RACK-A01
        # interface ref hops to bare instance ref, total 2 hops
        assert len(chains[0]) == 2

    def test_iter(self) -> None:
        g = MateGraph()
        m1 = self._make_mate("t1", "A", "B")
        m2 = self._make_mate("t2", "C", "D")
        g.add(m1)
        g.add(m2)
        assert list(g) == [m1, m2]
