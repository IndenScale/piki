"""约束求解器 —— 兼容性重导出。

.. deprecated::
    本模块已迁移到 ``adl.geometry.constraint_solver``。
    ADL 核心不再内置几何求解；请在生成器/几何后端使用新位置。
"""

from __future__ import annotations

from adl.geometry.constraint_solver import (
    AxisConstraintParams,
    FaceConstraintParams,
    FaceName,
    ReferenceFace,
    SlotConstraintParams,
    solve_axis_mate,
    solve_face_mate,
    solve_slot_mate,
)

__all__ = [
    "FaceName",
    "ReferenceFace",
    "FaceConstraintParams",
    "AxisConstraintParams",
    "SlotConstraintParams",
    "solve_face_mate",
    "solve_axis_mate",
    "solve_slot_mate",
]
