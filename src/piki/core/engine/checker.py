"""Checker：规则发现、执行、报告。"""

from __future__ import annotations

import inspect
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

from ..models.diagnostic import Diagnostic, Location, Severity
from ..models.mating import parse_mate_ref
from .context import Context


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
        return sum(
            1 for r in self.results if not r.passed and r.severity == Severity.WARNING
        ) + sum(1 for d in self.diagnostics if d.severity == Severity.WARNING)

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

        # 运行内置 L2 检查（成功时也记录 PASS）
        for rule_id, name, severity, check_fn in [
            (
                "REFS-001",
                "Layout-Instance 引用完整性",
                Severity.ERROR,
                self.check_reference_integrity,
            ),
            ("TAGS-001", "Tag Schema 合规性", Severity.WARNING, self.check_tag_schema),
            ("FK-001", "通用外键引用完整性", Severity.ERROR, self.check_foreign_keys),
            (
                "INTERFACE-COMPAT-001",
                "接口类型兼容性检查",
                Severity.ERROR,
                self.check_interface_compatibility,
            ),
            (
                "MATE-001",
                "Mate Instance 引用完整性",
                Severity.ERROR,
                self.check_mate_references,
            ),
            (
                "MATE-002",
                "Mate Family 兼容性检查",
                Severity.ERROR,
                self.check_mate_family_compat,
            ),
            (
                "MATE-003",
                "Mate 约束验证",
                Severity.ERROR,
                self.check_mate_constraints,
            ),
        ]:
            try:
                check_fn(ctx)
                report.results.append(
                    RuleResult(
                        rule_id=rule_id,
                        name=name,
                        passed=True,
                        file=getattr(ctx, "_current_file", ""),
                        severity=severity,
                    )
                )
            except AssertionError as exc:
                report.results.append(
                    RuleResult(
                        rule_id=rule_id,
                        name=name,
                        passed=False,
                        message=str(exc),
                        file=getattr(ctx, "_current_file", ""),
                        severity=severity,
                    )
                )

        # 运行内置 FQID 冲突检查
        try:
            self.check_fqid_duplicates(ctx)
        except AssertionError as exc:
            report.results.append(
                RuleResult(
                    rule_id="REFS-002",
                    name="FQID 冲突检查",
                    passed=False,
                    message=str(exc),
                    file=getattr(ctx, "_current_file", ""),
                    severity=Severity.ERROR,
                )
            )

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
                    RuleResult(
                        rule_id=rule_id, name=name, passed=True, file=file, severity=severity
                    )
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

    def check_reference_integrity(self, ctx: Context) -> None:
        """L2 引用完整性检查（ADR-004, ADR-008, ADR-009）。

        自动运行，检查 Layout → Instance 引用的一致性：
        1. Layout 中的 instance 引用是否存在
        2. Layout 中被引用的 Instance 是否仍为 _invalid（Schema 失败）

        注意：此检查忽略 --files 过滤，始终检查完整 Layout 的引用完整性。
        """
        layout = ctx.layout
        if layout is None:
            return

        # 使用完整项目树的 Instance（不受 files 过滤影响）
        all_instances = ctx._registry.all_instances_tree()
        all_ids = set(all_instances.keys())
        valid_ids = {iid for iid, inst in all_instances.items() if inst.family != "_invalid"}

        for entry_id, entry in layout.entries.items():
            ctx.set_current_file(str(layout.source) if layout.source else "")

            # 1. 检查 Instance 是否存在
            if entry_id not in all_ids:
                assert False, (
                    f"Layout 引用的 Instance '{entry_id}' 在项目树中不存在。"
                    f" 请检查 instances/ 目录是否包含该 Instance 文件。"
                )

            # 2. 检查 Instance 是否通过 Schema 校验
            if entry_id not in valid_ids:
                inst = ctx.find_instance(entry_id)
                if inst is not None and inst.family == "_invalid":
                    assert False, (
                        f"Layout 引用的 Instance '{entry_id}' Schema 校验失败，"
                        f"无法用于部署。请先修复该 Instance 的错误。"
                    )

        ctx.clear_current_file()

    def check_tag_schema(self, ctx: Context) -> None:
        """L2 Tag Schema 检查（ADR-009 §3.3）。

        当 piki.toml 中定义了 [tags] allowed 列表时，
        检查所有 Instance 的 tags 键是否在允许范围内。
        未定义 allowed 列表时不作检查。
        """
        allowed_tags = ctx._registry.allowed_tags
        if not allowed_tags:
            return

        for inst in ctx.instances():
            tags_raw = inst._resolved.get("tags")
            if not isinstance(tags_raw, dict):
                continue

            # 只检查有实际值的 Tag 键（过滤空字符串和空 extra）
            active_keys: set[str] = set()
            for k, v in tags_raw.items():
                if k == "extra":
                    if isinstance(v, dict):
                        active_keys.update(ek for ek, ev in v.items() if ev)
                    continue
                if v:  # 非空值
                    active_keys.add(k)

            unknown_keys = active_keys - allowed_tags
            if unknown_keys:
                ctx.set_current_file(str(inst.source))
                assert False, (
                    f"Instance '{inst.id}' 使用了未在 piki.toml [tags] 中声明的 Tag 键: "
                    f"{', '.join(sorted(unknown_keys))}。"
                    f" 允许的键: {', '.join(sorted(allowed_tags))}。"
                )
        ctx.clear_current_file()

    def check_foreign_keys(self, ctx: Context) -> None:
        """L2 通用外键引用完整性检查 (ADR-007).

        扫描所有 Instance 中的引用字段：
        1. 以 _id 结尾的字段 → 检查 Instance 是否存在
        2. 以 _interface 结尾的字段 → 解析 instance_id/interface_id，
           检查 Instance 和 Interface 是否都存在
        """
        from ..models.interface import get_interfaces_from_resolved, resolve_interface_ref

        all_ids = set(ctx._registry.all_instances_tree().keys())

        for inst in ctx.instances():
            ctx.set_current_file(str(inst.source))

            for field_name, field_value in inst._resolved.items():
                if not isinstance(field_value, str) or not field_value:
                    continue

                # 接口引用：from_interface / to_interface
                if field_name.endswith("_interface") and "/" in field_value:
                    try:
                        instance_id, interface_id = resolve_interface_ref(field_value)
                    except ValueError as exc:
                        assert False, (
                            f"Instance '{inst.id}' 的字段 '{field_name}' 接口引用格式无效: {exc}"
                        )
                    target = ctx.find_instance(instance_id)
                    if target is None:
                        assert False, (
                            f"Instance '{inst.id}' 的字段 '{field_name}' 引用了 "
                            f"不存在的 Instance '{instance_id}'。"
                        )
                    interfaces = get_interfaces_from_resolved(target)
                    if interface_id not in {i.id for i in interfaces}:
                        assert False, (
                            f"Instance '{inst.id}' 的字段 '{field_name}' 引用了 "
                            f"Interface '{field_value}'，但 Instance '{instance_id}' "
                            f"未声明该接口。"
                        )
                    continue

                # 普通外键引用：以 _id 结尾
                if not field_name.endswith("_id"):
                    continue

                if field_value not in all_ids:
                    assert False, (
                        f"Instance '{inst.id}' 的字段 '{field_name}' 引用了 "
                        f"不存在的 Instance '{field_value}'。"
                    )

        ctx.clear_current_file()

    def check_interface_compatibility(self, ctx: Context) -> None:
        """L2 接口类型兼容性检查 (ADR-007, RFC-001).

        对于所有 Connection Instance，使用兼容性矩阵检查
        from_interface 和 to_interface 的 interface_type 是否兼容。
        """
        from ..models.interface import get_interfaces_from_resolved, resolve_interface_ref

        try:
            from piki.extensions.telecom.types import are_compatible, is_valid_interface_type
        except ImportError:
            # telecom 插件未安装时降级为严格相等
            def are_compatible(a, b):
                return a == b

            def is_valid_interface_type(v):
                return True

        for inst in ctx.instances():
            from_ref = inst._resolved.get("from_interface")
            to_ref = inst._resolved.get("to_interface")

            # 只检查同时有 from_interface 和 to_interface 的实例（即连接实例）
            if not from_ref or not to_ref:
                continue
            if not isinstance(from_ref, str) or not isinstance(to_ref, str):
                continue
            if "/" not in from_ref or "/" not in to_ref:
                continue

            ctx.set_current_file(str(inst.source))

            # 解析 from
            try:
                from_inst_id, from_iface_id = resolve_interface_ref(from_ref)
            except ValueError as exc:
                assert False, f"引用格式无效: {exc}"

            from_target = ctx.find_instance(from_inst_id)
            if from_target is None:
                continue  # FK-001 已报错，不重复

            # 解析 to
            try:
                to_inst_id, to_iface_id = resolve_interface_ref(to_ref)
            except ValueError as exc:
                assert False, f"引用格式无效: {exc}"

            to_target = ctx.find_instance(to_inst_id)
            if to_target is None:
                continue  # FK-001 已报错

            # 获取接口类型
            from_interfaces = get_interfaces_from_resolved(from_target)
            to_interfaces = get_interfaces_from_resolved(to_target)

            from_iface = next((i for i in from_interfaces if i.id == from_iface_id), None)
            to_iface = next((i for i in to_interfaces if i.id == to_iface_id), None)

            if from_iface is None or to_iface is None:
                continue  # FK-001 已报错

            # 同类型 → 兼容（快速路径）
            if from_iface.interface_type == to_iface.interface_type:
                continue

            # 两个都是已知类型 → 查兼容性矩阵
            from_known = is_valid_interface_type(from_iface.interface_type)
            to_known = is_valid_interface_type(to_iface.interface_type)

            if from_known and to_known:
                if are_compatible(
                    from_iface.interface_type, to_iface.interface_type
                ) or are_compatible(to_iface.interface_type, from_iface.interface_type):
                    continue
                # 已知类型但矩阵说不兼容 → Error
                assert False, (
                    f"接口类型不兼容: "
                    f"{from_ref} (type={from_iface.interface_type}) vs "
                    f"{to_ref} (type={to_iface.interface_type})"
                )

            # 至少一个未知类型 → 降级为 Warning，不做有罪推定
            if not from_known:
                ctx.set_suggestion(
                    f"Interface '{from_iface_id}' 使用了未收录的类型: {from_iface.interface_type}"
                )
            if not to_known:
                ctx.set_suggestion(
                    f"Interface '{to_iface_id}' 使用了未收录的类型: {to_iface.interface_type}"
                )

        ctx.clear_current_file()

    def check_cable_interface_match(self, ctx: Context) -> None:
        """L2 线缆-接口类型匹配检查 (RFC-001).

        对于所有 Connection Instance，检查 cable_type 是否与两端接口类型匹配。
        光纤接口不应接铜缆，铜缆接口不应接光纤跳线。
        """
        from ..models.interface import get_interfaces_from_resolved, resolve_interface_ref

        try:
            from piki.extensions.telecom.types import INTERFACE_CABLE_MAP, is_valid_interface_type
        except ImportError:
            return  # telecom 插件未安装时跳过

        for inst in ctx.instances():
            from_ref = inst._resolved.get("from_interface")
            to_ref = inst._resolved.get("to_interface")
            cable_type = inst._resolved.get("cable_type")

            if not from_ref or not to_ref or not cable_type:
                continue
            if not isinstance(from_ref, str) or not isinstance(to_ref, str):
                continue
            if "/" not in from_ref or "/" not in to_ref:
                continue
            if not isinstance(cable_type, str):
                continue

            ctx.set_current_file(str(inst.source))

            # 解析 from
            try:
                from_inst_id, from_iface_id = resolve_interface_ref(from_ref)
            except ValueError:
                continue  # FK-001 / COMPAT-001 会报

            from_target = ctx.find_instance(from_inst_id)
            if from_target is None:
                continue

            # 解析 to
            try:
                to_inst_id, to_iface_id = resolve_interface_ref(to_ref)
            except ValueError:
                continue

            to_target = ctx.find_instance(to_inst_id)
            if to_target is None:
                continue

            from_interfaces = get_interfaces_from_resolved(from_target)
            to_interfaces = get_interfaces_from_resolved(to_target)

            from_iface = next((i for i in from_interfaces if i.id == from_iface_id), None)
            to_iface = next((i for i in to_interfaces if i.id == to_iface_id), None)

            if from_iface is None or to_iface is None:
                continue

            # 检查两端接口的 cable_type 匹配
            for iface, ref_name in [(from_iface, from_ref), (to_iface, to_ref)]:
                if not is_valid_interface_type(iface.interface_type):
                    continue
                valid_cables = INTERFACE_CABLE_MAP.get(iface.interface_type, frozenset())
                if valid_cables and cable_type not in valid_cables:
                    assert False, (
                        f"线缆类型不匹配: "
                        f"{ref_name} (type={iface.interface_type}) "
                        f"不支持 cable_type={cable_type}。"
                        f"支持的线缆: {', '.join(sorted(valid_cables))}"
                    )

        ctx.clear_current_file()

    def check_mate_references(self, ctx: Context) -> None:
        """L2: Mate parent/child Instance references must exist."""
        reg = ctx._registry
        for mate in reg.mates:
            parent_inst_id, _ = parse_mate_ref(mate.parent)
            child_inst_id, _ = parse_mate_ref(mate.child)
            parent_inst = reg.find_instance(parent_inst_id)
            child_inst = reg.find_instance(child_inst_id)
            ctx.set_current_file(str(getattr(mate, "_source", "")))
            if parent_inst is None:
                assert False, f"Mate '{mate.type}' parent instance '{parent_inst_id}' not found"
            if child_inst is None:
                assert False, f"Mate '{mate.type}' child instance '{child_inst_id}' not found"
        ctx.clear_current_file()

    def check_mate_family_compat(self, ctx: Context) -> None:
        """L2: Mate Family must match Mate type restrictions."""
        reg = ctx._registry
        for mate in reg.mates:
            type_meta = reg.mate_types.get(mate.type)
            if not type_meta:
                continue
            parent_inst_id, _ = parse_mate_ref(mate.parent)
            child_inst_id, _ = parse_mate_ref(mate.child)
            parent_inst = reg.find_instance(parent_inst_id)
            child_inst = reg.find_instance(child_inst_id)
            if not parent_inst or not child_inst:
                continue
            ctx.set_current_file(str(getattr(mate, "_source", "")))
            if type_meta.applicable_parent_families:
                if parent_inst.family not in type_meta.applicable_parent_families:
                    assert False, (
                        f"Mate '{mate.type}' parent '{parent_inst_id}' "
                        f"has family '{parent_inst.family}', restricted to: "
                        f"{type_meta.applicable_parent_families}"
                    )
            if type_meta.applicable_child_families:
                if child_inst.family not in type_meta.applicable_child_families:
                    assert False, (
                        f"Mate '{mate.type}' child '{child_inst_id}' "
                        f"has family '{child_inst.family}', restricted to: "
                        f"{type_meta.applicable_child_families}"
                    )
        ctx.clear_current_file()

    def check_mate_constraints(self, ctx: Context) -> None:
        """L2: Mate constraint conditions must pass."""
        reg = ctx._registry
        diagnostics = reg.validate_mates()
        for d in diagnostics:
            if d.code == "MATE-003":
                ctx.set_current_file(str(d.location.uri) if d.location.uri else "")
                assert False, d.message
        ctx.clear_current_file()

    def check_fqid_duplicates(self, ctx: Context) -> None:
        """L2 FQID 冲突检查（ADR-009 §6.2）。

        检查同一项目树下是否存在简单 ID 冲突的 Instance。
        如果某个 ID 出现在多个同级或祖先/后代项目中，报告冲突。
        """
        reg = ctx._registry
        all_instances = reg.all_instances_with_fqid()
        all_simple = reg.all_instances_tree()

        # 统计每个简单 ID 的出现次数（在同一项目树中）
        id_counts: dict[str, list[str]] = {}
        for fqid_val, inst in all_instances.items():
            simple_id = inst.id
            if simple_id not in id_counts:
                id_counts[simple_id] = []
            id_counts[simple_id].append(fqid_val)

        for simple_id, fqids in id_counts.items():
            if len(fqids) > 1:
                # 使用第一个 Instance 的文件作为上下文
                inst = all_simple.get(simple_id)
                if inst:
                    ctx.set_current_file(str(inst.source))
                assert False, (
                    f"Instance ID '{simple_id}' 在项目树中出现 {len(fqids)} 次: "
                    f"{', '.join(fqids)}。请使用全限定 ID 引用。"
                )
        ctx.clear_current_file()

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
