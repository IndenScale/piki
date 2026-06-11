"""piki-telecom 内置插件：电信/数据中心。"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from piki.core.engine.checker import Checker, rule
from piki.core.engine.registry import Registry
from piki.core.models.diagnostic import Severity
from piki.core.models.geometry import GeometryAssets
from piki.core.models.tags import Tags
from piki.core.plugin import Plugin


class RackFamily(BaseModel):
    id: str = Field(...)
    name: str = Field(default="")
    location: str = Field(default="")
    total_u: int = Field(..., ge=1, le=48)
    power_capacity_w: float = Field(default=0, ge=0)  # 机柜配电容量（W）
    # 物理尺寸（毫米），用于 3D 碰撞检测和物理尺寸匹配
    depth_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    width_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    # 3D 空间定位（毫米）
    position_x_mm: float = Field(default=0.0)
    position_y_mm: float = Field(default=0.0)
    position_z_mm: float = Field(default=0.0)
    # 标签（ADR-009）
    tags: Tags = Field(default_factory=Tags)
    # 几何资产（可选）
    assets: GeometryAssets | None = Field(default=None)


class PduFamily(BaseModel):
    id: str = Field(...)
    name: str = Field(default="")
    rack_id: str = Field(default="")
    phase: str = Field(default="L1")          # 相线，如 L1, L2, L3
    capacity_w: float = Field(..., gt=0)      # 额定功率（W）
    tags: Tags = Field(default_factory=Tags)  # 标签（ADR-009）


class ServerFamily(BaseModel):
    id: str = Field(...)
    name: str = Field(default="")
    model: str = Field(default="")
    status: str = Field(default="planned")
    rack_id: str = Field(default="")
    position_u: int = Field(default=1, ge=1, le=48)
    pdu_id: str = Field(default="")            # 引用 PduFamily.id
    height_u: int = Field(default=2, ge=1, le=48)
    tdp_w: float = Field(default=300, gt=0)
    psu_count: int = Field(default=1, ge=1)
    psu_redundancy: bool = Field(default=False)
    tags: Tags = Field(default_factory=Tags)  # 标签（ADR-009）
    # 物理尺寸（毫米），用于 3D 碰撞检测和物理尺寸匹配
    depth_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    width_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    height_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})  # 设备高度（1U ≈ 44.45mm，但这里用实际物理高度）
    weight_kg: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    # 3D 空间定位（毫米，相对于机柜原点）
    position_x_mm: float = Field(default=0.0)
    position_y_mm: float = Field(default=0.0)
    position_z_mm: float = Field(default=0.0)
    # 标签（ADR-009）
    tags: Tags = Field(default_factory=Tags)
    # 几何资产（可选）
    assets: GeometryAssets | None = Field(default=None)


class TelecomPlugin(Plugin):
    name = "telecom"
    version = "0.1.0"

    @property
    def library_dir(self) -> Path:
        return Path(__file__).parent / "library"

    def register_families(self, registry: Registry) -> None:
        registry.add_family("RackFamily", RackFamily)
        registry.add_family("PduFamily", PduFamily)
        registry.add_family("ServerFamily", ServerFamily)

    def register_rules(self, checker: Checker) -> None:
        checker.add_rule("TELECOM-POWER-001", "PDU 功率预算检查", check_pdu_budget, priority=10, severity=Severity.ERROR)
        checker.add_rule("TELECOM-POWER-002", "PDU 相线平衡检查", check_pdu_phase_balance, priority=5, severity=Severity.WARNING)
        checker.add_rule("TELECOM-RACK-001", "U 位冲突检查", check_rack_space, priority=5, severity=Severity.ERROR)
        checker.add_rule("TELECOM-RACK-002", "机柜容量检查", check_rack_capacity, priority=5, severity=Severity.ERROR)
        checker.add_rule("TELECOM-RACK-003", "设备物理尺寸与机柜匹配检查", check_device_physical_fit, priority=3, severity=Severity.WARNING)
        checker.add_rule("TELECOM-COLLISION-001", "机柜内设备 3D 碰撞检测", check_rack_3d_collision, priority=5, severity=Severity.WARNING)
        checker.add_rule("TELECOM-FK-001", "外键完整性检查", check_foreign_keys, priority=10, severity=Severity.WARNING)

    def register_generators(self, checker: Checker) -> None:
        checker.add_generator("bom-csv", "BOM CSV 导出", generate_bom_csv)


def check_pdu_budget(ctx):
    """检查每个 PDU 的负载率不超过项目阈值。"""
    pdus = {p.id: p for p in ctx.query("pdus")}
    threshold = ctx.config.get("power_threshold", 0.8)

    for pdu in ctx.query("pdus"):
        ctx.set_current_file(str(pdu.source))
        devices = ctx.query("devices", pdu_id=pdu.id)
        total_power = sum(d.resolved.tdp_w for d in devices)
        load_ratio = total_power / pdu.resolved.capacity_w
        assert load_ratio <= threshold, (
            f"{pdu.id} 负载率 {load_ratio:.1%}（{total_power}W / {pdu.resolved.capacity_w}W），"
            f"超过项目阈值 {threshold:.1%}。"
            f"已接入设备: {', '.join(d.id for d in devices)}"
        )

    # 检查设备引用的 PDU 是否都存在
    for device in ctx.query("devices"):
        ctx.set_current_file(str(device.source))
        assert device.pdu_id in pdus, (
            f"设备 {device.id} 引用的 PDU {device.pdu_id} 不存在"
        )
    ctx.clear_current_file()


def check_rack_space(ctx):
    """检查同一机柜内没有 U 位重叠的设备。"""
    for rack in ctx.query("racks"):
        ctx.set_current_file(str(rack.source))
        devices = ctx.query("devices", rack_id=rack.id).order_by("position_u")
        occupied = []
        for d in devices:
            height = d.resolved.height_u
            start = d.position_u
            end = start + height - 1
            occupied.append((start, end, d.id, d.source))

        for i, (s1, e1, id1, src1) in enumerate(occupied):
            for s2, e2, id2, src2 in occupied[i + 1 :]:
                if not (e1 < s2 or e2 < s1):
                    overlap_start = max(s1, s2)
                    overlap_end = min(e1, e2)
                    ctx.set_current_file(str(src1))
                    assert False, (
                        f"机柜 {rack.id} U{overlap_start}-U{overlap_end} 冲突: "
                        f"{id1}（U{s1}-U{e1}）与 {id2}（U{s2}-U{e2}）"
                    )
    ctx.clear_current_file()


def check_rack_capacity(ctx):
    """检查机柜内设备总高度不超过机柜容量。"""
    for rack in ctx.query("racks"):
        ctx.set_current_file(str(rack.source))
        devices = ctx.query("devices", rack_id=rack.id)
        total_height = sum(d.resolved.height_u for d in devices)
        assert total_height <= rack.resolved.total_u, (
            f"机柜 {rack.id} 已用 U 位 {total_height}，超过总容量 {rack.resolved.total_u}"
        )
    ctx.clear_current_file()


def check_pdu_phase_balance(ctx):
    """检查同一机柜内三相 PDU 的负载是否均衡。

    三相负载不平衡度 = (最大相功率 - 最小相功率) / 平均相功率
    阈值由项目配置 power_phase_imbalance_threshold 控制（默认 15%）。
    只有机柜内存在多相 PDU 时才检查。
    """
    from collections import defaultdict

    threshold = ctx.config.get("power_phase_imbalance_threshold", 0.15)

    # 按机柜分组统计各相功率
    rack_phases: dict[str, dict[str, float]] = defaultdict(dict)
    for pdu in ctx.query("pdus"):
        devices = ctx.query("devices", pdu_id=pdu.id)
        total_power = sum(d.resolved.tdp_w for d in devices)
        rack_phases[pdu.rack_id][pdu.phase] = total_power

    for rack_id, phases in rack_phases.items():
        # 只有多相才检查平衡
        if len(phases) < 2:
            continue

        powers = list(phases.values())
        avg_power = sum(powers) / len(powers)
        if avg_power <= 0:
            continue

        max_power = max(powers)
        min_power = min(powers)
        imbalance = (max_power - min_power) / avg_power

        if imbalance > threshold:
            rack = ctx.query("racks", id=rack_id).first()
            ctx.set_current_file(str(rack.source) if rack else "")
            phase_info = ", ".join(f"{ph}={pw:.0f}W" for ph, pw in phases.items())
            assert False, (
                f"机柜 {rack_id} 三相负载不平衡度 {imbalance:.1%}，"
                f"超过阈值 {threshold:.1%}。"
                f"各相功率: {phase_info}"
            )
    ctx.clear_current_file()


def check_device_physical_fit(ctx):
    """检查设备物理尺寸是否适合机柜。

    当设备和机柜的 depth_mm/width_mm 都有非零值时：
    - 设备深度 ≤ 机柜深度
    - 设备宽度 ≤ 机柜宽度

    任一尺寸缺失（为 0）时跳过检查，避免误报。
    """
    racks = {r.id: r for r in ctx.query("racks")}

    for device in ctx.query("devices"):
        rack = racks.get(device.rack_id)
        if rack is None:
            continue

        dev_depth = device.resolved.depth_mm
        dev_width = device.resolved.width_mm
        rack_depth = rack.resolved.depth_mm
        rack_width = rack.resolved.width_mm

        # 跳过：任一方缺少尺寸数据
        if dev_depth <= 0 or rack_depth <= 0:
            dev_depth = 0
        if dev_width <= 0 or rack_width <= 0:
            dev_width = 0
        if dev_depth == 0 and dev_width == 0:
            continue

        ctx.set_current_file(str(device.source))

        if dev_depth > 0 and dev_depth > rack_depth:
            assert False, (
                f"设备 {device.id} 深度 {dev_depth}mm 超过机柜 {rack.id} "
                f"深度 {rack_depth}mm，无法安装。"
            )

        if dev_width > 0 and dev_width > rack_width:
            assert False, (
                f"设备 {device.id} 宽度 {dev_width}mm 超过机柜 {rack.id} "
                f"宽度 {rack_width}mm，无法安装。"
            )
    ctx.clear_current_file()


def check_foreign_keys(ctx):
    """检查所有外键引用是否有效。"""
    racks = {r.id: r for r in ctx.query("racks")}
    pdus = {p.id: p for p in ctx.query("pdus")}

    for device in ctx.query("devices"):
        ctx.set_current_file(str(device.source))
        assert device.rack_id in racks, (
            f"设备 {device.id} 引用的机柜 {device.rack_id} 不存在"
        )
        assert device.pdu_id in pdus, (
            f"设备 {device.id} 引用的 PDU {device.pdu_id} 不存在"
        )

    for pdu in ctx.query("pdus"):
        ctx.set_current_file(str(pdu.source))
        assert pdu.rack_id in racks, (
            f"PDU {pdu.id} 引用的机柜 {pdu.rack_id} 不存在"
        )
    ctx.clear_current_file()


def check_rack_3d_collision(ctx):
    """检查同一机柜内设备的 3D 空间碰撞。

    使用 AABB 包围盒进行 O(n²) 碰撞检测。
    无尺寸信息的设备自动跳过。
    """
    from piki.ext.geometry import build_aabb_from_instance, find_collisions

    for rack in ctx.query("racks"):
        devices = ctx.query("devices", rack_id=rack.id)
        items: list[tuple[str, "AABB"]] = []

        for device in devices:
            aabb = build_aabb_from_instance(device)
            if aabb is not None:
                items.append((device.id, aabb))

        if len(items) < 2:
            continue

        collisions = find_collisions(items)
        if collisions:
            ctx.set_current_file(str(rack.source))
            pairs = ", ".join(f"{a} ↔ {b}" for a, b in collisions)
            assert False, (
                f"机柜 {rack.id} 内发现 {len(collisions)} 处设备空间冲突: {pairs}"
            )
    ctx.clear_current_file()


def generate_bom_csv(ctx, config):
    """生成 BOM CSV。"""
    import csv
    import io
    from pathlib import Path

    devices = ctx.query("devices").list()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Model", "Rack", "Position_U", "PDU", "TDP_W", "Height_U"])
    for d in devices:
        writer.writerow([
            d.id,
            d.model or "",
            d.rack_id,
            d.position_u,
            d.pdu_id,
            d.resolved.tdp_w,
            d.resolved.height_u,
        ])

    content = output.getvalue()
    out_path = config.get("output")
    if out_path:
        Path(out_path).write_text(content, encoding="utf-8")
    else:
        print(content)
