"""piki plugins — 插件管理。

列出、管理已安装的行业插件。
"""

from __future__ import annotations

from piki.core.plugin import discover_plugins


def cmd_plugins_list() -> int:
    """执行 plugins list 命令。

    扫描内置 extensions 和外部 piki.plugins 包，列出所有可用插件。

    Returns:
        退出码：始终返回 0。
    """
    plugins = discover_plugins()
    print("Available plugins:")
    for name in sorted(plugins):
        cls = plugins[name]
        print(f"  {name:<20} {cls.version}")
    return 0
