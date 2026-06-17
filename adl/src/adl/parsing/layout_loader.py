"""Layout 文件加载器。

每个子项目只有一个 Layout 文件（ADR-001），位于 layouts/ 下。
Layout 文件是一个 YAML 列表，每项描述一个 Instance 的部署信息。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..models.geometry import Transform
from ..models.layout import Layout, LayoutEntry


def load_layout_file(path: Path, name: str = "") -> Layout:
    """从 YAML 文件加载 Layout。

    格式（列表）:
        - instance: SRV-01
          rack_id: RACK-A01
          position_u: 10
          pdu_id: PDU-A
        - instance: SRV-02
          grid_id: B-3
          position_x_mm: 1000
          position_y_mm: 2000

    格式（分 section dict）:
        hvac:
          - instance: PUMP-01
            grid_id: B-3
        electrical:
          - instance: UPS-01
            rack_id: RACK-A01
    """
    if not path.exists():
        return Layout(name=name or path.stem)

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    entries: dict[str, LayoutEntry] = {}
    sections: dict[str, list[LayoutEntry]] = {}

    if isinstance(data, list):
        for item in data:
            entry = _parse_entry(item)
            if entry:
                entries[entry.instance] = entry
    elif isinstance(data, dict):
        for section_name, items in data.items():
            section_entries: list[LayoutEntry] = []
            if not isinstance(items, list):
                continue
            for item in items:
                entry = _parse_entry(item)
                if entry:
                    entries[entry.instance] = entry
                    section_entries.append(entry)
            if section_entries:
                sections[section_name] = section_entries

    return Layout(
        name=name or path.stem,
        entries=entries,
        source=path,
        sections=sections,
    )


def _parse_entry(item: dict[str, Any]) -> LayoutEntry | None:
    """从 YAML dict 解析单个 LayoutEntry。"""
    instance_id = item.get("instance")
    if not instance_id:
        return None

    known = {
        "instance",
        "rack_id",
        "position_u",
        "pdu_id",
        "row_id",
        "bay_index",
        "grid_id",
        "grid_position",
        "position_x_mm",
        "position_y_mm",
        "position_z_mm",
        "parent",
        "transform",
    }
    extra = {k: v for k, v in item.items() if k not in known}

    transform = _parse_transform(item.get("transform"))
    grid_position = _parse_grid_position(item.get("grid_position"))

    return LayoutEntry(
        instance=str(instance_id),
        rack_id=item.get("rack_id"),
        position_u=item.get("position_u"),
        pdu_id=item.get("pdu_id"),
        row_id=item.get("row_id"),
        bay_index=item.get("bay_index"),
        grid_id=item.get("grid_id"),
        grid_position=grid_position,
        position_x_mm=item.get("position_x_mm"),
        position_y_mm=item.get("position_y_mm"),
        position_z_mm=item.get("position_z_mm"),
        parent=item.get("parent"),
        transform=transform,
        extra=extra,
    )


def _parse_grid_position(data: Any) -> tuple[str, str] | None:
    """从 YAML 值解析 grid_position，支持 [A, \"3\"] 列表。"""
    if data is None:
        return None
    if isinstance(data, (list, tuple)) and len(data) == 2:
        return (str(data[0]), str(data[1]))
    return None


def _parse_transform(data: Any) -> Transform | None:
    """从 YAML 值解析 Transform，支持 dict 与列表简写。"""
    if data is None:
        return None

    if isinstance(data, Transform):
        return data

    if isinstance(data, dict):
        return Transform.model_validate(data)

    # 允许 YAML 中省略，表示默认单位变换
    if data == {}:
        return Transform()

    return Transform.model_validate(data)


def find_layout_file(project_root: Path) -> Path | None:
    """在项目根目录下查找唯一的 Layout 文件。"""
    layouts_dir = project_root / "layouts"
    if not layouts_dir.exists():
        return None

    candidate = layouts_dir / "layout.yaml"
    if candidate.exists():
        return candidate

    for yaml_file in layouts_dir.rglob("layout.yaml"):
        return yaml_file

    yaml_files = sorted(layouts_dir.rglob("*.yaml"))
    if yaml_files:
        return yaml_files[0]

    return None
