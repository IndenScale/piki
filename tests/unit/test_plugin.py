"""Plugin 单元测试 —— 覆盖插件发现和基类。"""

from __future__ import annotations

from piki.core.plugin import Plugin, discover_plugins


class TestPluginBase:
    """测试 Plugin 基类。"""

    def test_default_methods(self) -> None:
        """基类方法默认不执行任何操作。"""
        p = Plugin()
        assert p.name == ""
        assert p.version == "0.1.0"
        # 以下调用不应抛异常
        p.register_families(None)  # type: ignore[arg-type]
        p.register_rules(None)  # type: ignore[arg-type]
        p.register_generators(None)  # type: ignore[arg-type]


class TestDiscoverPlugins:
    """测试插件发现。"""

    def test_discovers_builtin_telecom(self) -> None:
        plugins = discover_plugins()
        assert "telecom" in plugins
        cls = plugins["telecom"]
        assert cls.name == "telecom"
        assert cls.version == "0.1.0"

    def test_returns_dict(self) -> None:
        plugins = discover_plugins()
        assert isinstance(plugins, dict)
        for name, cls in plugins.items():
            assert isinstance(name, str)
            assert issubclass(cls, Plugin)
            assert cls is not Plugin
            assert cls.name
