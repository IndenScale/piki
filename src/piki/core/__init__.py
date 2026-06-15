"""piki core — 框架内核。"""

from adl.diagnostics import Severity

from .__version__ import __version__
from .engine.checker import generator, rule
from .engine.context import Context
from .plugin import Plugin
from .project import Project

__all__ = [
    "__version__",
    "Plugin",
    "Context",
    "rule",
    "generator",
    "Severity",
    "Project",
]
