"""项目自定义规则：液冷环路完整性检查。

检查液冷方舱内所有液冷设备的冷却液流量总和
是否与外部供液连接容量匹配。
"""

from piki.core.engine.checker import rule


@rule("DC-LIQUID-001", "液冷环路流量匹配检查", priority=8)
def check_liquid_loop_flow(ctx):
    """检查每个液冷方舱的冷却液需求与供液连接容量匹配。"""
    for container in ctx.query("containers", container_type="liquid-cooling"):
        # 计算方舱内所有液冷设备的总流量需求
        liquid_devices = ctx.query(
            "equipment",
            container_id=container.id,
            liquid_cooled=True,
        )
        total_flow = sum(d.coolant_flow_lpm for d in liquid_devices)

        if total_flow <= 0:
            continue

        # 查找进入该方舱的液冷连接
        incoming_conns = ctx.query(
            "connections", to_container=container.id, connection_type="liquid"
        )
        total_supply = sum(c.capacity for c in incoming_conns)

        # 也查找从该方舱出去的液冷连接（作为供液源）
        outgoing_conns = ctx.query(
            "connections", from_container=container.id, connection_type="liquid"
        )
        total_supply += sum(c.capacity for c in outgoing_conns)

        assert total_supply >= total_flow, (
            f"液冷方舱 {container.id} 冷却液需求 {total_flow}L/min "
            f"超过供液容量 {total_supply}L/min。"
            f"液冷设备: {', '.join(d.id for d in liquid_devices)}"
        )
