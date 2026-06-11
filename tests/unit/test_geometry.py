"""几何算法单元测试 —— AABB、碰撞检测、build_aabb_from_instance。"""

from __future__ import annotations

from pathlib import Path

import pytest

from piki.core.models.base import ResolvedInstance
from piki.core.models.geometry import (
    GeometryAssets,
    InlineGeometry,
    Transform,
    Vec3,
)
from piki.ext.geometry import AABB, build_aabb_from_instance, find_collisions


class TestAABB:
    """测试 AABB 基本操作。"""

    def test_from_box_default(self) -> None:
        aabb = AABB.from_box(Vec3(x=2.0, y=4.0, z=6.0))
        assert aabb.min == Vec3(x=-1.0, y=-2.0, z=-3.0)
        assert aabb.max == Vec3(x=1.0, y=2.0, z=3.0)

    def test_from_box_with_translation(self) -> None:
        aabb = AABB.from_box(
            Vec3(x=2.0, y=2.0, z=2.0),
            Transform(translation=Vec3(x=5.0, y=0.0, z=0.0)),
        )
        assert aabb.min == Vec3(x=4.0, y=-1.0, z=-1.0)
        assert aabb.max == Vec3(x=6.0, y=1.0, z=1.0)

    def test_intersects_overlapping(self) -> None:
        a = AABB(min=Vec3(x=0, y=0, z=0), max=Vec3(x=2, y=2, z=2))
        b = AABB(min=Vec3(x=1, y=1, z=1), max=Vec3(x=3, y=3, z=3))
        assert a.intersects(b) is True

    def test_intersects_touching(self) -> None:
        a = AABB(min=Vec3(x=0, y=0, z=0), max=Vec3(x=2, y=2, z=2))
        b = AABB(min=Vec3(x=2, y=0, z=0), max=Vec3(x=4, y=2, z=2))
        assert a.intersects(b) is True

    def test_intersects_separated(self) -> None:
        a = AABB(min=Vec3(x=0, y=0, z=0), max=Vec3(x=1, y=1, z=1))
        b = AABB(min=Vec3(x=2, y=0, z=0), max=Vec3(x=3, y=1, z=1))
        assert a.intersects(b) is False

    def test_volume(self) -> None:
        aabb = AABB(min=Vec3(x=0, y=0, z=0), max=Vec3(x=2, y=3, z=4))
        assert aabb.volume() == 24.0

    def test_union(self) -> None:
        a = AABB(min=Vec3(x=0, y=0, z=0), max=Vec3(x=1, y=1, z=1))
        b = AABB(min=Vec3(x=2, y=2, z=2), max=Vec3(x=3, y=3, z=3))
        u = a.union(b)
        assert u.min == Vec3(x=0, y=0, z=0)
        assert u.max == Vec3(x=3, y=3, z=3)

    def test_center(self) -> None:
        aabb = AABB(min=Vec3(x=0, y=0, z=0), max=Vec3(x=2, y=4, z=6))
        assert aabb.center() == Vec3(x=1.0, y=2.0, z=3.0)

    def test_size(self) -> None:
        aabb = AABB(min=Vec3(x=0, y=0, z=0), max=Vec3(x=2, y=4, z=6))
        assert aabb.size() == Vec3(x=2.0, y=4.0, z=6.0)


