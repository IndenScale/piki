"""CLI 子命令实现。

模块列表：
    init.py     — piki init：初始化项目
    check.py    — piki check：运行设计检查
    report.py   — piki report：生成报告文件
    generate.py — piki generate：运行生成器
    plugins.py  — piki plugins：插件管理
"""

from .init import cmd_init
from .check import cmd_check
from .generate import cmd_generate
from .report import cmd_report
from .plugins import cmd_plugins_list

__all__ = ["cmd_init", "cmd_check", "cmd_generate", "cmd_report", "cmd_plugins_list"]
