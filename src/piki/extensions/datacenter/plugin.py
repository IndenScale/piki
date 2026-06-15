"""piki-datacenter 内置插件：模块化数据中心 / 方舱式部署。

面向场景：
- 集装箱式模块化机房（智算液冷方舱、通算/存储风冷方舱）
- 锂电储能方舱、配电方舱
- 方舱间管线连接（液冷管路、电缆、光纤）
- 方舱级 PUE / 负载率 / 冗余检查

与 telecom 插件的区别：
- telecom：机柜(Rack) + PDU + 服务器(Server) — 传统机房微观视角
- datacenter：方舱(Container) + 配电单元(PowerUnit) + 设备(Equipment) — 模块化宏观视角
"""

from __future__ import annotations

from pathlib import Path

from adl.diagnostics import Severity
from adl.models import GeometryAssets, Tags
from adl.types import TypeRegistry
from pydantic import BaseModel, Field

from piki.core.engine.checker import Checker
from piki.core.engine.generator_registry import GeneratorResult
from piki.core.plugin import Plugin

# ---------------------------------------------------------------------------
# Family 定义
# ---------------------------------------------------------------------------


class ContainerFamily(BaseModel):
    """方舱 / 集装箱式模块化机房。"""

    id: str = Field(...)
    name: str = Field(default="")
    container_type: str = Field(...)  # liquid-cooling | air-cooling | battery | power-distribution
    standard: str = Field(default="20ft")  # 20ft | 40ft | custom
    length_mm: float = Field(default=6058, gt=0, json_schema_extra={"piki_non_overridable": True})
    width_mm: float = Field(default=2438, gt=0, json_schema_extra={"piki_non_overridable": True})
    height_mm: float = Field(default=2591, gt=0, json_schema_extra={"piki_non_overridable": True})
    max_weight_kg: float = Field(default=24000, gt=0)  # 最大总重（kg）
    power_capacity_kw: float = Field(default=0, ge=0)  # 配电容量（kW）
    cooling_capacity_kw: float = Field(default=0, ge=0)  # 制冷容量（kW）
    location: str = Field(default="")  # 场地位置描述
    status: str = Field(default="planned")  # planned | installed | operating | retired
    # 3D 空间定位（毫米）
    position_x_mm: float = Field(default=0.0)
    position_y_mm: float = Field(default=0.0)
    position_z_mm: float = Field(default=0.0)
    # 几何资产（可选）
    assets: GeometryAssets | None = Field(default=None)
    tags: Tags = Field(default_factory=Tags)  # 标签（ADR-001）


class PowerUnitFamily(BaseModel):
    """配电单元：UPS、HVDC、锂电储能、柴油发电机等。"""

    id: str = Field(...)
    name: str = Field(default="")
    unit_type: str = Field(...)  # ups | hvdc | battery | diesel | solar | pdu-rack
    container_id: str = Field(...)  # 所属方舱
    capacity_kw: float = Field(..., gt=0)  # 额定容量（kW）
    redundancy_n: int = Field(default=1, ge=1)  # N+几冗余，1=N, 2=N+1
    phase: str = Field(default="L1")  # L1 | L2 | L3 | three-phase
    efficiency: float = Field(default=0.95, ge=0, le=1)  # 转换效率
    status: str = Field(default="planned")


class EquipmentFamily(BaseModel):
    """设备：IT 设备（服务器、存储、网络）和基础设施设备（空调、冷却塔）。"""

    id: str = Field(...)
    name: str = Field(default="")
    model: str = Field(default="")
    equipment_type: str = Field(...)  # compute | storage | network | cooling | other
    container_id: str = Field(...)  # 所在方舱
    power_unit_id: str = Field(...)  # 供电来源
    power_kw: float = Field(default=5, gt=0)  # 额定功耗（kW）
    weight_kg: float = Field(default=100, gt=0)  # 重量（kg）
    status: str = Field(default="planned")
    # 物理尺寸（毫米），用于 3D 碰撞检测和空间边界检查
    length_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    width_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    height_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    depth_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    # 3D 空间定位（毫米，相对于方舱原点）
    position_x_mm: float = Field(default=0.0)
    position_y_mm: float = Field(default=0.0)
    position_z_mm: float = Field(default=0.0)
    # 几何资产（可选）
    assets: GeometryAssets | None = Field(default=None)
    # 标签（ADR-001）
    tags: Tags = Field(default_factory=Tags)
    # 液冷设备特有
    liquid_cooled: bool = Field(default=False)
    coolant_flow_lpm: float = Field(default=0, ge=0)  # 冷却液流量 L/min
    coolant_inlet_temp_c: float = Field(default=0, ge=0)  # 进水温度 °C


