"""SpatialCollisionPass —— 兼容性重导出。

.. deprecated::
    本 Pass 已迁移到 ``adl.geometry.passes.spatial_collision``。
    它不再由 ADL 编译器默认注册；请在 piki 规则或生成器阶段按需启用。
"""

from __future__ import annotations

from adl.geometry.passes.spatial_collision import SpatialCollisionPass

__all__ = ["SpatialCollisionPass"]
