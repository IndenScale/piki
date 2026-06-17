"""InterfaceSignature —— 兼容性重导出。

.. deprecated::
    本模块已迁移到 ``adl.geometry.interface_signature``。
    接口运动自由度签名属于几何后端，ADL 核心不再默认导出。
"""

from __future__ import annotations

from adl.geometry.interface_signature import (
    DOF,
    DiscreteState,
    DOFType,
    InterfaceSignature,
    SignatureCoupling,
    SignatureStage,
    build_default_signatures,
    couple_signatures,
    get_signature,
    register_signature,
)

__all__ = [
    "DOFType",
    "DOF",
    "DiscreteState",
    "SignatureStage",
    "InterfaceSignature",
    "SignatureCoupling",
    "couple_signatures",
    "register_signature",
    "get_signature",
    "build_default_signatures",
]
