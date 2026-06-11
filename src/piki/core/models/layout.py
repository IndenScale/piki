"""Layout 数据模型：Instance 部署决策的声明层。

ADR-008 将 Instance（设备身份）与 Layout（部署位置）分离。
Layout 文件描述"这台设备部署在哪、怎么接"，不描述设备自身属性。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LayoutEntry:
    """Layout 中的单条部署记录。"""

    instance: str                 # Instance ID 引用
    # 机柜式部署（数据中心）
    rack_id: str | None = None
    position_u: int | None = None
    pdu_id: str | None = None
    # 自由空间部署（暖通、消防、结构设备）
    grid_id: str | None = None
    position_x_mm: float | None = None
    position_y_mm: float | None = None
    position_z_mm: float | None = None
    # 连接关系
    connections: list[dict[str, str]] = field(default_factory=list)
    # 额外部署参数
    extra: dict[str, Any] = field(default_factory=dict)

    def to_flat(self) -> dict[str, Any]:
        """将 LayoutEntry 转为扁平 dict，用于合并到 resolved。"""
        flat: dict[str, Any] = {}
        if self.rack_id is not None:
            flat["rack_id"] = self.rack_id
        if self.position_u is not None:
            flat["position_u"] = self.position_u
        if self.pdu_id is not None:
            flat["pdu_id"] = self.pdu_id
        if self.grid_id is not None:
            flat["grid_id"] = self.grid_id
        if self.position_x_mm is not None:
            flat["position_x_mm"] = self.position_x_mm
        if self.position_y_mm is not None:
            flat["position_y_mm"] = self.position_y_mm
        if self.position_z_mm is not None:
            flat["position_z_mm"] = self.position_z_mm
        for conn in self.connections:
            # 连接关系保持在 extra 中，规则按需读取
            pass
        flat.update(self.extra)
        return flat


@dataclass
class Layout:
    """一个项目/子项目的完整 Layout。

    按照 ADR-008，每个子项目只有一个 Layout 文件。
    """

    name: str                           # Layout 名称（通常是目录名）
    entries: dict[str, LayoutEntry] = field(default_factory=dict)  # instance_id -> LayoutEntry
    source: Path | None = None
    sections: dict[str, list[LayoutEntry]] = field(default_factory=dict)  # discipline -> entries

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
        # 需要机柜的 total_u 信息，由调用方提供
        used = {e.position_u for e in self.entries.values()
                if e.rack_id == rack_id and e.position_u is not None}
        return set()
