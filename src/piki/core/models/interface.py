"""Interface 数据模型 (ADR-007, RFC-001).

Interface 是 Instance 对外暴露的可连接点，内嵌在 Instance 的 interfaces 列表中。
"""

from __future__ import annotations

import warnings
from typing import Any

from pydantic import BaseModel, Field, field_validator


class InterfaceSpec(BaseModel):
    """离散的可连接接口。

    内嵌在 Family/Instance 中，不作为独立 Instance。
    """

    id: str = Field(..., description="Instance 内唯一标识：eth0, power-a, hole-3")
    interface_type: str = Field(..., description="接口类型：SFP28, IEC-C14, M16-bolt-hole")
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
        try:
            from piki.extensions.telecom.types import is_valid_interface_type, known_interface_types

            if not is_valid_interface_type(v):
                known = ", ".join(known_interface_types())
                warnings.warn(
                    f"Unknown interface_type: '{v}'. Known telecom types: {known}",
                    UserWarning,
                    stacklevel=2,
                )
        except ImportError:
            # telecom 插件未安装时不做校验
            pass
        return v


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

    Interface 存储在 _resolved['interfaces'] 中，
    可能是 list[dict] 形式，需转换为 InterfaceSpec。
    """
    raw = inst._resolved.get("interfaces")
    if raw is None:
        return []
    if isinstance(raw, list):
        result = []
        for item in raw:
            if isinstance(item, InterfaceSpec):
                result.append(item)
            elif isinstance(item, dict):
                try:
                    result.append(InterfaceSpec.model_validate(item))
                except Exception:
                    pass
        return result
    return []
