"""ADL 数据模型层。

包括装配体声明的核心数据结构：
- Instance / Model / ResolvedInstance
- Interface / Footprint
- Mate / MateConstraint / MateGraph
- Layout
- Assembly
- Catalog
- Tags
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
from .geometry import GeometryAssets
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
    "GeometryAssets",
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
]
