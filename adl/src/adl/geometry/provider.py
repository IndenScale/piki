"""GeometryProvider — 在目标输出阶段按需注入几何。

ADL 核心只保留工程声明（rack_id、position_u、width_mm 等）。
本 Provider 在生成器/渲染器/空间规则需要时，才把这些声明解析为：
- 全局 Transform
- 轴对齐包围盒 BBox / AABB
- 碰撞对
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from adl.geometry.models import (
    BBox,
    Transform,
    Vec3,
    bbox_from_resolved,
    compose_transforms,
    transform_from_absolute,
)

if TYPE_CHECKING:
    from adl.models import Layout, LayoutEntry, MateSpec, ResolvedInstance
    from adl.project import Project

_U_MM = 44.45


@dataclass
class ResolvedGeometry:
    """单个实例解析后的几何摘要。"""

    transform: Transform
    bbox: BBox | None = None


class GeometryProvider:
    """根据 ADL 项目声明解析几何。

    不修改 Project；所有计算结果按需生成并缓存。
    """

    def __init__(self, project: "Project") -> None:
        self.project = project
        self._cache: dict[str, ResolvedGeometry | None] = {}

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def resolve(self, instance_id: str) -> ResolvedGeometry | None:
        """返回实例的全局 Transform 与可选 BBox。"""
        if instance_id in self._cache:
            return self._cache[instance_id]

        inst = self.project.find_instance(instance_id)
        if inst is None:
            self._cache[instance_id] = None
            return None

        layout = self.project.layout
        if layout is None:
            # 无 layout 时退化为从 resolved 字段读取绝对坐标
            geom = self._resolve_from_instance_only(inst)
            self._cache[instance_id] = geom
            return geom

        tf = self._resolve_transform(instance_id, inst, layout)
        if tf is None:
            self._cache[instance_id] = None
            return None

        bbox = self._bbox_from_instance(inst)
        geom = ResolvedGeometry(transform=tf, bbox=bbox)
        self._cache[instance_id] = geom
        return geom

    def collisions(self) -> list[tuple[str, str]]:
        """O(n²) AABB 碰撞检测，返回碰撞实例 ID 对。"""
        objects: list[tuple[str, BBox, Transform]] = []
        mate_pairs = self._build_mate_pairs()

        for inst_id in self.project.instances:
            geom = self.resolve(inst_id)
            if geom is None or geom.bbox is None:
                continue
            objects.append((inst_id, geom.bbox, geom.transform))

        collisions: list[tuple[str, str]] = []
        for i in range(len(objects)):
            for j in range(i + 1, len(objects)):
                id_a, bbox_a, tf_a = objects[i]
                id_b, bbox_b, tf_b = objects[j]
                pair = (id_a, id_b) if id_a < id_b else (id_b, id_a)
                if pair in mate_pairs:
                    continue
                if _aabb_overlap(bbox_a, tf_a, bbox_b, tf_b):
                    collisions.append(pair)
        return collisions

    def mate_transform(self, mate: "MateSpec") -> Transform | None:
        """根据单个 Mate 声明计算 child 的全局 Transform（简化实现）。"""
        from adl.models.mating import parse_mate_ref

        parent_id, _ = parse_mate_ref(mate.parent)
        child_id, _ = parse_mate_ref(mate.child)

        parent_geom = self.resolve(parent_id)
        child_geom = self.resolve(child_id)
        if parent_geom is None or child_geom is None:
            return None

        mtype = mate.type
        at = mate.at if mate.at else {}

        if mtype == "placed-on":
            parent_top = parent_geom.transform.translation.z + (parent_geom.bbox.hh if parent_geom.bbox else 0)
            child_z = parent_top + (child_geom.bbox.hh if child_geom.bbox else 0)
            return Transform(
                translation=Vec3(
                    x=parent_geom.transform.translation.x,
                    y=parent_geom.transform.translation.y,
                    z=child_z,
                )
            )

        if mtype in ("rack-mount", "rack-mount-19inch"):
            parent_front = parent_geom.transform.translation.x + (parent_geom.bbox.hd if parent_geom.bbox else 0)
            child_dx = parent_front - (child_geom.bbox.hd if child_geom.bbox else 0)
            u_start = int(at.get("u_start", at.get("position_u", 1)))
            child_dz = (u_start - 1) * _U_MM + (child_geom.bbox.hh if child_geom.bbox else 0)
            return Transform(
                translation=Vec3(x=child_dx, y=parent_geom.transform.translation.y, z=child_dz)
            )

        # 其他 mate 类型：返回 layout 已解析的 child 位姿
        return child_geom.transform

    # ------------------------------------------------------------------
    # 内部解析
    # ------------------------------------------------------------------

    def _resolve_from_instance_only(self, inst: "ResolvedInstance") -> ResolvedGeometry | None:
        resolved = inst._resolved
        x = float(resolved.get("position_x_mm", 0) or 0)
        y = float(resolved.get("position_y_mm", 0) or 0)
        z = float(resolved.get("position_z_mm", 0) or 0)
        tf = transform_from_absolute(x, y, z)
        bbox = self._bbox_from_instance(inst)
        return ResolvedGeometry(transform=tf, bbox=bbox)

    def _resolve_transform(
        self,
        instance_id: str,
        inst: "ResolvedInstance",
        layout: "Layout",
    ) -> Transform | None:
        """递归解析 layout parent 链 + mate 约束，得到全局 Transform。"""
        entry = layout.get(instance_id)
        if entry is None:
            return self._resolve_from_instance_only(inst).transform

        # 递归 parent
        if entry.parent is not None:
            parent_geom = self.resolve(entry.parent)
            if parent_geom is None:
                return None
            local_tf = entry.transform or Transform()
            return compose_transforms(parent_geom.transform, local_tf)

        # rack + U 位
        if entry.rack_id is not None and entry.position_u is not None:
            rack_geom = self.resolve(entry.rack_id)
            if rack_geom is None or rack_geom.bbox is None:
                # rack 无几何时退化
                return self._rack_u_transform_fallback(entry, layout)
            rack_bbox = rack_geom.bbox
            child_bbox = self._bbox_from_instance(inst)
            if child_bbox is None:
                return self._rack_u_transform_fallback(entry, layout)
            parent_front = rack_geom.transform.translation.x + rack_bbox.hd
            child_dx = parent_front - child_bbox.hd
            child_dz = (
                rack_geom.transform.translation.z
                - rack_bbox.hh
                + (entry.position_u - 1) * _U_MM
                + child_bbox.hh
            )
            return Transform(
                translation=Vec3(
                    x=child_dx,
                    y=rack_geom.transform.translation.y,
                    z=child_dz,
                )
            )

        # 绝对坐标 / grid
        x = entry.position_x_mm
        y = entry.position_y_mm
        z = entry.position_z_mm
        grid_point = self._resolve_grid_position(entry, layout)
        if grid_point is not None:
            x = grid_point.x if x is None else x
            y = grid_point.y if y is None else y
            z = grid_point.z if z is None else z
        return transform_from_absolute(x, y, z)

    def _rack_u_transform_fallback(self, entry: "LayoutEntry", layout: "Layout") -> Transform:
        """rack 无几何时的退化计算。"""
        x = entry.position_x_mm or 0.0
        y = entry.position_y_mm or 0.0
        z = (entry.position_u or 1) * _U_MM
        return transform_from_absolute(x, y, z)

    def _resolve_grid_position(self, entry: "LayoutEntry", layout: "Layout") -> Vec3 | None:
        grid_id = entry.grid_id
        if grid_id is None:
            return None
        grid = layout.grids.get(grid_id)
        if grid is None:
            return None
        grid_position = entry.grid_position
        if grid_position is None and entry.row_id is not None and entry.bay_index is not None:
            grid_position = (entry.row_id, str(entry.bay_index))
        if grid_position is None:
            return None
        return grid.resolve(grid_position[0], grid_position[1])

    def _bbox_from_instance(self, inst: "ResolvedInstance") -> BBox | None:
        """从 ResolvedInstance 提取 BBox。"""
        bbox = bbox_from_resolved(inst._resolved)
        if bbox.width == 0 and bbox.height == 0 and bbox.depth == 0:
            return None
        return bbox

    def _build_mate_pairs(self) -> set[tuple[str, str]]:
        """构建 Mate 关系对，用于碰撞排除。"""
        from adl.models.mating import parse_mate_ref

        pairs: set[tuple[str, str]] = set()
        for mate in self.project.mate_graph.list():
            parent_inst, _ = parse_mate_ref(mate.parent)
            child_inst, _ = parse_mate_ref(mate.child)
            if parent_inst and child_inst:
                pair = (parent_inst, child_inst) if parent_inst < child_inst else (child_inst, parent_inst)
                pairs.add(pair)
        return pairs


# ---------------------------------------------------------------------------
# AABB 碰撞检测（简化版，忽略旋转）
# ---------------------------------------------------------------------------


def _aabb_overlap(
    bbox_a: BBox,
    tf_a: Transform,
    bbox_b: BBox,
    tf_b: Transform,
) -> bool:
    """检测两个包围盒在全局坐标系中是否重叠（仅平移）。"""
    cx_a = tf_a.translation.x
    cy_a = tf_a.translation.y
    cz_a = tf_a.translation.z
    cx_b = tf_b.translation.x
    cy_b = tf_b.translation.y
    cz_b = tf_b.translation.z

    overlap_x = abs(cx_a - cx_b) < (bbox_a.hw + bbox_b.hw)
    overlap_y = abs(cy_a - cy_b) < (bbox_a.hh + bbox_b.hh)
    overlap_z = abs(cz_a - cz_b) < (bbox_a.hd + bbox_b.hd)

    return overlap_x and overlap_y and overlap_z
