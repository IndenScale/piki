"""Datacenter 插件集成测试 —— 直接调用规则函数，不经过 CLI。"""

from __future__ import annotations

from pathlib import Path

import pytest

from piki.core.engine.checker import Checker
from piki.core.engine.context import Context
from piki.core.engine.registry import Registry
from piki.extensions.datacenter.plugin import (
    ConnectionFamily,
    ContainerFamily,
    EquipmentFamily,
    PowerUnitFamily,
    check_connection_capacity,
    check_container_power_budget,
    check_equipment_container_fit,
)


@pytest.fixture
def dc_ctx(tmp_path: Path) -> Context:
    """构造一个包含完整数据中心数据的 Context。"""
    registry = Registry()
    registry.add_family("ContainerFamily", ContainerFamily)
    registry.add_family("PowerUnitFamily", PowerUnitFamily)
    registry.add_family("EquipmentFamily", EquipmentFamily)
    registry.add_family("ConnectionFamily", ConnectionFamily)

    # 型号库
    lib = tmp_path / "models" / "equipment"
    lib.mkdir(parents=True)
    (lib / "gpu-server.yaml").write_text(
        "model: gpu-server\nfamily: EquipmentFamily\n"
        "equipment_type: compute\npower_kw: 12\nweight_kg: 85\n"
        "liquid_cooled: true\ncoolant_flow_lpm: 15\n"
        "length_mm: 900\nwidth_mm: 450\nheight_mm: 88\n",
        encoding="utf-8",
    )
    (lib / "cpu-server.yaml").write_text(
        "model: cpu-server\nfamily: EquipmentFamily\n"
        "equipment_type: compute\npower_kw: 3\nweight_kg: 25\n"
        "length_mm: 750\nwidth_mm: 440\nheight_mm: 44\n",
        encoding="utf-8",
    )
    registry.load_models(lib.parent)

    # 方舱型号库（物理尺寸在 Model 中，ADR-008）
    container_lib = tmp_path / "models" / "containers"
    container_lib.mkdir(parents=True)
    (container_lib / "liquid-40ft.yaml").write_text(
        "model: liquid-40ft\nfamily: ContainerFamily\n"
        "container_type: liquid-cooling\nstandard: 40ft\n"
        "length_mm: 12192\nwidth_mm: 2438\nheight_mm: 2896\n"
        "max_weight_kg: 30480\npower_capacity_kw: 500\n"
        "cooling_capacity_kw: 550\n",
        encoding="utf-8",
    )
    registry.load_models(container_lib.parent)

    # 方舱
    containers = tmp_path / "containers"
    containers.mkdir()
    (containers / "AI-LIQUID-01.yaml").write_text(
        "id: AI-LIQUID-01\nfamily: ContainerFamily\nmodel: liquid-40ft\n",
        encoding="utf-8",
    )
    registry.load_collection(containers)

    # 配电
    power = tmp_path / "power"
    power.mkdir()
    (power / "HVDC-MAIN.yaml").write_text(
        "id: HVDC-MAIN\nfamily: PowerUnitFamily\n"
        "unit_type: hvdc\ncontainer_id: AI-LIQUID-01\n"
        "capacity_kw: 500\nredundancy_n: 2\n",
        encoding="utf-8",
    )
    registry.load_collection(power)

    # 设备
    equipment = tmp_path / "equipment"
    equipment.mkdir()
    (equipment / "GPU-A01-01.yaml").write_text(
        "id: GPU-A01-01\nmodel: gpu-server\ncontainer_id: AI-LIQUID-01\npower_unit_id: HVDC-MAIN\n",
        encoding="utf-8",
    )
    (equipment / "CPU-G01-01.yaml").write_text(
        "id: CPU-G01-01\nmodel: cpu-server\ncontainer_id: AI-LIQUID-01\npower_unit_id: HVDC-MAIN\n",
        encoding="utf-8",
    )
    registry.load_collection(equipment)

    config = {"power_threshold": 0.85, "min_redundancy_n": 2}
    return Context(registry, config)


