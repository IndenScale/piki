"""几何算法单元测试 —— piki 插件侧的 AABB 原语。

通用碰撞检测已迁移到 ``adl.geometry.GeometryProvider``；相关测试见
``adl/tests/``。本文件只保留 piki.ext.geometry 中 AABB 类的单元测试。
"""

from __future__ import annotations

from adl.geometry import Transform, Vec3

from piki.ext.geometry import AABB


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
