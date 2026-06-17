"""Layout 数据模型：Instance 部署决策的声明层。

ADR-001 将 Instance（设备身份）与 Layout（部署位置）分离。
Layout 文件描述"这台设备部署在哪、怎么接"，不描述设备自身属性。

ADR-013 相对坐标：Layout 只保留声明式放置关系（parent/transform 链、
rack_id/position_u、grid 坐标、绝对坐标）。全局位姿与包围盒计算属于
几何后端 ``adl.geometry``，在目标输出阶段按需注入。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from adl.geometry import Transform, Vec3, compose_transforms, transform_from_absolute
from adl.models.grid import Grid

_U_MM = 44.45


@dataclass
class LayoutEntry:
    """Layout 中的单条部署记录。"""

    instance: str
    rack_id: str | None = None
    position_u: int | None = None
    pdu_id: str | None = None
    row_id: str | None = None
    bay_index: int | None = None
    grid_id: str | None = None
    grid_position: tuple[str, str] | None = None
    position_x_mm: float | None = None
    position_y_mm: float | None = None
    position_z_mm: float | None = None
    parent: str | None = None
    transform: Transform | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_relative(self) -> bool:
        return self.parent is not None

    @property
    def absolute_fields(self) -> dict[str, Any]:
        return {
            k: v
            for k, v in {
                "rack_id": self.rack_id,
                "position_u": self.position_u,
                "pdu_id": self.pdu_id,
                "row_id": self.row_id,
                "bay_index": self.bay_index,
                "grid_id": self.grid_id,
                "grid_position": self.grid_position,
                "position_x_mm": self.position_x_mm,
                "position_y_mm": self.position_y_mm,
                "position_z_mm": self.position_z_mm,
            }.items()
            if v is not None
        }

    def to_flat(self) -> dict[str, Any]:
        flat: dict[str, Any] = {}
        if self.rack_id is not None:
            flat["rack_id"] = self.rack_id
        if self.position_u is not None:
            flat["position_u"] = self.position_u
        if self.pdu_id is not None:
            flat["pdu_id"] = self.pdu_id
        if self.row_id is not None:
            flat["row_id"] = self.row_id
        if self.bay_index is not None:
            flat["bay_index"] = self.bay_index
        if self.grid_id is not None:
            flat["grid_id"] = self.grid_id
        if self.grid_position is not None:
            flat["grid_position"] = list(self.grid_position)
        if self.position_x_mm is not None:
            flat["position_x_mm"] = self.position_x_mm
        if self.position_y_mm is not None:
            flat["position_y_mm"] = self.position_y_mm
        if self.position_z_mm is not None:
            flat["position_z_mm"] = self.position_z_mm
        if self.parent is not None:
            flat["parent"] = self.parent
        if self.transform is not None:
            flat["transform"] = self.transform.model_dump()
        flat.update(self.extra)
        return flat


@dataclass
class Layout:
    """一个项目/子项目的完整 Layout。"""

    name: str
    entries: dict[str, LayoutEntry] = field(default_factory=dict)
    source: Path | None = None
    sections: dict[str, list[LayoutEntry]] = field(default_factory=dict)
    grids: dict[str, Grid] = field(default_factory=dict)
    _transform_cache: dict[str, Transform | None] = field(default_factory=dict, repr=False)

    def get(self, instance_id: str) -> LayoutEntry | None:
        return self.entries.get(instance_id)

    def instances_in(self, rack_id: str) -> list[LayoutEntry]:
        return [e for e in self.entries.values() if e.rack_id == rack_id]

    def at(self, rack_id: str, position_u: int) -> LayoutEntry | None:
        for e in self.entries.values():
            if e.rack_id == rack_id and e.position_u == position_u:
                return e
        return None

    def connected_to(self, pdu_id: str) -> list[LayoutEntry]:
        return [e for e in self.entries.values() if e.pdu_id == pdu_id]

    def free_positions(self, rack_id: str) -> set[int]:
        return {
            e.position_u
            for e in self.entries.values()
            if e.rack_id == rack_id and e.position_u is not None
        }

    def layout_parent(self, instance_id: str) -> str | None:
        entry = self.entries.get(instance_id)
        return entry.parent if entry else None

    def layout_children(self, instance_id: str) -> list[str]:
        """返回直接以 ``instance_id`` 为 parent 的实例 ID 列表。"""
        return [e.instance for e in self.entries.values() if e.parent == instance_id]

    def layout_ancestors(self, instance_id: str) -> list[str]:
        """返回从直接父级到根的路径（不含自身）。"""
        path: list[str] = []
        current = self.layout_parent(instance_id)
        while current is not None:
            path.append(current)
            current = self.layout_parent(current)
        return path

    def layout_descendants(self, instance_id: str) -> list[str]:
        """返回 ``instance_id`` 下的所有后代实例 ID（递归）。"""
        result: list[str] = []
        stack = [instance_id]
        while stack:
            current = stack.pop()
            for child in self.layout_children(current):
                result.append(child)
                stack.append(child)
        return result

    def placement_of(self, instance_id: str) -> LayoutEntry | None:
        """返回实例的声明式放置条目。

        这是 Layout 的核心 API：只返回"声明了什么"，不做几何计算。
        """
        return self.entries.get(instance_id)

    # ═══════════════════════════════════════════════════════════
    # 轻量位姿解析（仅基于声明字段，无 BBox / Mate 几何约束）
    # ═══════════════════════════════════════════════════════════

    def resolved_transform(
        self,
        instance_id: str,
        *,
        resolve_u: bool = True,
    ) -> Transform | None:
        """解析 Layout 声明链得到的全局 Transform。

        这是一个轻量、纯声明式的实现：
        - parent 链通过 ``entry.transform`` 级联
        - rack + position_u 退化为 ``(position_u - 1) * 44.45`` 的 Z 向平移
        - 绝对坐标 / grid 坐标直接映射

        注意：本方法**不包含** Mate 约束求解和 BBox 面片计算。
        若需要完整几何（含机柜深度对齐、Mate 覆盖等），请使用
        ``adl.geometry.GeometryProvider``。
        """
        if instance_id in self._transform_cache:
            return self._transform_cache[instance_id]

        entry = self.entries.get(instance_id)
        if entry is None:
            self._transform_cache[instance_id] = None
            return None

        if entry.parent is not None:
            parent_tf = self.resolved_transform(entry.parent, resolve_u=resolve_u)
            if parent_tf is None:
                return None
            local_tf = entry.transform or Transform()
            result = compose_transforms(parent_tf, local_tf)
            self._transform_cache[instance_id] = result
            return result

        if entry.rack_id is not None:
            rack_tf = self.resolved_transform(entry.rack_id, resolve_u=resolve_u)
            if rack_tf is None:
                return None
            z = (entry.position_u or 1) * _U_MM if resolve_u else 0.0
            local_tf = Transform(translation=Vec3(x=0.0, y=0.0, z=z))
            result = compose_transforms(rack_tf, local_tf)
            self._transform_cache[instance_id] = result
            return result

        x = entry.position_x_mm
        y = entry.position_y_mm
        z = entry.position_z_mm

        grid_point = self._resolve_grid_position(entry)
        if grid_point is not None:
            x = grid_point.x if x is None else x
            y = grid_point.y if y is None else y
            z = grid_point.z if z is None else z

        result = transform_from_absolute(x, y, z)
        self._transform_cache[instance_id] = result
        return result

    def _resolve_grid_position(self, entry: LayoutEntry) -> Vec3 | None:
        grid_id = entry.grid_id
        if grid_id is None:
            return None
        grid = self.grids.get(grid_id)
        if grid is None:
            return None
        grid_position = entry.grid_position
        if grid_position is None and entry.row_id is not None and entry.bay_index is not None:
            grid_position = (entry.row_id, str(entry.bay_index))
        if grid_position is None:
            return None
        return grid.resolve(grid_position[0], grid_position[1])

    def detect_cycles(self) -> list[list[str]]:
        cycles: list[list[str]] = []
        visited: set[str] = set()
        for instance_id in self.entries:
            if instance_id in visited:
                continue
            path: list[str] = []
            current: str | None = instance_id
            while current is not None:
                if current in path:
                    cycle_start = path.index(current)
                    cycles.append(path[cycle_start:])
                    break
                if current in visited:
                    break
                path.append(current)
                visited.add(current)
                entry = self.entries.get(current)
                current = entry.parent if entry is not None else None
        return cycles