class TestEquipmentContainerFitRule:
    """测试方舱内设备空间边界规则。"""

    def test_passes_when_fits(self, dc_ctx: Context) -> None:
        # GPU 服务器 900x450x88 能装进 12192x2438x2896 的方舱
        check_equipment_container_fit(dc_ctx)  # 不应抛异常

    def test_skips_when_no_dimensions(self, dc_ctx: Context, tmp_path: Path) -> None:
        # 创建没有尺寸数据的设备
        registry = Registry()
        registry.add_family("ContainerFamily", ContainerFamily)
        registry.add_family("EquipmentFamily", EquipmentFamily)

        # 物理尺寸在 Model 中（ADR-008）
        clib = tmp_path / "clib2"
        clib.mkdir()
        (clib / "small-container.yaml").write_text(
            "model: small-container\nfamily: ContainerFamily\ncontainer_type: air-cooling\n"
            "length_mm: 1000\nwidth_mm: 1000\nheight_mm: 1000\n",
            encoding="utf-8",
        )
        registry.load_models(clib)
        containers = tmp_path / "containers2"
        containers.mkdir()
        (containers / "C1.yaml").write_text(
            "id: C1\nfamily: ContainerFamily\ncontainer_type: air-cooling\nmodel: small-container\n",
            encoding="utf-8",
        )
        registry.load_collection(containers)

        equipment = tmp_path / "equipment2"
        equipment.mkdir()
        (equipment / "E1.yaml").write_text(
            "id: E1\nfamily: EquipmentFamily\n"
            "equipment_type: compute\ncontainer_id: C1\npower_unit_id: PU1\n",
            encoding="utf-8",
        )
        registry.load_collection(equipment)

        ctx = Context(registry, {})
        check_equipment_container_fit(ctx)  # 不应抛异常（尺寸为 0，跳过）

    def test_fails_when_too_long(self, dc_ctx: Context, tmp_path: Path) -> None:
        # 创建设备长度超过方舱的场景
        base = tmp_path / "toolong"
        base.mkdir()

        registry = Registry()
        registry.add_family("ContainerFamily", ContainerFamily)
        registry.add_family("EquipmentFamily", EquipmentFamily)

        # 物理尺寸在 Model 中（ADR-008）
        clib = base / "clib"
        clib.mkdir()
        (clib / "small-container.yaml").write_text(
            "model: small-container\nfamily: ContainerFamily\ncontainer_type: air-cooling\n"
            "length_mm: 1000\nwidth_mm: 1000\nheight_mm: 1000\n",
            encoding="utf-8",
        )
        registry.load_models(clib)
        containers = base / "containers"
        containers.mkdir()
        (containers / "C1.yaml").write_text(
            "id: C1\nfamily: ContainerFamily\ncontainer_type: air-cooling\nmodel: small-container\n",
            encoding="utf-8",
        )
        registry.load_collection(containers)

        # 设备型号库（物理尺寸在 Model 中）
        elib = base / "elib"
        elib.mkdir()
        (elib / "long-server.yaml").write_text(
            "model: long-server\nfamily: EquipmentFamily\n"
            "equipment_type: compute\nlength_mm: 1500\nwidth_mm: 500\nheight_mm: 500\n",
            encoding="utf-8",
        )
        registry.load_models(elib)
        equipment = base / "equipment"
        equipment.mkdir()
        (equipment / "E1.yaml").write_text(
            "id: E1\nfamily: EquipmentFamily\n"
            "equipment_type: compute\ncontainer_id: C1\npower_unit_id: PU1\n"
            "model: long-server\n",
            encoding="utf-8",
        )
        registry.load_collection(equipment)

        ctx = Context(registry, {})
        with pytest.raises(AssertionError, match="长度 .* 超过方舱"):
            check_equipment_container_fit(ctx)


