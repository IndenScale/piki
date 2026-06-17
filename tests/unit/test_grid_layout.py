"""Grid 轴网与 Layout 集成单元测试。"""

from __future__ import annotations

from pathlib import Path

from adl.geometry import Vec3
from adl.models import Grid, GridAxis, Layout, LayoutEntry
from adl.parsing import load_grids, load_layout_file
from adl.project import Project
from adl.validation import ADLValidator


class TestGridModel:
    """测试 Grid 数据模型。"""

    def test_resolve_basic(self) -> None:
        grid = Grid(
            id="ROOM-GRID",
            type="orthogonal",
            origin=Vec3(x=0, y=0, z=0),
            axes=[
                GridAxis(direction=Vec3(x=0, y=1, z=0), lines={"A": 0, "B": 1200}),
                GridAxis(direction=Vec3(x=1, y=0, z=0), lines={"1": 0, "2": 3000}),
            ],
        )
        point = grid.resolve("A", "2")
        assert point is not None
        assert point.x == 3000
        assert point.y == 0
        assert point.z == 0

    def test_resolve_missing_line(self) -> None:
        grid = Grid(
            id="ROOM-GRID",
            type="orthogonal",
            origin=Vec3(x=0, y=0, z=0),
            axes=[
                GridAxis(direction=Vec3(x=0, y=1, z=0), lines={"A": 0}),
                GridAxis(direction=Vec3(x=1, y=0, z=0), lines={"1": 0}),
            ],
        )
        assert grid.resolve("A", "3") is None
        assert grid.resolve("C", "1") is None

    def test_has_line(self) -> None:
        grid = Grid(
            id="ROOM-GRID",
            type="orthogonal",
            axes=[
                GridAxis(lines={"A": 0}),
                GridAxis(lines={"1": 0}),
            ],
        )
        assert grid.has_line(0, "A")
        assert grid.has_line(1, "1")
        assert not grid.has_line(0, "1")
        assert not grid.has_line(2, "A")

    def test_orthogonal_requires_two_axes(self) -> None:
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Grid(id="BAD", type="orthogonal", axes=[GridAxis(lines={"A": 0})])


class TestGridLoader:
    """测试 Grid 文件加载器。"""

    def test_load_grids(self, tmp_path: Path) -> None:
        grids_dir = tmp_path / "grids"
        grids_dir.mkdir()
        (grids_dir / "room-grid.yaml").write_text(
            """
id: ROOM-GRID
type: orthogonal
origin: [100, 200, 0]
axes:
  - direction: [0, 1, 0]
    lines:
      A: 0
      B: 1200
  - direction: [1, 0, 0]
    lines:
      "1": 0
      "2": 3000
""",
            encoding="utf-8",
        )

        grids = load_grids(tmp_path)
        assert "ROOM-GRID" in grids
        grid = grids["ROOM-GRID"]
        assert grid.origin.x == 100
        point = grid.resolve("B", "2")
        assert point is not None
        assert point.x == 100 + 3000
        assert point.y == 200 + 1200

    def test_load_grids_empty_dir(self, tmp_path: Path) -> None:
        grids = load_grids(tmp_path)
        assert grids == {}


class TestLayoutEntryGridFields:
    """测试 LayoutEntry 支持 Grid 字段。"""

    def test_grid_fields(self) -> None:
        entry = LayoutEntry(
            instance="RACK-A03",
            grid_id="ROOM-GRID",
            grid_position=("A", "3"),
        )
        assert entry.grid_id == "ROOM-GRID"
        assert entry.grid_position == ("A", "3")
        assert "grid_id" in entry.absolute_fields
        assert "grid_position" in entry.absolute_fields

    def test_to_flat_includes_grid(self) -> None:
        entry = LayoutEntry(
            instance="RACK-A03",
            grid_id="ROOM-GRID",
            grid_position=("A", "3"),
        )
        flat = entry.to_flat()
        assert flat["grid_id"] == "ROOM-GRID"
        assert flat["grid_position"] == ["A", "3"]


class TestLayoutGridResolver:
    """测试 Layout 从 Grid 解析全局位姿。"""

    def _sample_grid(self) -> Grid:
        return Grid(
            id="ROOM-GRID",
            type="orthogonal",
            origin=Vec3(x=100, y=200, z=0),
            axes=[
                GridAxis(direction=Vec3(x=0, y=1, z=0), lines={"A": 0, "B": 1200}),
                GridAxis(direction=Vec3(x=1, y=0, z=0), lines={"1": 0, "2": 3000}),
            ],
        )

    def test_resolved_from_grid(self) -> None:
        entries = {
            "RACK-A02": LayoutEntry(
                instance="RACK-A02",
                grid_id="ROOM-GRID",
                grid_position=("A", "2"),
            ),
        }
        layout = Layout(name="test", entries=entries, grids={"ROOM-GRID": self._sample_grid()})
        transform = layout.resolved_transform("RACK-A02")
        assert transform is not None
        assert transform.translation.x == 100 + 3000
        assert transform.translation.y == 200 + 0
        assert transform.translation.z == 0

    def test_explicit_position_overrides_grid(self) -> None:
        entries = {
            "RACK-A02": LayoutEntry(
                instance="RACK-A02",
                grid_id="ROOM-GRID",
                grid_position=("A", "2"),
                position_x_mm=5000,
                position_z_mm=100,
            ),
        }
        layout = Layout(name="test", entries=entries, grids={"ROOM-GRID": self._sample_grid()})
        transform = layout.resolved_transform("RACK-A02")
        assert transform is not None
        # x 被显式覆盖，y 仍从 Grid 解析，z 被显式覆盖
        assert transform.translation.x == 5000
        assert transform.translation.y == 200 + 0
        assert transform.translation.z == 100

    def test_row_bay_fallback(self) -> None:
        entries = {
            "RACK-B01": LayoutEntry(
                instance="RACK-B01",
                grid_id="ROOM-GRID",
                row_id="B",
                bay_index=1,
            ),
        }
        layout = Layout(name="test", entries=entries, grids={"ROOM-GRID": self._sample_grid()})
        transform = layout.resolved_transform("RACK-B01")
        assert transform is not None
        assert transform.translation.x == 100 + 0
        assert transform.translation.y == 200 + 1200

    def test_missing_grid_returns_zero(self) -> None:
        """Grid 不存在时，显式坐标缺失的维度回落到 0。"""
        entries = {
            "RACK-X": LayoutEntry(
                instance="RACK-X",
                grid_id="MISSING",
                grid_position=("A", "1"),
            ),
        }
        layout = Layout(name="test", entries=entries)
        transform = layout.resolved_transform("RACK-X")
        assert transform is not None
        assert transform.translation.x == 0
        assert transform.translation.y == 0


