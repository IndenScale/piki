"""基础几何算法 —— AABB、OBB、碰撞检测。

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
    """轴对齐包围盒（Axis-Aligned Bounding Box）。"""

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


def _mm_to_m(mm: float) -> float:
    """毫米转米。"""
    return mm / 1000.0


def build_aabb_from_instance(inst: ResolvedInstance) -> AABB | None:
    """从 ResolvedInstance 构建 AABB。

    优先级：
    1. assets.usd.inline (box) → 直接用尺寸和变换
    2. assets.usd.procedural → 计算 CSG 结果的 AABB（需 CSG 引擎）
    3. physical 尺寸字段 → 生成 Box 代理几何
    4. 无尺寸信息 → 返回 None
    """
    # 1. 尝试 assets.usd.inline
    assets = getattr(inst, "assets", None)
    if assets and assets.usd and assets.usd.inline:
        inline = assets.usd.inline
        if inline.type == "box" and inline.size:
            return AABB.from_box(inline.size, inline.transform)
        # 其他 primitive 类型简化处理：用外接球近似
        if inline.radius is not None and inline.height is not None:
            # cylinder / capsule
            r = inline.radius
            h = inline.height
            size = Vec3(x=r * 2, y=h, z=r * 2)
            return AABB.from_box(size, inline.transform)
        if inline.radius is not None:
            # sphere
            r = inline.radius * 2
            size = Vec3(x=r, y=r, z=r)
            return AABB.from_box(size, inline.transform)

    # 2. 尝试 CSG procedural（需要 CSG 引擎支持）
    if assets and assets.usd and assets.usd.procedural:
        try:
            from .csg import eval_csg_aabb

            return eval_csg_aabb(assets.usd.procedural)
        except ImportError:
            pass  # CSG 引擎未安装，降级处理

    # 3. 从 physical 尺寸字段生成代理几何
    # 支持多种字段命名：length_mm/width_mm/height_mm 或 depth_mm/width_mm/height_mm
    resolved = inst.resolved
    width_mm = getattr(resolved, "width_mm", 0.0) or 0.0
    depth_mm = getattr(resolved, "depth_mm", 0.0) or 0.0
    length_mm = getattr(resolved, "length_mm", 0.0) or 0.0
    height_mm = getattr(resolved, "height_mm", 0.0) or 0.0

    # 深度优先使用 depth_mm，否则 length_mm
    depth = depth_mm if depth_mm > 0 else length_mm
    # 高度
    height = height_mm
    # 宽度
    width = width_mm

    if width <= 0 or height <= 0 or depth <= 0:
        return None

    # 转换为米，构建 AABB
    size = Vec3(
        x=_mm_to_m(width),
        y=_mm_to_m(height),
        z=_mm_to_m(depth),
    )

    # 如果有 position 字段，应用平移
    pos_x = getattr(resolved, "position_x_mm", 0.0) or 0.0
    pos_y = getattr(resolved, "position_y_mm", 0.0) or 0.0
    pos_z = getattr(resolved, "position_z_mm", 0.0) or 0.0

    # 如果 Y 位置未显式设置但有 position_u（机柜 U 位），
    # 则从 position_u 推导 Y：1U = 44.45mm，U 位从底部向上
    position_u = getattr(resolved, "position_u", None)
    if pos_y == 0.0 and position_u is not None:
        pos_y = position_u * 44.45

    # 也支持嵌套 position 对象
    position = getattr(resolved, "position", None)
    if position is not None:
        pos_x = getattr(position, "x", pos_x) or pos_x
        pos_y = getattr(position, "y", pos_y) or pos_y
        pos_z = getattr(position, "z", pos_z) or pos_z

    transform = Transform(
        translation=Vec3(
            x=_mm_to_m(pos_x),
            y=_mm_to_m(pos_y),
            z=_mm_to_m(pos_z),
        )
    )

    return AABB.from_box(size, transform)


def find_collisions(
    items: list[tuple[str, AABB]],
) -> list[tuple[str, str]]:
    """O(n²) 碰撞检测，返回碰撞对列表。

    Args:
        items: [(id, aabb), ...]

    Returns:
        [(id1, id2), ...] 碰撞的 ID 对（每对只出现一次）
    """
    collisions: list[tuple[str, str]] = []
    for i, (id1, box1) in enumerate(items):
        for id2, box2 in items[i + 1 :]:
            if box1.intersects(box2):
                collisions.append((id1, id2))
    return collisions
