"""AssemblyFamily 与层级遍历单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from piki.core.engine.context import Context
from piki.core.engine.registry import Registry
from piki.core.models.assembly import AssemblyFamily


@pytest.fixture
def assembly_ctx(tmp_path: Path) -> Context:
    """构造一个带装配层级和 Mate 的 Context。

    结构：
        KB-MAIN (KeyboardAssemblyFamily)
        ├── PLATE-01 (PlateFamily)
        │   └── SW-A (SwitchFamily)
        └── PCB-01 (PcbFamily)
    """

    class PlateFamily(BaseModel):
        id: str
        material: str

    class PcbFamily(BaseModel):
        id: str
        controller: str

    class SwitchFamily(BaseModel):
        id: str
        stem_type: str

    registry = Registry()
    registry.add_family("AssemblyFamily", AssemblyFamily)
    registry.add_family("PlateFamily", PlateFamily)
    registry.add_family("PcbFamily", PcbFamily)
    registry.add_family("SwitchFamily", SwitchFamily)

    assemblies = tmp_path / "assemblies"
    assemblies.mkdir()
    (assemblies / "KB-MAIN.yaml").write_text(
        "id: KB-MAIN\nfamily: AssemblyFamily\nchildren:\n  - PLATE-01\n  - PCB-01\n",
        encoding="utf-8",
    )
    registry.load_collection(assemblies)

    plates = tmp_path / "plates"
    plates.mkdir()
    (plates / "PLATE-01.yaml").write_text(
        "id: PLATE-01\nfamily: PlateFamily\nmaterial: pc\n",
        encoding="utf-8",
    )
    registry.load_collection(plates)

    pcbs = tmp_path / "pcbs"
    pcbs.mkdir()
    (pcbs / "PCB-01.yaml").write_text(
        "id: PCB-01\nfamily: PcbFamily\ncontroller: rp2040\n",
        encoding="utf-8",
    )
    registry.load_collection(pcbs)

    switches = tmp_path / "switches"
    switches.mkdir()
    (switches / "SW-A.yaml").write_text(
        "id: SW-A\nfamily: SwitchFamily\nstem_type: mx\n",
        encoding="utf-8",
    )
    registry.load_collection(switches)

    # Mates
    mates = tmp_path / "mates" / "switch-plate-snap"
    mates.mkdir(parents=True)
    (mates / "PLATE-01-SW-A.yaml").write_text(
        "type: switch-plate-snap\nparent: PLATE-01\nchild: SW-A\n",
        encoding="utf-8",
    )
    registry.load_mates(tmp_path)

    return Context(registry, {})


class TestAssemblyFamily:
    """测试核心 AssemblyFamily。"""

    def test_basic_fields(self) -> None:
        asm = AssemblyFamily(id="A1", name="sub-assy", children=["C1", "C2"])
        assert asm.id == "A1"
        assert asm.children == ["C1", "C2"]
        assert asm.sub_assemblies == []

    def test_inheritance(self) -> None:
        """AssemblyFamily 可作为插件 Family 的基类。"""

        class SubAssembly(AssemblyFamily):
            custom_field: str

        sub = SubAssembly(id="S1", custom_field="x", children=["C1"])
        assert sub.id == "S1"
        assert sub.custom_field == "x"
        assert sub.children == ["C1"]


class TestMatedDescendants:
    """测试 Context.mated_descendants 层级遍历。"""

    def test_direct_children(self, assembly_ctx: Context) -> None:
        # KB-MAIN 通过 children 字段引用 PLATE-01 和 PCB-01，但没有 Mate
        # 所以 mated_descendants 只看 Mate 图，这里应该是空
        assert assembly_ctx.mated_descendants("KB-MAIN") == []

    def test_recursive_descendants_via_mate(self, assembly_ctx: Context) -> None:
        # PLATE-01 通过 Mate 承载 SW-A
        descendants = assembly_ctx.mated_descendants("PLATE-01")
        assert "SW-A" in descendants


class TestMatedAncestors:
    """测试 Context.mated_ancestors 层级遍历。"""

    def test_ancestor_chain(self, assembly_ctx: Context) -> None:
        # SW-A 被 PLATE-01 承载
        ancestors = assembly_ctx.mated_ancestors("SW-A")
        assert "PLATE-01" in ancestors
