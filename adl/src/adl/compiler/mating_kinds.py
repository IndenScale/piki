"""MatingKind — 配合类型枚举和默认值注册。

定义接口之间的几何约束类型。不包含领域数据——领域数据由插件注册。
"""

from __future__ import annotations

from enum import Enum


class MatingKind(str, Enum):
    """接口配合类型。

    决定几何约束求解器的约束方程：
    - face:  两个平面法向对齐 + 距离 = 0
    - axis:  两条轴线重合（同轴约束）
    - point: 两个点重合（球窝约束）
    - slot:  一个方向自由平移 + 其余约束
    - rail:  沿导轨方向平移 + 两个方向约束
    - none:  无几何约束（仅逻辑配对：如电气信号、数据协议）
    """

    FACE = "face"
    AXIS = "axis"
    POINT = "point"
    SLOT = "slot"
    RAIL = "rail"
    NONE = "none"

    @property
    def constrained_dof(self) -> int:
        """返回此配合类型约束的自由度数（0-6）。"""
        return {
            MatingKind.FACE: 3,
            MatingKind.AXIS: 4,
            MatingKind.POINT: 3,
            MatingKind.SLOT: 2,
            MatingKind.RAIL: 5,
            MatingKind.NONE: 0,
        }[self]


# ---------------------------------------------------------------------------
# 默认注册表（由插件填充）
# ---------------------------------------------------------------------------

_DEFAULT_PARAMS: dict[str, dict] = {}


def get_default_mating_kind(interface_type: str) -> MatingKind:
    """获取接口类型的默认 mating_kind。"""
    params = _DEFAULT_PARAMS.get(interface_type, {})
    kind_str = params.get("mating_kind", "none")
    return MatingKind(kind_str)


def get_default_mating_params(interface_type: str) -> dict:
    """获取接口类型的默认 mating_params。"""
    return _DEFAULT_PARAMS.get(interface_type, {}).get("mating_params", {})


def register_mating_defaults(
    interface_type: str,
    mating_kind: str,
    mating_params: dict | None = None,
) -> None:
    """注册接口类型的默认配合参数（由插件调用）。"""
    _DEFAULT_PARAMS[interface_type] = {
        "mating_kind": mating_kind,
        "mating_params": mating_params or {},
    }


def reset_mating_defaults() -> None:
    """清空配合默认值注册表。仅供测试或编译器初始化使用。"""
    _DEFAULT_PARAMS.clear()
