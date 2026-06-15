"""YAML / TOML 加载工具。

load_yaml 现在返回 SourceTrackedDict，支持字段级行号追踪。
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from .yaml_source import load_yaml_with_source


def load_yaml(path: Path) -> dict[str, Any]:
    """加载 YAML 文件，返回带源码位置追踪的 dict。

    返回 SourceTrackedDict，可通过 _get_source(key) 获取字段行号。
    对于不需要行号的代码，可以当作普通 dict 使用。
    """
    return load_yaml_with_source(path)


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def load_toml(path: Path) -> dict[str, Any]:
    with open(path, "rb") as f:
        return tomllib.load(f)
