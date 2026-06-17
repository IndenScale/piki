"""MateSugarResolvePass — Mate 语法糖消解。

将裸 Instance ID 的 Mate 引用消解为具体的接口引用：
  parent: PDU-A, child: SRV-01
  → parent: PDU-A/iec-c14-out-3, child: SRV-01/power-a

消解规则：
  1. 在两端各遍历所有 Interface
  2. 找出 interface_type 兼容的候选对
  3. 恰好 1 对 → 自动消解
  4. 0 对 → MATE-003 诊断
  5. >1 对 → MATE-004 诊断
"""

from __future__ import annotations

from adl.compiler.hir import MateUnit
from adl.compiler.pass_manager import Pass, PassContext, PassResult, PassStage
from adl.compiler.symbols import RefKind, SymbolRef
from adl.diagnostics import Diagnostic, Location, Severity


class MateSugarResolvePass(Pass):
    """Mate 语法糖消解 Pass。"""

    name = "mate-sugar-resolve"
    stage = PassStage.HIR
    description = "将裸 Instance ID 的 Mate 引用消解为接口引用"

    def run(self, ctx: PassContext) -> PassResult:
        result = PassResult()
        comp = ctx.compilation
        if comp is None:
            return result

        ts = ctx.type_system
        modified = False

        for mate_id, mate in list(comp.mates.items()):
            parent_text = mate.parent_ref.text if mate.parent_ref else ""
            child_text = mate.child_ref.text if mate.child_ref else ""

            # 已是接口引用 → 跳过
            parent_is_iface = "/" in parent_text
            child_is_iface = "/" in child_text
            if parent_is_iface and child_is_iface:
                continue

            # 至少一端是裸 ID → 需要消解
            parent_inst = comp.instances.get(parent_text) if not parent_is_iface else None
            child_inst = comp.instances.get(child_text) if not child_is_iface else None

            if parent_inst is None and not parent_is_iface:
                ctx.emit(_diag("MATE-002", f"Mate '{mate_id}' 的 parent '{parent_text}' 未找到", mate))
                continue
            if child_inst is None and not child_is_iface:
                ctx.emit(_diag("MATE-002", f"Mate '{mate_id}' 的 child '{child_text}' 未找到", mate))
                continue

            # 收集兼容候选
            candidates: list[tuple[str, str]] = []

            if not parent_is_iface and not child_is_iface:
                # 两端都是裸 ID → 穷举兼容对
                for p_iface in (parent_inst.interfaces if parent_inst else []):
                    for c_iface in (child_inst.interfaces if child_inst else []):
                        if _is_compatible(p_iface.interface_type, c_iface.interface_type, ts):
                            candidates.append(
                                (f"{parent_text}/{p_iface.id}", f"{child_text}/{c_iface.id}")
                            )
            elif not parent_is_iface:
                # parent 是裸 ID，child 已是接口引用
                child_type = _get_interface_type(comp, child_text)
                for p_iface in (parent_inst.interfaces if parent_inst else []):
                    if _is_compatible(p_iface.interface_type, child_type, ts):
                        candidates.append((f"{parent_text}/{p_iface.id}", child_text))
            else:
                # child 是裸 ID，parent 已是接口引用
                parent_type = _get_interface_type(comp, parent_text)
                for c_iface in (child_inst.interfaces if child_inst else []):
                    if _is_compatible(parent_type, c_iface.interface_type, ts):
                        candidates.append((parent_text, f"{child_text}/{c_iface.id}"))

            if len(candidates) == 0:
                ctx.emit(
                    _diag(
                        "MATE-003",
                        f"Mate '{mate_id}': 未找到兼容接口对 "
                        f"({parent_text} ↔ {child_text})",
                        mate,
                    )
                )
                continue

            if len(candidates) > 1:
                pairs = ", ".join(f"{p}↔{c}" for p, c in candidates[:5])
                ctx.emit(
                    _diag(
                        "MATE-004",
                        f"Mate '{mate_id}': 接口对不唯一（{len(candidates)} 对候选）。"
                        f" 请显式指定，候选: {pairs}",
                        mate,
                    )
                )
                continue

            # 恰好 1 对 → 消解
            p_ref, c_ref = candidates[0]
            mate.parent_ref = SymbolRef(text=p_ref, kind=RefKind.INSTANCE_INTERFACE)
            mate.child_ref = SymbolRef(text=c_ref, kind=RefKind.INSTANCE_INTERFACE)
            modified = True

        result.modified = modified
        return result


def _is_compatible(type_a: str, type_b: str, ts) -> bool:
    """检查两个接口类型是否兼容。"""
    if type_a == type_b:
        return True
    if ts is None:
        return False
    return ts.is_compatible_interface(type_a, type_b)


def _get_interface_type(comp, ref: str) -> str:
    """从接口引用获取接口类型。"""
    if "/" not in ref:
        return ""
    inst_id, iface_id = ref.split("/", 1)
    inst = comp.instances.get(inst_id)
    if inst is None:
        return ""
    for iface in inst.interfaces:
        if iface.id == iface_id:
            return iface.interface_type
    return ""


def _diag(code: str, message: str, mate: MateUnit) -> Diagnostic:
    loc = Location.from_path(mate.ast_source) if mate.ast_source else Location(uri="")
    return Diagnostic(
        severity=Severity.ERROR,
        message=message,
        location=loc,
        code=code,
        source="adl.compiler.mate_sugar",
    )
