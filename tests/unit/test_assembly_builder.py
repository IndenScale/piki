"""AssemblyBuilder 单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from adl.geometry import AssemblyBuilder

from adl import ProjectLoader, TypeRegistry
from piki.extensions.assembly import AssemblyPartFamily


@pytest.fixture
def type_registry() -> TypeRegistry:
    reg = TypeRegistry()
    reg.add_family("AssemblyPartFamily", AssemblyPartFamily)
    return reg


def build_project(tmp_path: Path, registry: TypeRegistry) -> Path:
    """构造一个最小装配体项目：base + child 的 slot 配合。"""
    (tmp_path / "models").mkdir()
    (tmp_path / "models/base.yaml").write_text(
        "model: base\n"
        "family: AssemblyPartFamily\n"
        "name: Base\n"
        "width_mm: 100\n"
        "height_mm: 10\n"
        "depth_mm: 100\n"
        "interfaces:\n"
        "  - id: slot-1\n"
        "    interface_type: generic-slot\n"
        "    local_transform:\n"
        "      translation: [0, 5, 50]\n"
        "    mating_params:\n"
        "      slot_dir: [0, 0, -1]\n",
        encoding="utf-8",
    )
    (tmp_path / "models/child.yaml").write_text(
        "model: child\n"
        "family: AssemblyPartFamily\n"
        "name: Child\n"
        "width_mm: 20\n"
        "height_mm: 20\n"
        "depth_mm: 40\n"
        "interfaces:\n"
        "  - id: pin\n"
        "    interface_type: generic-slot\n"
        "    local_transform:\n"
        "      translation: [0, 0, -20]\n",
        encoding="utf-8",
    )

    (tmp_path / "instances" / "parts").mkdir(parents=True)
    (tmp_path / "instances/parts/BASE-01.yaml").write_text(
        "id: BASE-01\nmodel: base\n",
        encoding="utf-8",
    )
    (tmp_path / "instances/parts/CHILD-01.yaml").write_text(
        "id: CHILD-01\nmodel: child\n",
        encoding="utf-8",
    )

    (tmp_path / "layouts").mkdir(parents=True)
    (tmp_path / "layouts" / "layout.yaml").write_text(
        "entries:\n"
        "  - instance: BASE-01\n"
        "    position_x_mm: 0\n"
        "    position_y_mm: 0\n"
        "    position_z_mm: 0\n",
        encoding="utf-8",
    )

    (tmp_path / "mates" / "slot").mkdir(parents=True)
    (tmp_path / "mates/slot/base-child.yaml").write_text(
        "type: slot\n"
        "parent: BASE-01/slot-1\n"
        "child: CHILD-01/pin\n"
        "at:\n"
        "  t:\n"
        "    min: 0\n"
        "    max: 40\n"
        "    default: 10\n"
        "    step: 1\n",
        encoding="utf-8",
    )

    return tmp_path


class TestAssemblyBuilder:
    """测试 AssemblyBuilder 核心行为。"""

    def test_builds_entities(self, tmp_path: Path, type_registry: TypeRegistry) -> None:
        root = build_project(tmp_path, type_registry)
        project = ProjectLoader(root, type_registry).load()
        scene = AssemblyBuilder(project).build()

        assert len(scene.entities) == 2
        assert {e.id for e in scene.entities} == {"BASE-01", "CHILD-01"}

    def test_slot_mate_transform(self, tmp_path: Path, type_registry: TypeRegistry) -> None:
        """slot 配合应正确计算 child 全局位姿。"""
        root = build_project(tmp_path, type_registry)
        project = ProjectLoader(root, type_registry).load()
        scene = AssemblyBuilder(project).build()

        child = scene.entity_by_id("CHILD-01")
        assert child is not None
        # base 原点在 (0,0,0)，slot-1 在 (0,5,50)，pin 在 child 局部 (0,0,-20)
        # t=10 沿 -Z => child center = (0, 5, 50) + (0,0,-10) - (0,0,-20) = (0,5,60)
        assert child.transform.translation.x == pytest.approx(0.0)
        assert child.transform.translation.y == pytest.approx(5.0)
        assert child.transform.translation.z == pytest.approx(60.0)

    def test_extracts_controls(self, tmp_path: Path, type_registry: TypeRegistry) -> None:
        root = build_project(tmp_path, type_registry)
        project = ProjectLoader(root, type_registry).load()
        scene = AssemblyBuilder(project).build()

        assert len(scene.controls) == 1
        ctrl = scene.controls[0]
        assert ctrl.param == "t"
        assert ctrl.default == 10.0
        assert ctrl.min == 0.0
        assert ctrl.max == 40.0

    def test_no_collisions_in_simple_project(
        self, tmp_path: Path, type_registry: TypeRegistry
    ) -> None:
        root = build_project(tmp_path, type_registry)
        project = ProjectLoader(root, type_registry).load()
        scene = AssemblyBuilder(project).build()

        assert scene.collisions == []
        assert scene.diagnostics == []
