"""项目自定义规则：PUE 估算检查。

PUE = 总设施能耗 / IT 设备能耗
行业参考值：
- 传统机房：1.5 ~ 2.0
- 模块化数据中心：1.2 ~ 1.4
- 液冷智算中心：1.05 ~ 1.15
"""

from piki.core.engine.checker import rule


@rule("DC-PUE-001", "PUE 估算检查", priority=3)
def check_pue_estimate(ctx):
    """检查项目整体 PUE 是否在合理范围内。"""
    max_pue = ctx.config.get("max_pue", 1.4)

    total_it_power = 0.0
    total_cooling_power = 0.0

    for device in ctx.query("equipment"):
        if device.equipment_type == "compute" or device.equipment_type == "storage":
            total_it_power += device.power_kw
        elif device.equipment_type == "cooling":
            total_cooling_power += device.power_kw

    if total_it_power <= 0:
        return

    # 简化 PUE 估算：PUE ≈ (IT + 制冷 + 配电损耗) / IT
    # 配电损耗按 5% 估算
    distribution_loss = total_it_power * 0.05
    pue = (total_it_power + total_cooling_power + distribution_loss) / total_it_power

    assert pue <= max_pue, (
        f"项目估算 PUE = {pue:.2f}，超过阈值 {max_pue}。"
        f"IT 功耗: {total_it_power:.1f}kW, 制冷功耗: {total_cooling_power:.1f}kW"
    )
