"""几何资产 Schema —— 兼容性重导出。

.. deprecated::
    本模块已迁移到 ``adl.geometry``。
    请优先从 ``adl.geometry`` 导入几何类型；
    ``adl.models.geometry`` 仅保留用于平滑过渡。
"""

from __future__ import annotations

from adl.geometry.models import (
    AssetReference,
    BBox,
    CSGNode,
    GeometryAssets,
    InlineGeometry,
    KinematicEnvelope,
    LoadCapacity,
    Space,
    Transform,
    Vec3,
    bbox_from_resolved,
    compose_transforms,
    transform_from_absolute,
)

__all__ = [
    "Vec3",
    "Transform",
    "compose_transforms",
    "transform_from_absolute",
    "InlineGeometry",
    "CSGNode",
    "AssetReference",
    "GeometryAssets",
    "KinematicEnvelope",
    "Space",
    "LoadCapacity",
    "BBox",
    "bbox_from_resolved",
]
