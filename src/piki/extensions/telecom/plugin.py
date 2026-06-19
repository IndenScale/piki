"""piki-telecom 内置插件：电信/数据中心。"""

from __future__ import annotations

from pathlib import Path

from adl.diagnostics import Severity
from adl.geometry import GeometryAssets, KinematicEnvelope, LoadCapacity, Space, Transform, Vec3
from adl.models import (
    InterfaceSpec,
    Tags,
    resolve_interface_ref,
)
from adl.types import TypeRegistry
from pydantic import BaseModel, Field

from piki.core.engine.checker import Checker
from piki.core.engine.generator_registry import GeneratorResult
from piki.core.plugin import Plugin
from piki.extensions.telecom.types import (
    INTERFACE_CABLE_MAP,
    are_compatible,
    is_valid_interface_type,
)


class RoutePoint(BaseModel):
    """线缆/连接途径点（全局毫米坐标）。"""

    x_mm: float = Field(default=0.0)
    y_mm: float = Field(default=0.0)
    z_mm: float = Field(default=0.0)


class FacilityFamily(BaseModel):
    """机房基础设施：门、ODF、供电柜、走线架、消防箱、抬高地板、斜坡等。"""

    id: str = Field(...)
    name: str = Field(default="")
    facility_type: str = Field(
        ...
    )  # door | odf | power-cabinet | cable-tray | fire-box | raised-floor | floor-grid | ramp | etc.
    room_id: str = Field(default="")
    # 物理尺寸（毫米）——允许实例覆盖，因为门/走线架等设施尺寸多样
    width_mm: float = Field(default=0, ge=0)
    depth_mm: float = Field(default=0, ge=0)
    height_mm: float = Field(default=0, ge=0)
    # 机房平面定位（毫米）
    floor_x_mm: float = Field(default=0.0)
    floor_y_mm: float = Field(default=0.0)
    orientation_deg: float = Field(default=0.0)
    # 3D 空间定位（毫米）
    position_x_mm: float = Field(default=0.0)
    position_y_mm: float = Field(default=0.0)
    position_z_mm: float = Field(default=0.0)
    # 轴网锚定：用于走线架/门等设施与排或通道配合
    row_id: str = Field(default="", description="所锚定的机柜排 ID")
    aisle_label: str = Field(default="", description="所锚定的通道/ aisle 标签")
    # ADR-014: 运动包络（门/盖板等）
    kinematics: KinematicEnvelope | None = Field(default=None)
    # ADR-014: 承重能力（地板/货架/斜坡等）
    load_capacity: LoadCapacity | None = Field(default=None)
    # ADR-014: 抬高地板网格接口（仅 facility_type == raised-floor 时生效）
    panel_width_mm: float = Field(default=0, ge=0, description="地板面板宽度（毫米）")
    panel_depth_mm: float = Field(default=0, ge=0, description="地板面板深度（毫米）")
    grid_origin_x_mm: float = Field(default=0.0, description="网格原点 X（毫米）")
    grid_origin_y_mm: float = Field(default=0.0, description="网格原点 Y（毫米）")
    # 作用域：background 存量不涉及 / context 存量但需接线 / new 本次新增
    scope: str = Field(default="new")
    status: str = Field(default="planned")
    # 标签
    tags: Tags = Field(default_factory=Tags)
    # 几何资产（可选）
    assets: GeometryAssets | None = Field(default=None)


class SpaceFamily(BaseModel):
    """无形空间区域：车辆动线、门开合扫掠区、除尘地垫、维护净空区等。"""

    id: str = Field(...)
    name: str = Field(default="")
    space_type: str = Field(
        ...
    )  # vehicle-path | clearance-zone | sticky-mat | plenum-zone | access-aisle
    room_id: str = Field(default="")
    shape: Space = Field(...)
    # 作用域：background / context / new
    scope: str = Field(default="background")
    status: str = Field(default="planned")
    # 标签
    tags: Tags = Field(default_factory=Tags)


class RackRowFamily(BaseModel):
    """机柜排：机房轴网中的一排机柜基准线。

    一排机柜共享同一 centerline_y_mm，沿 X 方向等距排列。
    """

    id: str = Field(...)
    name: str = Field(default="")
    room_id: str = Field(default="")
    row_index: int = Field(default=0, ge=0, description="排序号，0-based")
    orientation_deg: float = Field(default=90.0, description="排正面朝向：90=朝 +X，270=朝 -X")
    centerline_y_mm: float = Field(default=0.0, description="排中心线在房间 Y 轴坐标")
    start_x_mm: float = Field(default=0.0, description="排内第一个机柜左下角 X 坐标")
    rack_count: int = Field(default=0, ge=0, description="排内机柜数量")
    rack_inline_spacing_mm: float = Field(default=0.0, description="同排机柜间距（毫米）")
    scope: str = Field(default="new")
    status: str = Field(default="planned")
    tags: Tags = Field(default_factory=Tags)


class RoomFamily(BaseModel):
    """机房/房间：定义机房平面边界与机柜排列参数。"""

    id: str = Field(...)
    name: str = Field(default="")
    # 机房平面尺寸（毫米）
    length_mm: float = Field(default=10000, gt=0)  # X 方向长度
    width_mm: float = Field(default=8000, gt=0)  # Y 方向宽度
    height_mm: float = Field(default=3000, gt=0)  # 净高
    # 机柜排列参数
    rack_bay_spacing_mm: float = Field(default=1200, ge=0)  # 列间通道宽度（冷/热通道）
    front_wall_x_mm: float = Field(default=0.0, description="前墙在全局X轴的坐标（毫米）")
    floor_height_mm: float = Field(default=400, ge=0, description="抬高地板高度（毫米）")
    tile_size_mm: float = Field(default=600, ge=0, description="防静电地板砖尺寸（毫米）")
    rack_inline_spacing_mm: float = Field(default=600, ge=0)  # 同列机柜间距
    wall_margin_mm: float = Field(default=1000, ge=0)  # 靠墙最小距离
    # 轴网参数：当机柜使用 row_id/bay_index 时，用于推导 floor_x_mm/floor_y_mm
    rack_row_count: int = Field(default=2, ge=1, description="机柜排数")
    racks_per_row: int = Field(default=4, ge=1, description="每排机柜数量")
    rack_width_mm: float = Field(default=600.0, description="标准机柜宽度（毫米）")
    rack_depth_mm: float = Field(default=1000.0, description="标准机柜深度（毫米）")
    # 标签
    tags: Tags = Field(default_factory=Tags)


class RackFamily(BaseModel):
    id: str = Field(...)
    name: str = Field(default="")
    location: str = Field(default="")
    total_u: int = Field(..., ge=1, le=48)
    power_capacity_w: float = Field(default=0, ge=0)  # 机柜配电容量（W）
    # 物理尺寸（毫米），用于 3D 碰撞检测和物理尺寸匹配
    depth_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    width_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    # 机柜自重、承重与散热能力
    weight_kg: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    max_load_kg: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    cooling_capacity_w: float = Field(
        default=0, ge=0, json_schema_extra={"piki_non_overridable": True}
    )
    # 前后维护空间（毫米），用于工法前提检查
    maintenance_front_mm: float = Field(
        default=800, ge=0, json_schema_extra={"piki_non_overridable": True}
    )
    maintenance_rear_mm: float = Field(
        default=600, ge=0, json_schema_extra={"piki_non_overridable": True}
    )
    # 机房平面定位（毫米）
    room_id: str = Field(default="")
    room_column: str = Field(default="")
    room_row: int = Field(default=0, ge=0)
    # 轴网相对定位：row_id + bay_index 可由 RoomFamily 推导 floor_x/floor_y
    row_id: str = Field(default="", description="所属机柜排 ID")
    bay_index: int = Field(default=-1, ge=-1, description="排内机柜序号，0-based")
    front_face_direction: str = Field(
        default="front",
        description="正面朝向：front=朝通道侧，rear=朝墙/背向通道",
    )
    floor_x_mm: float = Field(default=0.0)  # 机柜左下角 X 坐标
    floor_y_mm: float = Field(default=0.0)  # 机柜左下角 Y 坐标
    orientation_deg: float = Field(default=0.0)  # 机柜正面朝向，0=朝北（+Y）
    # 3D 空间定位（毫米），保留给局部 3D/USD 场景
    position_x_mm: float = Field(default=0.0)
    position_y_mm: float = Field(default=0.0)
    position_z_mm: float = Field(default=0.0)
    # 作用域：background / context / new
    scope: str = Field(default="new")
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
    scope: str = Field(default="new")
    tags: Tags = Field(default_factory=Tags)  # 标签（ADR-001）
    interfaces: list[InterfaceSpec] = Field(
        default_factory=list, description="可连接接口 (ADR-005)"
    )