class TestConnectionCapacityRule:
    """测试连接容量规则。"""

    def test_passes_when_capacity_sufficient(self, dc_ctx: Context, tmp_path: Path) -> None:
        # 添加液冷连接，容量足够
        connections = tmp_path / "connections"
        connections.mkdir()
        (connections / "LIQUID-AI.yaml").write_text(
            "id: LIQUID-AI\nfamily: ConnectionFamily\n"
            "connection_type: liquid\nfrom_container: AI-LIQUID-01\n"
            "to_container: AI-LIQUID-01\ncapacity: 100\n",
            encoding="utf-8",
        )
        # 注意：from_container == to_container 会被 DC-CONN-001 拒绝
        # 创建两个不同的方舱
        registry = Registry()
        registry.add_family("ContainerFamily", ContainerFamily)
        registry.add_family("EquipmentFamily", EquipmentFamily)
        registry.add_family("ConnectionFamily", ConnectionFamily)

        # 物理尺寸在 Model 中（ADR-008）
        cc_lib = tmp_path / "cc_lib"
        cc_lib.mkdir()
        (cc_lib / "liquid-40ft.yaml").write_text(
            "model: liquid-40ft\nfamily: ContainerFamily\ncontainer_type: liquid-cooling\n"
            "length_mm: 12192\nwidth_mm: 2438\nheight_mm: 2896\n",
            encoding="utf-8",
        )
        registry.load_models(cc_lib)
        containers = tmp_path / "conn_containers"
        containers.mkdir()
        (containers / "C1.yaml").write_text(
            "id: C1\nfamily: ContainerFamily\ncontainer_type: liquid-cooling\nmodel: liquid-40ft\n",
            encoding="utf-8",
        )
        (containers / "C2.yaml").write_text(
            "id: C2\nfamily: ContainerFamily\ncontainer_type: liquid-cooling\nmodel: liquid-40ft\n",
            encoding="utf-8",
        )
        registry.load_collection(containers)

        equipment = tmp_path / "conn_equipment"
        equipment.mkdir()
        (equipment / "E1.yaml").write_text(
            "id: E1\nfamily: EquipmentFamily\n"
            "equipment_type: compute\ncontainer_id: C2\npower_unit_id: PU1\n"
            "liquid_cooled: true\ncoolant_flow_lpm: 15\n",
            encoding="utf-8",
        )
        registry.load_collection(equipment)

        connections_dir = tmp_path / "conn_connections"
        connections_dir.mkdir()
        (connections_dir / "CONN1.yaml").write_text(
            "id: CONN1\nfamily: ConnectionFamily\n"
            "connection_type: liquid\nfrom_container: C1\n"
            "to_container: C2\ncapacity: 20\n",
            encoding="utf-8",
        )
        registry.load_collection(connections_dir)

        ctx = Context(registry, {})
        check_connection_capacity(ctx)  # 容量 20 >= 需求 15，不应抛异常

    def test_fails_when_capacity_insufficient(self, dc_ctx: Context, tmp_path: Path) -> None:
        # 创建连接容量不足的场景
        # 注意：集合名必须是 "connections" 才能被 ctx.query("connections") 查到
        base = tmp_path / "insuf"
        base.mkdir()

        registry = Registry()
        registry.add_family("ContainerFamily", ContainerFamily)
        registry.add_family("EquipmentFamily", EquipmentFamily)
        registry.add_family("ConnectionFamily", ConnectionFamily)

        # 物理尺寸在 Model 中（ADR-008）
        ic_lib = base / "ic_lib"
        ic_lib.mkdir()
        (ic_lib / "liquid-40ft.yaml").write_text(
            "model: liquid-40ft\nfamily: ContainerFamily\ncontainer_type: liquid-cooling\n"
            "length_mm: 12192\nwidth_mm: 2438\nheight_mm: 2896\n",
            encoding="utf-8",
        )
        registry.load_models(ic_lib)
        containers = base / "containers"
        containers.mkdir()
        (containers / "C1.yaml").write_text(
            "id: C1\nfamily: ContainerFamily\ncontainer_type: liquid-cooling\nmodel: liquid-40ft\n",
            encoding="utf-8",
        )
        (containers / "C2.yaml").write_text(
            "id: C2\nfamily: ContainerFamily\ncontainer_type: liquid-cooling\nmodel: liquid-40ft\n",
            encoding="utf-8",
        )
        registry.load_collection(containers)

        equipment = base / "equipment"
        equipment.mkdir()
        (equipment / "E1.yaml").write_text(
            "id: E1\nfamily: EquipmentFamily\n"
            "equipment_type: compute\ncontainer_id: C2\npower_unit_id: PU1\n"
            "liquid_cooled: true\ncoolant_flow_lpm: 15\n",
            encoding="utf-8",
        )
        registry.load_collection(equipment)

        connections = base / "connections"
        connections.mkdir()
        (connections / "CONN1.yaml").write_text(
            "id: CONN1\nfamily: ConnectionFamily\n"
            "connection_type: liquid\nfrom_container: C1\n"
            "to_container: C2\ncapacity: 5\n",
            encoding="utf-8",
        )
        registry.load_collection(connections)

        ctx = Context(registry, {})
        with pytest.raises(AssertionError, match="容量 .* 小于"):
            check_connection_capacity(ctx)


class TestCheckerIntegration:
    """测试 Checker 运行 datacenter 规则。"""

    def test_checker_runs_rules(self, dc_ctx: Context) -> None:
        checker = Checker()
        checker.add_rule("DC-SPACE-001", "方舱空间边界", check_equipment_container_fit, priority=5)
        checker.add_rule("DC-POWER-001", "方舱功率预算", check_container_power_budget, priority=10)

        report = checker.run(dc_ctx)
        assert report.passed is True
        assert report.error_count == 0
