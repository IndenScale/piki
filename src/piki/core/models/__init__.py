"""数据模型层 —— 核心数据结构、Diagnostic 系统。"""

from .assembly import AssemblyFamily
from .base import Instance, Model, ResolvedInstance, _make_namespace, _unflatten
from .diagnostic import (
    CodeDescription,
    Diagnostic,
    DiagnosticReport,
    Location,
    Position,
    Range,
    RelatedInformation,
    Severity,
)
from .interface import InterfaceSpec, get_interfaces_from_resolved, resolve_interface_ref
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

__all__ = [
    # base
    "Instance",
    "Model",
    "ResolvedInstance",
    "_make_namespace",
    "_unflatten",
    # assembly
    "AssemblyFamily",
    # interface
    "InterfaceSpec",
    "resolve_interface_ref",
    "get_interfaces_from_resolved",
    # mating
    "MateSpec",
    "MateConstraint",
    "MateConstraintOperator",
    "MateTypeMeta",
    "InterfacePairing",
    "MateGraph",
    "parse_mate_ref",
    "is_interface_ref",
    "evaluate_operator",
    # diagnostic
    "Severity",
    "Position",
    "Range",
    "Location",
    "RelatedInformation",
    "CodeDescription",
    "Diagnostic",
    "DiagnosticReport",
]
