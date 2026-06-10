"""Telecom 插件集成测试 —— 直接调用规则函数，不经过 CLI。"""

from __future__ import annotations

from pathlib import Path

import pytest

from piki.core.engine.checker import Checker
from piki.core.engine.context import Context
from piki.core.project import Project
from piki.core.engine.registry import Registry
from piki.extensions.telecom.plugin import (
    PduFamily,
    RackFamily,
    ServerFamily,
    TelecomPlugin,
    check_pdu_budget,
    check_rack_space,
)


@pytest.fixture
def telecom_ctx(tmp_path: Path) -> Context:
    """构造一个包含完整电信数据的 Context。"""
    registry = Registry()
    registry.add_family("RackFamily", RackFamily)
    registry.add_family("PduFamily", PduFamily)
    registry.add_family("ServerFamily", ServerFamily)

    # 型号库
    lib = tmp_path / "library" / "devices"
    lib.mkdir(parents=True)
    (lib / "generic-server.yaml").write_text(
        "model: generic-server\nfamily: ServerFamily\nheight_u: 2\ntdp_w: 300\n",
        encoding="utf-8",
    )
    registry.load_library(lib.parent)

    # 机柜
    racks = tmp_path / "racks"
    racks.mkdir()
    (racks / "RACK-A01.yaml").write_text(
        "id: RACK-A01\nfamily: RackFamily\ntotal_u: 42\n",
        encoding="utf-8",
    )
    registry.load_collection(racks)

    # PDU
    pdus = tmp_path / "pdus"
    pdus.mkdir()
    (pdus / "PDU-A.yaml").write_text(
        "id: PDU-A\nfamily: PduFamily\nrack_id: RACK-A01\ncapacity_w: 2000\n",
        encoding="utf-8",
    )
    (pdus / "PDU-B.yaml").write_text(
        "id: PDU-B\nfamily: PduFamily\nrack_id: RACK-A01\ncapacity_w: 2000\n",
        encoding="utf-8",
    )
    registry.load_collection(pdus)

    # 设备
    devices = tmp_path / "devices"
    devices.mkdir()
    (devices / "SRV-01.yaml").write_text(
        "id: SRV-01\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 10\npdu_id: PDU-A\n",
        encoding="utf-8",
    )
    (devices / "SRV-02.yaml").write_text(
        "id: SRV-02\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 8\npdu_id: PDU-A\ntdp_w: 250\n",
        encoding="utf-8",
    )
    registry.load_collection(devices)

    config = {"power_threshold": 0.4}
    return Context(registry, config)


class TestPduBudgetRule:
    """测试 PDU 功率预算规则。"""

    def test_passes_under_threshold(self, telecom_ctx: Context) -> None:
        # SRV-01: 300W, SRV-02: 250W -> 550W / 2000W = 27.5% < 40%
        check_pdu_budget(telecom_ctx)  # 不应抛异常

    def test_fails_over_threshold(self, telecom_ctx: Context, tmp_path: Path) -> None:
        # 添加一个 400W 设备到 PDU-A
        # 总功率: 300 + 250 + 400 = 950W / 2000W = 47.5% > 40%
        devices = tmp_path / "devices"
        (devices / "SRV-03.yaml").write_text(
            "id: SRV-03\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 6\npdu_id: PDU-A\ntdp_w: 400\n",
            encoding="utf-8",
        )
        telecom_ctx._registry.load_collection(devices)

        with pytest.raises(AssertionError, match="PDU-A 负载率 47.5%"):
            check_pdu_budget(telecom_ctx)

    def test_fails_missing_pdu(self, telecom_ctx: Context, tmp_path: Path) -> None:
        # 设备引用不存在的 PDU
        devices = tmp_path / "devices"
        (devices / "SRV-BAD.yaml").write_text(
            "id: SRV-BAD\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 1\npdu_id: PDU-Z\n",
            encoding="utf-8",
        )
        telecom_ctx._registry.load_collection(devices)

        with pytest.raises(AssertionError, match="PDU-Z 不存在"):
            check_pdu_budget(telecom_ctx)

    def test_pdu_b_still_ok(self, telecom_ctx: Context, tmp_path: Path) -> None:
        # 把超载设备放到 PDU-B（空载），应通过
        devices = tmp_path / "devices"
        (devices / "SRV-03.yaml").write_text(
            "id: SRV-03\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 6\npdu_id: PDU-B\ntdp_w: 400\n",
            encoding="utf-8",
        )
        telecom_ctx._registry.load_collection(devices)
        check_pdu_budget(telecom_ctx)  # 不应抛异常


class TestRackSpaceRule:
    """测试 U 位冲突规则。"""

    def test_passes_no_conflict(self, telecom_ctx: Context) -> None:
        # SRV-01: U10-U11, SRV-02: U8-U9 -> 不冲突
        check_rack_space(telecom_ctx)  # 不应抛异常

    def test_fails_conflict(self, telecom_ctx: Context, tmp_path: Path) -> None:
        # SRV-03 也放在 U10 -> 与 SRV-01 冲突
        devices = tmp_path / "devices"
        (devices / "SRV-03.yaml").write_text(
            "id: SRV-03\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 10\npdu_id: PDU-B\n",
            encoding="utf-8",
        )
        telecom_ctx._registry.load_collection(devices)

        with pytest.raises(AssertionError, match="U10-U11 冲突"):
            check_rack_space(telecom_ctx)

    def test_adjacent_no_conflict(self, telecom_ctx: Context, tmp_path: Path) -> None:
        # SRV-03 放在 U12 -> 与 SRV-01(U10-U11) 相邻但不冲突
        devices = tmp_path / "devices"
        (devices / "SRV-03.yaml").write_text(
            "id: SRV-03\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 12\npdu_id: PDU-B\n",
            encoding="utf-8",
        )
        telecom_ctx._registry.load_collection(devices)
        check_rack_space(telecom_ctx)  # 不应抛异常


class TestCheckerIntegration:
    """测试 Checker 运行 telecom 规则。"""

    def test_checker_runs_both_rules(self, telecom_ctx: Context) -> None:
        checker = Checker()
        checker.add_rule("TELECOM-POWER-001", "PDU 功率预算检查", check_pdu_budget, priority=10)
        checker.add_rule("TELECOM-RACK-001", "U 位冲突检查", check_rack_space, priority=5)

        report = checker.run(telecom_ctx)
        assert report.passed is True
        assert report.pass_count == 2
        assert report.error_count == 0

    def test_checker_reports_failure(self, telecom_ctx: Context, tmp_path: Path) -> None:
        # 制造 U 位冲突
        devices = tmp_path / "devices"
        (devices / "SRV-03.yaml").write_text(
            "id: SRV-03\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 10\npdu_id: PDU-B\n",
            encoding="utf-8",
        )
        telecom_ctx._registry.load_collection(devices)

        checker = Checker()
        checker.add_rule("TELECOM-POWER-001", "PDU 功率预算检查", check_pdu_budget, priority=10)
        checker.add_rule("TELECOM-RACK-001", "U 位冲突检查", check_rack_space, priority=5)

        report = checker.run(telecom_ctx)
        assert report.passed is False
        assert report.error_count == 1
        assert report.pass_count == 1
        assert "U10-U11 冲突" in report.results[1].message
