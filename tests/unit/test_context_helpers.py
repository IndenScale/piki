"""Context 辅助 API 单元测试 —— instance_family、Mate 便捷访问。"""

from __future__ import annotations

from pathlib import Path

import pytest
from adl.models.mating import MateSpec
from pydantic import BaseModel

from piki.core.engine.context import Context
from piki.core.engine.registry import Registry


@pytest.fixture
def ctx(tmp_path: Path) -> Context:
    """构造一个带 Instance 和 Mate 的 Context。"""

    class SwitchFamily(BaseModel):
        id: str
        stem_type: str

    class PcbFamily(BaseModel):
        id: str
        switch_footprint: str

    registry = Registry()
    registry.add_family("SwitchFamily", SwitchFamily)
    registry.add_family("PcbFamily", PcbFamily)

    switches = tmp_path / "switches"
    switches.mkdir()
    (switches / "SW-A.yaml").write_text(
        "id: SW-A\nfamily: SwitchFamily\nstem_type: mx\n",
        encoding="utf-8",
    )
    registry.load_collection(switches)

    pcbs = tmp_path / "pcbs"
    pcbs.mkdir()
    (pcbs / "PCB-01.yaml").write_text(
        "id: PCB-01\nfamily: PcbFamily\nswitch_footprint: hotswap-mx\n",
        encoding="utf-8",
    )
    registry.load_collection(pcbs)

    registry.load_mates(tmp_path)
    (tmp_path / "mates" / "switch-pcb-solder").mkdir(parents=True)
    (tmp_path / "mates" / "switch-pcb-solder" / "PCB-01-SW-A.yaml").write_text(
        "type: switch-pcb-solder\nparent: PCB-01\nchild: SW-A\n",
        encoding="utf-8",
    )
    registry.load_mates(tmp_path)

    return Context(registry, {})


class TestInstanceFamily:
    """测试 instance_family 公开 API。"""

    def test_returns_family(self, ctx: Context) -> None:
        assert ctx.instance_family("SW-A") == "SwitchFamily"
        assert ctx.instance_family("PCB-01") == "PcbFamily"

    def test_returns_none_for_missing(self, ctx: Context) -> None:
        assert ctx.instance_family("MISSING") is None


class TestFindModelPublicApi:
    """测试 find_model 公开 API。"""

    def test_finds_model(self, ctx: Context, tmp_path: Path) -> None:
        models = tmp_path / "models"
        models.mkdir()
        (models / "gateron-yellow-pro.yaml").write_text(
            "model: gateron-yellow-pro\nfamily: SwitchFamily\nstem_type: mx\n",
            encoding="utf-8",
        )
        ctx._registry.load_models(models)

        model = ctx.find_model("gateron-yellow-pro")
        assert model is not None
        assert model.id == "gateron-yellow-pro"
        assert model.family == "SwitchFamily"

    def test_missing_model_returns_none(self, ctx: Context) -> None:
        assert ctx.find_model("missing") is None


class TestMateInstanceAccessors:
    """测试 Mate 便捷访问 API。"""

    def test_mate_parent_instance(self, ctx: Context) -> None:
        mate = ctx.mate_graph.related_to("SW-A")[0]
        parent = ctx.mate_parent_instance(mate)
        assert parent is not None
        assert parent.id == "PCB-01"
        assert parent.family == "PcbFamily"

    def test_mate_child_instance(self, ctx: Context) -> None:
        mate = ctx.mate_graph.related_to("SW-A")[0]
        child = ctx.mate_child_instance(mate)
        assert child is not None
        assert child.id == "SW-A"
        assert child.family == "SwitchFamily"

    def test_mate_instance_accessor_for_interface_ref(self, ctx: Context) -> None:
        """Interface 级 Mate 引用也能正确解析到实例。"""
        registry = ctx._registry
        registry._mates.append(
            MateSpec(type="optical-link", parent="PCB-01/eth0", child="SW-A/pin-1")
        )
        registry._mate_graph.add(registry._mates[-1])

        mate = registry._mates[-1]
        assert ctx.mate_parent_instance(mate).id == "PCB-01"
        assert ctx.mate_child_instance(mate).id == "SW-A"
