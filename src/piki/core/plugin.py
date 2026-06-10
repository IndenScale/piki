"""Plugin 基类和插件发现机制。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .checker import Checker
    from .registry import Registry


class Plugin:
    """行业插件基类。"""

    name: str = ""
    version: str = "0.1.0"

    def register_families(self, registry: Registry) -> None:
        """注册 Family 定义。"""
        pass

    def register_rules(self, checker: Checker) -> None:
        """注册检查规则。"""
        pass

    def register_generators(self, checker: Checker) -> None:
        """注册生成器。"""
        pass


def discover_plugins() -> dict[str, type[Plugin]]:
    """发现插件：先扫描内置 extensions，再扫描外部 piki.plugins 包。"""
    from importlib import import_module
    from pkgutil import iter_modules

    plugins: dict[str, type[Plugin]] = {}

    # 1. 内置 extensions
    try:
        import piki.extensions as ext_pkg

        for _, name, _ in iter_modules(ext_pkg.__path__, ext_pkg.__name__ + "."):
            try:
                mod = import_module(name)
                for attr in dir(mod):
                    obj = getattr(mod, attr)
                    if (
                        isinstance(obj, type)
                        and issubclass(obj, Plugin)
                        and obj is not Plugin
                        and getattr(obj, "name", None)
                    ):
                        plugins[obj.name] = obj
            except Exception as exc:  # pragma: no cover
                import logging

                logging.getLogger(__name__).warning(
                    "Failed to load extension %s: %s", name, exc
                )
    except ImportError:
        pass

    # 2. 外部 plugins（pip 安装的第三方插件）
    try:
        import piki.plugins as plugins_pkg

        for _, name, _ in iter_modules(
            plugins_pkg.__path__, plugins_pkg.__name__ + "."
        ):
            try:
                mod = import_module(name)
                for attr in dir(mod):
                    obj = getattr(mod, attr)
                    if (
                        isinstance(obj, type)
                        and issubclass(obj, Plugin)
                        and obj is not Plugin
                        and getattr(obj, "name", None)
                    ):
                        plugins[obj.name] = obj
            except Exception as exc:  # pragma: no cover
                import logging

                logging.getLogger(__name__).warning(
                    "Failed to load plugin %s: %s", name, exc
                )
    except ImportError:
        pass

    return plugins
