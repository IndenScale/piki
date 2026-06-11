"""项目自定义规则：跨机柜约束检查。

本示例展示如何编写涉及多个集合的复杂规则。
"""

from piki.core.engine.checker import rule
from piki.core.engine.context import Context


@rule("DC-BALANCE-001", "机柜负载均衡检查")
def check_rack_load_balance(ctx: Context) -> None:
    """检查同一列机柜的负载是否均衡。

    同一列（如 A 列）的机柜，设备数量差异不应超过 2 台。
    """
    from collections import defaultdict

    # 按列分组统计设备数
    rack_devices: dict[str, list[str]] = defaultdict(list)
    for device in ctx.query("devices"):
        rack_id = device.rack_id
        # 提取列名（如 RACK-A01 -> A）
        col = rack_id.split("-")[1][0] if "-" in rack_id else ""
        rack_devices[rack_id].append(device.id)

    # 按列检查均衡性
    col_racks: dict[str, list[int]] = defaultdict(list)
    for rack_id, devices in rack_devices.items():
        col = rack_id.split("-")[1][0] if "-" in rack_id else ""
        col_racks[col].append(len(devices))

    for col, counts in col_racks.items():
        if len(counts) < 2:
            continue
        max_count = max(counts)
        min_count = min(counts)
        assert max_count - min_count <= 2, (
            f"{col} 列机柜负载不均衡："
            f"最多 {max_count} 台，最少 {min_count} 台，差异超过 2 台"
        )
