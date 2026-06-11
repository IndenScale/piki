"""Checker 单元测试 —— 覆盖规则引擎、装饰器、生成器。"""

from __future__ import annotations

import types

from piki.core.engine.checker import (
    _GEN_ATTR,
    _RULE_ATTR,
    Checker,
    CheckReport,
    RuleResult,
    generator,
    register_module_rules,
    rule,
)
from piki.core.engine.context import Context
from piki.core.engine.registry import Registry
from piki.core.models.diagnostic import Severity


class TestCheckerRun:
    """测试规则执行。"""

    def test_single_pass(self) -> None:
        checker = Checker()
        ctx = Context(Registry(), {})

        def always_pass(ctx: Context) -> None:
            pass

        checker.add_rule("R-001", "总是通过", always_pass)
        report = checker.run(ctx)
        assert report.passed is True
        assert report.error_count == 0
        assert report.pass_count == 1

    def test_single_fail(self) -> None:
        checker = Checker()
        ctx = Context(Registry(), {})

        def always_fail(ctx: Context) -> None:
            assert False, "出错了"

        checker.add_rule("R-001", "总是失败", always_fail)
        report = checker.run(ctx)
        assert report.passed is False
        assert report.error_count == 1
        assert report.pass_count == 0
        assert "出错了" in report.results[0].message

    def test_priority_order(self) -> None:
        """高 priority 先执行。"""
        checker = Checker()
        ctx = Context(Registry(), {})
        order: list[str] = []

        def first(ctx: Context) -> None:
            order.append("first")

        def second(ctx: Context) -> None:
            order.append("second")

        checker.add_rule("R-002", "后", second, priority=5)
        checker.add_rule("R-001", "先", first, priority=10)
        checker.run(ctx)
        assert order == ["first", "second"]

    def test_mixed_results(self) -> None:
        checker = Checker()
        ctx = Context(Registry(), {})

        checker.add_rule("R-001", "通过", lambda ctx: None)
        checker.add_rule("R-002", "失败", lambda ctx: exec("assert False, 'err'"))
        report = checker.run(ctx)
        assert report.error_count == 1
        assert report.pass_count == 1

    def test_exception_handling(self) -> None:
        """非 AssertionError 异常也应被捕获。"""
        checker = Checker()
        ctx = Context(Registry(), {})

        def boom(ctx: Context) -> None:
            raise ValueError("爆炸")

        checker.add_rule("R-001", "异常", boom)
        report = checker.run(ctx)
        assert report.error_count == 1
        assert "ValueError" in report.results[0].message


class TestGenerator:
    """测试生成器注册和执行。"""

    def test_register_and_generate(self) -> None:
        checker = Checker()
        ctx = Context(Registry(), {})
        called_with: dict = {}

        def my_gen(ctx: Context, config: dict) -> None:
            called_with["config"] = config

        checker.add_generator("my-gen", "我的生成器", my_gen)
        assert [(gid, name) for gid, name, _fn in checker.list_generators()] == [
            ("my-gen", "我的生成器")
        ]

        checker.generate("my-gen", ctx, {"format": "csv"})
        assert called_with["config"] == {"format": "csv"}

    def test_unknown_generator(self) -> None:
        checker = Checker()
        ctx = Context(Registry(), {})
        with pytest.raises(KeyError, match="Unknown generator"):
            checker.generate("missing", ctx, {})


