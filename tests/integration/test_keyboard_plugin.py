"""Keyboard 插件集成测试 —— 直接调用规则函数，不经过 CLI。"""

from __future__ import annotations

from pathlib import Path

import pytest

from piki.core.engine.checker import Checker
from piki.core.engine.context import Context
from piki.core.engine.registry import Registry
from piki.extensions.consumer_electronics.plugin import (
    ConsumerElectronicsPlugin,
)
from piki.extensions.keyboard.plugin import (
    KeyboardPlugin,
    check_battery_capacity,
    check_current_budget,
    check_key_cluster_count,
    check_key_cluster_matrix_bounds,
    check_keyboard_sub_assemblies,
    check_keycap_stem_compatibility,
    check_mounting_style_consistency,
    check_switch_pcb_pin_compatibility,
    check_switch_plate_cutout_compatibility,
    check_usb_cable_match,
    check_wireless_antenna,
    generate_keyboard_bom_csv,
)


@pytest.fixture
def keyboard_ctx(tmp_path: Path) -> Context:
    """构造一个包含完整键盘数据的 Context。"""
    registry = Registry()

    keyboard_plugin = KeyboardPlugin()
    keyboard_plugin.register_families(registry)
    ce_plugin = ConsumerElectronicsPlugin()
    ce_plugin.register_families(registry)

    # 型号库
    models = tmp_path / "models"
    models.mkdir()
    (models / "gateron-yellow-pro.yaml").write_text(
        "model: gateron-yellow-pro\nfamily: SwitchFamily\n"
        "manufacturer: gateron\nstem_type: mx\npin_count: 5\n",
        encoding="utf-8",
    )
    (models / "pbt-dye-sub-oem-65.yaml").write_text(
        "model: pbt-dye-sub-oem-65\nfamily: KeycapFamily\n"
        "material: pbt\nprofile: oem\nstem_mount: mx\n",
        encoding="utf-8",
    )
    (models / "aluminum-65.yaml").write_text(
        "model: aluminum-65\nfamily: CaseFamily\n"
        "case_type: aluminum\nmounting_style: gasket\n"
        "length_mm: 320\nwidth_mm: 112\nheight_mm: 35\n"
        "wall_thickness_mm: 3.0\nhas_antenna_aperture: true\n",
        encoding="utf-8",
    )
    (models / "pc-65.yaml").write_text(
        "model: pc-65\nfamily: PlateFamily\n"
        "material: pc\nthickness_mm: 1.5\nlayout: 65%\n"
        "switch_cutout_type: mx\nmounting_style: gasket\n",
        encoding="utf-8",
    )
    (models / "rp2040-wireless-65.yaml").write_text(
        "model: rp2040-wireless-65\nfamily: PcbFamily\n"
        "controller: rp2040\nmatrix_rows: 5\nmatrix_cols: 16\n"
        "switch_footprint: hotswap-mx\nled_support: true\nwireless: true\n"
        "usb_connector_type: usb-c\nmax_usb_current_ma: 500\n",
        encoding="utf-8",
    )
    (models / "li-po-4000.yaml").write_text(
        "model: li-po-4000\nfamily: BatteryFamily\n"
        "capacity_mah: 4000\nmax_discharge_current_ma: 2000\n",
        encoding="utf-8",
    )
    (models / "usb-c-coiled.yaml").write_text(
        "model: usb-c-coiled\nfamily: CableFamily\nconnector_type: usb-c\ncable_type: coiled\n",
        encoding="utf-8",
    )
    registry.load_models(models)

    # Assembly
    assemblies = tmp_path / "assembly"
    assemblies.mkdir()
    (assemblies / "KB-MAIN.yaml").write_text(
        "id: KB-MAIN\nfamily: KeyboardAssemblyFamily\n"
        "layout: 65%\nkey_count: 8\nconnectivity: [usb, bluetooth, 2.4g]\n"
        "mounting_style: gasket\nwireless: true\nled_support: true\n"
        "case_id: CASE-01\nplate_id: PLATE-01\npcb_id: PCB-01\n"
        "battery_id: BATT-01\ncable_id: CABLE-01\n",
        encoding="utf-8",
    )
    registry.load_collection(assemblies)

    # Cases
    cases = tmp_path / "cases"
    cases.mkdir()
    (cases / "CASE-01.yaml").write_text(
        "id: CASE-01\nmodel: aluminum-65\n",
        encoding="utf-8",
    )
    registry.load_collection(cases)

    # Plates
    plates = tmp_path / "plates"
    plates.mkdir()
    (plates / "PLATE-01.yaml").write_text("id: PLATE-01\nmodel: pc-65\n", encoding="utf-8")
    registry.load_collection(plates)

    # PCBs
    pcbs = tmp_path / "pcbs"
    pcbs.mkdir()
    (pcbs / "PCB-01.yaml").write_text(
        "id: PCB-01\nmodel: rp2040-wireless-65\n",
        encoding="utf-8",
    )
    registry.load_collection(pcbs)

    # Switches
    switches = tmp_path / "switches"
    switches.mkdir()
    (switches / "SW-A.yaml").write_text(
        "id: SW-A\nmodel: gateron-yellow-pro\n",
        encoding="utf-8",
    )
    registry.load_collection(switches)

    # Keycaps
    keycaps = tmp_path / "keycaps"
    keycaps.mkdir()
    (keycaps / "KC-A.yaml").write_text(
        "id: KC-A\nmodel: pbt-dye-sub-oem-65\n",
        encoding="utf-8",
    )
    registry.load_collection(keycaps)

    # Battery
    batteries = tmp_path / "batteries"
    batteries.mkdir()
    (batteries / "BATT-01.yaml").write_text("id: BATT-01\nmodel: li-po-4000\n", encoding="utf-8")
    registry.load_collection(batteries)

    # Cable
    cables = tmp_path / "cables"
    cables.mkdir()
    (cables / "CABLE-01.yaml").write_text("id: CABLE-01\nmodel: usb-c-coiled\n", encoding="utf-8")
    registry.load_collection(cables)

    # Mates
    mates = tmp_path / "mates"
    mates.mkdir()
    (mates / "switch-plate-snap").mkdir()
    (mates / "switch-plate-snap" / "PLATE-01-SW-A.yaml").write_text(
        "type: switch-plate-snap\nparent: PLATE-01\nchild: SW-A\n",
        encoding="utf-8",
    )
    (mates / "switch-pcb-solder").mkdir()
    (mates / "switch-pcb-solder" / "PCB-01-SW-A.yaml").write_text(
        "type: switch-pcb-solder\nparent: PCB-01\nchild: SW-A\n",
        encoding="utf-8",
    )
    (mates / "keycap-stem-mount").mkdir()
    (mates / "keycap-stem-mount" / "SW-A-KC-A.yaml").write_text(
        "type: keycap-stem-mount\nparent: SW-A\nchild: KC-A\n",
        encoding="utf-8",
    )
    (mates / "usb-cable-mate").mkdir()
    (mates / "usb-cable-mate" / "PCB-01-CABLE-01.yaml").write_text(
        "type: usb-cable-mate\nparent: PCB-01\nchild: CABLE-01\n",
        encoding="utf-8",
    )
    registry.load_mates(tmp_path)

    config = {
        "min_wireless_runtime_hours": 30,
        "switch_active_ma": 0.1,
        "led_full_brightness_ma": 20.0,
        "led_brightness_pct": 50.0,
        "controller_active_ma": 15.0,
        "controller_sleep_ma": 0.05,
        "wireless_extra_ma": 5.0,
        "active_duty_cycle_pct": 10.0,
    }
    return Context(registry, config)


