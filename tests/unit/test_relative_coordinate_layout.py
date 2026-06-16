"""ADR-013 层级相对坐标布局单元测试。"""

from __future__ import annotations

from pathlib import Path

from adl.models import LayoutEntry, Transform
from adl.models.geometry import Vec3, compose_transforms
from adl.parsing import load_layout_file
from adl.project import Project
from adl.validation import ADLValidator

from piki.core.engine.context import Context
from piki.core.engine.registry import Registry


class TestLayoutEntryRelativeFields:
    """测试 LayoutEntry 支持 parent / transform。"""

    def test_relative_entry(self) -> None:
        entry = LayoutEntry(
            instance="PCB-01",
            parent="PLATE-01",
            transform=Transform(translation=Vec3(x=6, y=6, z=10)),
        )
        assert entry.is_relative
        assert entry.parent == "PLATE-01"
        assert entry.transform is not None
        assert entry.transform.translation.x == 6

    def test_absolute_entry(self) -> None:
        entry = LayoutEntry(
            instance="SRV-01",
            rack_id="RACK-A",
            position_u=10,
        )
        assert not entry.is_relative
        assert entry.parent is None

    def test_to_flat_includes_relative(self) -> None:
        entry = LayoutEntry(
            instance="PCB-01",
            parent="PLATE-01",
            transform=Transform(translation=Vec3(x=1, y=2, z=3)),
        )
        flat = entry.to_flat()
        assert flat["parent"] == "PLATE-01"
        assert flat["transform"]["translation"] == {"x": 1, "y": 2, "z": 3}


class TestLayoutLoaderRelative:
    """测试 Layout YAML 加载器解析相对坐标。"""

    def test_load_relative_transform_list(self, tmp_path: Path) -> None:
        layout_file = tmp_path / "layout.yaml"
        layout_file.write_text(
            """
- instance: TOP
  position_x_mm: 100
  position_y_mm: 200
  position_z_mm: 300
- instance: CHILD
  parent: TOP
  transform:
    translation: [10, 20, 30]
    rotation: [0, 0, 90]
""",
            encoding="utf-8",
        )
        layout = load_layout_file(layout_file)
        assert "CHILD" in layout.entries
        child = layout.entries["CHILD"]
        assert child.parent == "TOP"
        assert child.transform is not None
        assert child.transform.translation.x == 10
        assert child.transform.rotation.z == 90

    def test_load_default_transform(self, tmp_path: Path) -> None:
        layout_file = tmp_path / "layout.yaml"
        layout_file.write_text(
            """
- instance: CHILD
  parent: TOP
""",
            encoding="utf-8",
        )
        layout = load_layout_file(layout_file)
        child = layout.entries["CHILD"]
        assert child.transform is None


class TestLayoutResolver:
    """测试 Layout 的装配树与全局位姿解析。"""

    def _sample_layout(self) -> None:
        return None  # type: ignore[return-value]

    def test_resolved_absolute(self) -> None:
        layout = load_layout_file.__wrapped__ if hasattr(load_layout_file, "__wrapped__") else None  # type: ignore[attr-defined]
        layout = None  # placeholder to avoid unused

        entries = {
            "RACK-A01": LayoutEntry(
                instance="RACK-A01",
                position_x_mm=100,
                position_y_mm=200,
                position_z_mm=300,
            ),
        }
        from adl.models import Layout

        layout = Layout(name="test", entries=entries)

        transform = layout.resolved_transform("RACK-A01")
        assert transform is not None
        assert transform.translation.x == 100
        assert transform.translation.y == 200
        assert transform.translation.z == 300

    def test_resolved_single_relative(self) -> None:
        entries = {
            "TOP": LayoutEntry(
                instance="TOP",
                position_x_mm=100,
                position_y_mm=0,
                position_z_mm=0,
            ),
            "CHILD": LayoutEntry(
                instance="CHILD",
                parent="TOP",
                transform=Transform(translation=Vec3(x=50, y=0, z=0)),
            ),
        }
        from adl.models import Layout

        layout = Layout(name="test", entries=entries)

        transform = layout.resolved_transform("CHILD")
        assert transform is not None
        assert transform.translation.x == 150

    def test_resolved_nested_relative(self) -> None:
        entries = {
            "TOP": LayoutEntry(
                instance="TOP",
                position_x_mm=0,
                position_y_mm=0,
                position_z_mm=0,
            ),
            "SUB": LayoutEntry(
                instance="SUB",
                parent="TOP",
                transform=Transform(translation=Vec3(x=100, y=0, z=0)),
            ),
            "PLATE": LayoutEntry(
                instance="PLATE",
                parent="SUB",
                transform=Transform(translation=Vec3(x=6, y=6, z=8)),
            ),
        }
        from adl.models import Layout

        layout = Layout(name="test", entries=entries)

        transform = layout.resolved_transform("PLATE")
        assert transform is not None
        assert transform.translation.x == 106
        assert transform.translation.y == 6
        assert transform.translation.z == 8

    def test_assembly_tree(self) -> None:
        entries = {
            "TOP": LayoutEntry(instance="TOP"),
            "SUB": LayoutEntry(instance="SUB", parent="TOP"),
            "PLATE-1": LayoutEntry(instance="PLATE-1", parent="SUB"),
            "PLATE-2": LayoutEntry(instance="PLATE-2", parent="SUB"),
        }
        from adl.models import Layout

        layout = Layout(name="test", entries=entries)

        assert layout.layout_parent("PLATE-1") == "SUB"
        assert layout.layout_children("SUB") == ["PLATE-1", "PLATE-2"]
        assert layout.layout_ancestors("PLATE-1") == ["SUB", "TOP"]
        assert layout.layout_descendants("TOP") == ["SUB", "PLATE-1", "PLATE-2"]

    def test_detect_cycle(self) -> None:
        entries = {
            "A": LayoutEntry(instance="A", parent="B"),
            "B": LayoutEntry(instance="B", parent="C"),
            "C": LayoutEntry(instance="C", parent="A"),
        }
        from adl.models import Layout

        layout = Layout(name="test", entries=entries)
        cycles = layout.detect_cycles()
        assert len(cycles) == 1
        assert set(cycles[0]) == {"A", "B", "C"}

    def test_missing_parent_returns_none(self) -> None:
        entries = {
            "CHILD": LayoutEntry(
                instance="CHILD",
                parent="MISSING",
                transform=Transform(),
            ),
        }
        from adl.models import Layout

        layout = Layout(name="test", entries=entries)
        assert layout.resolved_transform("CHILD") is None


