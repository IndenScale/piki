"""集成测试：INTERFACE-COMPAT-001 和 INTERFACE-CABLE-001 (RFC-001)."""

from __future__ import annotations

from pathlib import Path

from piki.core.engine.checker import Checker
from piki.core.engine.context import Context
from piki.core.engine.registry import Registry
from piki.extensions.telecom.plugin import (
    FiberConnectionFamily,
    PduFamily,
    RackFamily,
    ServerFamily,
)


def _make_ctx_with_connection(
    tmp_path: Path,
    from_type: str,
    to_type: str,
    cable_type: str | None = None,
) -> Context:
    """构造含两个设备（不同接口类型）和一根光纤连接的 Context。

    SRV-01 使用 from_type，SRV-02 使用 to_type。
    """
    registry = Registry()
    registry.add_family("RackFamily", RackFamily)
    registry.add_family("PduFamily", PduFamily)
    registry.add_family("ServerFamily", ServerFamily)
    registry.add_family("FiberConnectionFamily", FiberConnectionFamily)

    # 型号
    lib = tmp_path / "models" / "devices"
    lib.mkdir(parents=True)
    (lib / "generic-server.yaml").write_text(
        "model: generic-server\nfamily: ServerFamily\nheight_u: 2\ntdp_w: 300\n",
        encoding="utf-8",
    )
    registry.load_models(lib.parent)

    # 基础设施
    racks = tmp_path / "racks"
    racks.mkdir()
    (racks / "RACK-A01.yaml").write_text(
        "id: RACK-A01\nfamily: RackFamily\ntotal_u: 42\n",
        encoding="utf-8",
    )
    registry.load_collection(racks)

    pdus = tmp_path / "pdus"
    pdus.mkdir()
    (pdus / "PDU-A.yaml").write_text(
        "id: PDU-A\nfamily: PduFamily\nrack_id: RACK-A01\ncapacity_w: 2000\nphase: L1\n",
        encoding="utf-8",
    )
    registry.load_collection(pdus)

    # 设备（各自不同的接口类型）
    devices = tmp_path / "devices"
    devices.mkdir()
    (devices / "SRV-01.yaml").write_text(
        f"id: SRV-01\nmodel: generic-server\nrack_id: RACK-A01\n"
        f"position_u: 10\npdu_id: PDU-A\n"
        f"interfaces:\n  - id: eth0\n    interface_type: {from_type}\n    direction: bidirectional\n",
        encoding="utf-8",
    )
    (devices / "SRV-02.yaml").write_text(
        f"id: SRV-02\nmodel: generic-server\nrack_id: RACK-A01\n"
        f"position_u: 12\npdu_id: PDU-A\n"
        f"interfaces:\n  - id: eth0\n    interface_type: {to_type}\n    direction: bidirectional\n",
        encoding="utf-8",
    )
    registry.load_collection(devices)

    # 连接
    conns = tmp_path / "connections"
    conns.mkdir()
    conn_yaml = (
        "id: FIBER-01\nfamily: FiberConnectionFamily\nname: test link\n"
        "from_interface: SRV-01/eth0\nto_interface: SRV-02/eth0\n"
    )
    if cable_type:
        conn_yaml += f"cable_type: {cable_type}\n"
    else:
        conn_yaml += "cable_type: OM4-LC-LC\n"

    (conns / "FIBER-01.yaml").write_text(conn_yaml, encoding="utf-8")
    registry.load_collection(conns)

    return Context(registry, {})


