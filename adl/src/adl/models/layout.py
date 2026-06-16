"""Layout 数据模型：Instance 部署决策的声明层。

ADR-001 将 Instance（设备身份）与 Layout（部署位置）分离。
Layout 文件描述"这台设备部署在哪、怎么接"，不描述设备自身属性。

ADR-005 将连接关系提升为独立 Instance，从 Layout 中移除。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from adl.models.geometry import Transform, compose_transforms, transform_from_absolute


@dataclass
class LayoutEntry:
    """Layout 中的单条部署记录。"""

    instance: str  # Instance ID 引用
    # 机柜式部署（数据中心）
    rack_id: str | None = None
    position_u: int | None = None
    pdu_id: str | None = None
    # 机房轴网部署（电信机房排/列）
    row_id: str | None = None
    bay_index: int | None = None
    # 自由空间部署（暖通、消防、结构设备）
    grid_id: str | None = None
    position_x_mm: float | None = None
    position_y_mm: float | None = None
    position_z_mm: float | None = None
    # 层级相对坐标（ADR-013）
    parent: str | None = None
    transform: Transform | None = None
    # 额外部署参数
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_relative(self) -> bool:
        """当前条目是否使用相对坐标模式。"""
        return self.parent is not None

    @property
    def absolute_fields(self) -> dict[str, Any]:
        """返回当前条目中所有已填写的绝对坐标字段。"""
        return {
            k: v
            for k, v in {
                "rack_id": self.rack_id,
                "position_u": self.position_u,
                "pdu_id": self.pdu_id,
                "row_id": self.row_id,
                "bay_index": self.bay_index,
                "grid_id": self.grid_id,
                "position_x_mm": self.position_x_mm,
                "position_y_mm": self.position_y_mm,
                "position_z_mm": self.position_z_mm,
            }.items()
            if v is not None
        }

    def to_flat(self) -> dict[str, Any]:
        """将 LayoutEntry 转为扁平 dict，用于合并到 resolved。"""
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
    """一个项目/子项目的完整 Layout。

    按照 ADR-001，每个子项目只有一个 Layout 文件。
    """

    name: str
    entries: dict[str, LayoutEntry] = field(default_factory=dict)
    source: Path | None = None
    sections: dict[str, list[LayoutEntry]] = field(default_factory=dict)

    def get(self, instance_id: str) -> LayoutEntry | None:
        """按 Instance ID 查找布局条目。"""
        return self.entries.get(instance_id)

    def instances_in(self, rack_id: str) -> list[LayoutEntry]:
        """查询指定机柜内的所有部署。"""
        return [e for e in self.entries.values() if e.rack_id == rack_id]

    def at(self, rack_id: str, position_u: int) -> LayoutEntry | None:
        """查询指定机柜指定 U 位的部署。"""
        for e in self.entries.values():
            if e.rack_id == rack_id and e.position_u == position_u:
                return e
        return None

    def connected_to(self, pdu_id: str) -> list[LayoutEntry]:
        """查询接入指定 PDU 的所有设备。"""
        return [e for e in self.entries.values() if e.pdu_id == pdu_id]

    def free_positions(self, rack_id: str) -> set[int]:
        """查询指定机柜的空闲 U 位（需要外部传入 total_u）。"""
        return {
            e.position_u
            for e in self.entries.values()
            if e.rack_id == rack_id and e.position_u is not None
        }

    # ------------------------------------------------------------------
    # 层级相对坐标（ADR-013）
    # ------------------------------------------------------------------

    def layout_parent(self, instance_id: str) -> str | None:
        """返回实例在空间装配树中的直接父级。"""
        entry = self.entries.get(instance_id)
        return entry.parent if entry is not None else None

    def layout_children(self, instance_id: str) -> list[str]:
        """返回实例在空间装配树中的直接子级。"""
        return [e.instance for e in self.entries.values() if e.parent == instance_id]

    def layout_ancestors(self, instance_id: str) -> list[str]:
        """返回从根到该实例的父级路径（不含自身）。"""
        result: list[str] = []
        visited: set[str] = set()
        current = self.layout_parent(instance_id)
        while current is not None:
            if current in visited:
                break
            visited.add(current)
            result.append(current)
            current = self.layout_parent(current)
        return result

    def layout_descendants(self, instance_id: str) -> list[str]:
        """返回该实例下的所有后代实例（递归，不含自身）。"""
        result: list[str] = []
        visited: set[str] = set()

        def dfs(current: str) -> None:
            for child_id in self.layout_children(current):
                if child_id in visited:
                    continue
                visited.add(child_id)
                result.append(child_id)
                dfs(child_id)

        dfs(instance_id)
        return result

    def resolved_transform(self, instance_id: str) -> Transform | None:
        """返回实例在项目全局坐标系下的解析后位姿。

        对绝对坐标条目，返回由其 ``position_x/y/z_mm`` 构成的 Transform；
        对相对坐标条目，递归级联父级全局位姿与子级局部 transform。
        """
        entry = self.entries.get(instance_id)
        if entry is None:
            return None

        if entry.parent is None:
            return transform_from_absolute(
                entry.position_x_mm,
                entry.position_y_mm,
                entry.position_z_mm,
            )

        parent_transform = self.resolved_transform(entry.parent)
        if parent_transform is None:
            return None

        local_transform = entry.transform or Transform()
        return compose_transforms(parent_transform, local_transform)

    def detect_cycles(self) -> list[list[str]]:
        """检测 ``parent`` 引用中存在的环，返回所有环上的实例 ID 列表。"""
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