class TestADLValidatorRelativeLayout:
    """测试 ADLValidator 对相对坐标的校验。"""

    def _make_project(self, layout) -> Project:
        project = Project(
            root=Path("."),
            config={},
            type_registry=None,  # type: ignore[arg-type]
        )
        project.layout = layout
        return project

    def test_mixed_absolute_relative_error(self) -> None:
        entries = {
            "CHILD": LayoutEntry(
                instance="CHILD",
                parent="TOP",
                position_x_mm=10,
            ),
        }
        from adl.models import Layout

        layout = Layout(name="test", entries=entries)
        validator = ADLValidator(self._make_project(layout))
        diagnostics = validator._validate_relative_layout()
        assert any(d.code == "LAYOUT-001" for d in diagnostics)

    def test_missing_parent_error(self) -> None:
        entries = {
            "CHILD": LayoutEntry(instance="CHILD", parent="TOP"),
        }
        from adl.models import Layout

        layout = Layout(name="test", entries=entries)
        validator = ADLValidator(self._make_project(layout))
        diagnostics = validator._validate_relative_layout()
        assert any(d.code == "LAYOUT-002" for d in diagnostics)

    def test_self_parent_error(self) -> None:
        entries = {
            "A": LayoutEntry(instance="A", parent="A"),
        }
        from adl.models import Layout

        layout = Layout(name="test", entries=entries)
        validator = ADLValidator(self._make_project(layout))
        diagnostics = validator._validate_relative_layout()
        assert any(d.code == "LAYOUT-003" for d in diagnostics)

    def test_cycle_error(self) -> None:
        entries = {
            "A": LayoutEntry(instance="A", parent="B"),
            "B": LayoutEntry(instance="B", parent="A"),
        }
        from adl.models import Layout

        layout = Layout(name="test", entries=entries)
        validator = ADLValidator(self._make_project(layout))
        diagnostics = validator._validate_relative_layout()
        assert any(d.code == "LAYOUT-004" for d in diagnostics)


class TestContextRelativeLayout:
    """测试 Context 暴露的相对坐标 API。"""

    def test_context_methods(self, tmp_path: Path) -> None:
        registry = Registry()
        ctx = Context(registry, {})

        layout_file = tmp_path / "layouts" / "layout.yaml"
        layout_file.parent.mkdir(parents=True)
        layout_file.write_text(
            """
- instance: TOP
  position_x_mm: 0
  position_y_mm: 0
  position_z_mm: 0
- instance: SUB
  parent: TOP
  transform:
    translation: [100, 0, 0]
- instance: PLATE
  parent: SUB
  transform:
    translation: [6, 6, 8]
""",
            encoding="utf-8",
        )
        registry.load_layout(tmp_path)

        assert ctx.layout_parent("PLATE") == "SUB"
        assert ctx.layout_children("SUB") == ["PLATE"]
        assert ctx.layout_ancestors("PLATE") == ["SUB", "TOP"]
        assert ctx.layout_descendants("TOP") == ["SUB", "PLATE"]

        transform = ctx.resolved_transform("PLATE")
        assert transform is not None
        assert transform.translation.x == 106


class TestComposeTransforms:
    """测试 Transform 级联数学。"""

    def test_translation_only(self) -> None:
        parent = Transform(translation=Vec3(x=10, y=0, z=0))
        child = Transform(translation=Vec3(x=5, y=0, z=0))
        composed = compose_transforms(parent, child)
        assert composed.translation.x == 15

    def test_rotation_around_z(self) -> None:

        parent = Transform(rotation=Vec3(x=0, y=0, z=90))
        child = Transform(translation=Vec3(x=1, y=0, z=0))
        composed = compose_transforms(parent, child)
        assert abs(composed.translation.x) < 1e-9
        assert abs(composed.translation.y - 1) < 1e-9
        assert abs(composed.rotation.z - 90) < 1e-9