class ConnectionFamily(BaseModel):
    """方舱间连接：液冷管路、电缆、光纤。"""

    id: str = Field(...)
    name: str = Field(default="")
    connection_type: str = Field(...)  # liquid | power | fiber
    from_container: str = Field(...)
    to_container: str = Field(...)
    capacity: float = Field(default=0, ge=0)  # 容量：kW(电缆) / L/min(液冷) / Gbps(光纤)
    length_m: float = Field(default=0, ge=0)  # 长度（米）
    status: str = Field(default="planned")


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class DatacenterPlugin(Plugin):
    name = "datacenter"
    version = "0.1.0"

    @property
    def model_dir(self) -> Path:
        return Path(__file__).parent / "models"

    def register_types(self, type_registry: TypeRegistry) -> None:
        type_registry.add_family("ContainerFamily", ContainerFamily)
        type_registry.add_family("PowerUnitFamily", PowerUnitFamily)
        type_registry.add_family("EquipmentFamily", EquipmentFamily)
        type_registry.add_family("ConnectionFamily", ConnectionFamily)

        # 注册 datacenter 领域的 Mate 类型 (ADR-006).
        from adl.models import MateTypeMeta

        type_registry.add_mate_type(
            "grid-mount",
            MateTypeMeta(
                type="grid-mount",
                description="方舱内设备装配",
                applicable_parent_families={"ContainerFamily"},
                applicable_child_families={"EquipmentFamily", "PowerUnitFamily"},
            ),
        )
        type_registry.add_mate_type(
            "power-cable",
            MateTypeMeta(
                type="power-cable",
                description="配电单元到设备供电电缆",
            ),
        )

    def register_rules(self, checker: Checker) -> None:
        checker.add_rule(
            "DC-POWER-001",
            "方舱功率预算检查",
            check_container_power_budget,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "DC-COOLING-001",
            "液冷方舱制冷容量检查",
            check_liquid_cooling_capacity,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "DC-WEIGHT-001",
            "方舱总重检查",
            check_container_weight,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "DC-SPACE-001",
            "方舱内设备空间边界检查",
            check_equipment_container_fit,
            priority=5,
            severity=Severity.WARNING,
        )
        checker.add_rule(
            "DC-COLLISION-001",
            "方舱内设备 3D 碰撞检测",
            check_equipment_3d_collision,
            priority=5,
            severity=Severity.WARNING,
        )
        checker.add_rule(
            "DC-CONN-001",
            "连接完整性检查",
            check_connection_integrity,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "DC-CONN-002",
            "连接容量检查",
            check_connection_capacity,
            priority=5,
            severity=Severity.WARNING,
        )
        checker.add_rule(
            "DC-FK-001",
            "外键完整性检查",
            check_dc_foreign_keys,
            priority=10,
            severity=Severity.WARNING,
        )
        checker.add_rule(
            "DC-REDUNDANCY-001",
            "配电冗余检查",
            check_power_redundancy,
            priority=5,
            severity=Severity.WARNING,
        )

    def register_generators(self, checker: Checker) -> None:
        checker.add_generator("dc-bom-csv", "数据中心 BOM CSV 导出", generate_dc_bom_csv)


# ---------------------------------------------------------------------------
# 规则实现
# ---------------------------------------------------------------------------


