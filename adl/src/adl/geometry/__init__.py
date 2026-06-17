"""ADL 几何后端。

几何能力从 ADL 核心声明层剥离后集中于此：
- 三维向量、变换、包围盒等基础几何模型
- 接口运动自由度签名
- 基于 Mate 的约束求解
- AABB 碰撞检测
- GeometryProvider：按需解析几何

ADL 核心（adl.models / adl.project / adl.compiler）不依赖本包；
只有生成器、渲染器或可选空间规则才需要导入。
"""

from __future__ import annotations

from adl.geometry.assembly_builder import AssemblyBuilder
from adl.geometry.assembly_scene import (
    AssemblyControl,
    AssemblyEntity,
    AssemblyMaterial,
    AssemblyScene,
    InterfacePose,
)
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
from adl.geometry.provider import GeometryProvider, ResolvedGeometry

__all__ = [
    # assembly builder
    "AssemblyBuilder",
    # assembly scene
    "AssemblyScene",
    "AssemblyEntity",
    "AssemblyControl",
    "AssemblyMaterial",
    "InterfacePose",
    # models
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
    # constraint solver
    "FaceName",
    "ReferenceFace",
    "FaceConstraintParams",
    "AxisConstraintParams",
    "SlotConstraintParams",
    "solve_face_mate",
    "solve_axis_mate",
    "solve_slot_mate",
    # interface signature
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
    # provider
    "GeometryProvider",
    "ResolvedGeometry",
]
