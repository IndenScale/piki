"""Plugin 基类和插件发现机制。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adl.types import TypeRegistry

if TYPE_CHECKING:
    from .checker import Checker
    from .engine.registry import Registry


class Plugin:
    """行业插件基类。

    插件是领域知识的封装单元，负责：
    1. 通过 ``register_types`` 向 ADL 注册 Family Schema、Mate type、Interface type。
    2. 通过 ``register_rules`` 向 piki 规则引擎注册检查规则。
    3. 通过 ``register_generators`` 向 piki 注册生成器。
    """

    name: str = ""
    version: str = "0.1.0"

    def register_types(self, type_registry: TypeRegistry) -> None:
        """注册 ADL 类型：Family Schema、Mate type、Interface type 等。"""
        pass

    def register_rules(self, checker: "Checker") -> None:
        """注册检查规则。"""
        pass

    def register_generators(self, checker: "Checker") -> None:
        """注册生成器。"""
        pass

    # ------------------------------------------------------------------
    # 向后兼容接口（旧插件 / 旧测试）
    # ------------------------------------------------------------------

    def register_families(self, registry: "Registry") -> None:
        """向后兼容：委托到 ``register_types``。

        旧代码和旧测试可能直接调用 ``plugin.register_families(registry)``。
        如果 registry 背后有 Project，则取出其 TypeRegistry 传给新接口。
        """
        project = getattr(registry, "project", None)
        if project is not None:
            self.register_types(project.type_registry)

    def register_mate_types(self, registry: "Registry") -> None:
        """向后兼容：Mate type 注册已合并到 ``register_types``，此方法不再调用。"""
        project = getattr(registry, "project", None)
        if project is not None:
            self.register_types(project.type_registry)


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

                logging.getLogger(__name__).warning("Failed to load extension %s: %s", name, exc)
    except ImportError:
        pass

    # 2. 外部 plugins（pip 安装的第三方插件）
    try:
        import piki.plugins as plugins_pkg

        for _, name, _ in iter_modules(plugins_pkg.__path__, plugins_pkg.__name__ + "."):
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

                logging.getLogger(__name__).warning("Failed to load plugin %s: %s", name, exc)
    except ImportError:
        pass

    return plugins
