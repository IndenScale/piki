"""piki-telecom 内置插件：电信/数据中心。"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from piki.core.engine.checker import Checker, rule
from piki.core.engine.registry import Registry
from piki.core.models.diagnostic import Severity
from piki.core.plugin import Plugin


class RackFamily(BaseModel):
    id: str = Field(...)
    name: str = Field(default="")
    location: str = Field(default="")
    total_u: int = Field(..., ge=1, le=48)
    power_capacity_w: float = Field(default=0, ge=0)  # 机柜配电容量（W）


class PduFamily(BaseModel):
    id: str = Field(...)
    name: str = Field(default="")
    rack_id: str = Field(...)
    phase: str = Field(default="L1")          # 相线，如 L1, L2, L3
    capacity_w: float = Field(..., gt=0)      # 额定功率（W）


class ServerFamily(BaseModel):
    id: str = Field(...)
    name: str = Field(default="")
    model: str = Field(default="")
    status: str = Field(default="planned")
    rack_id: str = Field(...)
    position_u: int = Field(..., ge=1, le=48)
    pdu_id: str = Field(...)                  # 引用 PduFamily.id
    height_u: int = Field(default=2, ge=1, le=48)
    tdp_w: float = Field(default=300, gt=0)
    psu_count: int = Field(default=1, ge=1)
    psu_redundancy: bool = Field(default=False)


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
        checker.add_rule("TELECOM-RACK-001", "U 位冲突检查", check_rack_space, priority=5, severity=Severity.ERROR)
        checker.add_rule("TELECOM-RACK-002", "机柜容量检查", check_rack_capacity, priority=5, severity=Severity.ERROR)
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
