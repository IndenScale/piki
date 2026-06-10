"""数据模型层 —— 核心数据结构、Diagnostic 系统。"""

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

__all__ = [
    # base
    "Instance",
    "Model",
    "ResolvedInstance",
    "_make_namespace",
    "_unflatten",
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
