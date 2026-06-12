"""单元测试：Telecom 插件 Family Schema。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from piki.extensions.telecom.plugin import (
    FiberPatchCordFamily,
    PduFamily,
    PortConnectionFamily,
    PortFamily,
    RackFamily,
    ServerFamily,
    TransceiverFamily,
)


class TestPortFamily:
    """PortFamily Schema 校验。"""

    def test_minimal_valid_port(self) -> None:
        port = PortFamily(
            id="SRV-01-eth0",
            device_id="SRV-01",
            port_name="eth0",
            port_type="SFP28",
        )
        assert port.device_id == "SRV-01"
        assert port.port_name == "eth0"
        assert port.port_type == "SFP28"
        assert port.status == "planned"
        assert port.direction == "bidirectional"

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            PortFamily(id="SRV-01-eth0")

    def test_invalid_status(self) -> None:
        # status 是 str，没有枚举限制，任意字符串可过
        port = PortFamily(
            id="SRV-01-eth0",
            device_id="SRV-01",
            port_name="eth0",
            port_type="SFP28",
            status="retired",
        )
        assert port.status == "retired"


class TestPortConnectionFamily:
    """PortConnectionFamily Schema 校验。"""

    def test_minimal_valid_connection(self) -> None:
        conn = PortConnectionFamily(
            id="CONN-A-B",
            from_port="SRV-A/eth0",
            to_port="SRV-B/eth0",
        )
        assert conn.from_port == "SRV-A/eth0"
        assert conn.to_port == "SRV-B/eth0"
        assert conn.cable_type == ""
        assert conn.length_m == 0

    def test_full_connection(self) -> None:
        conn = PortConnectionFamily(
            id="CONN-A-B",
            from_port="SRV-A/eth0",
            to_port="SRV-B/eth0",
            cable_type="OM4-LC-LC",
            length_m=12.5,
            status="installed",
        )
        assert conn.cable_type == "OM4-LC-LC"
        assert conn.length_m == 12.5
        assert conn.status == "installed"

    def test_negative_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PortConnectionFamily(
                id="CONN-A-B",
                from_port="SRV-A/eth0",
                to_port="SRV-B/eth0",
                length_m=-1.0,
            )

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            PortConnectionFamily(id="CONN-A-B")


class TestExistingFamiliesStillValid:
    """确保新增 Family 不影响现有 Family Schema。"""

    def test_server_family(self) -> None:
        server = ServerFamily(id="SRV-01", model="generic-server")
        assert server.height_u == 2
        assert server.tdp_w == 300

    def test_pdu_family(self) -> None:
        pdu = PduFamily(id="PDU-A", capacity_w=2000)
        assert pdu.phase == "L1"

    def test_rack_family(self) -> None:
        rack = RackFamily(id="RACK-A01", total_u=42)
        assert rack.total_u == 42

    def test_transceiver_family(self) -> None:
        xcvr = TransceiverFamily(id="SFP-01", form_factor="SFP28")
        assert xcvr.speed_gbps == 25.0

    def test_fiber_patch_cord_family(self) -> None:
        fiber = FiberPatchCordFamily(id="FIBER-01")
        assert fiber.fiber_type == "OM4"
