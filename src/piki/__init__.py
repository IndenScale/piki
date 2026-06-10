"""piki: 工程设计的挑剔伙伴。

公共 API 从 core 透传，便于用户写规则时 `from piki import rule, Context`。
"""

from piki.core import (
    __version__,
    Plugin,
    Context,
    rule,
    generator,
    Severity,
    Project,
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