def check_container_power_budget(ctx):
    """检查每个方舱内设备总功耗不超过方舱配电容量。"""
    threshold = ctx.config.get("power_threshold", 0.8)

    for container in ctx.query("containers"):
        ctx.set_current_file(str(container.source))
        cap = container.power_capacity_kw
        if cap <= 0:
            continue

        devices = ctx.query("equipment", container_id=container.id)
        total = sum(d.power_kw for d in devices)
        ratio = total / cap

        assert ratio <= threshold, (
            f"方舱 {container.id} 功率负载率 {ratio:.1%}（{total:.1f}kW / {cap:.1f}kW），"
            f"超过项目阈值 {threshold:.1%}。"
            f"已部署设备: {', '.join(d.id for d in devices)}"
        )
    ctx.clear_current_file()


def check_liquid_cooling_capacity(ctx):
    """检查液冷方舱的制冷容量是否满足液冷设备需求。"""
    for container in ctx.query("containers", container_type="liquid-cooling"):
        ctx.set_current_file(str(container.source))
        cooling_cap = container.cooling_capacity_kw
        if cooling_cap <= 0:
            continue

        devices = ctx.query("equipment", container_id=container.id, liquid_cooled=True)
        total_heat = sum(d.power_kw for d in devices)

        assert total_heat <= cooling_cap, (
            f"液冷方舱 {container.id} 热负荷 {total_heat:.1f}kW 超过制冷容量 {cooling_cap:.1f}kW。"
            f"液冷设备: {', '.join(d.id for d in devices)}"
        )
    ctx.clear_current_file()


def check_container_weight(ctx):
    """检查方舱内设备总重不超过方舱最大承重。"""
    for container in ctx.query("containers"):
        ctx.set_current_file(str(container.source))
        max_w = container.max_weight_kg
        if max_w <= 0:
            continue

        devices = ctx.query("equipment", container_id=container.id)
        total = sum(d.weight_kg for d in devices)

        assert total <= max_w, (
            f"方舱 {container.id} 设备总重 {total:.0f}kg 超过最大承重 {max_w:.0f}kg"
        )
    ctx.clear_current_file()


def check_connection_integrity(ctx):
    """检查所有连接的两端方舱和容量引用是否有效。"""
    containers = {c.id: c for c in ctx.query("containers")}

    for conn in ctx.query("connections"):
        ctx.set_current_file(str(conn.source))
        assert conn.from_container in containers, (
            f"连接 {conn.id} 的源方舱 {conn.from_container} 不存在"
        )
        assert conn.to_container in containers, (
            f"连接 {conn.id} 的目标方舱 {conn.to_container} 不存在"
        )
        assert conn.from_container != conn.to_container, (
            f"连接 {conn.id} 的源方舱和目标方舱不能相同"
        )
    ctx.clear_current_file()


def check_equipment_container_fit(ctx):
    """检查方舱内设备是否超出方舱物理边界。

    当 equipment 和 container 都有尺寸字段时：
    - 设备长度 ≤ 方舱长度
    - 设备宽度 ≤ 方舱宽度
    - 设备高度 ≤ 方舱高度

    任一尺寸缺失（为 0）时跳过检查，避免误报。
    """
    containers = {c.id: c for c in ctx.query("containers")}

    for device in ctx.query("equipment"):
        container = containers.get(device.container_id)
        if container is None:
            continue

        dev_length = device.length_mm or device.depth_mm
        dev_width = device.width_mm
        dev_height = device.height_mm
        cnt_length = container.length_mm
        cnt_width = container.width_mm
        cnt_height = container.height_mm

        # 跳过：任一方缺少尺寸数据
        if dev_length <= 0 or cnt_length <= 0:
            dev_length = 0
        if dev_width <= 0 or cnt_width <= 0:
            dev_width = 0
        if dev_height <= 0 or cnt_height <= 0:
            dev_height = 0
        if dev_length == 0 and dev_width == 0 and dev_height == 0:
            continue

        ctx.set_current_file(str(device.source))

        if dev_length > 0 and dev_length > cnt_length:
            assert False, (
                f"设备 {device.id} 长度 {dev_length}mm 超过方舱 {container.id} "
                f"长度 {cnt_length}mm，无法容纳。"
            )

        if dev_width > 0 and dev_width > cnt_width:
            assert False, (
                f"设备 {device.id} 宽度 {dev_width}mm 超过方舱 {container.id} "
                f"宽度 {cnt_width}mm，无法容纳。"
            )

        if dev_height > 0 and dev_height > cnt_height:
            assert False, (
                f"设备 {device.id} 高度 {dev_height}mm 超过方舱 {container.id} "
                f"高度 {cnt_height}mm，无法容纳。"
            )
    ctx.clear_current_file()


