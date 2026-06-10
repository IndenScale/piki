"""piki check — 运行设计检查。

加载项目、执行所有规则、格式化输出结果。
"""

from __future__ import annotations

from pathlib import Path

from piki.core.project import Project
from piki.core.reporting.formats import format_report


def cmd_check(
    path: str | None,
    fmt: str,
    skip: list[str] | None = None,
    only: list[str] | None = None,
    files: list[str] | None = None,
    output: str | None = None,
) -> int:
    """执行 check 命令。

    Args:
        path: 项目目录路径，None 表示当前目录（向上扫描 piki.toml）。
        fmt: 输出格式，可选 "human" / "json" / "junit" / "markdown"。
        skip: 要跳过的规则 ID 列表。
        only: 只运行的规则 ID 列表。
        files: 只检查的文件路径列表（相对项目根目录）。
        output: 输出文件路径，None 则输出到终端。

    Returns:
        退出码：0 表示所有检查通过，1 表示有检查未通过或发生错误。
    """
    try:
        project = Project.discover(path or ".")
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1

    project.load()
    report = project.run_check(skip=skip, only=only, files=files)
    formatted = format_report(report, fmt)

    if output:
        Path(output).write_text(formatted, encoding="utf-8")
        print(f"Report written to {output}")
    else:
        print(formatted)

    return 0 if report.passed else 1
