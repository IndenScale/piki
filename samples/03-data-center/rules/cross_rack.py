"""跨机柜分布规则：同系统设备不应全部部署在同一机柜（防单点故障），
使用 Tag 过滤（ADR-009 §3.3）。"""

from piki.core.engine.checker import rule
from piki.core.engine.context import Context
from piki.core.models.diagnostic import Severity


@rule("CROSS-RACK-001", "跨机柜分布检查（按 system Tag）", priority=10, severity=Severity.WARNING)
def check_cross_rack_by_system(ctx: Context) -> None:
    """使用 Tag 过滤：同一 system 的设备应分布在至少 2 个机柜中。"""
    all_instances = list(ctx.instances())

    # 按 system tag 分组
    system_groups: dict[str, list[str]] = {}
    for inst in all_instances:
        system_tag = inst._resolved.get("tags.system", "")
        if not system_tag:
            continue
        layout = ctx.layout_entry(inst.id)
        if layout is None or layout.rack_id is None:
            continue
        if system_tag not in system_groups:
            system_groups[system_tag] = []
        system_groups[system_tag].append(layout.rack_id)

    for system_name, racks in system_groups.items():
        unique_racks = set(racks)
        if len(unique_racks) < 2:
            ctx.set_current_file(str(inst.source))
            assert False, (
                f"系统 '{system_name}' 的所有 {len(racks)} 台设备仅分布在 {len(unique_racks)} 个机柜中，"
                f"建议至少分布在 2 个机柜以防止单点故障。"
            )
    ctx.clear_current_file()