class TestKeyboardBasicRules:
    """测试键盘基础规则。"""

    def test_stem_compatibility_passes(self, keyboard_ctx: Context) -> None:
        check_keycap_stem_compatibility(keyboard_ctx)

    def test_switch_pcb_pin_compatibility_passes(self, keyboard_ctx: Context) -> None:
        check_switch_pcb_pin_compatibility(keyboard_ctx)

    def test_switch_plate_cutout_passes(self, keyboard_ctx: Context) -> None:
        check_switch_plate_cutout_compatibility(keyboard_ctx)

    def test_mounting_style_consistency_passes(self, keyboard_ctx: Context) -> None:
        check_mounting_style_consistency(keyboard_ctx)

    def test_wireless_antenna_passes(self, keyboard_ctx: Context) -> None:
        check_wireless_antenna(keyboard_ctx)

    def test_usb_cable_match_passes(self, keyboard_ctx: Context) -> None:
        check_usb_cable_match(keyboard_ctx)


class TestKeyboardPowerRules:
    """测试键盘电源规则。"""

    def test_battery_capacity_passes(self, keyboard_ctx: Context) -> None:
        check_battery_capacity(keyboard_ctx)

    def test_current_budget_passes(self, keyboard_ctx: Context) -> None:
        check_current_budget(keyboard_ctx)

    def test_fails_when_battery_too_small(self, keyboard_ctx: Context, tmp_path: Path) -> None:
        batteries = tmp_path / "batteries"
        (batteries / "BATT-TINY.yaml").write_text(
            "id: BATT-TINY\nfamily: BatteryFamily\ncapacity_mah: 10\n"
            "max_discharge_current_ma: 500\nvoltage_v: 3.7\n",
            encoding="utf-8",
        )
        keyboard_ctx._registry.load_collection(batteries)

        assemblies = tmp_path / "assembly"
        assemblies.mkdir(exist_ok=True)
        (assemblies / "KB-TINY.yaml").write_text(
            "id: KB-TINY\nfamily: KeyboardAssemblyFamily\n"
            "layout: 65%\nkey_count: 8\nconnectivity: [bluetooth]\n"
            "mounting_style: gasket\nwireless: true\nled_support: false\n"
            "battery_id: BATT-TINY\n",
            encoding="utf-8",
        )
        keyboard_ctx._registry.load_collection(assemblies)

        with pytest.raises(AssertionError, match="低于项目要求"):
            check_battery_capacity(keyboard_ctx)


