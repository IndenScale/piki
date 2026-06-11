"""CLI 入口 — 只做参数解析和路由。

命令列表：
    piki init [PATH] [--plugin PLUGIN]     初始化项目
    piki check [PATH] [OPTIONS]            运行设计检查
    piki report [PATH] [OPTIONS]           生成报告文件
    piki generate [GENERATOR] [PATH]       运行生成器
    piki plugins list                      列出可用插件

退出码：
    0  — 成功 / 所有检查通过
    1  — 有检查未通过，或发生错误
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from piki.core import __version__
from .commands import cmd_init, cmd_check, cmd_generate, cmd_report, cmd_plugins_list, cmd_preview


def build_parser() -> argparse.ArgumentParser:
    """构建 argparse 解析器，定义所有 CLI 命令和参数。"""
    parser = argparse.ArgumentParser(
        prog="piki",
        description="Text-Native CAD — 用文本定义设计，用规则检查合理性。",
    )
    parser.add_argument("--version", action="version", version=f"piki {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, help="可用命令")

    # --- init ---
    init = sub.add_parser("init", help="初始化一个新的 piki 项目")
    init.add_argument("path", nargs="?", help="目标目录（默认当前目录）")
    init.add_argument("--plugin", default="telecom", help="要启用的插件（默认 telecom）")

    # --- check ---
    check = sub.add_parser("check", help="运行设计检查")
    check.add_argument("path", nargs="?", help="项目目录（向上扫描 piki.toml）")
    check.add_argument(
        "--format",
        default="human",
        choices=["human", "json", "junit", "markdown"],
        help="输出格式（默认 human）",
    )
    check.add_argument(
        "--skip",
        action="append",
        default=[],
        help="跳过指定规则 ID（可多次使用）",
    )
    check.add_argument(
        "--only",
        action="append",
        default=[],
        help="只运行指定规则 ID（可多次使用）",
    )
    check.add_argument(
        "--files",
        nargs="*",
        default=None,
        help="只检查指定文件（相对项目根目录的路径）",
    )
    check.add_argument(
        "--output", "-o",
        help="输出到文件而非终端",
    )

    # --- report ---
    report = sub.add_parser("report", help="生成设计检查报告文件")
    report.add_argument("path", nargs="?", help="项目目录")
    report.add_argument(
        "--format",
        default="markdown",
        choices=["human", "json", "junit", "markdown"],
        help="输出格式（默认 markdown）",
    )
    report.add_argument(
        "--skip",
        action="append",
        default=[],
        help="跳过指定规则 ID（可多次使用）",
    )
    report.add_argument(
        "--only",
        action="append",
        default=[],
        help="只运行指定规则 ID（可多次使用）",
    )
    report.add_argument(
        "--output", "-o",
        help="输出文件路径（默认 piki-report.md）",
    )

    # --- generate ---
    generate = sub.add_parser("generate", help="运行生成器导出产物")
    generate.add_argument(
        "generator",
        nargs="?",
        default=None,
        help="生成器 ID（省略则运行所有启用的生成器）",
    )
    generate.add_argument("path", nargs="?", help="项目目录")
    generate.add_argument(
        "--output", "-o",
        help="输出文件路径",
    )

    # --- preview ---
    preview = sub.add_parser("preview", help="生成 USD 场景并预览")
    preview.add_argument("path", nargs="?", help="项目目录")
    preview.add_argument(
        "--output", "-o",
        default="scene.usda",
        help="USD 输出文件路径（默认 scene.usda）",
    )
    preview.add_argument(
        "--no-view",
        action="store_true",
        help="只生成文件，不启动预览器",
    )

    # --- plugins ---
    plugins = sub.add_parser("plugins", help="管理插件")
    plugins_sub = plugins.add_subparsers(dest="subcommand", required=True)
    plugins_sub.add_parser("list", help="列出所有可用插件")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 主入口。

    Args:
        argv: 命令行参数列表，None 时从 sys.argv 读取。

    Returns:
        退出码：0 表示成功/检查通过，1 表示失败/错误。
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return cmd_init(args.path, args.plugin)
    if args.command == "check":
        return cmd_check(
            args.path,
            args.format,
            skip=args.skip,
            only=args.only,
            files=args.files,
            output=args.output,
        )
    if args.command == "report":
        return cmd_report(
            args.path,
            args.format,
            skip=args.skip,
            only=args.only,
            output=args.output,
        )
    if args.command == "generate":
        return cmd_generate(args.path, args.generator, args.output)
    if args.command == "preview":
        return cmd_preview(args.path, args.output, no_view=args.no_view)
    if args.command == "plugins":
        if args.subcommand == "list":
            return cmd_plugins_list()
    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
