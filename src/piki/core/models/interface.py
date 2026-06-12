"""Interface 数据模型 (ADR-005, RFC-001).

Interface 是 Instance 对外暴露的可连接点，内嵌在 Instance 的 interfaces 列表中。
"""

from __future__ import annotations

import warnings
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# 全局接口类型注册表
# ---------------------------------------------------------------------------

_known_interface_types: set[str] = set()


def register_interface_type(type_name: str) -> None:
    """注册一个已知接口类型。

    插件在初始化时调用，把自己的接口类型加入全局注册表。
    """
    _known_interface_types.add(type_name)


def register_interface_types(type_names: list[str]) -> None:
    """批量注册已知接口类型。"""
    _known_interface_types.update(type_names)


def is_known_interface_type(type_name: str) -> bool:
    """检查是否为已注册的已知接口类型。"""
    return type_name in _known_interface_types


def get_known_interface_types() -> list[str]:
    """返回所有已注册接口类型（排序）。"""
    return sorted(_known_interface_types)


class InterfaceSpec(BaseModel):
    """离散的可连接接口。

    内嵌在 Family/Instance 中，不作为独立 Instance。
    """

    id: str = Field(..., description="Instance 内唯一标识：eth0, power-a, hole-3")
    interface_type: str = Field(..., description="接口类型：SFP28, IEC-C14, M16-bolt-hole")
    active_type: str | None = Field(
        default=None,
        description="多形态接口（如 Combo 口）当前实际激活的类型。未指定时退化为 interface_type。",
    )
    direction: str = Field(
        default="bidirectional",
        description="input | output | bidirectional",
    )
    description: str = Field(default="", description="人类可读描述")

    # 接口自身的规格参数（自由扩展，由领域插件定义约束）
    specs: dict[str, Any] = Field(default_factory=dict, description="规格键值对")

    @field_validator("interface_type")
    @classmethod
    def validate_known_type(cls, v: str) -> str:
        """校验接口类型是否为已知值（RFC-001）。

        不是 Error——允许项目使用枚举外的自定义类型。
        对未知类型发出 UserWarning。
        """
        known_types = _known_interface_types
        if not known_types:
            # 向后兼容：未启用任何插件时，尝试加载 telecom 类型作为默认已知类型
            try:
                from piki.extensions.telecom.types import COMPATIBILITY

                known_types = set(COMPATIBILITY.keys())
            except ImportError:
                known_types = set()

        if known_types and v not in known_types:
            warnings.warn(
                f"Unknown interface_type: '{v}'. Known types: {', '.join(sorted(known_types))}",
                UserWarning,
                stacklevel=2,
            )
        return v


class FootprintSpec(BaseModel):
    """复合接口/连接器封装。

    一个 Footprint 包含多个 pin，每个 pin 是一个 InterfaceSpec。
    用于建模 USB-C 母座、JST 电池座、轴体焊盘等多 pin 连接器。
    """

    id: str = Field(..., description="Footprint 在 Instance 内唯一标识：usb-c, jst-batt")
    footprint_type: str = Field(..., description="封装类型：usb-c-16p, jst-ph-2pin")
    description: str = Field(default="", description="人类可读描述")
    pins: list[InterfaceSpec] = Field(default_factory=list, description="引脚列表")


def resolve_interface_ref(ref: str) -> tuple[str, str]:
    """解析 'instance_id/interface_id' 引用。

    Args:
        ref: 形如 'SRV-01/eth0' 的引用字符串。

    Returns:
        (instance_id, interface_id)

    Raises:
        ValueError: 引用格式无效（不含 '/'）。
    """
    if "/" not in ref:
        raise ValueError(
            f"Invalid interface reference: '{ref}'. Expected format: 'instance_id/interface_id'"
        )
    parts = ref.split("/", 1)
    return parts[0], parts[1]


def get_interfaces_from_resolved(inst: Any) -> list[InterfaceSpec]:
    """从 ResolvedInstance 中提取 InterfaceSpec 列表。

    包括：
    1. 直接声明在 interfaces 中的接口
    2. 声明在 footprints 中的连接器的每个 pin（pin id 自动带上 footprint id 前缀，
       例如 usb-c/VBUS）

    Interface 存储在 _resolved['interfaces'] 中，
    可能是 list[dict] 形式，需转换为 InterfaceSpec。
    """
    result: list[InterfaceSpec] = []

    # 1. 直接接口
    raw = inst._resolved.get("interfaces")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, InterfaceSpec):
                result.append(item)
            elif isinstance(item, dict):
                try:
                    result.append(InterfaceSpec.model_validate(item))
                except Exception:
                    pass

    # 2. Footprint 中的 pin
    raw_fps = inst._resolved.get("footprints")
    if isinstance(raw_fps, list):
        for fp_item in raw_fps:
            if isinstance(fp_item, FootprintSpec):
                fp = fp_item
            elif isinstance(fp_item, dict):
                try:
                    fp = FootprintSpec.model_validate(fp_item)
                except Exception:
                    continue
            else:
                continue
            for pin in fp.pins:
                # 给 pin id 加上 footprint 前缀，支持 3 级引用
                qualified_id = f"{fp.id}/{pin.id}"
                result.append(
                    InterfaceSpec(
                        id=qualified_id,
                        interface_type=pin.interface_type,
                        active_type=pin.active_type,
                        direction=pin.direction,
                        description=pin.description,
                        specs=pin.specs,
                    )
                )

    return result


def effective_interface_type(iface: InterfaceSpec) -> str:
    """返回接口用于兼容性/线缆检查的有效类型。

    对于 Combo/多形态接口，如果声明了 active_type，则使用 active_type；
    否则退化为 interface_type。
    """
    return iface.active_type if iface.active_type else iface.interface_type
