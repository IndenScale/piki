"""consumer-electronics KiCad importer 单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from piki.extensions.consumer_electronics.importer import (
    import_kicad_bom,
    import_kicad_netlist,
    import_kicad_pnp,
)


@pytest.fixture
def kicad_netlist(tmp_path: Path) -> Path:
    """构造一个最小 KiCad netlist XML。"""
    path = tmp_path / "keyboard.net"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<export version="D">
  <design>
    <source>keyboard.sch</source>
  </design>
  <components>
    <comp ref="J1">
      <value>USB-C</value>
      <footprint>Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12</footprint>
    </comp>
    <comp ref="C1">
      <value>10uF</value>
      <footprint>Capacitor_SMD:C_0603_1608Metric</footprint>
    </comp>
  </components>
  <nets>
    <net code="1" name="/VBUS">
      <node ref="J1" pin="1" pinfunction="VBUS" pintype="passive"/>
      <node ref="C1" pin="1" pinfunction="+" pintype="passive"/>
    </net>
    <net code="2" name="/GND">
      <node ref="J1" pin="A12" pinfunction="GND" pintype="passive"/>
      <node ref="C1" pin="2" pinfunction="-" pintype="passive"/>
    </net>
  </nets>
</export>
""",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def bom_csv(tmp_path: Path) -> Path:
    path = tmp_path / "bom.csv"
    path.write_text(
        "Ref,Value,Footprint\n"
        "J1,USB-C,Connector_USB:USB_C_Receptacle\n"
        "C1,10uF,Capacitor_SMD:C_0603\n"
        "R1,R10k,Resistor_SMD:R_0603\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def pnp_csv(tmp_path: Path) -> Path:
    path = tmp_path / "pnp.csv"
    path.write_text(
        "Ref,PosX,PosY,Rot,Side\nJ1,10.0,20.0,0.0,Top\nC1,15.0,25.0,90.0,Top\n",
        encoding="utf-8",
    )
    return path


class TestImportKicadNetlist:
    """测试 KiCad netlist 导入。"""

    def test_parses_nets(self, kicad_netlist: Path) -> None:
        nets = import_kicad_netlist(kicad_netlist)
        assert len(nets) == 2

    def test_net_nodes_format(self, kicad_netlist: Path) -> None:
        nets = import_kicad_netlist(kicad_netlist)
        vbus = next(n for n in nets if n["name"] == "/VBUS")
        assert "J1/1" in vbus["nodes"]
        assert "C1/1" in vbus["nodes"]

    def test_guesses_net_type(self, kicad_netlist: Path) -> None:
        nets = import_kicad_netlist(kicad_netlist)
        vbus = next(n for n in nets if n["name"] == "/VBUS")
        gnd = next(n for n in nets if n["name"] == "/GND")
        assert vbus["net_type"] == "power"
        assert gnd["net_type"] == "ground"

    def test_sanitizes_net_id(self, kicad_netlist: Path) -> None:
        nets = import_kicad_netlist(kicad_netlist)
        vbus = next(n for n in nets if n["name"] == "/VBUS")
        assert vbus["id"] == "NET-VBUS"


class TestImportKicadBom:
    """测试 KiCad BOM CSV 导入。"""

    def test_parses_components(self, bom_csv: Path) -> None:
        components = import_kicad_bom(bom_csv)
        assert len(components) == 3
        refs = {c["ref"] for c in components}
        assert refs == {"J1", "C1", "R1"}

    def test_multi_ref_cell(self, tmp_path: Path) -> None:
        path = tmp_path / "bom.csv"
        path.write_text(
            "Ref,Value,Footprint\n"
            "R1,R10k,Resistor_SMD:R_0603\n"
            '"R2,R3,R4",10k,Resistor_SMD:R_0603\n',
            encoding="utf-8",
        )
        components = import_kicad_bom(path)
        refs = [c["ref"] for c in components]
        assert refs == ["R1", "R2", "R3", "R4"]


class TestImportKicadPnp:
    """测试 KiCad pick-and-place CSV 导入。"""

    def test_parses_placements(self, pnp_csv: Path) -> None:
        placements = import_kicad_pnp(pnp_csv)
        assert len(placements) == 2
        j1 = next(p for p in placements if p["ref"] == "J1")
        assert j1["pos_x_mm"] == 10.0
        assert j1["pos_y_mm"] == 20.0
        assert j1["rotation_deg"] == 0.0
        assert j1["side"] == "Top"
