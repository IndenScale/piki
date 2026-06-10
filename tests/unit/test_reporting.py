"""Reporting 单元测试 —— 覆盖 human/json 格式输出。"""

from __future__ import annotations

from piki.core.engine.checker import CheckReport, RuleResult
from piki.core.reporting.formats import format_human, format_json, format_report


class TestFormatHuman:
    """测试人类可读格式。"""

    def test_empty_report(self) -> None:
        report = CheckReport()
        output = format_human(report)
        assert "总计: 0 错误, 0 通过" in output

    def test_pass_only(self) -> None:
        report = CheckReport(results=[
            RuleResult("R-001", "规则1", True),
        ])
        output = format_human(report)
        assert "[PASS] R-001: 规则1" in output
        assert "总计: 0 错误, 1 通过" in output

    def test_fail_with_message(self) -> None:
        report = CheckReport(results=[
            RuleResult("R-001", "规则1", True),
            RuleResult("R-002", "规则2", False, message="出错了\n第二行"),
        ])
        output = format_human(report)
        assert "[PASS] R-001: 规则1" in output
        assert "[FAIL] R-002: 规则2" in output
        assert "       出错了" in output
        assert "       第二行" in output
        assert "总计: 1 错误, 1 通过" in output

    def test_fail_empty_message(self) -> None:
        report = CheckReport(results=[
            RuleResult("R-001", "规则1", False, message=""),
        ])
        output = format_human(report)
        assert "[FAIL] R-001: 规则1" in output


class TestFormatJson:
    """测试 JSON 格式。"""

    def test_basic(self) -> None:
        report = CheckReport(results=[
            RuleResult("R-001", "规则1", True),
            RuleResult("R-002", "规则2", False, message="err", file="a.yaml"),
        ])
        output = format_json(report)
        import json
        data = json.loads(output)
        assert data["passed"] is False
        assert data["error_count"] == 1
        assert data["pass_count"] == 1
        assert len(data["results"]) == 2
        assert data["results"][0]["rule_id"] == "R-001"
        assert data["results"][1]["message"] == "err"
        assert data["results"][1]["file"] == "a.yaml"

    def test_empty(self) -> None:
        report = CheckReport()
        output = format_json(report)
        import json
        data = json.loads(output)
        assert data["passed"] is True
        assert data["results"] == []


class TestFormatReport:
    """测试 format_report 路由。"""

    def test_json_format(self) -> None:
        report = CheckReport(results=[
            RuleResult("R-001", "规则1", True),
        ])
        output = format_report(report, "json")
        assert '"passed": true' in output

    def test_human_default(self) -> None:
        report = CheckReport(results=[
            RuleResult("R-001", "规则1", True),
        ])
        output = format_report(report, "human")
        assert "[PASS]" in output

    def test_unknown_format_fallback(self) -> None:
        report = CheckReport(results=[
            RuleResult("R-001", "规则1", True),
        ])
        output = format_report(report, "unknown")
        assert "[PASS]" in output