def check_equipment_3d_collision(ctx):
    """检查同一方舱内设备的 3D 空间碰撞。

    使用 AABB 包围盒进行 O(n²) 碰撞检测。
    无尺寸或位置信息的设备自动跳过。
    """
    from piki.ext.geometry import build_aabb_from_instance, find_collisions

    {c.id: c for c in ctx.query("containers")}

    for container in ctx.query("containers"):
        devices = ctx.query("equipment", container_id=container.id)
        items: list[tuple[str, "AABB"]] = []

        for device in devices:
            aabb = build_aabb_from_instance(device)
            if aabb is not None:
                items.append((device.id, aabb))

        if len(items) < 2:
            continue

        collisions = find_collisions(items)
        if collisions:
            ctx.set_current_file(str(container.source))
            pairs = ", ".join(f"{a} ↔ {b}" for a, b in collisions)
            assert False, f"方舱 {container.id} 内发现 {len(collisions)} 处设备空间冲突: {pairs}"
    ctx.clear_current_file()


def check_connection_capacity(ctx):
    """检查连接的容量是否满足传输需求（双向校验）。

    对每种连接类型：
    - 液冷：检查 from_container 的供液能力 ≥ to_container 的需求
    - 电力：检查 from_container 的供电能力 ≥ to_container 的需求
    - 光纤：检查带宽容量 ≥ 目标方舱内网络设备的带宽需求
    """
    for conn in ctx.query("connections"):
        ctx.set_current_file(str(conn.source))
        cap = conn.capacity
        if cap <= 0:
            continue

        # 液冷连接：检查 to_container 的流量需求
        if conn.connection_type == "liquid":
            target_devices = ctx.query(
                "equipment", container_id=conn.to_container, liquid_cooled=True
            )
            total_flow = sum(d.coolant_flow_lpm for d in target_devices)
            if total_flow > 0:
                assert cap >= total_flow, (
                    f"液冷连接 {conn.id} 容量 {cap}L/min 小于目标方舱 {conn.to_container} "
                    f"需求 {total_flow}L/min"
                )

            # 双向校验：同时检查 from_container 是否能提供足够的供液
            source_devices = ctx.query(
                "equipment", container_id=conn.from_container, liquid_cooled=True
            )
            source_flow = sum(d.coolant_flow_lpm for d in source_devices)
            if source_flow > 0 and cap < source_flow:
                # 源方舱也有液冷需求时，连接容量应至少满足较大的一方
                max_demand = max(total_flow, source_flow)
                assert cap >= max_demand, (
                    f"液冷连接 {conn.id} 容量 {cap}L/min 小于 "
                    f"源方舱 {conn.from_container} 需求 {source_flow}L/min 与 "
                    f"目标方舱 {conn.to_container} 需求 {total_flow}L/min 中的较大值 {max_demand}L/min"
                )

        # 电力连接：检查 to_container 的功率需求
        elif conn.connection_type == "power":
            target_devices = ctx.query("equipment", container_id=conn.to_container)
            total_power = sum(d.power_kw for d in target_devices)
            if total_power > 0:
                assert cap >= total_power, (
                    f"电力连接 {conn.id} 容量 {cap}kW 小于目标方舱 {conn.to_container} "
                    f"需求 {total_power}kW"
                )

            # 双向校验：同时检查 from_container 的供电需求
            source_devices = ctx.query("equipment", container_id=conn.from_container)
            source_power = sum(d.power_kw for d in source_devices)
            if source_power > 0 and cap < source_power:
                max_demand = max(total_power, source_power)
                assert cap >= max_demand, (
                    f"电力连接 {conn.id} 容量 {cap}kW 小于 "
                    f"源方舱 {conn.from_container} 需求 {source_power}kW 与 "
                    f"目标方舱 {conn.to_container} 需求 {total_power}kW 中的较大值 {max_demand}kW"
                )

        # 光纤连接：检查带宽需求
        elif conn.connection_type == "fiber":
            target_devices = ctx.query(
                "equipment", container_id=conn.to_container, equipment_type="network"
            )
            # 简化：假设每个网络设备需要 10Gbps
            total_bandwidth = len(target_devices) * 10
            if total_bandwidth > 0:
                assert cap >= total_bandwidth, (
                    f"光纤连接 {conn.id} 容量 {cap}Gbps 小于目标方舱 {conn.to_container} "
                    f"网络设备带宽需求 {total_bandwidth}Gbps"
                )
    ctx.clear_current_file()


