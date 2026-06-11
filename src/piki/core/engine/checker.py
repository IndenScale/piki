"""Checker：规则发现、执行、报告。"""

from __future__ import annotations

import inspect
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from ..models.diagnostic import Diagnostic, Location, Range, Severity
from .context import Context
from .registry import Registry


@dataclass
class RuleResult:
    """规则执行结果（向后兼容）。"""

    rule_id: str
    name: str
    passed: bool
    message: str = ""
    file: str = ""
    severity: Severity = Severity.ERROR
    related_information: list = field(default_factory=list)
    suggestion: str = ""

    def to_diagnostic(self) -> Diagnostic:
        """转换为 Diagnostic。"""
        data: dict[str, Any] = {}
        if self.suggestion:
            data["suggestion"] = self.suggestion
        return Diagnostic(
            severity=Severity.INFO if self.passed else self.severity,
            message=self.message or ("通过" if self.passed else "失败"),
            location=Location.from_path(self.file) if self.file else Location(uri=""),
            code=self.rule_id,
            source="piki.checker",
            name=self.name,
            related_information=self.related_information,
            data=data,
        )


@dataclass
class CheckReport:
    """检查报告（向后兼容，内部使用 DiagnosticReport）。"""

    results: list[RuleResult] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed or r.severity < Severity.ERROR for r in self.results) and not any(
            d.severity >= Severity.ERROR for d in self.diagnostics
        )

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if not r.passed and r.severity >= Severity.ERROR) + sum(
            1 for d in self.diagnostics if d.severity == Severity.ERROR
        )

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if not r.passed and r.severity == Severity.WARNING) + sum(
            1 for d in self.diagnostics if d.severity == Severity.WARNING
        )

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    def all_diagnostics(self) -> list[Diagnostic]:
        """返回所有诊断：规则结果 + 独立诊断。"""
        rule_diagnostics = [r.to_diagnostic() for r in self.results]
        return rule_diagnostics + self.diagnostics


RuleFunc = Callable[[Context], None]
GenFunc = Callable[[Context, dict[str, Any]], None]


class Checker:
    """规则引擎。"""

    def __init__(self) -> None:
        self._rules: list[tuple[str, str, int, Severity, RuleFunc]] = []
        self._generators: dict[str, tuple[str, GenFunc]] = {}

    def add_rule(
        self,
        rule_id: str,
        name: str,
        func: RuleFunc,
        priority: int = 0,
        severity: Severity = Severity.ERROR,
    ) -> None:
        self._rules.append((rule_id, name, priority, severity, func))

    def add_generator(self, gen_id: str, name: str, func: GenFunc) -> None:
        self._generators[gen_id] = (name, func)

    def run(
        self,
        ctx: Context,
        skip: list[str] | None = None,
        only: list[str] | None = None,
        files: list[str] | None = None,
        rules_config: dict[str, Any] | None = None,
    ) -> CheckReport:
        skip_set = set(skip or [])
        only_set = set(only or [])
        rules_config = rules_config or {}
        # 设置文件过滤到 Context，query() 会自动过滤
        ctx.set_files_filter(files)
        # 按 priority 降序
        sorted_rules = sorted(self._rules, key=lambda x: x[2], reverse=True)
        report = CheckReport()
        for rule_id, name, _prio, default_severity, func in sorted_rules:
            if skip_set and rule_id in skip_set:
                continue
            if only_set and rule_id not in only_set:
                continue
            # 应用规则级配置覆盖默认 severity
            rule_cfg = rules_config.get(rule_id, {})
            severity = Severity.WARNING if rule_cfg.get("warning_only") else default_severity
            file = ""
            try:
                func(ctx)
                report.results.append(
                    RuleResult(rule_id=rule_id, name=name, passed=True, file=file, severity=severity)
                )
            except AssertionError as exc:
                message = str(exc) if str(exc) else "Assertion failed"
                # 尝试从异常中提取 file 信息（如果规则通过 ctx 设置了）
                file = getattr(ctx, "_current_file", "")
                related = getattr(ctx, "pop_related_info", lambda: [])()
                suggestion = getattr(ctx, "pop_suggestion", lambda: "")()
                report.results.append(
                    RuleResult(
                        rule_id=rule_id,
                        name=name,
                        passed=False,
                        message=message,
                        file=file,
                        severity=severity,
                        related_information=related,
                        suggestion=suggestion,
                    )
                )
            except Exception as exc:  # pragma: no cover
                file = getattr(ctx, "_current_file", "")
                related = getattr(ctx, "pop_related_info", lambda: [])()
                suggestion = getattr(ctx, "pop_suggestion", lambda: "")()
                report.results.append(
                    RuleResult(
                        rule_id=rule_id,
                        name=name,
                        passed=False,
                        message=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
                        file=file,
                        severity=severity,
                        related_information=related,
                        suggestion=suggestion,
                    )
                )
        return report

    def generate(self, gen_id: str, ctx: Context, config: dict[str, Any]) -> None:
        if gen_id not in self._generators:
            raise KeyError(f"Unknown generator: {gen_id}")
        _name, func = self._generators[gen_id]
        func(ctx, config)

    def list_generators(self) -> list[tuple[str, str, GenFunc]]:
        return [(gid, name, fn) for gid, (name, fn) in self._generators.items()]


# ---------------------------------------------------------------------------
# 装饰器接口（模块级别注册，无全局状态污染）
# ---------------------------------------------------------------------------
# 装饰器在函数对象上附加元数据属性，由 register_module_rules 扫描模块收集。

_RULE_ATTR = "__piki_rule_meta__"
_GEN_ATTR = "__piki_gen_meta__"


def rule(
    rule_id: str,
    name: str,
    priority: int = 0,
    severity: Severity = Severity.ERROR,
) -> Callable[[RuleFunc], RuleFunc]:
    """标记一个函数为 piki 规则。

    装饰器将元数据附加到函数对象上，不写入全局列表。
    register_module_rules 会扫描模块中所有带有该标记的函数。
    """

    def decorator(func: RuleFunc) -> RuleFunc:
        setattr(func, _RULE_ATTR, (rule_id, name, priority, severity))
        return func

    return decorator


def generator(gen_id: str, name: str) -> Callable[[GenFunc], GenFunc]:
    """标记一个函数为 piki 生成器。

    装饰器将元数据附加到函数对象上，不写入全局列表。
    register_module_rules 会扫描模块中所有带有该标记的函数。
    """

    def decorator(func: GenFunc) -> GenFunc:
        setattr(func, _GEN_ATTR, (gen_id, name))
        return func

    return decorator


def register_module_rules(checker: Checker, module: Any) -> None:
    """扫描模块中的 @rule / @generator 装饰器并注册到 Checker。

    通过 inspect 遍历模块的所有成员，查找带有 __piki_rule_meta__ 或
    __piki_gen_meta__ 属性的函数，将其注册到传入的 Checker 实例。
    """
    if module is None:
        return

    for _name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj):
            rule_meta = getattr(obj, _RULE_ATTR, None)
            if rule_meta is not None:
                # 兼容旧版 3 元组和新版 4 元组
                if len(rule_meta) == 3:
                    rule_id, name, priority = rule_meta
                    severity = Severity.ERROR
                else:
                    rule_id, name, priority, severity = rule_meta
                checker.add_rule(rule_id, name, obj, priority, severity)
            gen_meta = getattr(obj, _GEN_ATTR, None)
            if gen_meta is not None:
                gen_id, name = gen_meta
                checker.add_generator(gen_id, name, obj)
