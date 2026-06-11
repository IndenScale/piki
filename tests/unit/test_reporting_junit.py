"""Reporting JUnit 格式单元测试。"""

from __future__ import annotations

from piki.core.engine.checker import CheckReport, RuleResult
from piki.core.reporting.formats import format_junit


class TestFormatJUnit:
    """测试 JUnit XML 格式输出。"""

    def test_empty_report(self) -> None:
        report = CheckReport()
        output = format_junit(report)
        assert '<?xml version="1.0" encoding="UTF-8"?>' in output
        assert '<testsuite name="piki" tests="0" failures="0" errors="0"' in output

    def test_pass_only(self) -> None:
        report = CheckReport(
            results=[
                RuleResult("R-001", "规则1", True),
            ]
        )
        output = format_junit(report)
        assert '<testcase name="规则1" classname="R-001"' in output
        assert "<failure" not in output

    def test_fail_with_message(self) -> None:
        report = CheckReport(
            results=[
                RuleResult("R-001", "规则1", True),
                RuleResult("R-002", "规则2", False, message="出错了", file="a.yaml"),
            ]
        )
        output = format_junit(report)
        assert '<testcase name="规则1" classname="R-001"' in output
        assert '<testcase name="规则2" classname="R-002" file="a.yaml"' in output
        assert '<failure message="出错了">' in output
        assert "出错了" in output

    def test_report_counts(self) -> None:
        report = CheckReport(
            results=[
                RuleResult("R-001", "规则1", True),
                RuleResult("R-002", "规则2", False, message="err"),
                RuleResult("R-003", "规则3", False, message="err2"),
            ]
        )
        output = format_junit(report)
        assert 'tests="3"' in output
        assert 'failures="2"' in output
