"""ADL 数据模型层。

包括装配体声明的核心数据结构：
- Instance / Model / ResolvedInstance
- Interface / Footprint
- Mate / MateConstraint / MateGraph
- Layout
- Assembly
- Catalog
- Tags

注意：几何相关类型（Transform、BBox、GeometryAssets 等）已从本包迁移到
``adl.geometry``。为保持向后兼容，它们仍可通过 ``adl.models`` 访问，但
不建议在新代码中使用。
"""

from .assembly import AssemblyFamily
from .base import (
    Instance,
    Model,
    ResolvedInstance,
    _make_namespace,
    _unflatten,
    get_non_overridable_fields,
)
from .catalog import (
    CatalogEntry,
    ComponentCatalogFamily,
    ServiceMethodCatalogFamily,
    merge_service_methods,
)

# 几何类型已迁移到 adl.geometry；此处保留兼容导入。
from .geometry import (  # noqa: F401
    BBox,
    GeometryAssets,
    KinematicEnvelope,
    LoadCapacity,
    Space,
    Transform,
    bbox_from_resolved,
)
from .grid import Grid, GridAxis
from .interface import (
    FootprintSpec,
    InterfaceSpec,
    effective_interface_type,
    get_interfaces_from_resolved,
    register_interface_type,
    register_interface_types,
    resolve_interface_ref,
)
from .layout import Layout, LayoutEntry
from .mating import (
    InterfacePairing,
    MateConstraint,
    MateConstraintOperator,
    MateGraph,
    MateSpec,
    MateTypeMeta,
    evaluate_operator,
    is_interface_ref,
    parse_mate_ref,
)
from .tags import Tags

__all__ = [
    "Instance",
    "Model",
    "ResolvedInstance",
    "_make_namespace",
    "_unflatten",
    "get_non_overridable_fields",
    "AssemblyFamily",
    "CatalogEntry",
    "ComponentCatalogFamily",
    "ServiceMethodCatalogFamily",
    "merge_service_methods",
    # 几何类型已迁移到 adl.geometry；以下保留兼容导出。
    "GeometryAssets",
    "KinematicEnvelope",
    "LoadCapacity",
    "Space",
    "Grid",
    "GridAxis",
    "InterfaceSpec",
    "FootprintSpec",
    "resolve_interface_ref",
    "get_interfaces_from_resolved",
    "effective_interface_type",
    "register_interface_type",
    "register_interface_types",
    "MateSpec",
    "MateConstraint",
    "MateConstraintOperator",
    "MateTypeMeta",
    "InterfacePairing",
    "MateGraph",
    "parse_mate_ref",
    "is_interface_ref",
    "evaluate_operator",
    "Layout",
    "LayoutEntry",
    "Tags",
    # 几何类型已迁移到 adl.geometry；以下保留兼容导出。
    "BBox",
    "bbox_from_resolved",
    "Transform",
]
