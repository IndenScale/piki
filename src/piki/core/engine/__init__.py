"""规则引擎层 —— Checker、Registry、Query、Context、Generator。"""

from .checker import (
    Checker,
    CheckReport,
    GenFunc,
    RuleFunc,
    RuleResult,
    register_module_rules,
    rule,
)
from .context import Context
from .generator_registry import (
    GeneratorRegistry,
    GeneratorResult,
    generator,
)
from .query import QuerySet
from .registry import Registry

__all__ = [
    "Checker",
    "CheckReport",
    "RuleResult",
    "RuleFunc",
    "GenFunc",
    "rule",
    "generator",
    "register_module_rules",
    "GeneratorRegistry",
    "GeneratorResult",
    "Context",
    "Registry",
    "QuerySet",
]