class TestKeyboardAssemblyRule:
    """测试子装配体规则。"""

    def test_sub_assembly_must_exist(self, keyboard_ctx: Context, tmp_path: Path) -> None:
        assemblies = tmp_path / "assembly"
        assemblies.mkdir(exist_ok=True)
        (assemblies / "KB-BAD.yaml").write_text(
            "id: KB-BAD\nfamily: KeyboardAssemblyFamily\n"
            "layout: 65%\nkey_count: 1\nconnectivity: [usb]\n"
            "mounting_style: gasket\nsub_assemblies: [MISSING]\n",
            encoding="utf-8",
        )
        keyboard_ctx._registry.load_collection(assemblies)

        with pytest.raises(AssertionError, match="子装配体 MISSING 不存在"):
            check_keyboard_sub_assemblies(keyboard_ctx)

    def test_sub_assembly_must_be_assembly_family(
        self, keyboard_ctx: Context, tmp_path: Path
    ) -> None:
        assemblies = tmp_path / "assembly"
        assemblies.mkdir(exist_ok=True)
        (assemblies / "KB-BAD.yaml").write_text(
            "id: KB-BAD\nfamily: KeyboardAssemblyFamily\n"
            "layout: 65%\nkey_count: 1\nconnectivity: [usb]\n"
            "mounting_style: gasket\nsub_assemblies: [CASE-01]\n",
            encoding="utf-8",
        )
        keyboard_ctx._registry.load_collection(assemblies)

        with pytest.raises(AssertionError, match="不是装配体"):
            check_keyboard_sub_assemblies(keyboard_ctx)


class TestKeyClusterRules:
    """测试 KeyCluster 规则。"""

    def test_cluster_count_mismatch_fails(self, keyboard_ctx: Context, tmp_path: Path) -> None:
        clusters = tmp_path / "key_clusters"
        clusters.mkdir()
        (clusters / "BAD.yaml").write_text(
            "id: BAD\nfamily: KeyClusterFamily\n"
            "switch_model: gateron-yellow-pro\nkeycap_model: pbt-dye-sub-oem-65\n"
            "key_count: 3\nmatrix_positions:\n"
            "  - {row: 0, col: 1}\n  - {row: 0, col: 2}\n",
            encoding="utf-8",
        )
        keyboard_ctx._registry.load_collection(clusters)

        with pytest.raises(AssertionError, match="key_count=3 与 matrix_positions 数量 2"):
            check_key_cluster_count(keyboard_ctx)

    def test_cluster_matrix_bounds_fails(self, keyboard_ctx: Context, tmp_path: Path) -> None:
        clusters = tmp_path / "key_clusters"
        clusters.mkdir()
        (clusters / "BAD.yaml").write_text(
            "id: BAD\nfamily: KeyClusterFamily\n"
            "switch_model: gateron-yellow-pro\nkeycap_model: pbt-dye-sub-oem-65\n"
            "key_count: 1\nmatrix_positions:\n  - {row: 10, col: 0}\n",
            encoding="utf-8",
        )
        keyboard_ctx._registry.load_collection(clusters)

        with pytest.raises(AssertionError, match="row=10 超出 PCB"):
            check_key_cluster_matrix_bounds(keyboard_ctx)


class TestCheckerIntegration:
    """测试 Checker 运行 keyboard 规则。"""

    def test_checker_runs_keyboard_rules(self, keyboard_ctx: Context) -> None:
        checker = Checker()
        checker.add_rule("KB-STEM-001", "键帽 stem", check_keycap_stem_compatibility)
        checker.add_rule("KB-MOUNT-001", "安装方式", check_mounting_style_consistency)
        checker.add_rule("KB-CURRENT-001", "电流", check_current_budget)

        report = checker.run(keyboard_ctx)
        assert report.passed is True
        assert report.error_count == 0


class TestBomGenerator:
    """测试 BOM 生成器。"""

    def test_generates_bom(self, keyboard_ctx: Context) -> None:
        result = generate_keyboard_bom_csv(keyboard_ctx, {})
        assert result.success is True
        assert "KB-MAIN" in result.content
        assert "SWITCH-ALL" in result.content
        assert "KEYCAP-ALL" in result.content
