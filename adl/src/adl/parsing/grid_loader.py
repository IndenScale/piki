"""轴网（Grid）文件加载器。

Grid 资源位于项目 ``grids/`` 目录下，每个 ``.yaml`` 文件定义一个 Grid。
"""

from __future__ import annotations

from pathlib import Path

from adl.models.grid import Grid
from adl.parsing.loaders import load_yaml


def load_grids(root: Path) -> dict[str, Grid]:
    """扫描 ``grids/`` 目录并加载所有 Grid 资源。

    Args:
        root: 项目根目录。

    Returns:
        以 Grid ID 为键的字典。
    """
    grids: dict[str, Grid] = {}
    grids_dir = root / "grids"
    if not grids_dir.exists():
        return grids

    for path in sorted(grids_dir.rglob("*.yaml")):
        data = load_yaml(path)
        if not isinstance(data, dict):
            continue
        grid_id = data.get("id")
        if not grid_id:
            continue
        try:
            grid = Grid.model_validate(data)
        except Exception:
            # Schema 校验失败时跳过；项目加载器层的校验会补充诊断信息。
            continue
        grids[str(grid_id)] = grid

    return grids
