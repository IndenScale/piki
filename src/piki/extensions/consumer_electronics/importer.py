"""KiCad 数据导入器（POC）。

将现有 EDA 数据转换为 piki 可消费的 Instance/Net 描述：
- import_kicad_netlist: 解析 KiCad XML netlist → NetFamily 数据字典
- import_kicad_bom: 解析 BOM CSV → 组件清单
- import_kicad_pnp: 解析 pick-and-place CSV → 贴装位置

这些函数不直接写入文件系统，而是返回结构化数据，便于上层生成 YAML
或直接在测试中校验。
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


def _xml_tag(tag: str) -> str:
    """KiCad netlist 使用无命名空间的标签。"""
    return tag


def import_kicad_netlist(path: str | Path) -> list[dict[str, Any]]:
    """解析 KiCad XML netlist，返回 NetFamily 数据列表。

    每个 net 的节点格式为 "<component_ref>/<pin_number>"，与 piki 的
    instance_id/interface_id 引用格式一致。

    Args:
        path: KiCad 导出的 .net 文件路径。

    Returns:
        list[dict]: 每个 dict 可直接写入 NetFamily YAML，字段包括
            id, family, net_type, nodes, voltage_v 等。
    """
    tree = ET.parse(Path(path))
    root = tree.getroot()

    nets: list[dict[str, Any]] = []
    nets_elem = root.find("nets")
    if nets_elem is None:
        return nets

    for net_elem in nets_elem.findall("net"):
        name = net_elem.get("name", "")
        code = net_elem.get("code", "")
        nodes: list[str] = []
        for node_elem in net_elem.findall("node"):
            ref = node_elem.get("ref", "")
            pin = node_elem.get("pin", "")
            if ref and pin:
                nodes.append(f"{ref}/{pin}")

        # 根据 net 名前缀猜测类型
        net_type = _guess_net_type(name)

        nets.append(
            {
                "id": _sanitize_id(f"NET-{name.lstrip('/')}" or f"NET-{code}"),
                "family": "NetFamily",
                "name": name,
                "net_type": net_type,
                "nodes": nodes,
                "description": f"Imported from KiCad netlist: {name}",
            }
        )

    return nets


def _guess_net_type(name: str) -> str:
    """根据网络名猜测 net_type。"""
    upper = name.upper()
    if "GND" in upper or "VSS" in upper:
        return "ground"
    if upper.startswith("V") or "VCC" in upper or "VBUS" in upper or "VBAT" in upper:
        return "power"
    if "ROW" in upper:
        return "matrix_row"
    if "COL" in upper:
        return "matrix_col"
    return "data"


def _sanitize_id(raw: str) -> str:
    """把网络名转成合法的 YAML id（去掉特殊字符）。"""
    cleaned = raw.replace("/", "-").replace(" ", "-").replace(".", "-")
    # 避免连续横线
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")


def import_kicad_bom(
    path: str | Path,
    ref_col: str = "Ref",
    value_col: str = "Value",
    footprint_col: str = "Footprint",
) -> list[dict[str, Any]]:
    """解析 KiCad BOM CSV，返回组件清单。

    Args:
        path: BOM CSV 文件路径。
        ref_col: 位号列名。
        value_col: 值列名。
        footprint_col: 封装列名。

    Returns:
        list[dict]: 每个组件包含 ref, value, footprint, quantity。
    """
    rows: list[dict[str, Any]] = []
    with open(Path(path), newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            refs = row.get(ref_col, "")
            if not refs:
                continue
            for ref in refs.split(","):
                ref = ref.strip()
                if not ref:
                    continue
                rows.append(
                    {
                        "ref": ref,
                        "value": row.get(value_col, ""),
                        "footprint": row.get(footprint_col, ""),
                        "quantity": 1,
                    }
                )
    return rows


def import_kicad_pnp(
    path: str | Path,
    ref_col: str = "Ref",
    x_col: str = "PosX",
    y_col: str = "PosY",
    rot_col: str = "Rot",
    side_col: str = "Side",
) -> list[dict[str, Any]]:
    """解析 KiCad pick-and-place CSV，返回贴装位置列表。

    Args:
        path: pick-and-place CSV 文件路径。
        ref_col: 位号列名。
        x_col, y_col: 坐标列名。
        rot_col: 旋转角度列名。
        side_col: 层列名（Top/Bottom）。

    Returns:
        list[dict]: 每个组件的贴装信息。
    """
    placements: list[dict[str, Any]] = []
    with open(Path(path), newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ref = row.get(ref_col, "").strip()
            if not ref:
                continue
            placements.append(
                {
                    "ref": ref,
                    "pos_x_mm": _to_float(row.get(x_col, "")),
                    "pos_y_mm": _to_float(row.get(y_col, "")),
                    "rotation_deg": _to_float(row.get(rot_col, "")),
                    "side": row.get(side_col, ""),
                }
            )
    return placements


def _to_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0
