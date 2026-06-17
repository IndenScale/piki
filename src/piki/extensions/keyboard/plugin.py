"""piki-keyboard 内置插件：机械键盘设计校验。

面向场景：
- 铝坨坨 / 塑料 / 木壳机械键盘
- 有线 / 蓝牙 / 2.4G 三模键盘
- 热插拔 / 焊接轴体
- 硅胶 / Poron / EVA 隔音与 gasket 结构
- PBT / ABS 键帽，国产轴体（佳达隆、凯华、TTC、JWK 等）

与 telecom/datacenter 插件的区别：
- telecom：机柜级设备部署
- datacenter：方舱级模块化部署
- keyboard：消费电子产品级机电集成
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adl.diagnostics import Severity
from adl.geometry import GeometryAssets
from adl.models import (
    AssemblyFamily,
    FootprintSpec,
    InterfaceSpec,
    MateTypeMeta,
    Tags,
)
from adl.types import TypeRegistry
from pydantic import BaseModel, Field

from piki.core.engine.checker import Checker
from piki.core.engine.generator_registry import GeneratorResult
from piki.core.plugin import Plugin
from piki.extensions.consumer_electronics.plugin import make_power_budget

# 键盘领域常用接口类型
KEYBOARD_INTERFACE_TYPES = [
    "mx-stem",
    "choc-stem",
    "alps-stem",
    "box-stem",
    "usb-c",
    "usb-mini",
    "usb-micro",
    "trrs",
    "jst-ph-2pin",
    "jst-sh-2pin",
    "switch-pin",
    "led-pin",
]

# ---------------------------------------------------------------------------
# Family 定义
# ---------------------------------------------------------------------------


class KeyboardAssemblyFamily(AssemblyFamily):
    """整把键盘的装配体定义，继承核心 AssemblyFamily。"""

    layout: str = Field(...)  # 60%, 65%, 75%, tkl, full-size, numpad
    key_count: int = Field(default=0, ge=0)
    connectivity: list[str] = Field(default_factory=list)  # usb, bluetooth, 2.4g
    mounting_style: str = Field(...)  # gasket, tray, top, bottom, sandwich, integrated-plate
    wireless: bool = Field(default=False)
    led_support: bool = Field(default=False)
    operating_environment: str = Field(default="indoor")
    environment_id: str = Field(default="")
    assembly_type: str = Field(default="keyboard")
    # 顶层组件引用
    case_id: str = Field(default="")
    plate_id: str = Field(default="")
    pcb_id: str = Field(default="")
    battery_id: str = Field(default="")
    cable_id: str = Field(default="")


class CaseFamily(BaseModel):
    """键盘外壳。支持铝坨坨、塑料、木壳、亚克力等。"""

    id: str = Field(...)
    name: str = Field(default="")
    case_type: str = Field(...)  # aluminum, plastic, wood, acrylic, titanium
    mounting_style: str = Field(...)  # gasket, tray, top, bottom, sandwich
    length_mm: float = Field(default=0, ge=0)
    width_mm: float = Field(default=0, ge=0)
    height_mm: float = Field(default=0, ge=0)
    weight_g: float = Field(default=0, ge=0)
    wall_thickness_mm: float = Field(default=0, ge=0)
    process_id: str = Field(default="")
    surface_finish: str = Field(default="")
    has_usb_cutout: bool = Field(default=True)
    usb_cutout_position_x_mm: float = Field(default=0)
    usb_cutout_position_y_mm: float = Field(default=0)
    usb_cutout_width_mm: float = Field(default=12)
    usb_cutout_height_mm: float = Field(default=6)
    has_antenna_aperture: bool = Field(default=False)
    antenna_aperture_area_mm2: float = Field(default=0, ge=0)
    assets: GeometryAssets | None = Field(default=None)
    tags: Tags = Field(default_factory=Tags)


class PlateFamily(BaseModel):
    """定位板：决定轴体固定方式和手感。"""

    id: str = Field(...)
    name: str = Field(default="")
    material: str = Field(...)  # aluminum, brass, pc, fr4, pom, carbon_fiber, steel
    thickness_mm: float = Field(default=1.5, gt=0)
    layout: str = Field(...)
    switch_cutout_type: str = Field(default="mx")  # mx, choc, alps, box
    mounting_style: str = Field(...)  # gasket, tray, top, bottom, sandwich
    flex_cuts: bool = Field(default=False)
    assets: GeometryAssets | None = Field(default=None)
    tags: Tags = Field(default_factory=Tags)


class PcbFamily(BaseModel):
    """键盘 PCB：矩阵、控制器、接口。"""

    id: str = Field(...)
    name: str = Field(default="")
    controller: str = Field(...)  # stm32f072, rp2040, nrf52840, etc.
    matrix_rows: int = Field(..., ge=1)
    matrix_cols: int = Field(..., ge=1)
    switch_footprint: str = Field(default="mx")  # mx, choc, alps, hotswap-mx
    led_support: bool = Field(default=False)
    led_type: str = Field(default="")  # per-key, underglow, none
    wireless: bool = Field(default=False)
    usb_connector_type: str = Field(default="usb-c")  # usb-c, usb-mini, usb-micro
    has_battery_connector: bool = Field(default=False)
    battery_connector_type: str = Field(default="")
    mounting_holes: int = Field(default=0, ge=0)
    length_mm: float = Field(default=0, ge=0)
    width_mm: float = Field(default=0, ge=0)
    max_matrix_current_ma: int = Field(default=100, gt=0)
    max_usb_current_ma: int = Field(default=500, gt=0)
    interfaces: list[InterfaceSpec] = Field(default_factory=list)
    footprints: list[FootprintSpec] = Field(default_factory=list)
    assets: GeometryAssets | None = Field(default=None)
    tags: Tags = Field(default_factory=Tags)


class SwitchFamily(BaseModel):
    """机械轴体：国产轴体如佳达隆、凯华、TTC、JWK 等。"""

    id: str = Field(...)
    name: str = Field(default="")
    manufacturer: str = Field(...)  # gateron, kailh, ttc, jwk, outemu, akko, etc.
    stem_type: str = Field(...)  # mx, choc, alps, box, d-shape
    pin_count: int = Field(default=3, ge=2, le=5)
    led_support: bool = Field(default=False)
    led_pin_position: str = Field(default="")  # north, south
    operating_force_gf: float = Field(default=50, gt=0)
    bottom_out_force_gf: float = Field(default=60, gt=0)
    pre_travel_mm: float = Field(default=2.0, gt=0)
    total_travel_mm: float = Field(default=4.0, gt=0)
    lifetime_cycles: int = Field(default=50000000, ge=0)
    interfaces: list[InterfaceSpec] = Field(default_factory=list)
    assets: GeometryAssets | None = Field(default=None)
    tags: Tags = Field(default_factory=Tags)


class KeycapFamily(BaseModel):
    """键帽。"""

    id: str = Field(...)
    name: str = Field(default="")
    material: str = Field(...)  # pbt, abs, pom, resin
    material_id: str = Field(default="")  # 引用 MaterialFamily 实例
    profile: str = Field(...)  # cherry, oem, sa, dsa, xda, mda, kca, mt3
    stem_mount: str = Field(...)  # mx, choc, alps
    legend_method: str = Field(default="")  # double-shot, dye-sub, laser, none
    color: str = Field(default="")
    assets: GeometryAssets | None = Field(default=None)
    tags: Tags = Field(default_factory=Tags)


class StabilizerFamily(BaseModel):
    """卫星轴：用于大键。"""

    id: str = Field(...)
    name: str = Field(default="")
    stab_type: str = Field(...)  # plate-mount, screw-in, snap-in, clip-in
    wire_diameter_mm: float = Field(default=1.6, gt=0)
    housing_type: str = Field(default="")  # mx-plus, costar
    compatibility: list[str] = Field(default_factory=list)  # mx, choc, alps
    assets: GeometryAssets | None = Field(default=None)
    tags: Tags = Field(default_factory=Tags)


class DampenerFamily(BaseModel):
    """隔音/缓冲材料：硅胶、Poron、EVA。"""

    id: str = Field(...)
    name: str = Field(default="")
    material: str = Field(...)  # silicone, poron, eva, pe, ixpe
    thickness_mm: float = Field(..., gt=0)
    placement: str = Field(...)  # case-bottom, plate-pcb, gasket, switch-pad
    compression_ratio_max: float = Field(default=0.5, ge=0, le=1)
    assets: GeometryAssets | None = Field(default=None)
    tags: Tags = Field(default_factory=Tags)


class BatteryFamily(BaseModel):
    """锂电池：三模键盘供电。"""

    id: str = Field(...)
    name: str = Field(default="")
    chemistry: str = Field(default="li-po")  # li-po, li-ion
    capacity_mah: int = Field(..., gt=0)
    voltage_v: float = Field(default=3.7, gt=0)
    max_discharge_current_ma: int = Field(default=1000, gt=0)
    length_mm: float = Field(default=0, ge=0)
    width_mm: float = Field(default=0, ge=0)
    thickness_mm: float = Field(default=0, ge=0)
    weight_g: float = Field(default=0, ge=0)
    interfaces: list[InterfaceSpec] = Field(default_factory=list)
    footprints: list[FootprintSpec] = Field(default_factory=list)
    assets: GeometryAssets | None = Field(default=None)
    tags: Tags = Field(default_factory=Tags)


class CableFamily(BaseModel):
    """连接线：USB-C / 航插线 / TRRS。"""

    id: str = Field(...)
    name: str = Field(default="")
    connector_type: str = Field(...)  # usb-c, usb-a, trrs, aviator
    cable_type: str = Field(default="straight")  # straight, coiled, aviator
    length_m: float = Field(default=1.5, gt=0)
    supports_data: bool = Field(default=True)
    supports_power_a: float = Field(default=0.5, gt=0)
    interfaces: list[InterfaceSpec] = Field(default_factory=list)
    footprints: list[FootprintSpec] = Field(default_factory=list)
    assets: GeometryAssets | None = Field(default=None)
    tags: Tags = Field(default_factory=Tags)


class KeyClusterFamily(BaseModel):
    """键簇：批量声明一组相同型号的轴体+键帽。

    用于解决 68 键键盘需要 68 个 switch YAML + 68 个 keycap YAML 的文件爆炸问题。
    一个 KeyCluster 代表 N 颗使用相同轴体、相同键帽的按键，规则按 key_count 展开检查。
    """

    id: str = Field(...)
    name: str = Field(default="")
    switch_model: str = Field(...)
    keycap_model: str = Field(...)
    key_count: int = Field(..., ge=0)
    led_per_key: bool = Field(default=False)
    matrix_positions: list[dict[str, Any]] = Field(default_factory=list)
    description: str = Field(default="")
    tags: Tags = Field(default_factory=Tags)


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class KeyboardPlugin(Plugin):
    name = "keyboard"
    version = "0.1.0"

    @property
    def model_dir(self) -> Path:
        return Path(__file__).parent / "models"

    def register_types(self, type_registry: TypeRegistry) -> None:
        # 注册键盘领域接口类型到核心全局表
        type_registry.add_interface_types(KEYBOARD_INTERFACE_TYPES)

        # 注册核心 AssemblyFamily，使键盘装配体可复用核心层级遍历能力
        type_registry.add_family("AssemblyFamily", AssemblyFamily)

        type_registry.add_family("KeyboardAssemblyFamily", KeyboardAssemblyFamily)
        type_registry.add_family("CaseFamily", CaseFamily)
        type_registry.add_family("PlateFamily", PlateFamily)
        type_registry.add_family("PcbFamily", PcbFamily)
        type_registry.add_family("SwitchFamily", SwitchFamily)
        type_registry.add_family("KeycapFamily", KeycapFamily)
        type_registry.add_family("StabilizerFamily", StabilizerFamily)
        type_registry.add_family("DampenerFamily", DampenerFamily)
        type_registry.add_family("BatteryFamily", BatteryFamily)
        type_registry.add_family("CableFamily", CableFamily)
        type_registry.add_family("KeyClusterFamily", KeyClusterFamily)

        type_registry.add_mate_type(
            "case-bottom-dampener",
            MateTypeMeta(
                type="case-bottom-dampener",
                description="底壳硅胶/泡棉隔音垫",
                applicable_parent_families={"CaseFamily"},
                applicable_child_families={"DampenerFamily"},
            ),
        )
        type_registry.add_mate_type(
            "plate-gasket-mount",
            MateTypeMeta(
                type="plate-gasket-mount",
                description="定位板通过 gasket 装到外壳",
                applicable_parent_families={"CaseFamily"},
                applicable_child_families={"PlateFamily"},
            ),
        )
        type_registry.add_mate_type(
            "pcb-standoff-mount",
            MateTypeMeta(
                type="pcb-standoff-mount",
                description="PCB 通过铜柱/螺丝固定到外壳",
                applicable_parent_families={"CaseFamily"},
                applicable_child_families={"PcbFamily"},
            ),
        )
        type_registry.add_mate_type(
            "switch-plate-snap",
            MateTypeMeta(
                type="switch-plate-snap",
                description="轴体卡入定位板",
                applicable_parent_families={"PlateFamily"},
                applicable_child_families={"SwitchFamily"},
            ),
        )
        type_registry.add_mate_type(
            "switch-pcb-solder",
            MateTypeMeta(
                type="switch-pcb-solder",
                description="轴体针脚焊接到 PCB",
                applicable_parent_families={"PcbFamily"},
                applicable_child_families={"SwitchFamily"},
            ),
        )
        type_registry.add_mate_type(
            "stabilizer-plate-mount",
            MateTypeMeta(
                type="stabilizer-plate-mount",
                description="卫星轴卡入定位板",
                applicable_parent_families={"PlateFamily"},
                applicable_child_families={"StabilizerFamily"},
            ),
        )
        type_registry.add_mate_type(
            "stabilizer-pcb-snap",
            MateTypeMeta(
                type="stabilizer-pcb-snap",
                description="卫星轴卡入 PCB",
                applicable_parent_families={"PcbFamily"},
                applicable_child_families={"StabilizerFamily"},
            ),
        )
        type_registry.add_mate_type(
            "stabilizer-pcb-screw",
            MateTypeMeta(
                type="stabilizer-pcb-screw",
                description="卫星轴通过螺丝固定到 PCB",
                applicable_parent_families={"PcbFamily"},
                applicable_child_families={"StabilizerFamily"},
            ),
        )
        type_registry.add_mate_type(
            "keycap-stem-mount",
            MateTypeMeta(
                type="keycap-stem-mount",
                description="键帽菊花装到轴体/卫星轴上",
                applicable_parent_families={"SwitchFamily", "StabilizerFamily"},
                applicable_child_families={"KeycapFamily"},
            ),
        )
        type_registry.add_mate_type(
            "battery-pcb-cable",
            MateTypeMeta(
                type="battery-pcb-cable",
                description="电池通过 JST 等接口连接到 PCB",
                applicable_parent_families={"PcbFamily"},
                applicable_child_families={"BatteryFamily"},
            ),
        )
        type_registry.add_mate_type(
            "usb-cable-mate",
            MateTypeMeta(
                type="usb-cable-mate",
                description="USB 线插到 PCB 母座上",
                applicable_parent_families={"PcbFamily"},
                applicable_child_families={"CableFamily"},
            ),
        )

    def register_rules(self, checker: Checker) -> None:
        checker.add_rule(
            "KB-STEM-001",
            "键帽与轴体 stem 兼容",
            check_keycap_stem_compatibility,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "KB-SWITCH-001",
            "轴体针脚与 PCB 焊盘兼容",
            check_switch_pcb_pin_compatibility,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "KB-PLATE-001",
            "轴体与定位板开孔兼容",
            check_switch_plate_cutout_compatibility,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "KB-STAB-001",
            "卫星轴与定位板/PCB 兼容",
            check_stabilizer_compatibility,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "KB-MOUNT-001",
            "外壳/定位板/PCB 安装方式一致",
            check_mounting_style_consistency,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "KB-WIRELESS-001",
            "无线键盘外壳需预留天线开口",
            check_wireless_antenna,
            priority=10,
            severity=Severity.WARNING,
        )
        checker.add_rule(
            "KB-POWER-001",
            "电池容量满足无线续航要求",
            check_battery_capacity,
            priority=5,
            severity=Severity.WARNING,
        )
        checker.add_rule(
            "KB-CURRENT-001",
            "总电流不超过电池/控制器限额",
            check_current_budget,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "KB-USB-001",
            "USB 接口类型与线材匹配",
            check_usb_cable_match,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "KB-ENV-001",
            "PBT 键帽户外使用需确认耐候性",
            check_keycap_environmental_fit,
            priority=3,
            severity=Severity.INFO,
        )
        checker.add_rule(
            "KB-CLUSTER-001",
            "KeyCluster 引用的型号必须存在",
            check_key_cluster_models,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "KB-CLUSTER-002",
            "KeyCluster 键数与矩阵位置数量一致",
            check_key_cluster_count,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "KB-CLUSTER-003",
            "KeyCluster 矩阵位置在 PCB 矩阵范围内",
            check_key_cluster_matrix_bounds,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "KB-ASSEMBLY-001",
            "子装配体引用必须存在且为装配体 Family",
            check_keyboard_sub_assemblies,
            priority=10,
            severity=Severity.ERROR,
        )

    def register_generators(self, checker: Checker) -> None:
        checker.add_generator("keyboard-bom", "键盘 BOM CSV 导出", generate_keyboard_bom_csv)
        checker.add_generator("keyboard-spec", "键盘规格说明书", generate_keyboard_spec)


# ---------------------------------------------------------------------------
# 规则实现
# ---------------------------------------------------------------------------


def _find_mates_by_type(ctx, instance_id: str, mate_type: str):
    """查找涉及指定实例、指定类型的所有 Mate。"""
    return [m for m in ctx.mate_graph.related_to(instance_id) if m.type == mate_type]


def _get_mated_child_instance(ctx, mate):
    """从 Mate 中获取 child 对应的 ResolvedInstance。

    已迁移到核心 Context API：ctx.mate_child_instance(mate)
    """
    return ctx.mate_child_instance(mate)


def _get_mated_parent_instance(ctx, mate):
    """从 Mate 中获取 parent 对应的 ResolvedInstance。

    已迁移到核心 Context API：ctx.mate_parent_instance(mate)
    """
    return ctx.mate_parent_instance(mate)


def check_keycap_stem_compatibility(ctx):
    """检查键帽 stem 是否与轴体/卫星轴 stem 匹配。"""
    for keycap in ctx.query("keycaps"):
        mates = _find_mates_by_type(ctx, keycap.id, "keycap-stem-mount")
        for mate in mates:
            parent = _get_mated_parent_instance(ctx, mate)
            if parent is None:
                continue
            keycap_stem = keycap.resolved.stem_mount
            parent_family = parent.family
            if parent_family == "SwitchFamily":
                parent_stem = parent.resolved.stem_type
                assert parent_stem == keycap_stem, (
                    f"键帽 {keycap.id} stem_mount={keycap_stem} 与 "
                    f"轴体 {parent.id} stem_type={parent_stem} 不兼容"
                )
            elif parent_family == "StabilizerFamily":
                compatibility = parent.resolved.compatibility
                assert keycap_stem in compatibility, (
                    f"键帽 {keycap.id} stem_mount={keycap_stem} 不在 "
                    f"卫星轴 {parent.id} 兼容列表 {compatibility} 中"
                )


def check_switch_pcb_pin_compatibility(ctx):
    """检查轴体针脚数量是否与 PCB footprint 匹配。"""
    for sw in ctx.query("switches"):
        mates = _find_mates_by_type(ctx, sw.id, "switch-pcb-solder")
        for mate in mates:
            pcb = _get_mated_parent_instance(ctx, mate)
            if pcb is None:
                continue
            pin_count = sw.resolved.pin_count
            footprint = pcb.resolved.switch_footprint
            required_pins = 5 if "hotswap" in footprint or footprint == "mx" else 3
            if footprint == "choc":
                required_pins = 3
            assert pin_count == required_pins, (
                f"轴体 {sw.id} 针脚数 {pin_count} 与 PCB {pcb.id} "
                f"footprint {footprint} 要求 {required_pins} 针不兼容"
            )


def check_switch_plate_cutout_compatibility(ctx):
    """检查轴体底部外壳是否与定位板开孔类型匹配。"""
    for sw in ctx.query("switches"):
        mates = _find_mates_by_type(ctx, sw.id, "switch-plate-snap")
        for mate in mates:
            plate = _get_mated_parent_instance(ctx, mate)
            if plate is None:
                continue
            stem_type = sw.resolved.stem_type
            cutout_type = plate.resolved.switch_cutout_type
            assert stem_type == cutout_type, (
                f"轴体 {sw.id} stem_type={stem_type} 与定位板 {plate.id} "
                f"cutout={cutout_type} 不兼容"
            )


def check_stabilizer_compatibility(ctx):
    """检查卫星轴与定位板/PCB 的装配方式兼容。"""
    for stab in ctx.query("stabilizers"):
        stab_type = stab.resolved.stab_type
        has_pcb_screw = False
        for mate in ctx.mate_graph.related_to(stab.id):
            parent = _get_mated_parent_instance(ctx, mate)
            if parent is None:
                continue
            if mate.type == "stabilizer-plate-mount":
                # 常见卫星轴（含 screw-in）均可卡入定位板
                assert stab_type in ("plate-mount", "snap-in", "clip-in", "screw-in"), (
                    f"卫星轴 {stab.id} 类型 {stab_type} 无法装配到定位板 {parent.id}"
                )
            elif mate.type == "stabilizer-pcb-snap":
                assert stab_type in ("snap-in", "clip-in"), (
                    f"卫星轴 {stab.id} 类型 {stab_type} 无法卡入 PCB {parent.id}"
                )
            elif mate.type == "stabilizer-pcb-screw":
                has_pcb_screw = True
                assert stab_type in ("screw-in",), (
                    f"卫星轴 {stab.id} 类型 {stab_type} 无法通过螺丝固定到 PCB {parent.id}"
                )
        # screw-in 卫星轴必须至少有一个 PCB 螺丝固定点
        if stab_type == "screw-in" and not has_pcb_screw:
            assert False, f"screw-in 卫星轴 {stab.id} 缺少 PCB 螺丝固定 mate"


def check_mounting_style_consistency(ctx):
    """检查外壳、定位板、PCB 的安装方式一致。"""
    for assembly in ctx.query("assembly"):
        case_id = getattr(assembly.resolved, "case_id", "")
        plate_id = getattr(assembly.resolved, "plate_id", "")
        pcb_id = getattr(assembly.resolved, "pcb_id", "")

        styles = []
        if case_id:
            case = ctx.find_instance(case_id)
            if case:
                styles.append(("case", case.resolved.mounting_style))
        if plate_id:
            plate = ctx.find_instance(plate_id)
            if plate:
                styles.append(("plate", plate.resolved.mounting_style))
        if pcb_id:
            pcb = ctx.find_instance(pcb_id)
            if pcb:
                # PCB 通常跟随 case 的安装方式，若无显式字段则跳过
                pcb_style = getattr(pcb.resolved, "mounting_style", "")
                if pcb_style:
                    styles.append(("pcb", pcb_style))

        if len(styles) >= 2:
            first = styles[0][1]
            for name, style in styles[1:]:
                assert style == first, f"键盘 {assembly.id} 安装方式不一致: " + ", ".join(
                    f"{n}={s}" for n, s in styles
                )


def check_wireless_antenna(ctx):
    """无线键盘使用金属外壳时，应预留天线开口。"""
    for assembly in ctx.query("assembly"):
        if not assembly.resolved.wireless:
            continue
        case_id = getattr(assembly.resolved, "case_id", "")
        if not case_id:
            continue
        case = ctx.find_instance(case_id)
        if case is None:
            continue
        if (
            case.resolved.case_type in ("aluminum", "titanium")
            and not case.resolved.has_antenna_aperture
        ):
            ctx.set_suggestion(
                f"铝壳/钛壳键盘 {assembly.id} 无天线开口，可能导致蓝牙/2.4G 信号衰减。"
                f"建议增加天线窗口或使用塑料/FR4 上盖。"
            )
            assert False, f"无线键盘 {assembly.id} 使用金属外壳 {case.id} 但未预留天线开口"


def check_battery_capacity(ctx):
    """检查电池容量是否满足最低续航要求。"""
    min_runtime_hours = ctx.config.get("min_wireless_runtime_hours", 100)
    budget = make_power_budget(ctx)
    for assembly in ctx.query("assembly"):
        if not assembly.resolved.wireless:
            continue
        batt_id = getattr(assembly.resolved, "battery_id", "")
        if not batt_id:
            continue
        battery = ctx.find_instance(batt_id)
        if battery is None:
            continue
        capacity = battery.resolved.capacity_mah
        switch_count = _total_switch_count(ctx)
        led_count = switch_count if assembly.resolved.led_support else 0
        runtime = budget.estimate_runtime_hours(capacity, switch_count, led_count, wireless=True)
        assert runtime >= min_runtime_hours, (
            f"键盘 {assembly.id} 电池容量 {capacity}mAh 预计续航 {runtime:.0f}h，"
            f"低于项目要求 {min_runtime_hours}h"
        )


def check_current_budget(ctx):
    """检查键盘总电流不超过电池/USB 限额。"""
    budget = make_power_budget(ctx)
    for assembly in ctx.query("assembly"):
        pcb_id = getattr(assembly.resolved, "pcb_id", "")
        if not pcb_id:
            continue
        pcb = ctx.find_instance(pcb_id)
        if pcb is None:
            continue

        switch_count = _total_switch_count(ctx)
        led_count = switch_count if assembly.resolved.led_support else 0
        total_ma = budget.active_current_ma(
            switch_count, led_count, wireless=assembly.resolved.wireless
        )

        if assembly.resolved.wireless:
            batt_id = getattr(assembly.resolved, "battery_id", "")
            if batt_id:
                battery = ctx.find_instance(batt_id)
                if battery:
                    max_batt = battery.resolved.max_discharge_current_ma
                    assert total_ma <= max_batt, (
                        f"键盘 {assembly.id} 估算总电流 {total_ma:.0f}mA 超过电池 "
                        f"{battery.id} 最大放电电流 {max_batt}mA"
                    )

        max_usb = pcb.resolved.max_usb_current_ma
        assert total_ma <= max_usb, (
            f"键盘 {assembly.id} 估算总电流 {total_ma:.0f}mA 超过 USB 供电限额 {max_usb}mA"
        )


def check_usb_cable_match(ctx):
    """检查 USB 线材与 PCB 接口类型匹配。"""
    for cable in ctx.query("cables"):
        mates = _find_mates_by_type(ctx, cable.id, "usb-cable-mate")
        for mate in mates:
            pcb = _get_mated_parent_instance(ctx, mate)
            if pcb is None:
                continue
            cable_connector = cable.resolved.connector_type
            pcb_connector = pcb.resolved.usb_connector_type
            assert cable_connector == pcb_connector, (
                f"线材 {cable.id} 接口 {cable_connector} 与 PCB {pcb.id} "
                f"接口 {pcb_connector} 不匹配"
            )


def check_keycap_environmental_fit(ctx):
    """根据使用环境检查键帽材料适用性。"""
    for assembly in ctx.query("assembly"):
        env = assembly.resolved.operating_environment
        if env != "outdoor":
            continue
        for keycap in ctx.query("keycaps"):
            material = keycap.resolved.material
            if material == "abs":
                ctx.set_suggestion("户外使用建议改用 PBT 或 POM 键帽，ABS 易打油、黄变。")
                assert False, f"键盘 {assembly.id} 户外使用但键帽 {keycap.id} 为 ABS，耐候性不足"


def check_key_cluster_models(ctx):
    """检查 KeyCluster 引用的 switch/keycap 型号存在。"""
    for cluster in ctx.query("key_clusters"):
        sw_model = ctx.find_model(cluster.resolved.switch_model)
        assert sw_model is not None, (
            f"KeyCluster {cluster.id} 引用的轴体型号 {cluster.resolved.switch_model} 不存在"
        )
        kc_model = ctx.find_model(cluster.resolved.keycap_model)
        assert kc_model is not None, (
            f"KeyCluster {cluster.id} 引用的键帽型号 {cluster.resolved.keycap_model} 不存在"
        )


def check_key_cluster_count(ctx):
    """检查 KeyCluster 声明的键数与矩阵位置数量一致。"""
    for cluster in ctx.query("key_clusters"):
        expected = cluster.resolved.key_count
        actual = len(cluster.resolved.matrix_positions)
        assert expected == actual, (
            f"KeyCluster {cluster.id} key_count={expected} 与 matrix_positions 数量 {actual} 不一致"
        )


def check_key_cluster_matrix_bounds(ctx):
    """检查 KeyCluster 的矩阵位置在 PCB 矩阵范围内。"""
    assemblies = ctx.query("assembly").list()
    for cluster in ctx.query("key_clusters"):
        # 找到引用 PCB 的 assembly（支持多装配体场景）
        pcb_id = ""
        for assembly in assemblies:
            candidate = getattr(assembly.resolved, "pcb_id", "")
            if candidate:
                pcb_id = candidate
                break
        if not pcb_id:
            continue
        pcb = ctx.find_instance(pcb_id)
        if pcb is None:
            continue
        max_row = int(pcb.resolved.matrix_rows)
        max_col = int(pcb.resolved.matrix_cols)
        for pos in cluster.resolved.matrix_positions:
            row = int(getattr(pos, "row", -1))
            col = int(getattr(pos, "col", -1))
            assert 0 <= row < max_row, (
                f"KeyCluster {cluster.id} 矩阵位置 row={row} 超出 PCB {pcb_id} 范围 [0, {max_row})"
            )
            assert 0 <= col < max_col, (
                f"KeyCluster {cluster.id} 矩阵位置 col={col} 超出 PCB {pcb_id} 范围 [0, {max_col})"
            )


def check_keyboard_sub_assemblies(ctx):
    """检查 KeyboardAssembly 声明的子装配体存在且为装配体 Family。"""
    assembly_families = {"AssemblyFamily", "KeyboardAssemblyFamily"}
    for assembly in ctx.query("assembly"):
        for sub_id in getattr(assembly.resolved, "sub_assemblies", []):
            sub = ctx.find_instance(sub_id)
            assert sub is not None, f"装配体 {assembly.id} 引用的子装配体 {sub_id} 不存在"
            assert sub.family in assembly_families, (
                f"装配体 {assembly.id} 引用的 {sub_id} 不是装配体 (family={sub.family})"
            )


def _total_switch_count(ctx) -> int:
    """返回项目中所有轴体数量（独立 Instance + KeyCluster）。"""
    individual = len(ctx.query("switches"))
    cluster_total = sum(cluster.resolved.key_count for cluster in ctx.query("key_clusters"))
    return individual + cluster_total


# ---------------------------------------------------------------------------
# 生成器实现
# ---------------------------------------------------------------------------


def generate_keyboard_bom_csv(ctx, config) -> GeneratorResult:
    """生成键盘 BOM CSV。"""
    import csv
    import io
    from pathlib import Path

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "类型", "型号", "材料/工艺", "数量", "备注"])

    # 整机组装
    for assembly in ctx.query("assembly"):
        writer.writerow(
            [
                assembly.id,
                "键盘总成",
                assembly.resolved.name or "",
                assembly.resolved.layout,
                1,
                ",".join(assembly.resolved.connectivity),
            ]
        )

    # 主要组件
    for collection, label in [
        ("cases", "外壳"),
        ("plates", "定位板"),
        ("pcbs", "PCB"),
        ("batteries", "电池"),
        ("cables", "线材"),
    ]:
        for item in ctx.query(collection):
            model_id = getattr(item, "model_id", "") or ""
            writer.writerow(
                [
                    item.id,
                    label,
                    model_id,
                    getattr(item.resolved, "material", "")
                    or getattr(item.resolved, "case_type", ""),
                    1,
                    "",
                ]
            )

    # 轴体/键帽/卫星轴按数量统计
    cluster_switch_count = sum(cluster.resolved.key_count for cluster in ctx.query("key_clusters"))
    cluster_keycap_count = cluster_switch_count
    writer.writerow(
        [
            "SWITCH-ALL",
            "轴体",
            "",
            "",
            len(ctx.query("switches")) + cluster_switch_count,
            "",
        ]
    )
    writer.writerow(
        [
            "KEYCAP-ALL",
            "键帽",
            "",
            "",
            len(ctx.query("keycaps")) + cluster_keycap_count,
            "",
        ]
    )
    writer.writerow(["STAB-ALL", "卫星轴", "", "", len(ctx.query("stabilizers")), ""])
    writer.writerow(["DAMPENER-ALL", "隔音垫", "", "", len(ctx.query("dampeners")), ""])

    for cluster in ctx.query("key_clusters"):
        writer.writerow(
            [
                cluster.id,
                "键簇",
                f"{cluster.resolved.switch_model}/{cluster.resolved.keycap_model}",
                "",
                cluster.resolved.key_count,
                cluster.resolved.description or "",
            ]
        )

    content = output.getvalue()
    out_path = config.get("output")
    if out_path:
        file_path = Path(str(out_path))
        file_path.write_text(content, encoding="utf-8")
        return GeneratorResult.ok(
            "keyboard-bom", "键盘 BOM CSV 导出", content, file_path, "text/csv"
        )
    return GeneratorResult.ok("keyboard-bom", "键盘 BOM CSV 导出", content, content_type="text/csv")


def generate_keyboard_spec(ctx, config) -> GeneratorResult:
    """生成 Markdown 规格说明书。"""
    lines = ["# 键盘规格说明书", ""]

    for assembly in ctx.query("assembly"):
        lines.append(f"## {assembly.id}")
        lines.append(f"- 配列: {assembly.resolved.layout}")
        lines.append(f"- 键数: {assembly.resolved.key_count}")
        lines.append(f"- 连接方式: {', '.join(assembly.resolved.connectivity)}")
        lines.append(f"- 安装结构: {assembly.resolved.mounting_style}")
        lines.append(f"- 无线: {'是' if assembly.resolved.wireless else '否'}")
        lines.append("")

    case = ctx.query("cases").first()
    if case:
        lines.append(f"- 外壳: {case.resolved.case_type}，{case.resolved.mounting_style}")
        lines.append(
            f"- 尺寸: {case.resolved.length_mm} x {case.resolved.width_mm} x {case.resolved.height_mm} mm"
        )

    plate = ctx.query("plates").first()
    if plate:
        lines.append(f"- 定位板: {plate.resolved.material}，{plate.resolved.thickness_mm}mm")

    pcb = ctx.query("pcbs").first()
    if pcb:
        lines.append(
            f"- PCB: {pcb.resolved.controller}，矩阵 {pcb.resolved.matrix_rows}x{pcb.resolved.matrix_cols}"
        )

    switch = ctx.query("switches").first()
    if switch:
        lines.append(
            f"- 轴体: {switch.resolved.manufacturer} {switch.resolved.name}，{switch.resolved.operating_force_gf}gf"
        )

    keycap = ctx.query("keycaps").first()
    if keycap:
        lines.append(f"- 键帽: {keycap.resolved.material} {keycap.resolved.profile}")

    content = "\n".join(lines)
    out_path = config.get("output")
    if out_path:
        file_path = Path(str(out_path))
        file_path.write_text(content, encoding="utf-8")
        return GeneratorResult.ok(
            "keyboard-spec", "键盘规格说明书", content, file_path, "text/markdown"
        )
    return GeneratorResult.ok(
        "keyboard-spec", "键盘规格说明书", content, content_type="text/markdown"
    )
