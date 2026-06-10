"""piki report — 生成设计检查报告文件。

与 check 命令的区别：默认输出到文件（而非终端），默认格式为 markdown。
"""

from __future__ import annotations

from pathlib import Path

from piki.core.project import Project
from piki.core.reporting.formats import format_report


def cmd_report(
    path: str | None,
    fmt: str,
    skip: list[str] | None = None,
    only: list[str] | None = None,
    output: str | None = None,
) -> int:
    """执行 report 命令，生成报告文件。

    Args:
        path: 项目目录路径，None 表示当前目录（向上扫描 piki.toml）。
        fmt: 输出格式，可选 "human" / "json" / "junit" / "markdown"。
        skip: 要跳过的规则 ID 列表。
        only: 只运行的规则 ID 列表。
        output: 输出文件路径，None 则使用默认路径 "piki-report.md"。

    Returns:
        退出码：0 表示所有检查通过，1 表示有检查未通过或发生错误。
    """
    try:
        project = Project.discover(path or ".")
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1

    project.load()
    report = project.run_check(skip=skip, only=only)
    formatted = format_report(report, fmt)

    out_path = Path(output) if output else Path("piki-report.md")
    out_path.write_text(formatted, encoding="utf-8")
    print(f"Report written to {out_path}")

    return 0 if report.passed else 1
