"""项目自定义规则：冗余策略检查。

本示例展示如何根据项目配置编写条件规则。
"""

from piki.core.engine.checker import rule
from piki.core.engine.context import Context


@rule("DC-REDUNDANCY-001", "关键设备冗余检查")
def check_critical_device_redundancy(ctx: Context) -> None:
    """检查关键设备是否具备 PSU 冗余。

    当 piki.toml 中 min_pdu_redundancy = true 时启用。
    """
    # 读取项目配置
    if not ctx.config.get("min_pdu_redundancy", False):
        return

    # 关键设备：high-density-server 必须冗余
    critical_models = {"high-density-server"}

    for device in ctx.query("devices"):
        if device.model not in critical_models:
            continue

        ctx.set_current_file(str(device.source))
        assert device.resolved.psu_redundancy is True, (
            f"关键设备 {device.id}（型号 {device.model}）"
            f"必须启用 PSU 冗余，当前 psu_redundancy = {device.resolved.psu_redundancy}"
        )
        assert device.resolved.psu_count >= 2, (
            f"关键设备 {device.id} 必须配置至少 2 个 PSU，"
            f"当前 psu_count = {device.resolved.psu_count}"
        )
    ctx.clear_current_file()
