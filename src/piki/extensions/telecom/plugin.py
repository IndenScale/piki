"""piki-telecom 内置插件：电信/数据中心。"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from piki.core.engine.checker import Checker
from piki.core.engine.generator_registry import GeneratorResult
from piki.core.engine.registry import Registry
from piki.core.models.diagnostic import Severity
from piki.core.models.geometry import GeometryAssets
from piki.core.models.interface import InterfaceSpec, resolve_interface_ref
from piki.core.models.tags import Tags
from piki.core.plugin import Plugin
from piki.extensions.telecom.types import (
    INTERFACE_CABLE_MAP,
    are_compatible,
    is_valid_interface_type,
)


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
    # 标签（ADR-001）
    tags: Tags = Field(default_factory=Tags)
    # 几何资产（可选）
    assets: GeometryAssets | None = Field(default=None)


class PduFamily(BaseModel):
    id: str = Field(...)
    name: str = Field(default="")
    rack_id: str = Field(default="")
    phase: str = Field(default="L1")  # 相线，如 L1, L2, L3
    capacity_w: float = Field(..., gt=0)  # 额定功率（W）
    tags: Tags = Field(default_factory=Tags)  # 标签（ADR-001）
    interfaces: list[InterfaceSpec] = Field(
        default_factory=list, description="可连接接口 (ADR-005)"
    )


class ServerFamily(BaseModel):
    id: str = Field(...)
    name: str = Field(default="")
    model: str = Field(default="")
    status: str = Field(default="planned")
    interfaces: list[InterfaceSpec] = Field(
        default_factory=list, description="可连接接口 (ADR-005)"
    )
    rack_id: str = Field(default="")
    position_u: int = Field(default=1, ge=1, le=48)
    pdu_id: str = Field(default="")  # 引用 PduFamily.id
    height_u: int = Field(default=2, ge=1, le=48)
    tdp_w: float = Field(default=300, gt=0)
    psu_count: int = Field(default=1, ge=1)
    psu_redundancy: bool = Field(default=False)
    tags: Tags = Field(default_factory=Tags)  # 标签（ADR-001）
    # 物理尺寸（毫米），用于 3D 碰撞检测和物理尺寸匹配
    depth_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    width_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    height_mm: float = Field(
        default=0, ge=0, json_schema_extra={"piki_non_overridable": True}
    )  # 设备高度（1U ≈ 44.45mm，但这里用实际物理高度）
    weight_kg: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    # 3D 空间定位（毫米，相对于机柜原点）
    position_x_mm: float = Field(default=0.0)
    position_y_mm: float = Field(default=0.0)
    position_z_mm: float = Field(default=0.0)
    # 标签（ADR-001）
    tags: Tags = Field(default_factory=Tags)
    # 几何资产（可选）
    assets: GeometryAssets | None = Field(default=None)


class TransceiverFamily(BaseModel):
    """光模块 (SFP/SFP+/SFP28/QSFP28/QSFP-DD/OSFP).

    独立物理实体，有型号、datasheet、S/N。
    两个 Interface:
      - host: 插入交换机的笼子 (SFP28 cage)
      - line:  接光纤跳线的 LC/MPO 口
    """

    id: str = Field(...)
    name: str = Field(default="")
    model: str = Field(default="")
    form_factor: str = Field(...)  # SFP28, QSFP28, QSFP-DD, OSFP, SFP+, SFP
    reach: str = Field(default="SR")  # SR, LR, ER, ZR, DR, FR
    wavelength_nm: int = Field(default=850, ge=0)
    speed_gbps: float = Field(default=25.0, gt=0)
    status: str = Field(default="planned")
    interfaces: list[InterfaceSpec] = Field(
        default_factory=list, description="host(cage-side) + line(fiber-side)"
    )
    tags: Tags = Field(default_factory=Tags)


class FiberPatchCordFamily(BaseModel):
    """光纤跳线 (LC-LC / MPO-MPO / SC-LC).

    独立物理实体，有型号、长度、衰减。
    两个 Interface (end-a, end-b)，都是双向 LC/MPO/SC 口。
    """

    id: str = Field(...)
    name: str = Field(default="")
    model: str = Field(default="")
    fiber_type: str = Field(default="OM4")  # OM3, OM4, OM5, SM
    connector: str = Field(default="LC-LC")  # LC-LC, MPO-MPO, SC-LC
    length_m: float = Field(default=3.0, gt=0)
    attenuation_db: float = Field(default=0.3, ge=0)
    status: str = Field(default="planned")
    interfaces: list[InterfaceSpec] = Field(
        default_factory=list, description="end-a + end-b (双向 LC/MPO/SC)"
    )
    tags: Tags = Field(default_factory=Tags)


class PortFamily(BaseModel):
    """设备端口：逻辑上一等公民，可被 Connection 直接引用。"""

    id: str = Field(...)
    device_id: str = Field(..., description="所属设备 Instance ID")
    port_name: str = Field(..., description="设备内端口标识，如 eth0、Gi1/0/1")
    port_type: str = Field(..., description="接口类型：SFP28、SFP+、RJ45、LC、MPO 等")
    direction: str = Field(default="bidirectional")
    status: str = Field(default="planned")
    tags: Tags = Field(default_factory=Tags)


class PortConnectionFamily(BaseModel):
    """端口到端口的连接（telecom 粒度）。

    与 datacenter 的 ConnectionFamily（方舱↔方舱）区分。
    """

    id: str = Field(...)
    from_port: str = Field(..., description="源端口引用：DEVICE_ID/PORT_ID")
    to_port: str = Field(..., description="目标端口引用：DEVICE_ID/PORT_ID")
    cable_type: str = Field(default="")
    length_m: float = Field(default=0, ge=0)
    status: str = Field(default="planned")
    tags: Tags = Field(default_factory=Tags)


class TelecomPlugin(Plugin):
    name = "telecom"
    version = "0.1.0"

    @property
    def model_dir(self) -> Path:
        return Path(__file__).parent / "models"

    def register_families(self, registry: Registry) -> None:
        registry.add_family("RackFamily", RackFamily)
        registry.add_family("PduFamily", PduFamily)
        registry.add_family("ServerFamily", ServerFamily)
        registry.add_family("TransceiverFamily", TransceiverFamily)
        registry.add_family("FiberPatchCordFamily", FiberPatchCordFamily)
        registry.add_family("PortFamily", PortFamily)
        registry.add_family("PortConnectionFamily", PortConnectionFamily)

    def register_rules(self, checker: Checker) -> None:
        checker.add_rule(
            "TELECOM-POWER-001",
            "PDU 功率预算检查",
            check_pdu_budget,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-POWER-002",
            "PDU 相线平衡检查",
            check_pdu_phase_balance,
            priority=5,
            severity=Severity.WARNING,
        )
        checker.add_rule(
            "TELECOM-RACK-001",
            "U 位冲突检查",
            check_rack_space,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-RACK-002",
            "机柜容量检查",
            check_rack_capacity,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-RACK-003",
            "设备物理尺寸与机柜匹配检查",
            check_device_physical_fit,
            priority=3,
            severity=Severity.WARNING,
        )
        checker.add_rule(
            "TELECOM-COLLISION-001",
            "机柜内设备 3D 碰撞检测",
            check_rack_3d_collision,
            priority=5,
            severity=Severity.WARNING,
        )
        checker.add_rule(
            "TELECOM-FK-001",
            "外键完整性检查",
            check_foreign_keys,
            priority=10,
            severity=Severity.WARNING,
        )
        checker.add_rule(
            "TELECOM-PORT-001",
            "端口占用冲突检查",
            check_port_occupancy,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-PORT-002",
            "端口所属设备存在性检查",
            check_port_device_exists,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-CONN-001",
            "连接端点存在性检查",
            check_connection_endpoints,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-CONN-002",
            "连接端口类型兼容性检查",
            check_connection_port_compat,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-CONN-003",
            "连接线缆类型匹配检查",
            check_connection_cable_match,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "CATALOG-LIFECYCLE-001",
            "禁止非既有工程使用 EOL 器件",
            check_catalog_lifecycle,
            priority=10,
            severity=Severity.ERROR,
        )

    def register_generators(self, checker: Checker) -> None:
        checker.add_generator("bom-csv", "BOM CSV 导出", generate_bom_csv)
        checker.add_generator("rack-face-panel", "机柜面板图", generate_rack_face_panel)
        checker.add_generator("rack-face-panel-svg", "机柜面板图 SVG", generate_rack_face_panel_svg)
        checker.add_generator("power-budget", "功率预算汇总", generate_power_budget)
        checker.add_generator("cable-list", "线缆清单", generate_cable_list)
        checker.add_generator("port-map", "端口分配表", generate_port_map)
        checker.add_generator("procurement-bom", "采购 BOM", generate_procurement_bom)

    def register_mate_types(self, registry: Registry) -> None:
        """注册 telecom 领域的 Mate 类型 (ADR-006)."""
        from piki.core.models.mating import MateConstraint, MateConstraintOperator, MateTypeMeta

        # L1: 机柜装配
        registry.add_mate_type(
            "rack-mount-19inch",
            MateTypeMeta(
                type="rack-mount-19inch",
                description="19英寸机柜导轨装配",
                default_constrains=[
                    MateConstraint(
                        field="depth_mm",
                        operator=MateConstraintOperator.LTE,
                        value_ref="depth_mm",
                        message="设备深度超过机柜深度",
                    ),
                    MateConstraint(
                        field="width_mm",
                        operator=MateConstraintOperator.LTE,
                        value_ref="width_mm",
                        message="设备宽度超过机柜安装宽度",
                    ),
                ],
                applicable_parent_families={"RackFamily"},
                applicable_child_families={"ServerFamily", "PduFamily"},
            ),
        )

        # L1: 方舱内装配
        registry.add_mate_type(
            "grid-mount",
            MateTypeMeta(
                type="grid-mount",
                description="方舱内设备装配",
                applicable_parent_families={"ContainerFamily"},
                applicable_child_families={"EquipmentFamily", "PowerUnitFamily"},
            ),
        )

        # L2: 电源配合
        registry.add_mate_type(
            "power-iec-c14-c13",
            MateTypeMeta(
                type="power-iec-c14-c13",
                description="IEC C14-C13 电源配对",
            ),
        )

        # L2: 供电电缆
        registry.add_mate_type(
            "power-cable",
            MateTypeMeta(
                type="power-cable",
                description="配电单元到设备供电电缆",
            ),
        )

        # L2: 光模块插入交换机笼子
        registry.add_mate_type(
            "sfp28-cage",
            MateTypeMeta(
                type="sfp28-cage",
                description="光模块插入交换机/服务器笼子",
                default_constrains=[
                    MateConstraint(
                        field="speed_gbps",
                        operator=MateConstraintOperator.LTE,
                        value_ref="speed_gbps",
                        message="光模块速率超过笼子支持速率",
                    ),
                ],
            ),
        )

        # L2: 光纤跳线接头插入光模块/配线架
        registry.add_mate_type(
            "lc-connector",
            MateTypeMeta(
                type="lc-connector",
                description="LC 光纤连接器配对",
                default_constrains=[
                    MateConstraint(
                        field="fiber_type",
                        operator=MateConstraintOperator.EQ,
                        value_ref="fiber_type",
                        message="光纤类型不匹配",
                    ),
                ],
            ),
        )


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
        assert device.pdu_id in pdus, f"设备 {device.id} 引用的 PDU {device.pdu_id} 不存在"
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
        assert device.rack_id in racks, f"设备 {device.id} 引用的机柜 {device.rack_id} 不存在"
        assert device.pdu_id in pdus, f"设备 {device.id} 引用的 PDU {device.pdu_id} 不存在"

    for pdu in ctx.query("pdus"):
        ctx.set_current_file(str(pdu.source))
        assert pdu.rack_id in racks, f"PDU {pdu.id} 引用的机柜 {pdu.rack_id} 不存在"
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
            assert False, f"机柜 {rack.id} 内发现 {len(collisions)} 处设备空间冲突: {pairs}"
    ctx.clear_current_file()


# New generator functions to append to telecom/plugin.py


# ── 产物输出辅助 ──


def _resolve_output_path(config, default_filename: str) -> tuple[str | None, Path | None]:
    """解析产物输出路径。

    优先级：config["output"] (--output 显式指定) > config["target_dir"] (dist/ 约定目录) + default_filename
    """
    out_path = config.get("output")
    if out_path:
        return None, Path(str(out_path))
    target_dir = config.get("target_dir")
    if target_dir:
        file_path = Path(target_dir) / default_filename
        return None, file_path
    return None, None


def _write_and_return(
    gen_id, gen_name, content, file_path, content_type="text/plain"
) -> GeneratorResult:
    """写入文件并返回 GeneratorResult。"""
    if file_path:
        file_path.write_text(content, encoding="utf-8")
    return GeneratorResult.ok(gen_id, gen_name, content, file_path, content_type)


def check_catalog_lifecycle(ctx):
    """禁止非既有工程使用 EOL 器件（ADR-011）。"""
    for inst in ctx.instances():
        catalog = inst._resolved.get("catalog")
        if not isinstance(catalog, dict):
            continue
        if catalog.get("lifecycle") != "eol":
            continue
        context = inst._resolved.get("context")
        if context == "existing":
            continue
        ctx.set_current_file(str(inst.source))
        mpn = catalog.get("mpn") or catalog.get("catalog_id")
        assert False, (
            f"Instance '{inst.id}' 使用 EOL 器件 '{mpn}'，"
            f"仅 context='existing' 的既有设备允许使用。"
        )
    ctx.clear_current_file()


def generate_bom_csv(ctx, config) -> GeneratorResult:
    """生成 BOM CSV：设备清单汇总。"""
    import csv
    import io

    devices = ctx.query("devices").list()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Model", "Rack", "Position_U", "PDU", "TDP_W", "Height_U"])
    for d in devices:
        writer.writerow(
            [
                d.id,
                d.model or "",
                d.rack_id,
                d.position_u,
                d.pdu_id,
                d.resolved.tdp_w,
                d.resolved.height_u,
            ]
        )

    csv_content = output.getvalue()
    _, file_path = _resolve_output_path(config, "bom.csv")
    return _write_and_return("bom-csv", "BOM CSV 导出", csv_content, file_path, "text/csv")


def generate_procurement_bom(ctx, config) -> GeneratorResult:
    """生成采购 BOM：含 manufacturer、MPN、lifecycle（ADR-011）。"""
    import csv
    import io

    devices = ctx.instances().list()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Model", "Manufacturer", "MPN", "Lifecycle"])
    for d in devices:
        catalog = d._resolved.get("catalog") or {}
        writer.writerow(
            [
                d.id,
                d.model_id or "",
                catalog.get("manufacturer", ""),
                catalog.get("mpn", ""),
                catalog.get("lifecycle", ""),
            ]
        )

    csv_content = output.getvalue()
    _, file_path = _resolve_output_path(config, "procurement-bom.csv")
    return _write_and_return(
        "procurement-bom",
        "采购 BOM",
        csv_content,
        file_path,
        "text/csv",
    )


def generate_rack_face_panel(ctx, config) -> GeneratorResult:
    """生成机柜面板图：按机柜列出每个 U 位的设备占用情况。"""

    lines: list[str] = []
    racks = ctx.query("racks").order_by("id").list()

    if not racks:
        lines.append("No racks found.")
    else:
        for rack in racks:
            lines.append(f"{'=' * 60}")
            lines.append(
                f"Rack: {rack.id} ({rack.name or 'unnamed'})"
                f" | Location: {rack.location or 'N/A'}"
                f" | Total: {rack.total_u}U"
            )
            lines.append(f"{'=' * 60}")

            devices = ctx.query("devices", rack_id=rack.id).order_by("position_u").list()

            if not devices:
                for u in range(rack.total_u, 0, -1):
                    lines.append(f"  U{u:>3}: [empty]")
            else:
                dev_map: dict[int, object] = {}
                for d in devices:
                    start = d.position_u
                    height = d.resolved.height_u
                    for u in range(start, start + height):
                        dev_map[u] = d

                for u in range(rack.total_u, 0, -1):
                    d = dev_map.get(u)
                    if d is None:
                        lines.append(f"  U{u:>3}: [empty]")
                    else:
                        start = d.position_u
                        height = d.resolved.height_u
                        if u == start + height - 1:
                            label = f"{d.id} ({d.model or 'N/A'}, {d.resolved.tdp_w}W, {height}U)"
                            lines.append(f"  U{u:>3}: {label}")
                        elif u == start:
                            lines.append(f"  U{u:>3}: {d.id} ^ (bottom)")

            lines.append("")

    text_content = "\n".join(lines)
    _, file_path = _resolve_output_path(config, "rack-panel.txt")
    return _write_and_return("rack-face-panel", "机柜面板图", text_content, file_path)


def generate_rack_face_panel_svg(ctx, config) -> GeneratorResult:
    """生成机柜面板 SVG 图：彩色 U 位可视化，含图例。"""
    from xml.dom import minidom
    from xml.etree import ElementTree as ET

    racks = ctx.query("racks").order_by("id").list()
    if not racks:
        return GeneratorResult.ok(
            "rack-face-panel-svg",
            "机柜面板图 SVG",
            "",
            content_type="image/svg+xml",
        )

    # ── Layout constants (mm scaled to SVG px) ──
    U_HEIGHT = 18  # px per U
    PANEL_WIDTH = 240  # total panel width
    LABEL_WIDTH = 140  # right side label area
    DEVICE_AREA_X = 10  # device block left edge
    DEVICE_AREA_W = PANEL_WIDTH - LABEL_WIDTH - DEVICE_AREA_X - 5
    MARGIN_TOP = 30
    MARGIN_BOTTOM = 30
    RACK_LEFT = 30
    RACK_RIGHT = 30
    FONT_FAMILY = "monospace"
    FONT_SIZE = 10

    # Device color palette (cycling)
    COLORS = [
        "#4A90D9",
        "#5CB85C",
        "#F0AD4E",
        "#D9534F",
        "#8E44AD",
        "#1ABC9C",
        "#E67E22",
        "#2C3E50",
    ]
    color_map: dict[str, str] = {}

    # ── Build per-rack SVG content ──
    svg_outputs: dict[str, str] = {}

    for rack in racks:
        total_u = rack.resolved.total_u
        canvas_h = MARGIN_TOP + total_u * U_HEIGHT + MARGIN_BOTTOM

        devices = ctx.query("devices", rack_id=rack.id).order_by("-position_u").list()

        # Build U-map: which device occupies each U
        dev_map: dict[int, object] = {}
        dev_metadata: dict[str, dict] = {}
        for d in devices:
            start = d.resolved.position_u
            height = d.resolved.height_u
            for u in range(start, start + height):
                dev_map[u] = d
            dev_id = d.id
            if dev_id not in color_map:
                color_map[dev_id] = COLORS[len(color_map) % len(COLORS)]
            dev_metadata[dev_id] = {
                "name": getattr(d.resolved, "name", "") or d.id,
                "model": d.resolved.model or d.family or "",
                "family": d.family or "",
                "tdp_w": d.resolved.tdp_w,
                "height_u": height,
                "position_u": start,
            }

        # Build SVG elements
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        svg = ET.Element(
            "svg",
            {
                "xmlns": "http://www.w3.org/2000/svg",
                "width": str(PANEL_WIDTH + RACK_LEFT + RACK_RIGHT),
                "height": str(canvas_h),
                "viewBox": f"0 0 {PANEL_WIDTH + RACK_LEFT + RACK_RIGHT} {canvas_h}",
            },
        )

        style = ET.SubElement(svg, "style")
        style.text = (
            f".title          {{ font-family: {FONT_FAMILY}; font-size: 13px; font-weight: bold; fill: #222; }}"
            "\n"
            f".u-label         {{ font-family: {FONT_FAMILY}; font-size: {FONT_SIZE}px; fill: #666; }}"
            "\n"
            f".dev-label       {{ font-family: {FONT_FAMILY}; font-size: {FONT_SIZE - 1}px; fill: #222; }}"
            "\n"
            ".rack-outline    { fill: none; stroke: #999; stroke-width: 1.5; }"
            "\n"
            ".grid-line       { stroke: #e0e0e0; stroke-width: 0.5; }"
            "\n"
            f".empty-text      {{ font-family: {FONT_FAMILY}; font-size: {FONT_SIZE - 1}px; fill: #bbb; }}"
            "\n"
            f".legend-text     {{ font-family: {FONT_FAMILY}; font-size: {FONT_SIZE - 1}px; fill: #444; }}"
            "\n"
            f".legend-title    {{ font-family: {FONT_FAMILY}; font-size: {FONT_SIZE}px; font-weight: bold; fill: #333; }}"
        )

        # Background
        ET.SubElement(
            svg,
            "rect",
            {"x": "0", "y": "0", "width": "100%", "height": "100%", "fill": "#FAFAFA"},
        )

        # Title
        title_text = f"Rack: {rack.id}"
        if rack.resolved.name:
            title_text += f" — {rack.resolved.name}"
        title_text += f"  ({rack.resolved.total_u}U)"
        ET.SubElement(
            svg,
            "text",
            {
                "x": str(RACK_LEFT),
                "y": str(MARGIN_TOP - 12),
                "class": "title",
            },
        ).text = title_text

        # Rack outline (the 19-inch rack border)
        rack_x = DEVICE_AREA_X
        rack_y = MARGIN_TOP
        rack_w = DEVICE_AREA_W
        rack_h = total_u * U_HEIGHT
        ET.SubElement(
            svg,
            "rect",
            {
                "x": str(rack_x),
                "y": str(rack_y),
                "width": str(rack_w),
                "height": str(rack_h),
                "class": "rack-outline",
            },
        )

        # Grid lines + U labels + device blocks
        for u in range(total_u, 0, -1):
            # Y position: U1 at bottom, highest U at top
            y = MARGIN_TOP + (total_u - u) * U_HEIGHT

            # Grid line
            ET.SubElement(
                svg,
                "line",
                {
                    "x1": str(rack_x),
                    "y1": str(y + U_HEIGHT),
                    "x2": str(rack_x + rack_w),
                    "y2": str(y + U_HEIGHT),
                    "class": "grid-line",
                },
            )

            # U label (left of rack)
            ET.SubElement(
                svg,
                "text",
                {
                    "x": str(rack_x - 8),
                    "y": str(y + U_HEIGHT - 4),
                    "text-anchor": "end",
                    "class": "u-label",
                },
            ).text = str(u)

            # Device block
            d = dev_map.get(u)
            if d is not None:
                dev_id = d.id
                start = d.resolved.position_u
                height_u = d.resolved.height_u
                # Only draw at the bottom of the device block
                if u == start:
                    block_y = MARGIN_TOP + (total_u - start - height_u + 1) * U_HEIGHT
                    block_h = height_u * U_HEIGHT
                    c = color_map.get(dev_id, "#999")
                    ET.SubElement(
                        svg,
                        "rect",
                        {
                            "x": str(rack_x + 1),
                            "y": str(block_y + 1),
                            "width": str(rack_w - 2),
                            "height": str(block_h - 2),
                            "fill": c,
                            "rx": "2",
                            "ry": "2",
                        },
                    )
                    # Device label on block
                    label = dev_id
                    text_y = block_y + block_h / 2 + 3
                    ET.SubElement(
                        svg,
                        "text",
                        {
                            "x": str(rack_x + rack_w / 2),
                            "y": str(text_y),
                            "text-anchor": "middle",
                            "class": "dev-label",
                            "fill": "#fff",
                        },
                    ).text = label
            else:
                # Empty U
                ET.SubElement(
                    svg,
                    "text",
                    {
                        "x": str(rack_x + rack_w / 2),
                        "y": str(y + U_HEIGHT - 5),
                        "text-anchor": "middle",
                        "class": "empty-text",
                    },
                ).text = "—"

        # ── Legend (right side) ──
        legend_x = rack_x + rack_w + 12
        legend_y = MARGIN_TOP

        ET.SubElement(
            svg,
            "text",
            {"x": str(legend_x), "y": str(legend_y), "class": "legend-title"},
        ).text = "图例"

        legend_idx = 0
        for d in devices:
            dev_id = d.id
            meta = dev_metadata.get(dev_id, {})
            ly = legend_y + 16 + legend_idx * 38
            c = color_map.get(dev_id, "#999")

            # Color swatch
            ET.SubElement(
                svg,
                "rect",
                {
                    "x": str(legend_x),
                    "y": str(ly),
                    "width": "12",
                    "height": "12",
                    "fill": c,
                    "rx": "2",
                    "ry": "2",
                },
            )
            # Device info
            ET.SubElement(
                svg,
                "text",
                {
                    "x": str(legend_x + 18),
                    "y": str(ly + 10),
                    "class": "legend-text",
                },
            ).text = f"{meta.get('name') or dev_id}" + (
                f" ({meta.get('model') or meta.get('family') or ''})"
                if (meta.get("model") or meta.get("family"))
                else ""
            )
            ET.SubElement(
                svg,
                "text",
                {
                    "x": str(legend_x + 18),
                    "y": str(ly + 22),
                    "class": "legend-text",
                    "fill": "#888",
                },
            ).text = (
                f"U{meta.get('position_u', '?')}—U{meta.get('position_u', 0) + meta.get('height_u', 0) - 1}"
                f"  {meta.get('tdp_w', 0)}W  {meta.get('height_u', 0)}U"
            )
            legend_idx += 1

        # Pretty-print SVG
        raw = ET.tostring(svg, encoding="unicode")
        dom = minidom.parseString(raw)
        svg_str = dom.toprettyxml(indent="  ")

        svg_outputs[rack.id] = svg_str

    # ── Output: single SVG with all racks, or per-rack files ──
    if len(svg_outputs) == 1:
        full_svg = list(svg_outputs.values())[0]
        rack_id = list(svg_outputs.keys())[0]
        default_name = f"rack-panel-{rack_id}.svg"
        _, file_path = _resolve_output_path(config, default_name)
        return _write_and_return(
            "rack-face-panel-svg",
            "机柜面板图 SVG",
            full_svg,
            file_path,
            "image/svg+xml",
        )
    else:
        # Multiple racks: assemble into one combined SVG
        combined = _compose_multi_svg(svg_outputs, ET, minidom)
        _, file_path = _resolve_output_path(config, "rack-panels.svg")
        return _write_and_return(
            "rack-face-panel-svg",
            "机柜面板图 SVG",
            combined,
            file_path,
            "image/svg+xml",
        )


def _compose_multi_svg(svg_outputs, ET, minidom) -> str:
    """Combine multiple rack SVGs into a single multi-rack SVG document."""
    GAP = 40
    total_width = 0
    max_height = 0

    # Parse each SVG to measure
    parsed: list[tuple[str, ET.Element, int, int]] = []
    for rack_id, svg_str in svg_outputs.items():
        root = ET.fromstring(svg_str)
        w = int(root.get("width", "0"))
        h = int(root.get("height", "0"))
        parsed.append((rack_id, root, w, h))
        max_height = max(max_height, h)
        total_width += w

    total_width += GAP * (len(parsed) - 1)

    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(total_width + 20),
            "height": str(max_height + 20),
            "viewBox": f"0 0 {total_width + 20} {max_height + 20}",
        },
    )

    ET.SubElement(
        svg,
        "rect",
        {"x": "0", "y": "0", "width": "100%", "height": "100%", "fill": "#FAFAFA"},
    )

    offset_x = 10
    for _rack_id, root, w, h in parsed:
        g = ET.SubElement(svg, "g", {"transform": f"translate({offset_x}, 10)"})
        for child in root:
            g.append(child)
        offset_x += w + GAP

    raw = ET.tostring(svg, encoding="unicode")
    dom = minidom.parseString(raw)
    return dom.toprettyxml(indent="  ")


def generate_power_budget(ctx, config) -> GeneratorResult:
    """生成功率预算汇总表。"""
    import csv
    import io
    from collections import defaultdict

    output = io.StringIO()
    writer = csv.writer(output)

    all_devices = ctx.query("devices").list()
    all_pdus = ctx.query("pdus").list()
    all_racks = ctx.query("racks").list()

    total_it_power = sum(d.resolved.tdp_w for d in all_devices)
    total_pdu_capacity = sum(p.resolved.capacity_w for p in all_pdus)

    writer.writerow(["=== 功率预算汇总 ==="])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total IT Power (W)", total_it_power])
    writer.writerow(["Total PDU Capacity (W)", total_pdu_capacity])
    if total_pdu_capacity > 0:
        writer.writerow(["Overall Load Ratio", f"{total_it_power / total_pdu_capacity:.1%}"])
    writer.writerow([])

    writer.writerow(["=== 按 PDU 功率明细 ==="])
    writer.writerow(
        [
            "PDU ID",
            "Phase",
            "Capacity (W)",
            "Connected Devices",
            "Total Load (W)",
            "Load Ratio",
            "Margin (W)",
        ]
    )
    for pdu in sorted(all_pdus, key=lambda p: p.id):
        devices = ctx.query("devices", pdu_id=pdu.id).list()
        load = sum(d.resolved.tdp_w for d in devices)
        cap = pdu.resolved.capacity_w
        ratio = load / cap if cap > 0 else 0
        margin = cap - load
        writer.writerow(
            [
                pdu.id,
                pdu.phase,
                cap,
                len(devices),
                load,
                f"{ratio:.1%}",
                margin,
            ]
        )
    writer.writerow([])

    writer.writerow(["=== 按机柜功率明细 ==="])
    writer.writerow(["Rack ID", "Devices", "Total Load (W)", "Rack Capacity (W)", "Load Ratio"])
    for rack in sorted(all_racks, key=lambda r: r.id):
        devices = ctx.query("devices", rack_id=rack.id).list()
        load = sum(d.resolved.tdp_w for d in devices)
        cap = rack.resolved.power_capacity_w
        writer.writerow(
            [
                rack.id,
                len(devices),
                load,
                cap,
                f"{load / cap:.1%}" if cap > 0 else "N/A",
            ]
        )
    writer.writerow([])

    phase_power: dict[str, float] = defaultdict(float)
    for pdu in all_pdus:
        devices = ctx.query("devices", pdu_id=pdu.id).list()
        phase_power[pdu.phase] += sum(d.resolved.tdp_w for d in devices)

    if phase_power:
        writer.writerow(["=== 各相功率汇总 ==="])
        writer.writerow(["Phase", "Total Load (W)"])
        for phase in sorted(phase_power):
            writer.writerow([phase, phase_power[phase]])

    csv_content = output.getvalue()
    _, file_path = _resolve_output_path(config, "power-budget.csv")
    return _write_and_return("power-budget", "功率预算汇总", csv_content, file_path, "text/csv")


def generate_cable_list(ctx, config) -> GeneratorResult:
    """生成线缆清单：汇总光纤跳线和光模块。"""
    import csv
    import io

    cable_type = config.get("cable_type", "all")
    output = io.StringIO()
    writer = csv.writer(output)

    if cable_type in ("all", "fiber"):
        fibers = ctx.query("fibers").list()
        if fibers:
            writer.writerow(["=== 光纤跳线 ==="])
            writer.writerow(
                ["ID", "Model", "Type", "Connector", "Length (m)", "Attenuation (dB)", "Status"]
            )
            for f in sorted(fibers, key=lambda x: x.id):
                writer.writerow(
                    [
                        f.id,
                        f.model or "N/A",
                        f.fiber_type,
                        f.connector,
                        f.length_m,
                        f.attenuation_db,
                        f.status,
                    ]
                )
        else:
            writer.writerow(["=== 光纤跳线 === (none)"])
        writer.writerow([])

    if cable_type in ("all", "transceiver"):
        transceivers = ctx.query("transceivers").list()
        if transceivers:
            writer.writerow(["=== 光模块 ==="])
            writer.writerow(
                ["ID", "Model", "Form Factor", "Reach", "Speed (Gbps)", "Wavelength (nm)", "Status"]
            )
            for t in sorted(transceivers, key=lambda x: x.id):
                writer.writerow(
                    [
                        t.id,
                        t.model or "N/A",
                        t.form_factor,
                        t.reach,
                        t.speed_gbps,
                        t.wavelength_nm,
                        t.status,
                    ]
                )
        else:
            writer.writerow(["=== 光模块 === (none)"])
        writer.writerow([])

    csv_content = output.getvalue()
    _, file_path = _resolve_output_path(config, "cable-list.csv")
    return _write_and_return("cable-list", "线缆清单", csv_content, file_path, "text/csv")


def _resolve_port_ref(ref: str, ports: dict[str, Any]) -> Any | None:
    """解析 DEVICE_ID/PORT_NAME 引用，返回匹配的 PortFamily 实例。

    匹配逻辑：先按 Port Instance ID 查找，再按 device_id + port_name 组合查找。
    """
    # 1. 直接按 Instance ID 查找（允许用户直接写 Port Instance ID）
    if ref in ports:
        return ports[ref]

    # 2. 按 DEVICE_ID/PORT_NAME 解析查找
    if "/" not in ref:
        return None
    try:
        device_id, port_name = resolve_interface_ref(ref)
    except ValueError:
        return None

    for port in ports.values():
        if port.device_id == device_id and port.resolved.port_name == port_name:
            return port
    return None


def check_port_occupancy(ctx):
    """检查同一设备内端口标识唯一。"""
    seen: dict[tuple[str, str], str] = {}
    for port in ctx.query("ports"):
        ctx.set_current_file(str(port.source))
        key = (port.device_id, port.resolved.port_name)
        if key in seen:
            assert False, (
                f"设备 {port.device_id} 的端口 '{port.resolved.port_name}' 被重复定义: "
                f"{seen[key]} 与 {port.id}"
            )
        seen[key] = port.id
    ctx.clear_current_file()


def check_port_device_exists(ctx):
    """检查每个端口引用的设备都存在。"""
    devices = {d.id: d for d in ctx.query("devices")}
    for port in ctx.query("ports"):
        ctx.set_current_file(str(port.source))
        assert port.device_id in devices, f"端口 {port.id} 引用的设备 {port.device_id} 不存在"
    ctx.clear_current_file()


def check_connection_endpoints(ctx):
    """检查连接的 from_port / to_port 引用都存在且格式正确。"""
    ports = {p.id: p for p in ctx.query("ports")}
    for conn in ctx.query("port_connections"):
        ctx.set_current_file(str(conn.source))
        for endpoint_name in ("from_port", "to_port"):
            ref = getattr(conn.resolved, endpoint_name, "")
            if not ref:
                assert False, f"连接 {conn.id} 的 {endpoint_name} 未定义"
            port = _resolve_port_ref(ref, ports)
            assert port is not None, f"连接 {conn.id} 的 {endpoint_name} 引用端口 {ref} 不存在"
    ctx.clear_current_file()


def check_connection_port_compat(ctx):
    """检查连接两端端口类型兼容。"""
    ports = {p.id: p for p in ctx.query("ports")}
    for conn in ctx.query("port_connections"):
        ctx.set_current_file(str(conn.source))
        from_ref = conn.resolved.from_port
        to_ref = conn.resolved.to_port

        from_port = _resolve_port_ref(from_ref, ports)
        to_port = _resolve_port_ref(to_ref, ports)
        if from_port is None or to_port is None:
            continue  # CONN-001 会报不存在

        from_type = from_port.resolved.port_type
        to_type = to_port.resolved.port_type

        if from_type == to_type:
            continue

        if is_valid_interface_type(from_type) and is_valid_interface_type(to_type):
            if are_compatible(from_type, to_type) or are_compatible(to_type, from_type):
                continue
            assert False, (
                f"连接 {conn.id} 两端端口类型不兼容: "
                f"{from_ref} ({from_type}) vs {to_ref} ({to_type})"
            )
    ctx.clear_current_file()


def check_connection_cable_match(ctx):
    """检查连接线缆类型与端口类型匹配。"""
    ports = {p.id: p for p in ctx.query("ports")}
    for conn in ctx.query("port_connections"):
        cable_type = getattr(conn.resolved, "cable_type", "")
        if not cable_type:
            continue

        ctx.set_current_file(str(conn.source))
        for endpoint_name in ("from_port", "to_port"):
            ref = getattr(conn.resolved, endpoint_name, "")
            port = _resolve_port_ref(ref, ports)
            if port is None:
                continue  # CONN-001 会报不存在

            port_type = port.resolved.port_type
            if not is_valid_interface_type(port_type):
                continue

            valid_cables = INTERFACE_CABLE_MAP.get(port_type, frozenset())
            if valid_cables and cable_type not in valid_cables:
                assert False, (
                    f"连接 {conn.id} 的线缆类型不匹配: "
                    f"{ref} (port_type={port_type}) 不支持 cable_type={cable_type}。"
                    f"支持的线缆: {', '.join(sorted(valid_cables))}"
                )
    ctx.clear_current_file()


def generate_port_map(ctx, config) -> GeneratorResult:
    """生成端口分配表：每设备的端口占用与对端连接情况。"""
    import csv
    import io

    ports = ctx.query("ports").list()
    connections = ctx.query("port_connections").list()

    # 建立端口 ID -> 连接信息映射
    port_conn: dict[str, dict[str, Any]] = {}
    for conn in connections:
        for endpoint_name in ("from_port", "to_port"):
            ref = getattr(conn.resolved, endpoint_name, "")
            port = _resolve_port_ref(ref, {p.id: p for p in ports})
            if port is None:
                continue
            other_endpoint_name = "to_port" if endpoint_name == "from_port" else "from_port"
            other_ref = getattr(conn.resolved, other_endpoint_name, "")
            port_conn[port.id] = {
                "connected_to": other_ref,
                "cable_type": getattr(conn.resolved, "cable_type", ""),
                "length_m": getattr(conn.resolved, "length_m", 0),
            }

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Port Instance ID",
            "Device ID",
            "Port Name",
            "Port Type",
            "Status",
            "Connected To",
            "Cable Type",
            "Length (m)",
        ]
    )

    for port in sorted(ports, key=lambda p: (p.device_id, p.resolved.port_name)):
        conn_info = port_conn.get(port.id, {})
        writer.writerow(
            [
                port.id,
                port.device_id,
                port.resolved.port_name,
                port.resolved.port_type,
                port.resolved.status,
                conn_info.get("connected_to", ""),
                conn_info.get("cable_type", ""),
                conn_info.get("length_m", 0),
            ]
        )

    csv_content = output.getvalue()
    _, file_path = _resolve_output_path(config, "port-map.csv")
    return _write_and_return("port-map", "端口分配表", csv_content, file_path, "text/csv")