class TestLayoutLoaderGrid:
    """测试 Layout YAML 加载器解析 Grid 字段。"""

    def test_load_grid_position(self, tmp_path: Path) -> None:
        layout_file = tmp_path / "layout.yaml"
        layout_file.write_text(
            """
- instance: RACK-A03
  grid_id: ROOM-GRID
  grid_position: [A, "3"]
""",
            encoding="utf-8",
        )
        layout = load_layout_file(layout_file)
        entry = layout.entries["RACK-A03"]
        assert entry.grid_id == "ROOM-GRID"
        assert entry.grid_position == ("A", "3")


class TestADLValidatorGridLayout:
    """测试 ADLValidator 对 Grid 的校验。"""

    def _make_project(self, layout: Layout, grids: dict[str, Grid] | None = None) -> Project:
        project = Project(
            root=Path("."),
            config={},
            type_registry=None,  # type: ignore[arg-type]
        )
        project.layout = layout
        if grids:
            project.grids.update(grids)
            project.layout.grids.update(grids)
        return project

    def _sample_grid(self) -> Grid:
        return Grid(
            id="ROOM-GRID",
            type="orthogonal",
            axes=[
                GridAxis(lines={"A": 0, "B": 1200}),
                GridAxis(lines={"1": 0, "2": 3000}),
            ],
        )

    def test_grid_id_with_parent_error(self) -> None:
        entries = {
            "CHILD": LayoutEntry(
                instance="CHILD",
                parent="TOP",
                grid_id="ROOM-GRID",
                grid_position=("A", "1"),
            ),
        }
        layout = Layout(name="test", entries=entries)
        validator = ADLValidator(self._make_project(layout))
        diagnostics = validator._validate_relative_layout()
        assert any(d.code == "LAYOUT-001" for d in diagnostics)

    def test_missing_grid_error(self) -> None:
        entries = {
            "RACK-A01": LayoutEntry(
                instance="RACK-A01",
                grid_id="MISSING",
                grid_position=("A", "1"),
            ),
        }
        layout = Layout(name="test", entries=entries)
        validator = ADLValidator(self._make_project(layout))
        diagnostics = validator._validate_grid_layout()
        assert any(d.code == "GRID-001" for d in diagnostics)

    def test_invalid_grid_position_error(self) -> None:
        entries = {
            "RACK-A01": LayoutEntry(
                instance="RACK-A01",
                grid_id="ROOM-GRID",
                grid_position=("A", "99"),
            ),
        }
        layout = Layout(name="test", entries=entries)
        validator = ADLValidator(self._make_project(layout, {"ROOM-GRID": self._sample_grid()}))
        diagnostics = validator._validate_grid_layout()
        assert any(d.code == "GRID-002" for d in diagnostics)

    def test_grid_position_without_grid_id_error(self) -> None:
        entries = {
            "RACK-A01": LayoutEntry(
                instance="RACK-A01",
                grid_position=("A", "1"),
            ),
        }
        layout = Layout(name="test", entries=entries)
        validator = ADLValidator(self._make_project(layout))
        diagnostics = validator._validate_grid_layout()
        assert any(d.code == "GRID-003" for d in diagnostics)

    def test_grid_without_position_error(self) -> None:
        entries = {
            "RACK-A01": LayoutEntry(
                instance="RACK-A01",
                grid_id="ROOM-GRID",
            ),
        }
        layout = Layout(name="test", entries=entries)
        validator = ADLValidator(self._make_project(layout, {"ROOM-GRID": self._sample_grid()}))
        diagnostics = validator._validate_grid_layout()
        assert any(d.code == "GRID-004" for d in diagnostics)

    def test_valid_grid_passes(self) -> None:
        entries = {
            "RACK-A01": LayoutEntry(
                instance="RACK-A01",
                grid_id="ROOM-GRID",
                grid_position=("A", "1"),
            ),
        }
        layout = Layout(name="test", entries=entries)
        validator = ADLValidator(self._make_project(layout, {"ROOM-GRID": self._sample_grid()}))
        diagnostics = validator._validate_grid_layout()
        assert not any(d.code.startswith("GRID-") for d in diagnostics)