class TestFindCollisions:
    """测试碰撞检测。"""

    def test_no_collisions(self) -> None:
        items = [
            ("A", AABB(min=Vec3(x=0, y=0, z=0), max=Vec3(x=1, y=1, z=1))),
            ("B", AABB(min=Vec3(x=2, y=0, z=0), max=Vec3(x=3, y=1, z=1))),
        ]
        assert find_collisions(items) == []

    def test_one_collision(self) -> None:
        items = [
            ("A", AABB(min=Vec3(x=0, y=0, z=0), max=Vec3(x=2, y=2, z=2))),
            ("B", AABB(min=Vec3(x=1, y=1, z=1), max=Vec3(x=3, y=3, z=3))),
            ("C", AABB(min=Vec3(x=5, y=5, z=5), max=Vec3(x=6, y=6, z=6))),
        ]
        result = find_collisions(items)
        assert len(result) == 1
        assert result[0] == ("A", "B")

    def test_multiple_collisions(self) -> None:
        items = [
            ("A", AABB(min=Vec3(x=0, y=0, z=0), max=Vec3(x=2, y=2, z=2))),
            ("B", AABB(min=Vec3(x=1, y=1, z=1), max=Vec3(x=3, y=3, z=3))),
            ("C", AABB(min=Vec3(x=1.5, y=1.5, z=1.5), max=Vec3(x=4, y=4, z=4))),
        ]
        result = find_collisions(items)
        assert len(result) == 3  # A-B, A-C, B-C

    def test_single_item(self) -> None:
        items = [("A", AABB(min=Vec3(x=0, y=0, z=0), max=Vec3(x=1, y=1, z=1)))]
        assert find_collisions(items) == []

    def test_empty(self) -> None:
        assert find_collisions([]) == []


class TestBuildAABBFromInstance:
    """测试从 ResolvedInstance 构建 AABB。"""

    def _make_inst(self, resolved: dict, raw: dict | None = None) -> ResolvedInstance:
        return ResolvedInstance(
            id="TEST-01",
            family="TestFamily",
            raw=raw or {},
            _resolved=resolved,
            source=Path("/dev/null"),
        )

    def test_from_physical_dimensions(self) -> None:
        inst = self._make_inst({
            "width_mm": 1000.0,
            "height_mm": 2000.0,
            "depth_mm": 500.0,
        })
        aabb = build_aabb_from_instance(inst)
        assert aabb is not None
        # 1m x 2m x 0.5m, centered at origin
        assert aabb.min == pytest.approx(Vec3(x=-0.5, y=-1.0, z=-0.25), abs=1e-6)
        assert aabb.max == pytest.approx(Vec3(x=0.5, y=1.0, z=0.25), abs=1e-6)

    def test_from_physical_with_position(self) -> None:
        inst = self._make_inst({
            "width_mm": 1000.0,
            "height_mm": 2000.0,
            "depth_mm": 500.0,
            "position_x_mm": 500.0,
            "position_y_mm": 1000.0,
            "position_z_mm": 250.0,
        })
        aabb = build_aabb_from_instance(inst)
        assert aabb is not None
        # translated by (0.5, 1.0, 0.25)
        assert aabb.min == pytest.approx(Vec3(x=0.0, y=0.0, z=0.0), abs=1e-6)
        assert aabb.max == pytest.approx(Vec3(x=1.0, y=2.0, z=0.5), abs=1e-6)

    def test_from_inline_box(self) -> None:
        from piki.core.models.geometry import AssetReference
        inst = self._make_inst({
            "assets": GeometryAssets(
                usd=AssetReference(
                    inline=InlineGeometry(
                        type="box",
                        size=Vec3(x=2.0, y=3.0, z=4.0),
                        transform=Transform(translation=Vec3(x=1.0, y=0.0, z=0.0)),
                    )
                )
            ).model_dump(),
        })
        aabb = build_aabb_from_instance(inst)
        assert aabb is not None
        assert aabb.min == Vec3(x=0.0, y=-1.5, z=-2.0)
        assert aabb.max == Vec3(x=2.0, y=1.5, z=2.0)

    def test_no_dimensions_returns_none(self) -> None:
        inst = self._make_inst({"name": "no-dims"})
        assert build_aabb_from_instance(inst) is None

    def test_length_fallback_for_depth(self) -> None:
        inst = self._make_inst({
            "width_mm": 1000.0,
            "height_mm": 2000.0,
            "length_mm": 600.0,
            # no depth_mm
        })
        aabb = build_aabb_from_instance(inst)
        assert aabb is not None
        assert aabb.size().z == pytest.approx(0.6, abs=1e-6)
