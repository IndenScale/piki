"""命名规范检查：ServerFamily Instance ID 必须遵循 SRV-{rack后缀}-{序号} 格式。

使用 Layout 查询（ADR-008 §3）精确获取 Instance 的部署机柜。
"""

from piki.core.engine.checker import rule
from piki.core.engine.context import Context
from piki.core.models.diagnostic import Severity


@rule(
    "NAMING-001",
    "Server Instance ID 命名规范（使用 Layout 查询）",
    priority=5,
    severity=Severity.WARNING,
)
def check_naming(ctx: Context) -> None:
    """验证 ServerFamily Instance ID 的前缀部分与实际部署的 rack_id 前缀一致。"""
    for inst in ctx.instances():
        # 仅检查 ServerFamily 设备
        if inst.family != "ServerFamily":
            continue
        layout = ctx.layout_entry(inst.id)
        if layout is None or layout.rack_id is None:
            continue
        # 期望格式: SRV-{rack后缀}-{序号}，如 SRV-A01-01 对应 RACK-A01
        rack_suffix = layout.rack_id.replace("RACK-", "")
        expected_prefix = f"SRV-{rack_suffix}"
        if not inst.id.startswith(expected_prefix):
            ctx.set_current_file(str(inst.source))
            assert False, (
                f"Server Instance ID '{inst.id}' 应以 '{expected_prefix}' 开头，"
                f"以匹配其部署机柜 '{layout.rack_id}'。"
            )
    ctx.clear_current_file()
