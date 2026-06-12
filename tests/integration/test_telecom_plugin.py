"""Telecom 插件集成测试 —— 直接调用规则函数，不经过 CLI。"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from piki.core.engine.checker import Checker
from piki.core.engine.context import Context
from piki.core.engine.registry import Registry
from piki.extensions.telecom.plugin import (
    PduFamily,
    PortConnectionFamily,
    PortFamily,
    RackFamily,
    ServerFamily,
    check_connection_cable_match,
    check_connection_endpoints,
    check_connection_port_compat,
    check_device_physical_fit,
    check_pdu_budget,
    check_pdu_phase_balance,
    check_port_device_exists,
    check_port_occupancy,
    check_rack_space,
    generate_port_map,
)


@pytest.fixture
def telecom_ctx(tmp_path: Path) -> Context:
    """构造一个包含完整电信数据的 Context。"""
    registry = Registry()
    registry.add_family("RackFamily", RackFamily)
    registry.add_family("PduFamily", PduFamily)
    registry.add_family("ServerFamily", ServerFamily)

    # 型号库
    lib = tmp_path / "models" / "devices"
    lib.mkdir(parents=True)
    (lib / "generic-server.yaml").write_text(
        "model: generic-server\nfamily: ServerFamily\nheight_u: 2\ntdp_w: 300\n",
        encoding="utf-8",
    )
    registry.load_models(lib.parent)

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


class TestPduPhaseBalanceRule:
    """测试 PDU 相线平衡规则。"""

    def test_passes_single_phase(self, telecom_ctx: Context) -> None:
        # 只有 L1 相 PDU，不检查平衡
        check_pdu_phase_balance(telecom_ctx)  # 不应抛异常

    def test_passes_balanced_phases(self, telecom_ctx: Context, tmp_path: Path) -> None:
        # 创建全新的 registry 和 context，确保三相均衡
        # 使用 tmp_path 下的新子目录，避免与 fixture 的目录冲突
        base = tmp_path / "balanced"
        base.mkdir()

        registry = Registry()
        registry.add_family("RackFamily", RackFamily)
        registry.add_family("PduFamily", PduFamily)
        registry.add_family("ServerFamily", ServerFamily)

        lib = base / "models" / "devices"
        lib.mkdir(parents=True)
        (lib / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\nheight_u: 2\ntdp_w: 300\n",
            encoding="utf-8",
        )
        registry.load_models(lib.parent)

        racks = base / "racks"
        racks.mkdir()
        (racks / "RACK-A01.yaml").write_text(
            "id: RACK-A01\nfamily: RackFamily\ntotal_u: 42\n",
            encoding="utf-8",
        )
        registry.load_collection(racks)

        pdus = base / "pdus"
        pdus.mkdir()
        (pdus / "PDU-L1.yaml").write_text(
            "id: PDU-L1\nfamily: PduFamily\nrack_id: RACK-A01\nphase: L1\ncapacity_w: 2000\n",
            encoding="utf-8",
        )
        (pdus / "PDU-L2.yaml").write_text(
            "id: PDU-L2\nfamily: PduFamily\nrack_id: RACK-A01\nphase: L2\ncapacity_w: 2000\n",
            encoding="utf-8",
        )
        (pdus / "PDU-L3.yaml").write_text(
            "id: PDU-L3\nfamily: PduFamily\nrack_id: RACK-A01\nphase: L3\ncapacity_w: 2000\n",
            encoding="utf-8",
        )
        registry.load_collection(pdus)

        devices = base / "devices"
        devices.mkdir()
        # 三相各接一台 300W 设备，完全均衡
        (devices / "SRV-L1.yaml").write_text(
            "id: SRV-L1\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 10\npdu_id: PDU-L1\n",
            encoding="utf-8",
        )
        (devices / "SRV-L2.yaml").write_text(
            "id: SRV-L2\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 8\npdu_id: PDU-L2\n",
            encoding="utf-8",
        )
        (devices / "SRV-L3.yaml").write_text(
            "id: SRV-L3\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 6\npdu_id: PDU-L3\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        ctx = Context(registry, {"power_phase_imbalance_threshold": 0.15})
        check_pdu_phase_balance(ctx)  # 不应抛异常

    def test_fails_imbalanced_phases(self, telecom_ctx: Context, tmp_path: Path) -> None:
        # 创建全新场景：L1 满载，L2 空载
        base = tmp_path / "imbalanced"
        base.mkdir()

        registry = Registry()
        registry.add_family("RackFamily", RackFamily)
        registry.add_family("PduFamily", PduFamily)
        registry.add_family("ServerFamily", ServerFamily)

        lib = base / "models" / "devices"
        lib.mkdir(parents=True)
        (lib / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\nheight_u: 2\ntdp_w: 300\n",
            encoding="utf-8",
        )
        registry.load_models(lib.parent)

        racks = base / "racks"
        racks.mkdir()
        (racks / "RACK-A01.yaml").write_text(
            "id: RACK-A01\nfamily: RackFamily\ntotal_u: 42\n",
            encoding="utf-8",
        )
        registry.load_collection(racks)

        pdus = base / "pdus"
        pdus.mkdir()
        (pdus / "PDU-L1.yaml").write_text(
            "id: PDU-L1\nfamily: PduFamily\nrack_id: RACK-A01\nphase: L1\ncapacity_w: 2000\n",
            encoding="utf-8",
        )
        (pdus / "PDU-L2.yaml").write_text(
            "id: PDU-L2\nfamily: PduFamily\nrack_id: RACK-A01\nphase: L2\ncapacity_w: 2000\n",
            encoding="utf-8",
        )
        registry.load_collection(pdus)

        devices = base / "devices"
        devices.mkdir()
        # L1 接两台设备共 550W，L2 空载
        (devices / "SRV-01.yaml").write_text(
            "id: SRV-01\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 10\npdu_id: PDU-L1\n",
            encoding="utf-8",
        )
        (devices / "SRV-02.yaml").write_text(
            "id: SRV-02\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 8\npdu_id: PDU-L1\ntdp_w: 250\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        ctx = Context(registry, {})

        # 默认阈值 15%，L1=550W，L2=0W，不平衡度 = (550-0)/275 = 200% > 15%
        with pytest.raises(AssertionError, match="负载不平衡度"):
            check_pdu_phase_balance(ctx)


class TestDevicePhysicalFitRule:
    """测试设备物理尺寸与机柜匹配规则。"""

    def test_skips_when_no_dimensions(self, telecom_ctx: Context) -> None:
        # 默认机柜和设备都没有尺寸数据，应跳过
        check_device_physical_fit(telecom_ctx)  # 不应抛异常

    def test_passes_when_fits(self, telecom_ctx: Context, tmp_path: Path) -> None:
        # 物理尺寸应在 Model 中设置，不可被 Instance 覆盖（ADR-001）
        # 创建 rack model dir
        rack_models_dir = tmp_path / "models" / "racks"
        rack_models_dir.mkdir(parents=True)
        (rack_models_dir / "standard-rack.yaml").write_text(
            "model: standard-rack\nfamily: RackFamily\ndepth_mm: 1000\nwidth_mm: 600\n",
            encoding="utf-8",
        )
        telecom_ctx._registry.load_models(rack_models_dir.parent)

        racks = tmp_path / "racks"
        (racks / "RACK-A01.yaml").write_text(
            "id: RACK-A01\nfamily: RackFamily\nmodel: standard-rack\ntotal_u: 42\n",
            encoding="utf-8",
        )
        telecom_ctx._registry.load_collection(racks)

        check_device_physical_fit(telecom_ctx)  # 不应抛异常

    def test_fails_when_too_deep(self, telecom_ctx: Context, tmp_path: Path) -> None:
        # 设备深度超过机柜——物理尺寸在 Model 中（ADR-001）
        base = tmp_path / "toodeep"
        base.mkdir()

        registry = Registry()
        registry.add_family("RackFamily", RackFamily)
        registry.add_family("PduFamily", PduFamily)
        registry.add_family("ServerFamily", ServerFamily)

        lib = base / "models"
        lib.mkdir(parents=True)
        (lib / "devices" / "generic-server.yaml").parent.mkdir(parents=True, exist_ok=True)
        (lib / "devices" / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\nheight_u: 2\ntdp_w: 300\ndepth_mm: 715\nwidth_mm: 445\n",
            encoding="utf-8",
        )
        (lib / "racks" / "short-rack.yaml").parent.mkdir(parents=True, exist_ok=True)
        (lib / "racks" / "short-rack.yaml").write_text(
            "model: short-rack\nfamily: RackFamily\ndepth_mm: 500\nwidth_mm: 600\n",
            encoding="utf-8",
        )
        registry.load_models(lib)

        racks = base / "racks"
        racks.mkdir()
        (racks / "RACK-A01.yaml").write_text(
            "id: RACK-A01\nfamily: RackFamily\nmodel: short-rack\ntotal_u: 42\n",
            encoding="utf-8",
        )
        registry.load_collection(racks)

        pdus = base / "pdus"
        pdus.mkdir()
        (pdus / "PDU-A.yaml").write_text(
            "id: PDU-A\nfamily: PduFamily\nrack_id: RACK-A01\nphase: L1\ncapacity_w: 2000\n",
            encoding="utf-8",
        )
        registry.load_collection(pdus)

        devices = base / "devices"
        devices.mkdir()
        (devices / "SRV-01.yaml").write_text(
            "id: SRV-01\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 10\npdu_id: PDU-A\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        ctx = Context(registry, {})

        with pytest.raises(AssertionError, match="深度 .* 超过机柜"):
            check_device_physical_fit(ctx)


class TestCheckerIntegration:
    """测试 Checker 运行 telecom 规则。"""

    def test_checker_runs_both_rules(self, telecom_ctx: Context) -> None:
        checker = Checker()
        checker.add_rule("TELECOM-POWER-001", "PDU 功率预算检查", check_pdu_budget, priority=10)
        checker.add_rule("TELECOM-RACK-001", "U 位冲突检查", check_rack_space, priority=5)

        report = checker.run(telecom_ctx)
        assert report.passed is True
        assert report.pass_count == 10
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
        assert report.pass_count == 9
        rack_result = next((r for r in report.results if r.rule_id == "TELECOM-RACK-001"), None)
        assert rack_result is not None
        assert "U10-U11 冲突" in rack_result.message


class TestInterfaceCableRule:
    """测试 INTERFACE-CABLE-001：线缆类型与接口类型匹配。"""

    def _make_ctx(self, tmp_path: Path, cable_type: str) -> Context:
        registry = Registry()
        registry.add_family("ServerFamily", ServerFamily)

        class ConnectionFamily(BaseModel):
            id: str
            from_interface: str
            to_interface: str
            cable_type: str

        registry.add_family("ConnectionFamily", ConnectionFamily)

        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV-A.yaml").write_text(
            "id: SRV-A\nfamily: ServerFamily\ninterfaces:\n"
            "  - id: eth0\n    interface_type: SFP28\n",
            encoding="utf-8",
        )
        (devices / "SRV-B.yaml").write_text(
            "id: SRV-B\nfamily: ServerFamily\ninterfaces:\n"
            "  - id: eth0\n    interface_type: SFP28\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        connections = tmp_path / "connections"
        connections.mkdir()
        (connections / "CBL-AB.yaml").write_text(
            f"id: CBL-AB\nfamily: ConnectionFamily\n"
            f"from_interface: SRV-A/eth0\n"
            f"to_interface: SRV-B/eth0\n"
            f"cable_type: {cable_type}\n",
            encoding="utf-8",
        )
        registry.load_collection(connections)

        return Context(registry, {})

    def test_valid_fiber_cable_passes(self, tmp_path: Path) -> None:
        ctx = self._make_ctx(tmp_path, "OM4-LC-LC")
        checker = Checker()
        report = checker.run(ctx)
        assert report.passed is True
        assert report.error_count == 0

    def test_invalid_copper_cable_fails(self, tmp_path: Path) -> None:
        ctx = self._make_ctx(tmp_path, "Cat6A-RJ45")
        checker = Checker()
        report = checker.run(ctx)
        assert report.passed is False
        assert report.error_count == 1
        cable_result = next((r for r in report.results if r.rule_id == "INTERFACE-CABLE-001"), None)
        assert cable_result is not None
        assert "线缆类型不匹配" in cable_result.message
        assert "Cat6A-RJ45" in cable_result.message


class TestPortFamilyRule:
    """测试 TELECOM-PORT-001/002：端口占用与设备存在性。"""

    @pytest.fixture
    def port_ctx(self, tmp_path: Path) -> Context:
        registry = Registry()
        registry.add_family("RackFamily", RackFamily)
        registry.add_family("PduFamily", PduFamily)
        registry.add_family("ServerFamily", ServerFamily)
        registry.add_family("PortFamily", PortFamily)

        # 型号库
        lib = tmp_path / "models" / "devices"
        lib.mkdir(parents=True)
        (lib / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\nheight_u: 2\ntdp_w: 300\n",
            encoding="utf-8",
        )
        registry.load_models(lib.parent)

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
        registry.load_collection(pdus)

        # 设备
        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV-01.yaml").write_text(
            "id: SRV-01\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 10\npdu_id: PDU-A\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        # 端口
        ports = tmp_path / "ports"
        ports.mkdir()
        (ports / "SRV-01-eth0.yaml").write_text(
            "id: SRV-01-eth0\nfamily: PortFamily\ndevice_id: SRV-01\nport_name: eth0\nport_type: SFP28\n",
            encoding="utf-8",
        )
        (ports / "SRV-01-eth1.yaml").write_text(
            "id: SRV-01-eth1\nfamily: PortFamily\ndevice_id: SRV-01\nport_name: eth1\nport_type: SFP+\n",
            encoding="utf-8",
        )
        registry.load_collection(ports)

        return Context(registry, {})

    def test_passes_valid_ports(self, port_ctx: Context) -> None:
        check_port_occupancy(port_ctx)
        check_port_device_exists(port_ctx)

    def test_fails_duplicate_port_name(self, port_ctx: Context, tmp_path: Path) -> None:
        ports = tmp_path / "ports"
        (ports / "SRV-01-eth0-dup.yaml").write_text(
            "id: SRV-01-eth0-dup\nfamily: PortFamily\ndevice_id: SRV-01\nport_name: eth0\nport_type: SFP28\n",
            encoding="utf-8",
        )
        port_ctx._registry.load_collection(ports)

        with pytest.raises(AssertionError, match="端口 'eth0' 被重复定义"):
            check_port_occupancy(port_ctx)

    def test_fails_missing_device(self, port_ctx: Context, tmp_path: Path) -> None:
        ports = tmp_path / "ports"
        (ports / "BAD-PORT.yaml").write_text(
            "id: BAD-PORT\nfamily: PortFamily\ndevice_id: SRV-99\nport_name: eth0\nport_type: SFP28\n",
            encoding="utf-8",
        )
        port_ctx._registry.load_collection(ports)

        with pytest.raises(AssertionError, match="SRV-99 不存在"):
            check_port_device_exists(port_ctx)


class TestPortConnectionRule:
    """测试 TELECOM-CONN-001/002/003：连接端点、类型兼容、线缆匹配。"""

    @pytest.fixture
    def conn_ctx(self, tmp_path: Path) -> Context:
        registry = Registry()
        registry.add_family("RackFamily", RackFamily)
        registry.add_family("PduFamily", PduFamily)
        registry.add_family("ServerFamily", ServerFamily)
        registry.add_family("PortFamily", PortFamily)
        registry.add_family("PortConnectionFamily", PortConnectionFamily)

        # 型号库
        lib = tmp_path / "models" / "devices"
        lib.mkdir(parents=True)
        (lib / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\nheight_u: 2\ntdp_w: 300\n",
            encoding="utf-8",
        )
        registry.load_models(lib.parent)

        # 机柜 + PDU + 设备
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
            "id: PDU-A\nfamily: PduFamily\nrack_id: RACK-A01\ncapacity_w: 2000\n",
            encoding="utf-8",
        )
        registry.load_collection(pdus)

        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV-A.yaml").write_text(
            "id: SRV-A\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 10\npdu_id: PDU-A\n",
            encoding="utf-8",
        )
        (devices / "SRV-B.yaml").write_text(
            "id: SRV-B\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 8\npdu_id: PDU-A\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        # 端口
        ports = tmp_path / "ports"
        ports.mkdir()
        (ports / "SRV-A-eth0.yaml").write_text(
            "id: SRV-A-eth0\nfamily: PortFamily\ndevice_id: SRV-A\nport_name: eth0\nport_type: SFP28\n",
            encoding="utf-8",
        )
        (ports / "SRV-B-eth0.yaml").write_text(
            "id: SRV-B-eth0\nfamily: PortFamily\ndevice_id: SRV-B\nport_name: eth0\nport_type: SFP28\n",
            encoding="utf-8",
        )
        (ports / "SRV-B-eth1.yaml").write_text(
            "id: SRV-B-eth1\nfamily: PortFamily\ndevice_id: SRV-B\nport_name: eth1\nport_type: RJ45\n",
            encoding="utf-8",
        )
        registry.load_collection(ports)

        # 连接
        conns = tmp_path / "port_connections"
        conns.mkdir()
        (conns / "CONN-A-B.yaml").write_text(
            "id: CONN-A-B\nfamily: PortConnectionFamily\n"
            "from_port: SRV-A/eth0\nto_port: SRV-B/eth0\n"
            "cable_type: OM4-LC-LC\nlength_m: 2.0\n",
            encoding="utf-8",
        )
        registry.load_collection(conns)

        return Context(registry, {})

    def test_passes_valid_connection(self, conn_ctx: Context) -> None:
        check_connection_endpoints(conn_ctx)
        check_connection_port_compat(conn_ctx)
        check_connection_cable_match(conn_ctx)

    def test_fails_missing_endpoint(self, conn_ctx: Context, tmp_path: Path) -> None:
        conns = tmp_path / "port_connections"
        (conns / "CONN-BAD.yaml").write_text(
            "id: CONN-BAD\nfamily: PortConnectionFamily\n"
            "from_port: SRV-A/eth0\nto_port: SRV-B/missing\n",
            encoding="utf-8",
        )
        conn_ctx._registry.load_collection(conns)

        with pytest.raises(AssertionError, match="引用端口 .* 不存在"):
            check_connection_endpoints(conn_ctx)

    def test_fails_incompatible_port_types(self, conn_ctx: Context, tmp_path: Path) -> None:
        conns = tmp_path / "port_connections"
        (conns / "CONN-BAD.yaml").write_text(
            "id: CONN-BAD\nfamily: PortConnectionFamily\n"
            "from_port: SRV-A/eth0\nto_port: SRV-B/eth1\n",
            encoding="utf-8",
        )
        conn_ctx._registry.load_collection(conns)

        with pytest.raises(AssertionError, match="端口类型不兼容"):
            check_connection_port_compat(conn_ctx)

    def test_fails_invalid_cable_type(self, conn_ctx: Context, tmp_path: Path) -> None:
        conns = tmp_path / "port_connections"
        (conns / "CONN-BAD.yaml").write_text(
            "id: CONN-BAD\nfamily: PortConnectionFamily\n"
            "from_port: SRV-A/eth0\nto_port: SRV-B/eth0\n"
            "cable_type: Cat6A-RJ45\n",
            encoding="utf-8",
        )
        conn_ctx._registry.load_collection(conns)

        with pytest.raises(AssertionError, match="线缆类型不匹配"):
            check_connection_cable_match(conn_ctx)


class TestPortMapGenerator:
    """测试 port-map 生成器。"""

    def test_generates_port_map_csv(self, tmp_path: Path) -> None:
        registry = Registry()
        registry.add_family("RackFamily", RackFamily)
        registry.add_family("PduFamily", PduFamily)
        registry.add_family("ServerFamily", ServerFamily)
        registry.add_family("PortFamily", PortFamily)
        registry.add_family("PortConnectionFamily", PortConnectionFamily)

        # 型号库
        lib = tmp_path / "models" / "devices"
        lib.mkdir(parents=True)
        (lib / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\nheight_u: 2\ntdp_w: 300\n",
            encoding="utf-8",
        )
        registry.load_models(lib.parent)

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
            "id: PDU-A\nfamily: PduFamily\nrack_id: RACK-A01\ncapacity_w: 2000\n",
            encoding="utf-8",
        )
        registry.load_collection(pdus)

        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV-A.yaml").write_text(
            "id: SRV-A\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 10\npdu_id: PDU-A\n",
            encoding="utf-8",
        )
        (devices / "SRV-B.yaml").write_text(
            "id: SRV-B\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 8\npdu_id: PDU-A\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        ports = tmp_path / "ports"
        ports.mkdir()
        (ports / "SRV-A-eth0.yaml").write_text(
            "id: SRV-A-eth0\nfamily: PortFamily\ndevice_id: SRV-A\nport_name: eth0\nport_type: SFP28\n",
            encoding="utf-8",
        )
        (ports / "SRV-B-eth0.yaml").write_text(
            "id: SRV-B-eth0\nfamily: PortFamily\ndevice_id: SRV-B\nport_name: eth0\nport_type: SFP28\n",
            encoding="utf-8",
        )
        registry.load_collection(ports)

        conns = tmp_path / "port_connections"
        conns.mkdir()
        (conns / "CONN-A-B.yaml").write_text(
            "id: CONN-A-B\nfamily: PortConnectionFamily\n"
            "from_port: SRV-A/eth0\nto_port: SRV-B/eth0\n"
            "cable_type: OM4-LC-LC\nlength_m: 2.0\n",
            encoding="utf-8",
        )
        registry.load_collection(conns)

        ctx = Context(registry, {})
        result = generate_port_map(ctx, {})

        assert result.success is True
        assert "SRV-A-eth0" in result.content
        assert "SRV-B-eth0" in result.content
        assert "OM4-LC-LC" in result.content
        assert "2.0" in result.content
