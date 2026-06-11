"""几何规则集成测试 —— 3D 碰撞检测。"""

from __future__ import annotations

from pathlib import Path

import pytest

from piki.core.engine.checker import Checker
from piki.core.engine.context import Context
from piki.core.engine.registry import Registry
from piki.extensions.datacenter.plugin import (
    ContainerFamily,
    EquipmentFamily,
    PowerUnitFamily,
    DatacenterPlugin,
    check_equipment_3d_collision,
)
from piki.extensions.telecom.plugin import (
    RackFamily,
    PduFamily,
    ServerFamily,
    TelecomPlugin,
    check_rack_3d_collision,
)


class TestDatacenter3DCollision:
    """测试方舱内设备 3D 碰撞检测。"""

    def test_no_collision_when_separated(self, tmp_path: Path) -> None:
        registry = Registry()
        registry.add_family("ContainerFamily", ContainerFamily)
        registry.add_family("EquipmentFamily", EquipmentFamily)
        registry.add_family("PowerUnitFamily", PowerUnitFamily)

        containers = tmp_path / "containers"
        containers.mkdir()
        (containers / "C1.yaml").write_text(
            "id: C1\nfamily: ContainerFamily\ncontainer_type: air-cooling\n"
            "length_mm: 10000\nwidth_mm: 5000\nheight_mm: 5000\n",
            encoding="utf-8",
        )
        registry.load_collection(containers)

        power = tmp_path / "power"
        power.mkdir()
        (power / "PU1.yaml").write_text(
            "id: PU1\nfamily: PowerUnitFamily\nunit_type: ups\n"
            "container_id: C1\ncapacity_kw: 100\n",
            encoding="utf-8",
        )
        registry.load_collection(power)

        equipment = tmp_path / "equipment"
        equipment.mkdir()
        # 设备 A 在 (0, 0, 0)
        (equipment / "A.yaml").write_text(
            "id: A\nfamily: EquipmentFamily\nequipment_type: compute\n"
            "container_id: C1\npower_unit_id: PU1\n"
            "length_mm: 1000\nwidth_mm: 500\nheight_mm: 500\n"
            "position_x_mm: 0\nposition_y_mm: 0\nposition_z_mm: 0\n",
            encoding="utf-8",
        )
        # 设备 B 在 (2000, 0, 0) —— 不重叠
        (equipment / "B.yaml").write_text(
            "id: B\nfamily: EquipmentFamily\nequipment_type: compute\n"
            "container_id: C1\npower_unit_id: PU1\n"
            "length_mm: 1000\nwidth_mm: 500\nheight_mm: 500\n"
            "position_x_mm: 2000\nposition_y_mm: 0\nposition_z_mm: 0\n",
            encoding="utf-8",
        )
        registry.load_collection(equipment)

        ctx = Context(registry, {})
        check_equipment_3d_collision(ctx)  # 不应抛异常

    def test_collision_when_overlapping(self, tmp_path: Path) -> None:
        registry = Registry()
        registry.add_family("ContainerFamily", ContainerFamily)
        registry.add_family("EquipmentFamily", EquipmentFamily)
        registry.add_family("PowerUnitFamily", PowerUnitFamily)

        containers = tmp_path / "containers"
        containers.mkdir()
        (containers / "C1.yaml").write_text(
            "id: C1\nfamily: ContainerFamily\ncontainer_type: air-cooling\n"
            "length_mm: 10000\nwidth_mm: 5000\nheight_mm: 5000\n",
            encoding="utf-8",
        )
        registry.load_collection(containers)

        power = tmp_path / "power"
        power.mkdir()
        (power / "PU1.yaml").write_text(
            "id: PU1\nfamily: PowerUnitFamily\nunit_type: ups\n"
            "container_id: C1\ncapacity_kw: 100\n",
            encoding="utf-8",
        )
        registry.load_collection(power)

        equipment = tmp_path / "equipment"
        equipment.mkdir()
        # 设备 A 在 (0, 0, 0)
        (equipment / "A.yaml").write_text(
            "id: A\nfamily: EquipmentFamily\nequipment_type: compute\n"
            "container_id: C1\npower_unit_id: PU1\n"
            "length_mm: 1000\nwidth_mm: 500\nheight_mm: 500\n"
            "position_x_mm: 0\nposition_y_mm: 0\nposition_z_mm: 0\n",
            encoding="utf-8",
        )
        # 设备 B 在 (100, 0, 0) —— 与 A 重叠
        (equipment / "B.yaml").write_text(
            "id: B\nfamily: EquipmentFamily\nequipment_type: compute\n"
            "container_id: C1\npower_unit_id: PU1\n"
            "length_mm: 1000\nwidth_mm: 500\nheight_mm: 500\n"
            "position_x_mm: 100\nposition_y_mm: 0\nposition_z_mm: 0\n",
            encoding="utf-8",
        )
        registry.load_collection(equipment)

        ctx = Context(registry, {})
        with pytest.raises(AssertionError, match="空间冲突"):
            check_equipment_3d_collision(ctx)

    def test_skips_no_dimensions(self, tmp_path: Path) -> None:
        registry = Registry()
        registry.add_family("ContainerFamily", ContainerFamily)
        registry.add_family("EquipmentFamily", EquipmentFamily)
        registry.add_family("PowerUnitFamily", PowerUnitFamily)

        containers = tmp_path / "containers"
        containers.mkdir()
        (containers / "C1.yaml").write_text(
            "id: C1\nfamily: ContainerFamily\ncontainer_type: air-cooling\n"
            "length_mm: 10000\nwidth_mm: 5000\nheight_mm: 5000\n",
            encoding="utf-8",
        )
        registry.load_collection(containers)

        power = tmp_path / "power"
        power.mkdir()
        (power / "PU1.yaml").write_text(
            "id: PU1\nfamily: PowerUnitFamily\nunit_type: ups\n"
            "container_id: C1\ncapacity_kw: 100\n",
            encoding="utf-8",
        )
        registry.load_collection(power)

        equipment = tmp_path / "equipment"
        equipment.mkdir()
        # 无尺寸信息的设备
        (equipment / "A.yaml").write_text(
            "id: A\nfamily: EquipmentFamily\nequipment_type: compute\n"
            "container_id: C1\npower_unit_id: PU1\n",
            encoding="utf-8",
        )
        registry.load_collection(equipment)

        ctx = Context(registry, {})
        check_equipment_3d_collision(ctx)  # 不应抛异常（跳过无尺寸设备）


