"""报告格式化 —— 支持 Diagnostic 系统的多级 severity 输出。"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any

from adl.diagnostics import Severity

from ..engine.checker import CheckReport


def _severity_label(severity: Severity) -> str:
    return {
        Severity.FATAL: "[FATAL]",
        Severity.ERROR: "[ERROR]",
        Severity.WARNING: "[WARN]",
        Severity.INFO: "[INFO]",
        Severity.DEBUG: "[DEBUG]",
    }.get(severity, "[?]")


def format_human(report: CheckReport) -> str:
    lines: list[str] = []

    # 1. 规则结果（向后兼容）
    for result in report.results:
        status = "[PASS]" if result.passed else "[FAIL]"
        lines.append(f"{status} {result.rule_id}: {result.name}")
        if not result.passed and result.message:
            for msg_line in result.message.splitlines():
                lines.append(f"       {msg_line}")
        # related_information
        for ri in result.related_information:
            lines.append(f"       -> {ri.location}: {ri.message}")
        # 修复建议
        if result.suggestion:
            lines.append(f"       💡 建议: {result.suggestion}")

    # 2. Diagnostic 输出（带 severity 和位置）
    for diag in report.diagnostics:
        label = _severity_label(diag.severity)
        loc_str = f" {diag.location}" if diag.location.uri else ""
        code_str = f" [{diag.code}]" if diag.code else ""
        lines.append(f"{label}{code_str}{loc_str}: {diag.name or diag.source}")
        for msg_line in diag.message.splitlines():
            lines.append(f"       {msg_line}")
        # related_information
        for ri in diag.related_information:
            lines.append(f"       -> {ri.location}: {ri.message}")
        # 修复建议（来自 Diagnostic.data）
        suggestion = diag.data.get("suggestion", "") if diag.data else ""
        if suggestion:
            lines.append(f"       💡 建议: {suggestion}")

    lines.append("")
    lines.append("=" * 60)
    counts = f"{report.error_count} 错误"
    if report.warning_count > 0:
        counts += f", {report.warning_count} 警告"
    counts += f", {report.pass_count} 通过"
    lines.append(f"总计: {counts}")
    lines.append("=" * 60)
    return "\n".join(lines)


def format_json(report: CheckReport) -> str:
    """JSON 输出包含完整的 Diagnostic 信息（LSP-compatible）。"""
    data: dict[str, Any] = {
        "passed": report.passed,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
        "pass_count": report.pass_count,
        "results": [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "passed": r.passed,
                "message": r.message,
                "file": r.file,
            }
            for r in report.results
        ],
        "diagnostics": [d.to_dict() for d in report.all_diagnostics()],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def format_junit(report: CheckReport) -> str:
    """生成 JUnit XML 格式，便于 CI 集成。"""
    testsuites = ET.Element("testsuites")
    testsuite = ET.SubElement(
        testsuites,
        "testsuite",
        {
            "name": "piki",
            "tests": str(len(report.results) + len(report.diagnostics)),
            "failures": str(report.error_count),
            "errors": "0",
            "time": "0",
        },
    )
    # 规则结果
    for r in report.results:
        testcase = ET.SubElement(
            testsuite,
            "testcase",
            {
                "name": r.name,
                "classname": r.rule_id,
            },
        )
        if not r.passed:
            failure = ET.SubElement(testcase, "failure", {"message": r.message or "failed"})
            failure.text = r.message or "failed"
        if r.file:
            testcase.set("file", r.file)

    # Diagnostic 结果
    for d in report.diagnostics:
        testcase = ET.SubElement(
            testsuite,
            "testcase",
            {
                "name": d.name or d.code or "diagnostic",
                "classname": d.code or d.source,
            },
        )
        if d.severity >= Severity.ERROR:
            failure = ET.SubElement(testcase, "failure", {"message": d.message})
            failure.text = d.message
        if d.location.uri:
            testcase.set("file", str(d.location.path))

    ET.indent(testsuites, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(testsuites, encoding="unicode")


def format_markdown(report: CheckReport) -> str:
    """生成 Markdown 格式报告，适合 PR 评论或文档嵌入。"""
    lines: list[str] = ["# piki 检查报告", ""]

    # 汇总
    status = "✅ 全部通过" if report.passed else "❌ 存在错误"
    lines.append(f"**状态**: {status}")
    lines.append(
        f"**错误**: {report.error_count} | **警告**: {report.warning_count} | **通过**: {report.pass_count}"
    )
    lines.append("")

    # 规则结果
    if report.results:
        lines.append("## 规则检查结果")
        lines.append("")
        for r in report.results:
            icon = "✅" if r.passed else "❌"
            lines.append(f"- {icon} **{r.rule_id}**: {r.name}")
            if not r.passed and r.message:
                for msg_line in r.message.splitlines():
                    lines.append(f"  > {msg_line}")
            for ri in r.related_information:
                lines.append(f"  > → {ri.location}: {ri.message}")
            if r.suggestion:
                lines.append(f"  > 💡 **建议**: {r.suggestion}")
        lines.append("")

    # Diagnostic
    if report.diagnostics:
        lines.append("## 诊断信息")
        lines.append("")
        for d in report.diagnostics:
            icon = "✅" if d.passed else "❌"
            loc = f" `{d.location}`" if d.location.uri else ""
            lines.append(f"- {icon} **{d.code or d.source}**{loc}: {d.message}")
            for ri in d.related_information:
                lines.append(f"  > → {ri.location}: {ri.message}")
            suggestion = d.data.get("suggestion", "") if d.data else ""
            if suggestion:
                lines.append(f"  > 💡 **建议**: {suggestion}")
        lines.append("")

    return "\n".join(lines)


def format_report(report: CheckReport, fmt: str) -> str:
    if fmt == "json":
        return format_json(report)
    if fmt == "junit":
        return format_junit(report)
    if fmt == "markdown":
        return format_markdown(report)
    return format_human(report)