class TestDecorators:
    """测试 @rule 和 @generator 装饰器（模块级别元数据，无全局状态）。"""

    def test_rule_decorator_attaches_metadata(self) -> None:
        """装饰器应在函数上附加 __piki_rule_meta__，不写入全局列表。"""

        @rule("DECOR-001", "装饰器规则", priority=5)
        def my_rule(ctx: Context) -> None:
            pass

        meta = getattr(my_rule, _RULE_ATTR, None)
        assert meta is not None
        rule_id, name, prio, severity = meta
        assert rule_id == "DECOR-001"
        assert name == "装饰器规则"
        assert prio == 5
        assert severity == Severity.ERROR
        assert my_rule is not None

    def test_generator_decorator_attaches_metadata(self) -> None:
        """装饰器应在函数上附加 __piki_gen_meta__，不写入全局列表。"""

        @generator("my-gen", "我的生成器")
        def my_gen(ctx: Context, config: dict) -> None:
            pass

        meta = getattr(my_gen, _GEN_ATTR, None)
        assert meta is not None
        gen_id, name = meta
        assert gen_id == "my-gen"
        assert name == "我的生成器"
        assert my_gen is not None

    def test_register_module_rules_scans_module(self) -> None:
        """register_module_rules 应扫描模块中带有元数据的函数并注册。"""

        # 构造一个模拟模块
        mod = types.ModuleType("fake_rules")

        @rule("MOD-001", "模块规则")
        def mod_rule(ctx: Context) -> None:
            pass

        @generator("MOD-GEN-001", "模块生成器")
        def mod_gen(ctx: Context, config: dict) -> None:
            pass

        # 将函数放入模块
        mod.mod_rule = mod_rule  # type: ignore[attr-defined]
        mod.mod_gen = mod_gen  # type: ignore[attr-defined]

        checker = Checker()
        register_module_rules(checker, mod)

        assert len(checker._rules) == 1
        assert checker._rules[0][0] == "MOD-001"
        assert len(checker._generators) == 1
        assert "MOD-GEN-001" in checker._generators

    def test_register_module_rules_with_none_module(self) -> None:
        """传入 None 时应安全返回，不报错。"""
        checker = Checker()
        register_module_rules(checker, None)
        assert len(checker._rules) == 0
        assert len(checker._generators) == 0

    def test_register_module_rules_isolation(self) -> None:
        """不同模块的规则应相互隔离，不会互相污染。"""
        mod_a = types.ModuleType("rules_a")
        mod_b = types.ModuleType("rules_b")

        @rule("A-001", "规则 A")
        def rule_a(ctx: Context) -> None:
            pass

        @rule("B-001", "规则 B")
        def rule_b(ctx: Context) -> None:
            pass

        mod_a.rule_a = rule_a  # type: ignore[attr-defined]
        mod_b.rule_b = rule_b  # type: ignore[attr-defined]

        checker_a = Checker()
        checker_b = Checker()

        register_module_rules(checker_a, mod_a)
        register_module_rules(checker_b, mod_b)

        assert len(checker_a._rules) == 1
        assert checker_a._rules[0][0] == "A-001"
        assert len(checker_b._rules) == 1
        assert checker_b._rules[0][0] == "B-001"


class TestCheckReport:
    """测试 CheckReport 数据类。"""

    def test_empty_report_passes(self) -> None:
        report = CheckReport()
        assert report.passed is True
        assert report.error_count == 0
        assert report.pass_count == 0

    def test_passed_property(self) -> None:
        report = CheckReport(
            results=[
                RuleResult("R-001", "通过", True),
                RuleResult("R-002", "失败", False, message="err"),
            ]
        )
        assert report.passed is False
        assert report.error_count == 1
        assert report.pass_count == 1

    def test_all_pass(self) -> None:
        report = CheckReport(
            results=[
                RuleResult("R-001", "通过", True),
                RuleResult("R-002", "也通过", True),
            ]
        )
        assert report.passed is True


class TestRelatedInformationAndSuggestion:
    """测试 related_information 和 suggestion 在规则结果中的传递。"""

    def test_related_info_in_rule_result(self) -> None:
        from piki.core.models.diagnostic import Location

        checker = Checker()
        ctx = Context(Registry(), {})

        def rule_with_related(ctx: Context) -> None:
            ctx.set_current_file("/path/to/file.yaml")
            ctx.add_related_info(
                Location(uri="file:///path/to/other.yaml"),
                "关联信息：请检查此处",
            )
            assert False, "主错误"

        checker.add_rule("R-REL", "关联信息测试", rule_with_related)
        report = checker.run(ctx)

        assert report.error_count == 1
        result = report.results[0]
        assert result.rule_id == "R-REL"
        assert len(result.related_information) == 1
        assert result.related_information[0].message == "关联信息：请检查此处"

    def test_suggestion_in_rule_result(self) -> None:
        checker = Checker()
        ctx = Context(Registry(), {})

        def rule_with_suggestion(ctx: Context) -> None:
            ctx.set_current_file("/path/to/file.yaml")
            ctx.set_suggestion("将设备迁移到另一个 PDU")
            assert False, "PDU 过载"

        checker.add_rule("R-SUG", "建议测试", rule_with_suggestion)
        report = checker.run(ctx)

        assert report.error_count == 1
        result = report.results[0]
        assert result.suggestion == "将设备迁移到另一个 PDU"

    def test_suggestion_in_diagnostic(self) -> None:
        from piki.core.models.diagnostic import Severity

        checker = Checker()
        ctx = Context(Registry(), {})

        def rule_with_suggestion(ctx: Context) -> None:
            ctx.set_suggestion("检查配置文件")
            assert False, "配置错误"

        checker.add_rule("R-DIAG", "诊断测试", rule_with_suggestion)
        report = checker.run(ctx)

        diag = report.results[0].to_diagnostic()
        assert diag.data.get("suggestion") == "检查配置文件"
        assert diag.severity == Severity.ERROR

    def test_clear_current_file_clears_related(self) -> None:
        from piki.core.models.diagnostic import Location

        ctx = Context(Registry(), {})
        ctx.add_related_info(
            Location(uri="file:///a.yaml"),
            "info",
        )
        ctx.set_suggestion("建议")
        ctx.clear_current_file()

        assert ctx.pop_related_info() == []
        assert ctx.pop_suggestion() == ""


import pytest
