"""ADL (Assembly Definition Language) — 装配体定义语言运行时。

ADL 是一个独立的声明式建模语言运行时库，负责：
- 解析 YAML 形式的 ADL 声明
- 构建装配体的内存模型（Instance / Mate / Layout / Connection）
- 执行 ADL 层级的验证（Schema、引用完整性、Mate 约束）
- 返回结构化的 Diagnostic 报告

ADL 不依赖任何具体的编排框架（如 piki），也不包含插件、规则引擎或 CLI。
"""

from adl.diagnostics import (
    CodeDescription,
    Diagnostic,
    DiagnosticReport,
    Location,
    Position,
    Range,
    RelatedInformation,
    Severity,
)
from adl.models import (
    AssemblyFamily,
    CatalogEntry,
    FootprintSpec,
    Instance,
    InterfacePairing,
    InterfaceSpec,
    Layout,
    LayoutEntry,
    MateConstraint,
    MateConstraintOperator,
    MateGraph,
    MateSpec,
    MateTypeMeta,
    Model,
    ResolvedInstance,
    Tags,
    effective_interface_type,
    evaluate_operator,
    get_interfaces_from_resolved,
    is_interface_ref,
    parse_mate_ref,
    resolve_interface_ref,
)
from adl.project import Project, ProjectLoader
from adl.types import TypeRegistry

__all__ = [
    # project
    "Project",
    "ProjectLoader",
    # types
    "TypeRegistry",
    # diagnostics
    "Severity",
    "Position",
    "Range",
    "Location",
    "RelatedInformation",
    "CodeDescription",
    "Diagnostic",
    "DiagnosticReport",
    # models
    "Instance",
    "Model",
    "ResolvedInstance",
    "InterfaceSpec",
    "FootprintSpec",
    "resolve_interface_ref",
    "get_interfaces_from_resolved",
    "effective_interface_type",
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
    "AssemblyFamily",
    "CatalogEntry",
    "Tags",
]