class TestInterfaceCompat:
    """INTERFACE-COMPAT-001 集成测试。"""

    def test_same_type_passes(self, tmp_path: Path) -> None:
        """同类型连接应通过。"""
        ctx = _make_ctx_with_connection(tmp_path, "SFP28", "SFP28")
        checker = Checker()
        report = checker.run(ctx)
        assert report.passed is True
        compat = next((r for r in report.results if r.rule_id == "INTERFACE-COMPAT-001"), None)
        assert compat is not None
        assert compat.passed is True

    def test_compatible_types_pass(self, tmp_path: Path) -> None:
        """SFP28 ↔ SFP+ 兼容连接应通过。"""
        ctx = _make_ctx_with_connection(tmp_path, "SFP28", "SFP+")
        checker = Checker()
        report = checker.run(ctx)
        compat = next((r for r in report.results if r.rule_id == "INTERFACE-COMPAT-001"), None)
        assert compat is not None
        assert compat.passed is True

    def test_incompatible_types_fail(self, tmp_path: Path) -> None:
        """SFP28 ↔ QSFP28 不兼容连接应失败。"""
        ctx = _make_ctx_with_connection(tmp_path, "SFP28", "QSFP28")
        checker = Checker()
        report = checker.run(ctx)
        compat = next((r for r in report.results if r.rule_id == "INTERFACE-COMPAT-001"), None)
        assert compat is not None
        assert compat.passed is False
        assert "不兼容" in compat.message

    def test_power_pair_passes(self, tmp_path: Path) -> None:
        """IEC-C14 ↔ IEC-C13 公母配对应通过。"""
        ctx = _make_ctx_with_connection(tmp_path, "IEC-C14", "IEC-C13")
        checker = Checker()
        report = checker.run(ctx)
        compat = next((r for r in report.results if r.rule_id == "INTERFACE-COMPAT-001"), None)
        assert compat is not None
        assert compat.passed is True

    def test_power_mismatch_fails(self, tmp_path: Path) -> None:
        """IEC-C14 ↔ IEC-C20 不兼容应失败。"""
        ctx = _make_ctx_with_connection(tmp_path, "IEC-C14", "IEC-C20")
        checker = Checker()
        report = checker.run(ctx)
        compat = next((r for r in report.results if r.rule_id == "INTERFACE-COMPAT-001"), None)
        assert compat is not None
        assert compat.passed is False

    def test_unknown_type_no_error(self, tmp_path: Path) -> None:
        """未知 interface_type 不阻断检查，仅记录 Warning。"""
        ctx = _make_ctx_with_connection(tmp_path, "CUSTOM-FOO", "SFP28")
        checker = Checker()
        report = checker.run(ctx)
        compat = next((r for r in report.results if r.rule_id == "INTERFACE-COMPAT-001"), None)
        assert compat is not None
        # 未知类型不做有罪推定
        assert compat.passed is True


class TestCableInterfaceMatch:
    """INTERFACE-CABLE-001 集成测试。"""

    def test_sfp28_with_om4_passes(self, tmp_path: Path) -> None:
        """SFP28 口配 OM4-LC-LC 光纤跳线应通过。"""
        ctx = _make_ctx_with_connection(tmp_path, "SFP28", "SFP28", "OM4-LC-LC")
        checker = Checker()
        report = checker.run(ctx)
        cable = next((r for r in report.results if r.rule_id == "INTERFACE-CABLE-001"), None)
        assert cable is not None
        assert cable.passed is True

    def test_sfp28_with_cat6a_fails(self, tmp_path: Path) -> None:
        """SFP28 口配 Cat6A 铜缆应失败。"""
        ctx = _make_ctx_with_connection(tmp_path, "SFP28", "SFP28", "Cat6A-RJ45")
        checker = Checker()
        report = checker.run(ctx)
        cable = next((r for r in report.results if r.rule_id == "INTERFACE-CABLE-001"), None)
        assert cable is not None
        assert cable.passed is False
        assert "线缆类型不匹配" in cable.message

    def test_iec_c14_with_power_cable_passes(self, tmp_path: Path) -> None:
        """IEC-C14 口配电源线应通过。"""
        ctx = _make_ctx_with_connection(tmp_path, "IEC-C14", "IEC-C14", "IEC-C13-C14-10A")
        checker = Checker()
        report = checker.run(ctx)
        cable = next((r for r in report.results if r.rule_id == "INTERFACE-CABLE-001"), None)
        assert cable is not None
        assert cable.passed is True

    def test_iec_c14_with_fiber_fails(self, tmp_path: Path) -> None:
        """IEC-C14 电源口配光纤跳线应失败。"""
        ctx = _make_ctx_with_connection(tmp_path, "IEC-C14", "IEC-C14", "OM4-LC-LC")
        checker = Checker()
        report = checker.run(ctx)
        cable = next((r for r in report.results if r.rule_id == "INTERFACE-CABLE-001"), None)
        assert cable is not None
        assert cable.passed is False

    def test_unknown_type_skipped(self, tmp_path: Path) -> None:
        """未知 interface_type 不校验 cable。"""
        ctx = _make_ctx_with_connection(tmp_path, "CUSTOM-TYPE", "CUSTOM-TYPE", "any-cable")
        checker = Checker()
        report = checker.run(ctx)
        cable = next((r for r in report.results if r.rule_id == "INTERFACE-CABLE-001"), None)
        assert cable is not None
        assert cable.passed is True  # 未知类型不校验
