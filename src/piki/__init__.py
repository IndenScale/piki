"""piki: Software-Defined Hardware (SDH) Framework — 设计的本质是决策，不是画图。

公共 API 从 core 透传，便于用户写规则时 `from piki import rule, Context`。
"""

from piki.core import (
    Context,
    Plugin,
    Project,
    Severity,
    __version__,
    generator,
    rule,
)

__all__ = [
    "__version__",
    "Plugin",
    "Context",
    "rule",
    "generator",
    "Severity",
    "Project",
]