class ServerFamily(BaseModel):
    id: str = Field(...)
    name: str = Field(default="")
    model: str = Field(default="")
    status: str = Field(default="planned")
    scope: str = Field(default="new")
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
    scope: str = Field(default="new")
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
    # 线缆规格限制（来自型号默认值）
    max_distance_m: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    attenuation_db_per_km: float = Field(
        default=0.0, ge=0, json_schema_extra={"piki_non_overridable": True}
    )
    bend_radius_mm: float = Field(
        default=30.0, ge=0, json_schema_extra={"piki_non_overridable": True}
    )
    status: str = Field(default="planned")
    scope: str = Field(default="new")
    route: list[RoutePoint] = Field(default_factory=list, description="线缆走线路径途径点")
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
    # 端口在设备上的空间位置（毫米，相对于设备正面左下角）
    face: str = Field(default="front", description="端口所在面：front | rear")
    offset_x_mm: float = Field(default=0.0, description="设备宽度方向偏移（左→右）")
    offset_y_mm: float = Field(default=0.0, description="设备高度方向偏移（下→上）")
    offset_z_mm: float = Field(default=0.0, description="设备深度方向偏移（前→后）")
    status: str = Field(default="planned")
    scope: str = Field(default="new")
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
    scope: str = Field(default="new")
    route: list[RoutePoint] = Field(default_factory=list, description="连接走线路径途径点")
    tags: Tags = Field(default_factory=Tags)


