"""Mate 文件加载器 (ADR-006).

扫描 `mates/` 目录，按 type 子目录加载 Mate YAML 文件。
一个文件 = 一个 MateSpec。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..models.mating import (
    InterfacePairing,
    MateConstraint,
    MateSpec,
)

logger = logging.getLogger(__name__)


def load_mates(project_root: Path) -> list[MateSpec]:
    """扫描 `mates/` 目录并加载所有 Mate 定义。

    目录结构::

        mates/
        ├── rack-mount/
        │   ├── RACK-A01-SRV-01.yaml
        │   └── RACK-A01-SRV-02.yaml
        ├── power-iec/
        │   └── PDU-A-SRV-01-A.yaml
        └── optical-link/
            └── SW-01-SRV-01.yaml

    Args:
        project_root: 项目根目录。

    Returns:
        所有成功加载的 MateSpec 列表。
    """
    mates_dir = project_root / "mates"
    if not mates_dir.exists() or not mates_dir.is_dir():
        return []

    mates: list[MateSpec] = []
    errors: list[str] = []

    for type_dir in sorted(mates_dir.iterdir()):
        if not type_dir.is_dir():
            continue

        mate_type = type_dir.name
        for yaml_file in sorted(type_dir.glob("*.yaml")):
            yml_file = yaml_file.with_suffix(".yml")
            if yml_file.exists():
                yaml_file = yml_file

        for yaml_file in sorted(type_dir.glob("*.yaml")):
            try:
                data = _load_yaml_file(yaml_file)
                mate = _parse_mate_yaml(data, mate_type, yaml_file)
                if mate:
                    mates.append(mate)
            except Exception as exc:
                msg = f"{yaml_file}: {exc}"
                errors.append(msg)
                logger.warning("Failed to load mate: %s", msg)

        # Also handle .yml extension
        for yml_file in sorted(type_dir.glob("*.yml")):
            # Skip if .yaml already loaded
            if yml_file.with_suffix(".yaml").exists():
                continue
            try:
                data = _load_yaml_file(yml_file)
                mate = _parse_mate_yaml(data, mate_type, yml_file)
                if mate:
                    mates.append(mate)
            except Exception as exc:
                msg = f"{yml_file}: {exc}"
                errors.append(msg)
                logger.warning("Failed to load mate: %s", msg)

    if errors:
        logger.warning(
            "Failed to load %d mate file(s):\n%s",
            len(errors),
            "\n".join(f"  - {e}" for e in errors),
        )

    return mates


def _load_yaml_file(path: Path) -> dict[str, Any]:
    """加载 YAML 文件为 dict。"""
    import yaml

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        raise ValueError("YAML file is empty")
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping, got {type(data).__name__}")
    return data


def _parse_mate_yaml(
    data: dict[str, Any],
    default_type: str,
    source: Path,
) -> MateSpec | None:
    """从 YAML dict 解析 MateSpec。

    YAML 格式示例::

        type: rack-mount-19inch   # 可选，目录名作为默认值
        parent: RACK-A01
        child: SRV-01
        at:
          u_start: 10
          u_span: 2
        constrains:
          - field: depth_mm
            operator: "<="
            value_ref: depth_mm
            message: "服务器深度超过机柜深度"
        pairings:
          - from: SRV-01/power-a
            to: PDU-A/out-3
            pairing_type: power-iec-c14-c13
    """
    # mate_type 优先使用 YAML 中声明的，否则用目录名
    mate_type = data.get("type", default_type)

    # 必填字段
    parent = data.get("parent")
    child = data.get("child")

    if not parent:
        raise ValueError("Missing required field: 'parent'")
    if not child:
        raise ValueError("Missing required field: 'child'")

    # at
    at = data.get("at", {})
    if at is None:
        at = {}
    if not isinstance(at, dict):
        raise ValueError(f"'at' must be a mapping, got {type(at).__name__}")

    # 可选字段
    media = str(data.get("media", ""))
    length_m = float(data.get("length_m", 0.0))

    # constrains
    constrains = _parse_constrains(data.get("constrains", []))

    # pairings
    pairings = _parse_pairings(data.get("pairings", []))

    return MateSpec(
        type=mate_type,
        parent=str(parent),
        child=str(child),
        at=at,
        media=media,
        length_m=length_m,
        constrains=constrains,
        pairings=pairings,
    )


def _parse_constrains(raw: Any) -> list[MateConstraint]:
    """解析 constrains 列表。"""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"'constrains' must be a list, got {type(raw).__name__}")

    result: list[MateConstraint] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"constrains[{i}] must be a mapping")
        result.append(MateConstraint.model_validate(item))
    return result


def _parse_pairings(raw: Any) -> list[InterfacePairing]:
    """解析 pairings 列表。"""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"'pairings' must be a list, got {type(raw).__name__}")

    result: list[InterfacePairing] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"pairings[{i}] must be a mapping")
        # InterfacePairing 使用 alias from/to
        result.append(InterfacePairing.model_validate(item))
    return result
