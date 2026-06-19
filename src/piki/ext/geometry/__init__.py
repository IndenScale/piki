"""piki 插件侧的基础几何工具。

注意：
- 通用碰撞检测已迁移到 ``adl.geometry.GeometryProvider``；piki 规则应优先使用
  ``ctx.geometry_provider.collisions()`` 而不是本模块的 ``find_collisions``。
- 本模块保留 ``AABB`` 等低层原语，供规则实现自定义几何检查（如门扫掠区、车辆路径、
  旋转 footprint 等 ADL GeometryProvider 未直接提供的场景）。

不依赖外部库，纯 Python 实现。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adl.models import ResolvedInstance

from adl.geometry import Transform, Vec3


@dataclass(frozen=True)
class AABB:
    """轴对齐包围盒（Axis-Aligned Bounding Box）。

    坐标单位由调用方决定；piki 插件中的规则通常使用毫米（mm）。
    """

    min: Vec3
    max: Vec3

    @classmethod
    def from_box(
        cls,
        size: Vec3,
        transform: Transform | None = None,
    ) -> AABB:
        """从 Box 尺寸和变换构建 AABB。

        Box 中心在原点，尺寸为 size，应用变换后计算 AABB。
        """
        tx = transform.translation if transform else Vec3(x=0.0, y=0.0, z=0.0)
        sx = transform.scale if transform else Vec3(x=1.0, y=1.0, z=1.0)

        half_w = size.x * sx.x / 2.0
        half_h = size.y * sx.y / 2.0
        half_d = size.z * sx.z / 2.0

        return cls(
            min=Vec3(x=tx.x - half_w, y=tx.y - half_h, z=tx.z - half_d),
            max=Vec3(x=tx.x + half_w, y=tx.y + half_h, z=tx.z + half_d),
        )

    @classmethod
    def from_points(cls, points: list[Vec3]) -> AABB | None:
        """从点集构建 AABB。"""
        if not points:
            return None
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        zs = [p.z for p in points]
        return cls(
            min=Vec3(x=min(xs), y=min(ys), z=min(zs)),
            max=Vec3(x=max(xs), y=max(ys), z=max(zs)),
        )

    def intersects(self, other: AABB) -> bool:
        """判断两个 AABB 是否相交。"""
        return (
            self.min.x <= other.max.x
            and self.max.x >= other.min.x
            and self.min.y <= other.max.y
            and self.max.y >= other.min.y
            and self.min.z <= other.max.z
            and self.max.z >= other.min.z
        )

    def volume(self) -> float:
        """计算体积。"""
        return (self.max.x - self.min.x) * (self.max.y - self.min.y) * (self.max.z - self.min.z)

    def union(self, other: AABB) -> AABB:
        """计算两个 AABB 的并集包围盒。"""
        return AABB(
            min=Vec3(
                x=min(self.min.x, other.min.x),
                y=min(self.min.y, other.min.y),
                z=min(self.min.z, other.min.z),
            ),
            max=Vec3(
                x=max(self.max.x, other.max.x),
                y=max(self.max.y, other.max.y),
                z=max(self.max.z, other.max.z),
            ),
        )

    def center(self) -> Vec3:
        """计算中心点。"""
        return Vec3(
            x=(self.min.x + self.max.x) / 2.0,
            y=(self.min.y + self.max.y) / 2.0,
            z=(self.min.z + self.max.z) / 2.0,
        )

    def size(self) -> Vec3:
        """计算尺寸。"""
        return Vec3(
            x=self.max.x - self.min.x,
            y=self.max.y - self.min.y,
            z=self.max.z - self.min.z,
        )