class TelecomPlugin(Plugin):
    name = "telecom"
    version = "0.1.0"

    @property
    def model_dir(self) -> Path:
        return Path(__file__).parent / "models"

    def register_types(self, type_registry: TypeRegistry) -> None:
        type_registry.add_family("RoomFamily", RoomFamily)
        type_registry.add_family("FacilityFamily", FacilityFamily)
        type_registry.add_family("SpaceFamily", SpaceFamily)
        type_registry.add_family("RackRowFamily", RackRowFamily)
        type_registry.add_family("RackFamily", RackFamily)
        type_registry.add_family("PduFamily", PduFamily)
        type_registry.add_family("ServerFamily", ServerFamily)
        type_registry.add_family("TransceiverFamily", TransceiverFamily)
        type_registry.add_family("FiberPatchCordFamily", FiberPatchCordFamily)
        type_registry.add_family("PortFamily", PortFamily)
        type_registry.add_family("PortConnectionFamily", PortConnectionFamily)

        # 注册 telecom 领域的 Mate 类型 (ADR-006).
        from adl.models import MateConstraint, MateConstraintOperator, MateTypeMeta

        # L1: 机柜排装配（机柜属于某排某个 bay）
        type_registry.add_mate_type(
            "rack-in-row",
            MateTypeMeta(
                type="rack-in-row",
                description="机柜安装到机柜排指定 bay",
                applicable_parent_families={"RackRowFamily"},
                applicable_child_families={"RackFamily"},
            ),
        )

        # L1: 走线架安装到机柜排上方
        type_registry.add_mate_type(
            "cable-tray-over-row",
            MateTypeMeta(
                type="cable-tray-over-row",
                description="顶部走线架位于机柜排上方",
                applicable_parent_families={"RackRowFamily"},
                applicable_child_families={"FacilityFamily"},
            ),
        )

        # L1: 横向走线架跨越通道
        type_registry.add_mate_type(
            "cable-tray-cross-aisle",
            MateTypeMeta(
                type="cable-tray-cross-aisle",
                description="横向走线架跨越机房通道连接两排",
                applicable_parent_families={"RoomFamily"},
                applicable_child_families={"FacilityFamily"},
            ),
        )

        # L1: 机柜装配
        type_registry.add_mate_type(
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
        type_registry.add_mate_type(
            "grid-mount",
            MateTypeMeta(
                type="grid-mount",
                description="方舱内设备装配",
                applicable_parent_families={"ContainerFamily"},
                applicable_child_families={"EquipmentFamily", "PowerUnitFamily"},
            ),
        )

        # L2: 电源配合
        type_registry.add_mate_type(
            "power-iec-c14-c13",
            MateTypeMeta(
                type="power-iec-c14-c13",
                description="IEC C14-C13 电源配对",
            ),
        )

        # L2: 供电电缆
        type_registry.add_mate_type(
            "power-cable",
            MateTypeMeta(
                type="power-cable",
                description="配电单元到设备供电电缆",
            ),
        )

        # L2: 光模块插入交换机笼子
        type_registry.add_mate_type(
            "sfp28-cage",
            MateTypeMeta(
                type="sfp28-cage",
                description="SFP28/SFP+/SFP 光模块插入交换机/服务器笼子",
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
        type_registry.add_mate_type(
            "qsfp28-cage",
            MateTypeMeta(
                type="qsfp28-cage",
                description="QSFP28/QSFP+ 光模块插入交换机笼子",
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
        type_registry.add_mate_type(
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

        # ADR-014: 空间约束 Mate 类型
        type_registry.add_mate_type(
            "must-clear",
            MateTypeMeta(
                type="must-clear",
                description="child 的运动包络或几何体不得与 parent 相交",
                applicable_parent_families={"FacilityFamily", "RackFamily", "ServerFamily", "SpaceFamily"},
                applicable_child_families={"FacilityFamily", "SpaceFamily"},
            ),
        )
        type_registry.add_mate_type(
            "must-be-inside",
            MateTypeMeta(
                type="must-be-inside",
                description="child 必须位于 parent 的空间或几何范围内",
                applicable_parent_families={"RoomFamily", "SpaceFamily", "FacilityFamily"},
                applicable_child_families={"FacilityFamily", "SpaceFamily", "RackFamily"},
            ),
        )
        type_registry.add_mate_type(
            "minimum-distance",
            MateTypeMeta(
                type="minimum-distance",
                description="child 与 parent 之间保持最小净距",
                applicable_parent_families={"FacilityFamily", "RackFamily", "SpaceFamily"},
                applicable_child_families={"FacilityFamily", "SpaceFamily"},
            ),
        )

        # ADR-014: 地板装配关系
        type_registry.add_mate_type(
            "placed-on",
            MateTypeMeta(
                type="placed-on",
                description="child 放置在 parent 地板/平台顶面，并对齐网格",
                applicable_parent_families={"FacilityFamily"},
                applicable_child_families={"RackFamily", "FacilityFamily"},
            ),
        )
        type_registry.add_mate_type(
            "connects-to",
            MateTypeMeta(
                type="connects-to",
                description="child 与 parent 在几何上相接（如坡道与地板）",
                applicable_parent_families={"FacilityFamily"},
                applicable_child_families={"FacilityFamily"},
            ),
        )

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
            "TELECOM-WEIGHT-001",
            "机柜承重检查",
            check_rack_weight,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-COOL-001",
            "机柜散热能力检查",
            check_rack_cooling,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-CABLE-001",
            "线缆长度规格检查",
            check_cable_length,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-REDUNDANCY-001",
            "核心设备双路 PDU 冗余检查",
            check_dual_psu_redundancy,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-MAINTENANCE-001",
            "设备维护空间检查",
            check_maintenance_clearance,
            priority=3,
            severity=Severity.WARNING,
        )
        checker.add_rule(
            "TELECOM-FLOOR-001",
            "机柜平面布局碰撞检查",
            check_rack_floor_collision,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-FLOOR-002",
            "机柜维护通道宽度检查",
            check_rack_aisle_spacing,
            priority=5,
            severity=Severity.WARNING,
        )
        checker.add_rule(
            "TELECOM-FLOOR-003",
            "机柜编号规范检查",
            check_rack_naming,
            priority=3,
            severity=Severity.WARNING,
        )
        # ADR-014: 机房基础设施与可达性分析规则
        checker.add_rule(
            "TELECOM-ACCESS-001",
            "门开合扫掠区碰撞检查",
            check_door_swing_clearance,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-ACCESS-002",
            "车辆路径可达性检查",
            check_vehicle_path_accessibility,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-LOAD-001",
            "抬高地板均布载荷检查",
            check_floor_loading,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-LOAD-002",
            "机柜局部集中载荷检查",
            check_concentrated_floor_loading,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-RAMP-001",
            "物流坡道与抬高地板高度配合检查",
            check_ramp_floor_fit,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-RAMP-002",
            "物流坡道与抬高地板相接检查",
            check_ramp_connects_to_floor,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "TELECOM-FLOOR-005",
            "机柜/设施必须装配到抬高地板并网格对齐",
            check_placed_on_floor_grid,
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
        checker.add_generator("cable-schedule", "线缆排期表", generate_cable_schedule)
        checker.add_generator("cable-labels", "线缆标签", generate_cable_labels)
        checker.add_generator("port-diagram", "端口互连图", generate_port_diagram)
        checker.add_generator("floor-plan", "机房平面图", generate_floor_plan)
        checker.add_generator("procurement-bom", "采购 BOM", generate_procurement_bom)


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
        # Skip racks that failed schema validation (no total_u)
        rack_total = getattr(rack.resolved, "total_u", 0)
        if rack_total <= 0:
            continue
        ctx.set_current_file(str(rack.source))
        devices = ctx.query("devices", rack_id=rack.id)
        total_height = sum(d.resolved.height_u for d in devices)
        assert total_height <= rack_total, (
            f"机柜 {rack.id} 已用 U 位 {total_height}，超过总容量 {rack_total}"
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

        dev_depth = getattr(device.resolved, "depth_mm", 0)
        dev_width = getattr(device.resolved, "width_mm", 0)
        rack_depth = getattr(rack.resolved, "depth_mm", 0)
        rack_width = getattr(rack.resolved, "width_mm", 0)

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

    使用 ADL GeometryProvider 进行碰撞检测，避免与 adl/geometry 重复实现
    自定义 AABB + find_collisions 逻辑。
    """
    provider = ctx.geometry_provider
    if provider is None:
        ctx.clear_current_file()
        return

    all_collisions = provider.collisions()
    if not all_collisions:
        ctx.clear_current_file()
        return

    racks = {r.id: r for r in ctx.query("racks")}
    rack_device_ids = {
        rack_id: {d.id for d in ctx.query("devices", rack_id=rack_id)}
        for rack_id in racks
    }

    rack_collisions: dict[str, list[tuple[str, str]]] = {}
    for id_a, id_b in all_collisions:
        for rack_id, device_ids in rack_device_ids.items():
            if id_a in device_ids and id_b in device_ids:
                rack_collisions.setdefault(rack_id, []).append((id_a, id_b))
                break

    for rack_id, collisions in rack_collisions.items():
        rack = racks[rack_id]
        ctx.set_current_file(str(rack.source))
        pairs = ", ".join(f"{a} ↔ {b}" for a, b in collisions)
        assert False, f"机柜 {rack_id} 内发现 {len(collisions)} 处设备空间冲突: {pairs}"
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
    """生成 BOM CSV：设备清单汇总（含采购字段）。"""
    import csv
    import io

    devices = ctx.query("devices").list()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "ID",
            "Model",
            "Brand",
            "MPN",
            "Rack",
            "Position_U",
            "PDU",
            "TDP_W",
            "Typical_Power_W",
            "PSU_Count",
            "Height_U",
            "Status",
            "Unit_Price_CNY",
            "Quantity",
        ]
    )
    for d in devices:
        catalog = d._resolved.get("catalog") or {}
        writer.writerow(
            [
                d.id,
                getattr(d, "model_id", "") or "",
                catalog.get("manufacturer", ""),
                catalog.get("mpn", ""),
                d.rack_id,
                d.position_u,
                d.pdu_id,
                d.resolved.tdp_w,
                getattr(d.resolved, "typical_power_w", d.resolved.tdp_w),
                getattr(d.resolved, "psu_count", 1),
                d.resolved.height_u,
                getattr(d.resolved, "status", "planned"),
                catalog.get("unit_price_cny", ""),
                1,
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
                            model_id = getattr(d, "model_id", "") or "N/A"
                            status = getattr(d.resolved, "status", "planned")
                            label = f"{d.id} ({model_id}, {d.resolved.tdp_w}W, {height}U, {status})"
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
    rack_filter = config.get("rack")
    if rack_filter:
        racks = [r for r in racks if r.id == rack_filter]
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

    # Status-based color coding
    STATUS_COLORS = {
        "installed": "#5CB85C",  # green
        "planned": "#4A90D9",  # blue
        "retired": "#999999",  # gray
    }
    # Fallback cycling palette for distinct devices of same status
    ACCENT_COLORS = [
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
        total_u = getattr(rack.resolved, "total_u", 0)
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
            status = getattr(d.resolved, "status", "planned")
            if dev_id not in color_map:
                base = STATUS_COLORS.get(status, "#4A90D9")
                # If multiple devices share status, vary lightness slightly via accent fallback
                if list(STATUS_COLORS.values()).count(base) > 1 or any(
                    STATUS_COLORS.get(getattr(dd.resolved, "status", "planned"), "") == base
                    for dd in devices
                    if dd.id != dev_id
                ):
                    base = ACCENT_COLORS[len(color_map) % len(ACCENT_COLORS)]
                color_map[dev_id] = base
            dev_metadata[dev_id] = {
                "name": getattr(d.resolved, "name", "") or d.id,
                "model": getattr(d, "model_id", "") or d.family or "",
                "family": d.family or "",
                "tdp_w": d.resolved.tdp_w,
                "height_u": height,
                "position_u": start,
                "status": status,
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
        title_text += f"  ({getattr(rack.resolved, 'total_u', '?')}U)"
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
                f"  [{meta.get('status', 'planned')}]"
            )
            legend_idx += 1

        # Status legend
        status_legend_y = legend_y + 16 + legend_idx * 38 + 10
        ET.SubElement(
            svg,
            "text",
            {"x": str(legend_x), "y": str(status_legend_y), "class": "legend-title"},
        ).text = "状态"
        status_idx = 0
        for status, color in STATUS_COLORS.items():
            ly = status_legend_y + 16 + status_idx * 18
            ET.SubElement(
                svg,
                "rect",
                {
                    "x": str(legend_x),
                    "y": str(ly),
                    "width": "10",
                    "height": "10",
                    "fill": color,
                    "rx": "2",
                    "ry": "2",
                },
            )
            ET.SubElement(
                svg,
                "text",
                {"x": str(legend_x + 16), "y": str(ly + 9), "class": "legend-text"},
            ).text = status
            status_idx += 1

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
    """Combine multiple rack SVGs into a single multi-rack SVG document.

    使用字符串拼接避免 ElementTree 命名空间前缀污染。
    """
    import re

    GAP = 40
    total_width = 0
    max_height = 0
    contents: list[tuple[int, int, str]] = []

    svg_tag_re = re.compile(r"<svg[^>]*>", re.IGNORECASE)
    xml_decl_re = re.compile(r"<\?xml[^?]*\?>\s*")

    for _rack_id, svg_str in svg_outputs.items():
        # Strip XML declaration
        svg_str = xml_decl_re.sub("", svg_str)
        # Extract dimensions from opening <svg ...>
        match = svg_tag_re.search(svg_str)
        if not match:
            continue
        svg_open = match.group(0)
        w_match = re.search(r'width=["\'](\d+)["\']', svg_open)
        h_match = re.search(r'height=["\'](\d+)["\']', svg_open)
        w = int(w_match.group(1)) if w_match else 0
        h = int(h_match.group(1)) if h_match else 0
        # Strip opening <svg> and closing </svg>
        inner = svg_tag_re.sub("", svg_str, count=1)
        inner = re.sub(r"</svg\s*>", "", inner, flags=re.IGNORECASE).strip()
        contents.append((w, h, inner))
        max_height = max(max_height, h)
        total_width += w

    total_width += GAP * (len(contents) - 1)

    parts: list[str] = [
        '<?xml version="1.0" ?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width + 20}" height="{max_height + 20}" viewBox="0 0 {total_width + 20} {max_height + 20}">',
        '  <rect x="0" y="0" width="100%" height="100%" fill="#FAFAFA"/>',
    ]

    offset_x = 10
    for w, _h, inner in contents:
        parts.append(f'  <g transform="translate({offset_x}, 10)">')
        for line in inner.splitlines():
            parts.append(f"    {line}")
        parts.append("  </g>")
        offset_x += w + GAP

    parts.append("</svg>")
    return "\n".join(parts)


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


def _format_cable_route(from_rack, to_rack) -> str:
    """根据机柜平面位置生成路由描述。"""
    if not from_rack and not to_rack:
        return "unknown"
    if not from_rack or not to_rack:
        return "cross-rack (incomplete rack info)"
    if from_rack.id == to_rack.id:
        return f"{from_rack.id} 内跳线"

    def _pos(rack):
        col = getattr(rack, "room_column", "") or "?"
        row = getattr(rack, "room_row", "") or "?"
        x = getattr(rack, "floor_x_mm", 0) / 1000.0
        y = getattr(rack, "floor_y_mm", 0) / 1000.0
        return f"{rack.id}(列{col}行{row}, {x:.1f},{y:.1f}m)"

    route = f"{_pos(from_rack)} -> {_pos(to_rack)}"
    if getattr(from_rack, "room_id", "") and getattr(from_rack, "room_id", "") != getattr(
        to_rack, "room_id", ""
    ):
        route += "; 跨机房"
    elif getattr(from_rack, "room_column", "") == getattr(to_rack, "room_column", ""):
        fx = getattr(from_rack, "floor_x_mm", 0)
        tx = getattr(to_rack, "floor_x_mm", 0)
        direction = "水平" if abs(fx - tx) > 1 else "纵向"
        route += f"; 同列内{direction}走线"
    else:
        route += "; 跨列走线"
    return route


def generate_cable_schedule(ctx, config) -> GeneratorResult:
    """生成线缆排期表 CSV：按施工顺序列出所有光纤/铜缆连接。"""
    import csv
    import io

    ports = ctx.query("ports").list()
    connections = ctx.query("port_connections").list()
    port_map = {p.id: p for p in ports}
    racks = {r.id: r for r in ctx.query("racks")}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Cable ID",
            "From Device",
            "From Port",
            "From Rack",
            "To Device",
            "To Port",
            "To Rack",
            "Cable Type",
            "Length (m)",
            "Status",
            "Route",
        ]
    )

    for conn in sorted(connections, key=lambda c: c.id):
        from_port = _resolve_port_ref(conn.resolved.from_port, port_map)
        to_port = _resolve_port_ref(conn.resolved.to_port, port_map)
        from_dev = from_port.device_id if from_port else ""
        from_name = from_port.resolved.port_name if from_port else ""
        to_dev = to_port.device_id if to_port else ""
        to_name = to_port.resolved.port_name if to_port else ""

        from_device = ctx.find_instance(from_dev) if from_port else None
        to_device = ctx.find_instance(to_dev) if to_port else None
        from_rack = getattr(from_device, "rack_id", "") if from_device else ""
        to_rack = getattr(to_device, "rack_id", "") if to_device else ""
        from_rack_obj = racks.get(from_rack) if from_rack else None
        to_rack_obj = racks.get(to_rack) if to_rack else None

        route = _format_cable_route(from_rack_obj, to_rack_obj)

        writer.writerow(
            [
                conn.id,
                from_dev,
                from_name,
                from_rack,
                to_dev,
                to_name,
                to_rack,
                getattr(conn.resolved, "cable_type", ""),
                getattr(conn.resolved, "length_m", 0),
                getattr(conn.resolved, "status", "planned"),
                route,
            ]
        )

    csv_content = output.getvalue()
    _, file_path = _resolve_output_path(config, "cable-schedule.csv")
    return _write_and_return("cable-schedule", "线缆排期表", csv_content, file_path, "text/csv")


def generate_cable_labels(ctx, config) -> GeneratorResult:
    """生成线缆标签 SVG：A4 排版，每页多张标签，含二维码占位。"""
    from xml.dom import minidom
    from xml.etree import ElementTree as ET

    ports = ctx.query("ports").list()
    connections = ctx.query("port_connections").list()
    port_map = {p.id: p for p in ports}

    # Label dimensions (mm)
    LABEL_W = 30
    LABEL_H = 15
    COLS = 6
    ROWS = 18
    PAGE_W = LABEL_W * COLS
    PAGE_H = LABEL_H * ROWS
    FONT_SIZE = 2.2

    ET.register_namespace("", "http://www.w3.org/2000/svg")
    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(PAGE_W),
            "height": str(PAGE_H),
            "viewBox": f"0 0 {PAGE_W} {PAGE_H}",
        },
    )
    style = ET.SubElement(svg, "style")
    style.text = (
        f".label-text {{ font-family: monospace; font-size: {FONT_SIZE}px; fill: #222; }}"
        "\n"
        f".small-text {{ font-family: monospace; font-size: {FONT_SIZE - 0.4}px; fill: #555; }}"
        "\n"
        ".cut-line { stroke: #ccc; stroke-width: 0.2; fill: none; }"
    )

    # White background
    ET.SubElement(
        svg,
        "rect",
        {"x": "0", "y": "0", "width": str(PAGE_W), "height": str(PAGE_H), "fill": "#fff"},
    )

    for idx, conn in enumerate(connections):
        col = idx % COLS
        row = (idx // COLS) % ROWS
        x = col * LABEL_W
        y = row * LABEL_H

        # Label border
        ET.SubElement(
            svg,
            "rect",
            {
                "x": str(x + 0.5),
                "y": str(y + 0.5),
                "width": str(LABEL_W - 1),
                "height": str(LABEL_H - 1),
                "class": "cut-line",
            },
        )

        from_port = _resolve_port_ref(conn.resolved.from_port, port_map)
        to_port = _resolve_port_ref(conn.resolved.to_port, port_map)
        from_ref = (
            f"{from_port.device_id}/{from_port.resolved.port_name}"
            if from_port
            else conn.resolved.from_port
        )
        to_ref = (
            f"{to_port.device_id}/{to_port.resolved.port_name}"
            if to_port
            else conn.resolved.to_port
        )
        cable_type = getattr(conn.resolved, "cable_type", "")
        length = getattr(conn.resolved, "length_m", 0)

        # Cable ID
        ET.SubElement(
            svg,
            "text",
            {"x": str(x + 1), "y": str(y + 3), "class": "label-text"},
        ).text = conn.id
        # From -> To
        ET.SubElement(
            svg,
            "text",
            {"x": str(x + 1), "y": str(y + 6.5), "class": "small-text"},
        ).text = f"{from_ref} ->"
        ET.SubElement(
            svg,
            "text",
            {"x": str(x + 1), "y": str(y + 9.5), "class": "small-text"},
        ).text = f"  {to_ref}"
        # Cable spec
        ET.SubElement(
            svg,
            "text",
            {"x": str(x + 1), "y": str(y + 13), "class": "small-text"},
        ).text = f"{cable_type} {length}m"

    raw = ET.tostring(svg, encoding="unicode")
    dom = minidom.parseString(raw)
    svg_str = dom.toprettyxml(indent="  ")
    _, file_path = _resolve_output_path(config, "cable-labels.svg")
    return _write_and_return("cable-labels", "线缆标签", svg_str, file_path, "image/svg+xml")


def generate_port_diagram(ctx, config) -> GeneratorResult:
    """生成端口互连拓扑图 SVG：设备为节点，连接为边。"""
    from xml.dom import minidom
    from xml.etree import ElementTree as ET

    ports = ctx.query("ports").list()
    connections = ctx.query("port_connections").list()
    port_map = {p.id: p for p in ports}

    # Gather devices involved in connections
    device_ids: set[str] = set()
    edge_specs: list[dict[str, Any]] = []
    for conn in connections:
        from_port = _resolve_port_ref(conn.resolved.from_port, port_map)
        to_port = _resolve_port_ref(conn.resolved.to_port, port_map)
        if from_port is None or to_port is None:
            continue
        device_ids.add(from_port.device_id)
        device_ids.add(to_port.device_id)
        edge_specs.append(
            {
                "from_dev": from_port.device_id,
                "from_port": from_port.resolved.port_name,
                "to_dev": to_port.device_id,
                "to_port": to_port.resolved.port_name,
                "cable_type": getattr(conn.resolved, "cable_type", ""),
                "length_m": getattr(conn.resolved, "length_m", 0),
            }
        )

    if not device_ids:
        return GeneratorResult.ok("port-diagram", "端口互连图", "", content_type="image/svg+xml")

    devices = sorted(device_ids)
    node_positions: dict[str, tuple[float, float]] = {}
    node_w = 120
    node_h = 40
    gap_x = 80
    gap_y = 60
    cols = max(2, int(len(devices) ** 0.5))
    for i, dev_id in enumerate(devices):
        col = i % cols
        row = i // cols
        x = 50 + col * (node_w + gap_x)
        y = 50 + row * (node_h + gap_y)
        node_positions[dev_id] = (x, y)

    max_x = max(x for x, _ in node_positions.values()) + node_w + 50
    max_y = max(y for _, y in node_positions.values()) + node_h + 50

    ET.register_namespace("", "http://www.w3.org/2000/svg")
    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(max_x),
            "height": str(max_y),
            "viewBox": f"0 0 {max_x} {max_y}",
        },
    )
    style = ET.SubElement(svg, "style")
    style.text = (
        ".node { fill: #E3F2FD; stroke: #1976D2; stroke-width: 1.5; }"
        "\n"
        ".node-text { font-family: monospace; font-size: 11px; fill: #222; text-anchor: middle; }"
        "\n"
        ".edge { stroke: #666; stroke-width: 1; fill: none; }"
        "\n"
        ".edge-text { font-family: monospace; font-size: 9px; fill: #444; text-anchor: middle; }"
    )

    # Edges first (behind nodes)
    for edge in edge_specs:
        x1, y1 = node_positions[edge["from_dev"]]
        x2, y2 = node_positions[edge["to_dev"]]
        cx1 = (x1 + node_w / 2 + x2 + node_w / 2) / 2
        cy1 = min(y1, y2) - 20
        ET.SubElement(
            svg,
            "path",
            {
                "d": f"M {x1 + node_w / 2} {y1 + node_h / 2} Q {cx1} {cy1} {x2 + node_w / 2} {y2 + node_h / 2}",
                "class": "edge",
            },
        )
        mid_x = (x1 + node_w / 2 + x2 + node_w / 2) / 2
        mid_y = (y1 + node_h / 2 + y2 + node_h / 2) / 2 - 10
        ET.SubElement(
            svg,
            "text",
            {"x": str(mid_x), "y": str(mid_y), "class": "edge-text"},
        ).text = f"{edge['from_port']}↔{edge['to_port']}"
        ET.SubElement(
            svg,
            "text",
            {"x": str(mid_x), "y": str(mid_y + 12), "class": "edge-text"},
        ).text = f"{edge['cable_type']} {edge['length_m']}m"

    # Nodes
    for dev_id, (x, y) in node_positions.items():
        ET.SubElement(
            svg,
            "rect",
            {
                "x": str(x),
                "y": str(y),
                "width": str(node_w),
                "height": str(node_h),
                "rx": "4",
                "ry": "4",
                "class": "node",
            },
        )
        ET.SubElement(
            svg,
            "text",
            {"x": str(x + node_w / 2), "y": str(y + node_h / 2 + 4), "class": "node-text"},
        ).text = dev_id

    raw = ET.tostring(svg, encoding="unicode")
    dom = minidom.parseString(raw)
    svg_str = dom.toprettyxml(indent="  ")
    _, file_path = _resolve_output_path(config, "port-diagram.svg")
    return _write_and_return("port-diagram", "端口互连图", svg_str, file_path, "image/svg+xml")


def check_rack_weight(ctx):
    """检查机柜内设备总重量不超过机柜承重限制。"""
    for rack in ctx.query("racks"):
        ctx.set_current_file(str(rack.source))
        max_load = getattr(rack.resolved, "max_load_kg", 0)
        if max_load <= 0:
            continue
        devices = ctx.query("devices", rack_id=rack.id).list()
        total_weight = sum(getattr(d.resolved, "weight_kg", 0) for d in devices)
        assert total_weight <= max_load, (
            f"机柜 {rack.id} 总重量 {total_weight}kg 超过承重限制 {max_load}kg "
            f"(设备: {', '.join(d.id for d in devices)})"
        )
    ctx.clear_current_file()


def check_rack_cooling(ctx):
    """检查机柜内设备总 TDP 不超过机柜散热能力。"""
    for rack in ctx.query("racks"):
        ctx.set_current_file(str(rack.source))
        cooling = getattr(rack.resolved, "cooling_capacity_w", 0)
        if cooling <= 0:
            continue
        devices = ctx.query("devices", rack_id=rack.id).list()
        total_tdp = sum(getattr(d.resolved, "tdp_w", 0) for d in devices)
        assert total_tdp <= cooling, (
            f"机柜 {rack.id} 总 TDP {total_tdp}W 超过散热能力 {cooling}W "
            f"(设备: {', '.join(d.id for d in devices)})"
        )
    ctx.clear_current_file()


def check_cable_length(ctx):
    """检查光纤跳线长度不超过型号允许的最大距离。"""
    for fiber in ctx.query("fibers"):
        ctx.set_current_file(str(fiber.source))
        length = getattr(fiber.resolved, "length_m", 0)
        max_dist = getattr(fiber.resolved, "max_distance_m", 0)
        if max_dist <= 0:
            continue
        assert length <= max_dist, (
            f"光纤 {fiber.id} 长度 {length}m 超过型号最大传输距离 {max_dist}m"
        )
    ctx.clear_current_file()


def check_dual_psu_redundancy(ctx):
    """检查核心/汇聚设备是否具备双路 PDU 冗余供电。"""
    critical_tags = (
        ctx.config.get("rules", {})
        .get("TELECOM-REDUNDANCY-001", {})
        .get("critical_tags", ["role:core", "role:aggregation"])
    )
    for device in ctx.query("devices"):
        tags = getattr(device.resolved, "tags", None)
        if tags is None:
            continue
        if hasattr(tags, "as_flat_dict"):
            tag_dict = tags.as_flat_dict()
        elif hasattr(tags, "__dict__"):
            tag_dict = dict(tags.__dict__)
        else:
            tag_dict = dict(tags) if hasattr(tags, "__iter__") else {}

        is_critical = any(
            tag_dict.get(k) == v for tag in critical_tags for k, v in [tag.split(":", 1)]
        )
        if not is_critical:
            continue

        ctx.set_current_file(str(device.source))
        # 通过 mate 图查找供电 PDU
        parents = ctx.mated_parents(device.id)
        pdu_ids = set()
        for mate in parents:
            parent_id, _ = mate.parent.split("/", 1) if "/" in mate.parent else (mate.parent, "")
            parent_inst = ctx.find_instance(parent_id)
            if parent_inst and parent_inst.family == "PduFamily":
                pdu_ids.add(parent_id)

        assert len(pdu_ids) >= 2, (
            f"核心设备 {device.id} 必须双路 PDU 供电，当前仅发现 {len(pdu_ids)} 路 "
            f"({', '.join(sorted(pdu_ids)) if pdu_ids else '无'})"
        )
    ctx.clear_current_file()


def check_maintenance_clearance(ctx):
    """检查机柜维护空间配置是否合理。

    当前数据模型未建模机房平面布局，因此仅校验机柜级维护空间字段
    已被正确声明且为正值。后续可扩展为设备前后净距检查。
    """
    for rack in ctx.query("racks"):
        ctx.set_current_file(str(rack.source))
        front_req = getattr(rack.resolved, "maintenance_front_mm", 800)
        rear_req = getattr(rack.resolved, "maintenance_rear_mm", 600)
        assert front_req > 0 and rear_req > 0, (
            f"机柜 {rack.id} 维护空间配置异常：前={front_req}mm，后={rear_req}mm"
        )
    ctx.clear_current_file()


def _rack_floor_rect(rack) -> tuple[float, float, float, float]:
    """返回机柜在机房平面上的轴对齐包围盒 (x1, y1, x2, y2)。"""
    x = getattr(rack.resolved, "floor_x_mm", 0.0)
    y = getattr(rack.resolved, "floor_y_mm", 0.0)
    width = getattr(rack.resolved, "width_mm", 0.0)
    depth = getattr(rack.resolved, "depth_mm", 0.0)
    return (x, y, x + width, y + depth)


def check_rack_floor_collision(ctx):
    """检查同一机房内机柜平面布局不重叠。"""
    racks = ctx.query("racks").list()
    for i, r1 in enumerate(racks):
        room1 = getattr(r1.resolved, "room_id", "")
        if not room1:
            continue
        x1, y1, x2, y2 = _rack_floor_rect(r1)
        for r2 in racks[i + 1 :]:
            room2 = getattr(r2.resolved, "room_id", "")
            if room2 != room1:
                continue
            ctx.set_current_file(str(r1.source))
            a1, b1, a2, b2 = _rack_floor_rect(r2)
            overlap = not (x2 <= a1 or a2 <= x1 or y2 <= b1 or b2 <= y1)
            assert not overlap, f"机柜 {r1.id} 与 {r2.id} 在机房 {room1} 平面布局重叠"
    ctx.clear_current_file()


def check_rack_aisle_spacing(ctx):
    """检查同一排机柜间距及排间通道宽度满足 RoomFamily 要求。

    优先使用 row_id/bay_index 轴网语义；若不存在则回退到 room_column/room_row。
    """
    rooms = {r.id: r for r in ctx.query("rooms")}
    racks = ctx.query("racks").list()

    # 按机房、row_id 分组
    rows: dict[str, dict[str, list[Any]]] = {}
    fallback_bays: dict[str, dict[str, list[Any]]] = {}
    for rack in racks:
        room_id = getattr(rack.resolved, "room_id", "")
        if not room_id:
            continue
        row_id = getattr(rack.resolved, "row_id", "")
        if row_id:
            rows.setdefault(room_id, {}).setdefault(row_id, []).append(rack)
            continue
        # 回退：按 room_column 分组（旧数据兼容）
        col = getattr(rack.resolved, "room_column", "")
        if col:
            fallback_bays.setdefault(room_id, {}).setdefault(col, []).append(rack)

    def _check_rows(room_id: str, row_groups: dict[str, list[Any]]) -> None:
        room = rooms.get(room_id)
        if room is None:
            return
        bay_spacing = getattr(room.resolved, "rack_bay_spacing_mm", 1200)
        inline_spacing = getattr(room.resolved, "rack_inline_spacing_mm", 600)

        row_centers: dict[str, float] = {}
        for row_id, rack_list in row_groups.items():
            sorted_racks = sorted(rack_list, key=lambda r: getattr(r.resolved, "bay_index", 0))
            # 同排机柜沿 X 间距（当前 demo 排均沿 X 方向）
            for i in range(len(sorted_racks) - 1):
                r1, r2 = sorted_racks[i], sorted_racks[i + 1]
                ctx.set_current_file(str(r2.source))
                x1_min, _, x1_max, _ = _rack_floor_rect(r1)
                x2_min, _, x2_max, _ = _rack_floor_rect(r2)
                gap = x2_min - x1_max
                assert gap >= inline_spacing, (
                    f"机柜 {r1.id} 与 {r2.id} 同排间距 {gap}mm 小于要求 {inline_spacing}mm"
                )
            # 记录排中心 Y 用于排间间距检查
            ys = [(_rack_floor_rect(r)[1] + _rack_floor_rect(r)[3]) / 2 for r in rack_list]
            row_centers[row_id] = sum(ys) / len(ys)

        # 排间通道宽度（取排中心线间距减去平均深度的一半，近似）
        sorted_rows = sorted(row_groups.keys())
        for i in range(len(sorted_rows) - 1):
            row_a, row_b = sorted_rows[i], sorted_rows[i + 1]
            racks_a = row_groups[row_a]
            racks_b = row_groups[row_b]
            min_gap = float("inf")
            for ra in racks_a:
                _, ya_min, _, ya_max = _rack_floor_rect(ra)
                for rb in racks_b:
                    _, yb_min, _, yb_max = _rack_floor_rect(rb)
                    gap = yb_min - ya_max
                    if gap < min_gap:
                        min_gap = gap
            if min_gap < float("inf"):
                ctx.set_current_file(str(racks_b[0].source))
                assert min_gap >= bay_spacing, (
                    f"机房 {room_id} 排 {row_a} 与 {row_b} 之间通道宽度 {min_gap}mm "
                    f"小于要求 {bay_spacing}mm"
                )

    for room_id, row_groups in rows.items():
        _check_rows(room_id, row_groups)

    # 旧数据兼容路径
    for room_id, cols in fallback_bays.items():
        _check_rows(room_id, cols)

    ctx.clear_current_file()


def check_rack_naming(ctx):
    """检查机柜 ID 与 column/row 声明一致（如 RACK-A01 应对应 column=A, row=1）。"""
    import re

    for rack in ctx.query("racks"):
        col = getattr(rack.resolved, "room_column", "")
        row = getattr(rack.resolved, "room_row", 0)
        if not col or row <= 0:
            continue
        ctx.set_current_file(str(rack.source))
        pattern = rf"{re.escape(col)}\s*0*{row}\b"
        assert re.search(pattern, rack.id, re.IGNORECASE), (
            f"机柜 ID '{rack.id}' 与平面坐标声明不一致：column={col}, row={row}"
        )
    ctx.clear_current_file()


def generate_floor_plan(ctx, config) -> GeneratorResult:
    """生成机房平面图 SVG：机房轮廓、机柜位置、编号、状态。"""
    from xml.dom import minidom
    from xml.etree import ElementTree as ET

    rooms = ctx.query("rooms").list()
    racks = ctx.query("racks").list()

    if not rooms:
        return GeneratorResult.ok("floor-plan", "机房平面图", "", content_type="image/svg+xml")

    room = rooms[0]
    room_length = getattr(room.resolved, "length_mm", 10000)
    room_width = getattr(room.resolved, "width_mm", 8000)

    # SVG 画布：1mm = 0.1px，留边距
    SCALE = 0.1
    MARGIN = 50
    canvas_w = int(room_length * SCALE) + 2 * MARGIN
    canvas_h = int(room_width * SCALE) + 2 * MARGIN

    ET.register_namespace("", "http://www.w3.org/2000/svg")
    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(canvas_w),
            "height": str(canvas_h),
            "viewBox": f"0 0 {canvas_w} {canvas_h}",
        },
    )
    style = ET.SubElement(svg, "style")
    style.text = (
        ".room-outline { fill: #f5f5f5; stroke: #333; stroke-width: 2; }"
        "\n"
        ".rack { stroke: #555; stroke-width: 1; }"
        "\n"
        ".rack-label { font-family: monospace; font-size: 14px; fill: #222; text-anchor: middle; }"
        "\n"
        ".rack-info { font-family: monospace; font-size: 10px; fill: #666; text-anchor: middle; }"
        "\n"
        ".north { font-family: monospace; font-size: 12px; fill: #999; text-anchor: middle; }"
    )

    # Room outline
    ET.SubElement(
        svg,
        "rect",
        {
            "x": str(MARGIN),
            "y": str(MARGIN),
            "width": str(room_length * SCALE),
            "height": str(room_width * SCALE),
            "class": "room-outline",
        },
    )

    # North indicator
    ET.SubElement(
        svg,
        "text",
        {"x": str(canvas_w / 2), "y": str(MARGIN - 15), "class": "north"},
    ).text = "N 北"

    STATUS_COLORS = {
        "installed": "#5CB85C",
        "planned": "#4A90D9",
        "retired": "#999999",
    }

    for rack in racks:
        room_id = getattr(rack.resolved, "room_id", "")
        if room_id != room.id:
            continue
        x = getattr(rack.resolved, "floor_x_mm", 0.0)
        y = getattr(rack.resolved, "floor_y_mm", 0.0)
        width = getattr(rack.resolved, "width_mm", 600)
        depth = getattr(rack.resolved, "depth_mm", 1000)
        status = getattr(rack.resolved, "status", "planned")
        col = getattr(rack.resolved, "room_column", "")
        row = getattr(rack.resolved, "room_row", 0)

        sx = MARGIN + x * SCALE
        sy = MARGIN + y * SCALE
        sw = width * SCALE
        sd = depth * SCALE
        color = STATUS_COLORS.get(status, "#4A90D9")

        ET.SubElement(
            svg,
            "rect",
            {
                "x": str(sx),
                "y": str(sy),
                "width": str(sw),
                "height": str(sd),
                "fill": color,
                "class": "rack",
            },
        )
        ET.SubElement(
            svg,
            "text",
            {"x": str(sx + sw / 2), "y": str(sy + sd / 2 + 5), "class": "rack-label"},
        ).text = rack.id
        ET.SubElement(
            svg,
            "text",
            {"x": str(sx + sw / 2), "y": str(sy + sd / 2 + 20), "class": "rack-info"},
        ).text = f"{col}-{row} {status}"

    raw = ET.tostring(svg, encoding="unicode")
    dom = minidom.parseString(raw)
    svg_str = dom.toprettyxml(indent="  ")
    _, file_path = _resolve_output_path(config, "floor-plan.svg")
    return _write_and_return("floor-plan", "机房平面图", svg_str, file_path, "image/svg+xml")


# ---------------------------------------------------------------------------
# ADR-014: 机房基础设施与可达性分析 DRC 规则
# ---------------------------------------------------------------------------


def _inst_global_transform(ctx, inst: Any) -> Transform:
    """返回实例在项目全局坐标系下的 Transform，优先使用 Layout 级联结果。"""
    transform = ctx.resolved_transform(inst.id)
    if transform is not None:
        return transform
    resolved = inst.resolved
    x = getattr(resolved, "floor_x_mm", None) or getattr(resolved, "position_x_mm", 0.0)
    y = getattr(resolved, "floor_y_mm", None) or getattr(resolved, "position_y_mm", 0.0)
    z = getattr(resolved, "position_z_mm", 0.0)
    return Transform(translation=Vec3(x=float(x), y=float(y), z=float(z)))


def _inst_size_mm(inst: Any) -> tuple[float, float, float] | None:
    """从 instance 解析尺寸 (width, height, depth)，单位毫米。"""
    resolved = inst.resolved
    width = getattr(resolved, "width_mm", 0.0) or 0.0
    depth = getattr(resolved, "depth_mm", 0.0) or 0.0
    length = getattr(resolved, "length_mm", 0.0) or 0.0
    height = getattr(resolved, "height_mm", 0.0) or 0.0
    # 机柜高度从 U 位推导
    if height <= 0 and getattr(resolved, "total_u", None):
        height = float(resolved.total_u) * 44.45
    depth = depth if depth > 0 else length
    if width <= 0 or height <= 0 or depth <= 0:
        return None
    return float(width), float(height), float(depth)


def _build_aabb_mm(transform: Transform, width: float, height: float, depth: float) -> Any:
    """用毫米为单位从 transform 和尺寸构建 AABB。

    约定：width 沿局部 y，depth 沿局部 x，height 沿局部 z，
    因此 AABB 尺寸为 (x=depth, y=width, z=height)。
    """
    from piki.ext.geometry import AABB

    size = Vec3(x=depth, y=width, z=height)
    return AABB.from_box(size, transform)


def check_door_swing_clearance(ctx):
    """TELECOM-ACCESS-001: 门开合扫掠体不与周围实例碰撞。

    第一阶段采用 AABB 近似：以门为中心，门宽/门深较大值的 2 倍作为扫掠包络。
    """
    doors = [
        f
        for f in ctx.query("facilities")
        if getattr(f.resolved, "facility_type", "") == "door"
        and getattr(f.resolved, "kinematics", None) is not None
    ]
    obstacles = list(ctx.query("racks")) + [
        f
        for f in ctx.query("facilities")
        if getattr(f.resolved, "facility_type", "")
        not in ("door", "ramp", "raised-floor", "floor-grid", "door-landing")
    ]

    for door in doors:
        door_transform = _inst_global_transform(ctx, door)
        door_size = _inst_size_mm(door)
        if door_size is None:
            continue
        width, height, depth = door_size
        # 扫掠包络近似：以门中心为原点，覆盖门扇最大扫掠范围
        sweep_span = max(width, depth) * 2
        sweep_aabb = _build_aabb_mm(door_transform, sweep_span, height, sweep_span)

        for obs in obstacles:
            obs_transform = _inst_global_transform(ctx, obs)
            obs_size = _inst_size_mm(obs)
            if obs_size is None:
                continue
            obs_aabb = _build_aabb_mm(obs_transform, *obs_size)
            if sweep_aabb.intersects(obs_aabb):
                ctx.set_current_file(str(door.source))
                assert False, f"门 {door.id} 开合扫掠区与 {obs.id} 碰撞"
    ctx.clear_current_file()


def check_vehicle_path_accessibility(ctx):
    """TELECOM-ACCESS-002: 车辆路径宽度足够，转弯包络不与机柜/设施碰撞。

    第一阶段把 corridor 每段中心线扩展为包络 AABB，检查与障碍物是否相交。
    """
    from piki.ext.geometry import AABB

    paths = [
        s
        for s in ctx.query("spaces")
        if getattr(s.resolved, "space_type", "") == "vehicle-path"
    ]
    obstacles = list(ctx.query("racks")) + [
        f
        for f in ctx.query("facilities")
        if getattr(f.resolved, "facility_type", "")
        not in ("ramp", "raised-floor", "floor-grid", "door", "door-landing")
    ]

    for path in paths:
        shape = getattr(path.resolved, "shape", None)
        if shape is None or shape.type != "corridor":
            continue
        centerline = shape.centerline
        width = shape.corridor_width_mm
        height = shape.corridor_height_mm
        if not centerline or width is None or height is None:
            continue

        # 构建障碍物 AABB 列表（只建一次）
        obstacle_items: list[tuple[str, Any]] = []
        for obs in obstacles:
            obs_transform = _inst_global_transform(ctx, obs)
            obs_size = _inst_size_mm(obs)
            if obs_size is None:
                continue
            obstacle_items.append((obs.id, _build_aabb_mm(obs_transform, *obs_size)))

        half_w = width / 2.0
        half_h = height / 2.0
        for i in range(len(centerline) - 1):
            p1 = centerline[i]
            p2 = centerline[i + 1]
            seg_aabb = AABB(
                min=Vec3(
                    x=min(p1.x, p2.x) - half_w,
                    y=min(p1.y, p2.y) - half_w,
                    z=min(p1.z, p2.z) - half_h,
                ),
                max=Vec3(
                    x=max(p1.x, p2.x) + half_w,
                    y=max(p1.y, p2.y) + half_w,
                    z=max(p1.z, p2.z) + half_h,
                ),
            )

            for obs_id, obs_aabb in obstacle_items:
                if seg_aabb.intersects(obs_aabb):
                    ctx.set_current_file(str(path.source))
                    assert False, f"车辆路径 {path.id} 第 {i} 段与 {obs_id} 碰撞或空间不足"
    ctx.clear_current_file()


def check_floor_loading(ctx):
    """TELECOM-LOAD-001: 抬高地板均布承重 sufficient。"""
    floors = [
        f
        for f in ctx.query("facilities")
        if getattr(f.resolved, "facility_type", "") == "raised-floor"
    ]
    racks = list(ctx.query("racks"))

    for floor in floors:
        lc = getattr(floor.resolved, "load_capacity", None)
        if lc is None:
            continue
        floor_size = _inst_size_mm(floor)
        if floor_size is None:
            continue
        floor_width, _, floor_depth = floor_size
        floor_area_m2 = (floor_width / 1000.0) * (floor_depth / 1000.0)
        uniform_limit = (lc.uniform_load_kg_m2 or 0.0) * (lc.dynamic_factor or 1.0)
        if uniform_limit <= 0:
            continue

        total_weight = 0.0
        for rack in racks:
            rack_weight = getattr(rack.resolved, "weight_kg", 0.0) or 0.0
            devices = ctx.query("devices", rack_id=rack.id)
            device_weight = sum(
                getattr(d.resolved, "weight_kg", 0.0) or 0.0 for d in devices
            )
            total_weight += rack_weight + device_weight

        load_m2 = total_weight / floor_area_m2 if floor_area_m2 > 0 else 0.0
        if load_m2 > uniform_limit:
            ctx.set_current_file(str(floor.source))
            assert False, (
                f"抬高地板 {floor.id} 均布载荷 {load_m2:.1f}kg/m² "
                f"超过限制 {uniform_limit:.1f}kg/m²"
            )
    ctx.clear_current_file()


def check_concentrated_floor_loading(ctx):
    """TELECOM-LOAD-002: 单台机柜局部集中载荷检查。"""
    floors = [
        f
        for f in ctx.query("facilities")
        if getattr(f.resolved, "facility_type", "") == "raised-floor"
    ]
    racks = list(ctx.query("racks"))

    for floor in floors:
        lc = getattr(floor.resolved, "load_capacity", None)
        if lc is None:
            continue
        max_conc = lc.max_concentrated_load_kg * lc.dynamic_factor
        if max_conc <= 0:
            continue
        for rack in racks:
            rack_weight = getattr(rack.resolved, "weight_kg", 0.0) or 0.0
            devices = ctx.query("devices", rack_id=rack.id)
            total = rack_weight + sum(
                getattr(d.resolved, "weight_kg", 0.0) or 0.0 for d in devices
            )
            if total > max_conc:
                ctx.set_current_file(str(rack.source))
                assert False, (
                    f"机柜 {rack.id} 总重 {total:.1f}kg "
                    f"超过地板局部集中载荷限制 {max_conc:.1f}kg"
                )
    ctx.clear_current_file()


def check_ramp_floor_fit(ctx):
    """TELECOM-FLOOR-001: 物流坡道与抬高地板高度配合，坡度合规。"""
    ramps = [
        f
        for f in ctx.query("facilities")
        if getattr(f.resolved, "facility_type", "") == "ramp"
    ]
    floors = [
        f
        for f in ctx.query("facilities")
        if getattr(f.resolved, "facility_type", "") == "raised-floor"
    ]

    for ramp in ramps:
        ramp_height = getattr(ramp.resolved, "height_mm", 0.0) or 0.0
        ramp_depth = getattr(ramp.resolved, "depth_mm", 0.0) or 0.0
        if ramp_depth <= 0:
            continue
        slope = ramp_height / ramp_depth
        if slope > 0.15:
            ctx.set_current_file(str(ramp.source))
            assert False, f"物流坡道 {ramp.id} 坡度 {slope:.1%} 超过 15% 限制"

        for floor in floors:
            floor_height = getattr(floor.resolved, "height_mm", 0.0) or 0.0
            if abs(ramp_height - floor_height) > 10.0:
                ctx.set_current_file(str(ramp.source))
                assert False, (
                    f"坡道 {ramp.id} 顶端高度 {ramp_height:.0f}mm "
                    f"与抬高地板 {floor.id} 高度 {floor_height:.0f}mm 不匹配"
                )
    ctx.clear_current_file()


def _aabb_mm(ctx, inst):
    """返回 instance 在全局坐标系下的 AABB（毫米）。"""
    size = _inst_size_mm(inst)
    if size is None:
        return None
    transform = _inst_global_transform(ctx, inst)
    return _build_aabb_mm(transform, *size)


def _rack_footprint_aabb(ctx, rack):
    """返回机柜在机房平面上的真实 footprint AABB（考虑朝向，毫米）。"""
    import math

    from piki.ext.geometry import AABB

    transform = _inst_global_transform(ctx, rack)
    resolved = rack.resolved
    width = float(getattr(resolved, "width_mm", 0) or 0)
    depth = float(getattr(resolved, "depth_mm", 0) or 0)
    orientation = float(getattr(resolved, "orientation_deg", 0) or 0)
    rad = math.radians(orientation)
    cos_a = abs(math.cos(rad))
    sin_a = abs(math.sin(rad))
    # 旋转后的全局半长（忽略 z）
    half_x = depth / 2.0 * cos_a + width / 2.0 * sin_a
    half_y = depth / 2.0 * sin_a + width / 2.0 * cos_a
    return AABB(
        min=Vec3(
            x=transform.translation.x - half_x,
            y=transform.translation.y - half_y,
            z=transform.translation.z,
        ),
        max=Vec3(
            x=transform.translation.x + half_x,
            y=transform.translation.y + half_y,
            z=transform.translation.z,
        ),
    )


def _floor_top_z(floor_aabb):
    """地板顶面高度（毫米）。"""
    return floor_aabb.max.z


def check_placed_on_floor_grid(ctx):
    """TELECOM-FLOOR-005: 机柜/设施必须 placed-on 抬高地板，且底面与地板顶面平齐、 footprint 在地板范围内并对齐面板网格。"""
    floors = {
        f.id: f
        for f in ctx.query("facilities")
        if getattr(f.resolved, "facility_type", "") == "raised-floor"
    }
    if not floors:
        return

    TOL = 1.0  # 毫米

    floor_aabbs = {}
    floor_grids = {}
    for fid, floor in floors.items():
        aabb = _aabb_mm(ctx, floor)
        if aabb is None:
            continue
        floor_aabbs[fid] = aabb
        resolved = floor.resolved
        floor_grids[fid] = (
            float(resolved.panel_width_mm or 0) or 600.0,
            float(resolved.panel_depth_mm or 0) or 600.0,
            float(resolved.grid_origin_x_mm or 0),
            float(resolved.grid_origin_y_mm or 0),
        )

    placed_children = set()
    for floor_id, floor in floors.items():
        floor_aabb = floor_aabbs.get(floor_id)
        if floor_aabb is None:
            continue
        panel_w, panel_d, origin_x, origin_y = floor_grids[floor_id]
        top_z = _floor_top_z(floor_aabb)

        for mate in ctx.mated_children(floor_id):
            if mate.type != "placed-on":
                continue
            child = ctx.mate_child_instance(mate)
            if child is None:
                continue
            placed_children.add(child.id)
            if child.family == "RackFamily":
                child_aabb = _rack_footprint_aabb(ctx, child)
                child_size = _inst_size_mm(child)
                child_height = child_size[1] if child_size else 0.0
                child_bottom_z = child_aabb.min.z - child_height / 2.0
            else:
                child_aabb = _aabb_mm(ctx, child)
                child_bottom_z = child_aabb.min.z
            if child_aabb is None:
                continue

            # 底面与地板顶面平齐
            if abs(child_bottom_z - top_z) > TOL:
                ctx.set_current_file(str(child.source))
                assert False, (
                    f"{child.id} 底面高度 {child_aabb.min.z:.0f}mm "
                    f"与抬高地板 {floor_id} 顶面 {top_z:.0f}mm 未对齐"
                )

            # footprint 在地板范围内
            if (
                child_aabb.min.x < floor_aabb.min.x - TOL
                or child_aabb.max.x > floor_aabb.max.x + TOL
                or child_aabb.min.y < floor_aabb.min.y - TOL
                or child_aabb.max.y > floor_aabb.max.y + TOL
            ):
                ctx.set_current_file(str(child.source))
                assert False, f"{child.id}  footprint 超出抬高地板 {floor_id} 范围"

            # 机柜必须与面板网格对齐；其他设施只要落在地板范围内即可
            if child.family == "RackFamily":
                dx = (child_aabb.min.x - origin_x) % panel_w
                dy = (child_aabb.min.y - origin_y) % panel_d
                if min(dx, panel_w - dx) > TOL and dx > TOL:
                    ctx.set_current_file(str(child.source))
                    assert False, (
                        f"{child.id} X 向未对齐地板网格 "
                        f"(panel={panel_w}mm, origin={origin_x}mm)"
                    )
                if min(dy, panel_d - dy) > TOL and dy > TOL:
                    ctx.set_current_file(str(child.source))
                    assert False, (
                        f"{child.id} Y 向未对齐地板网格 "
                        f"(panel={panel_d}mm, origin={origin_y}mm)"
                    )

    # 机房内每个机柜都必须 placed-on 地板
    for rack in ctx.query("racks"):
        if rack.id not in placed_children:
            ctx.set_current_file(str(rack.source))
            assert False, f"机柜 {rack.id} 未通过 placed-on 装配到抬高地板"

    ctx.clear_current_file()


def check_ramp_connects_to_floor(ctx):
    """TELECOM-RAMP-002: 坡道必须通过 connects-to 与抬高地板相接，且顶端与地板前缘在几何上连续。"""
    floors = {
        f.id: f
        for f in ctx.query("facilities")
        if getattr(f.resolved, "facility_type", "") == "raised-floor"
    }
    ramps = [
        f
        for f in ctx.query("facilities")
        if getattr(f.resolved, "facility_type", "") == "ramp"
    ]
    if not floors or not ramps:
        return

    TOL = 5.0
    connected_ramps = set()

    for floor_id, floor in floors.items():
        floor_aabb = _aabb_mm(ctx, floor)
        if floor_aabb is None:
            continue
        top_z = _floor_top_z(floor_aabb)

        for mate in ctx.mated_children(floor_id):
            if mate.type != "connects-to":
                continue
            child = ctx.mate_child_instance(mate)
            if child is None or getattr(child.resolved, "facility_type", "") != "ramp":
                continue
            connected_ramps.add(child.id)
            ramp_aabb = _aabb_mm(ctx, child)
            if ramp_aabb is None:
                continue

            # 顶端高度一致
            if abs(ramp_aabb.max.z - top_z) > TOL:
                ctx.set_current_file(str(child.source))
                assert False, (
                    f"坡道 {child.id} 顶端高度 {ramp_aabb.max.z:.0f}mm "
                    f"与地板 {floor_id} 顶面 {top_z:.0f}mm 不连续"
                )

            # 坡道与地板在 X/Y 至少有一个方向相接且另一方向有重叠
            touches_x = abs(ramp_aabb.max.x - floor_aabb.min.x) <= TOL or abs(
                ramp_aabb.min.x - floor_aabb.max.x
            ) <= TOL
            touches_y = abs(ramp_aabb.max.y - floor_aabb.min.y) <= TOL or abs(
                ramp_aabb.min.y - floor_aabb.max.y
            ) <= TOL
            overlaps_y = ramp_aabb.min.y <= floor_aabb.max.y and ramp_aabb.max.y >= floor_aabb.min.y
            overlaps_x = ramp_aabb.min.x <= floor_aabb.max.x and ramp_aabb.max.x >= floor_aabb.min.x

            if not ((touches_x and overlaps_y) or (touches_y and overlaps_x)):
                ctx.set_current_file(str(child.source))
                assert False, (
                    f"坡道 {child.id} 与地板 {floor_id} 在平面未相接"
                )

    for ramp in ramps:
        if ramp.id not in connected_ramps:
            ctx.set_current_file(str(ramp.source))
            assert False, f"坡道 {ramp.id} 未通过 connects-to 装配到抬高地板"

    ctx.clear_current_file()