def check_dc_foreign_keys(ctx):
    """检查设备引用的方舱和配电单元是否存在。"""
    containers = {c.id: c for c in ctx.query("containers")}
    power_units = {p.id: p for p in ctx.query("power")}

    for device in ctx.query("equipment"):
        ctx.set_current_file(str(device.source))
        assert device.container_id in containers, (
            f"设备 {device.id} 引用的方舱 {device.container_id} 不存在"
        )
        assert device.power_unit_id in power_units, (
            f"设备 {device.id} 引用的配电单元 {device.power_unit_id} 不存在"
        )

    for pu in ctx.query("power"):
        ctx.set_current_file(str(pu.source))
        assert pu.container_id in containers, (
            f"配电单元 {pu.id} 引用的方舱 {pu.container_id} 不存在"
        )
    ctx.clear_current_file()


def check_power_redundancy(ctx):
    """检查配电单元的冗余配置是否满足项目要求。"""
    min_redundancy = ctx.config.get("min_redundancy_n", 1)

    for pu in ctx.query("power"):
        ctx.set_current_file(str(pu.source))
        assert pu.redundancy_n >= min_redundancy, (
            f"配电单元 {pu.id} 冗余配置为 N+{pu.redundancy_n - 1}，"
            f"低于项目要求的 N+{min_redundancy - 1}"
        )
    ctx.clear_current_file()


# ---------------------------------------------------------------------------
# 生成器
# ---------------------------------------------------------------------------


def generate_dc_bom_csv(ctx, config) -> GeneratorResult:
    """生成数据中心 BOM CSV。"""
    import csv
    import io
    from pathlib import Path

    containers = ctx.query("containers").list()
    equipment = ctx.query("equipment").list()
    power = ctx.query("power").list()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["=== 方舱清单 ==="])
    writer.writerow(["ID", "Type", "Standard", "Power_kW", "Cooling_kW", "Status"])
    for c in containers:
        writer.writerow(
            [
                c.id,
                c.container_type,
                c.standard,
                c.power_capacity_kw,
                c.cooling_capacity_kw,
                c.status,
            ]
        )

    writer.writerow([])

    writer.writerow(["=== 设备清单 ==="])
    writer.writerow(
        ["ID", "Type", "Model", "Container", "Power_kW", "Weight_kg", "LiquidCooled", "Status"]
    )
    for d in equipment:
        writer.writerow(
            [
                d.id,
                d.equipment_type,
                d.model or "",
                d.container_id,
                d.power_kw,
                d.weight_kg,
                d.liquid_cooled,
                d.status,
            ]
        )

    writer.writerow([])

    writer.writerow(["=== 配电清单 ==="])
    writer.writerow(["ID", "Type", "Container", "Capacity_kW", "Redundancy", "Status"])
    for p in power:
        writer.writerow(
            [
                p.id,
                p.unit_type,
                p.container_id,
                p.capacity_kw,
                f"N+{p.redundancy_n - 1}",
                p.status,
            ]
        )

    csv_content = output.getvalue()
    out_path = config.get("output")
    if out_path:
        file_path = Path(str(out_path))
        file_path.write_text(csv_content, encoding="utf-8")
        return GeneratorResult.ok(
            "dc-bom-csv", "DC BOM CSV 导出", csv_content, file_path, "text/csv"
        )
    return GeneratorResult.ok("dc-bom-csv", "DC BOM CSV 导出", csv_content, content_type="text/csv")