class TestTelecom3DCollision:
    """测试机柜内设备 3D 碰撞检测。"""

    def test_no_collision_when_separated(self, tmp_path: Path) -> None:
        registry = Registry()
        registry.add_family("RackFamily", RackFamily)
        registry.add_family("PduFamily", PduFamily)
        registry.add_family("ServerFamily", ServerFamily)

        racks = tmp_path / "racks"
        racks.mkdir()
        (racks / "R1.yaml").write_text(
            "id: R1\nfamily: RackFamily\ntotal_u: 42\n",
            encoding="utf-8",
        )
        registry.load_collection(racks)

        pdus = tmp_path / "pdus"
        pdus.mkdir()
        (pdus / "PDU1.yaml").write_text(
            "id: PDU1\nfamily: PduFamily\nrack_id: R1\ncapacity_w: 2000\n",
            encoding="utf-8",
        )
        registry.load_collection(pdus)

        devices = tmp_path / "devices"
        devices.mkdir()
        # 两个设备在不同位置
        (devices / "S1.yaml").write_text(
            "id: S1\nfamily: ServerFamily\nrack_id: R1\nposition_u: 10\n"
            "pdu_id: PDU1\nheight_u: 2\n"
            "depth_mm: 700\nwidth_mm: 440\n"
            "position_x_mm: 0\nposition_y_mm: 0\nposition_z_mm: 0\n",
            encoding="utf-8",
        )
        (devices / "S2.yaml").write_text(
            "id: S2\nfamily: ServerFamily\nrack_id: R1\nposition_u: 20\n"
            "pdu_id: PDU1\nheight_u: 2\n"
            "depth_mm: 700\nwidth_mm: 440\n"
            "position_x_mm: 2000\nposition_y_mm: 0\nposition_z_mm: 0\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        ctx = Context(registry, {})
        check_rack_3d_collision(ctx)  # 不应抛异常

    def test_collision_when_overlapping(self, tmp_path: Path) -> None:
        registry = Registry()
        registry.add_family("RackFamily", RackFamily)
        registry.add_family("PduFamily", PduFamily)
        registry.add_family("ServerFamily", ServerFamily)

        racks = tmp_path / "racks"
        racks.mkdir()
        (racks / "R1.yaml").write_text(
            "id: R1\nfamily: RackFamily\ntotal_u: 42\n",
            encoding="utf-8",
        )
        registry.load_collection(racks)

        pdus = tmp_path / "pdus"
        pdus.mkdir()
        (pdus / "PDU1.yaml").write_text(
            "id: PDU1\nfamily: PduFamily\nrack_id: R1\ncapacity_w: 2000\n",
            encoding="utf-8",
        )
        registry.load_collection(pdus)

        devices = tmp_path / "devices"
        devices.mkdir()
        # 两个设备在同一位置 —— 重叠
        (devices / "S1.yaml").write_text(
            "id: S1\nfamily: ServerFamily\nrack_id: R1\nposition_u: 10\n"
            "pdu_id: PDU1\nheight_u: 2\n"
            "depth_mm: 700\nwidth_mm: 440\nheight_mm: 88\n"
            "position_x_mm: 0\nposition_y_mm: 0\nposition_z_mm: 0\n",
            encoding="utf-8",
        )
        (devices / "S2.yaml").write_text(
            "id: S2\nfamily: ServerFamily\nrack_id: R1\nposition_u: 12\n"
            "pdu_id: PDU1\nheight_u: 2\n"
            "depth_mm: 700\nwidth_mm: 440\nheight_mm: 88\n"
            "position_x_mm: 0\nposition_y_mm: 0\nposition_z_mm: 0\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        ctx = Context(registry, {})
        with pytest.raises(AssertionError, match="空间冲突"):
            check_rack_3d_collision(ctx)
