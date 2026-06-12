"""piki-manufacturing 内置插件：制造约束即服务（DfX）。

提供跨产品域共享的 Family 和 Rule：
- ManufacturingProcessFamily：制造工艺约束（CNC、3D 打印、注塑等）
- BuildJobFamily：制造工单/批次
- DfX 规则：壁厚、拔模角、表面处理等
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from piki.core.engine.checker import Checker
from piki.core.engine.registry import Registry
from piki.core.models.diagnostic import Severity
from piki.core.models.tags import Tags
from piki.core.plugin import Plugin


class ManufacturingProcessFamily(BaseModel):
    """制造工艺约束库。

    描述一种制造工艺对零件几何/材料/表面处理的约束。
    """

    id: str = Field(...)
    name: str = Field(default="")
    process_type: str = Field(
        ...,
        description="工艺类型：cnc, injection_molding, die_casting, 3d_printing, sheet_metal",
    )
    # 几何约束
    min_wall_thickness_mm: float = Field(default=0, ge=0)
    max_wall_thickness_mm: float = Field(default=0, ge=0)
    min_hole_diameter_mm: float = Field(default=0, ge=0)
    draft_angle_min_deg: float = Field(default=0, ge=0)
    draft_angle_max_deg: float = Field(default=0, ge=0)
    # 尺寸约束
    max_part_size_x_mm: float = Field(default=0, ge=0)
    max_part_size_y_mm: float = Field(default=0, ge=0)
    max_part_size_z_mm: float = Field(default=0, ge=0)
    # 表面处理
    available_surface_finishes: list[str] = Field(default_factory=list)
    # 材料兼容性
    compatible_material_types: list[str] = Field(default_factory=list)
    description: str = Field(default="")
    tags: Tags = Field(default_factory=Tags)


class BuildJobFamily(BaseModel):
    """制造工单：关联零件与工艺，记录制造约束检查目标。"""

    id: str = Field(...)
    name: str = Field(default="")
    process_id: str = Field(...)
    part_id: str = Field(...)
    quantity: int = Field(default=1, ge=1)
    required_surface_finish: str = Field(default="")
    description: str = Field(default="")
    tags: Tags = Field(default_factory=Tags)


class ManufacturingPlugin(Plugin):
    name = "manufacturing"
    version = "0.1.0"

    @property
    def model_dir(self) -> Path:
        return Path(__file__).parent / "models"

    def register_families(self, registry: Registry) -> None:
        registry.add_family("ManufacturingProcessFamily", ManufacturingProcessFamily)
        registry.add_family("BuildJobFamily", BuildJobFamily)

    def register_mate_types(self, registry: Registry) -> None:
        pass

    def register_rules(self, checker: Checker) -> None:
        checker.add_rule(
            "DFX-001",
            "制造工单引用的工艺与零件必须存在",
            check_build_job_references,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "DFX-002",
            "零件尺寸在工艺加工范围内",
            check_part_fits_machine,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "DFX-003",
            "壁厚满足工艺最小/最大要求",
            check_wall_thickness,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "DFX-004",
            "注塑/压铸零件需满足拔模角",
            check_draft_angle,
            priority=5,
            severity=Severity.WARNING,
        )
        checker.add_rule(
            "DFX-005",
            "表面处理在工艺可用列表中",
            check_surface_finish,
            priority=3,
            severity=Severity.WARNING,
        )

    def register_generators(self, checker: Checker) -> None:
        pass


# ---------------------------------------------------------------------------
# 规则实现
# ---------------------------------------------------------------------------


def _get_process(ctx, process_id: str) -> ManufacturingProcessFamily | None:
    inst = ctx.find_instance(process_id)
    if inst is None or inst.family != "ManufacturingProcessFamily":
        return None
    return ManufacturingProcessFamily.model_validate(inst._resolved)


def _iter_part_process_pairs(ctx):
    """遍历所有需要 DfX 检查的 (part, process) 对。

    来源：
    1. 零件实例自带的 process_id 字段（设计阶段直接声明工艺）。
    2. BuildJob 实例引用的 part + process（下游制造工单场景）。
    """
    # 1. 零件自带 process_id
    for collection in ctx._registry.list_collections():
        if collection == "build_jobs":
            continue
        for inst in ctx.query(collection):
            process_id = getattr(inst.resolved, "process_id", "")
            if not process_id:
                continue
            process = _get_process(ctx, process_id)
            if process is not None:
                yield inst, process

    # 2. BuildJob
    for job in ctx.query("build_jobs"):
        process = _get_process(ctx, job.resolved.process_id)
        part = ctx.find_instance(job.resolved.part_id)
        if process is not None and part is not None:
            yield part, process


def _part_finish(part, process_source) -> str:
    """获取零件的表面处理目标。

    优先从 BuildJob 的 required_surface_finish 取，否则从零件 surface_finish 取。
    """
    if hasattr(process_source, "resolved"):
        job_finish = getattr(process_source.resolved, "required_surface_finish", "")
        if job_finish:
            return job_finish
    return getattr(part.resolved, "surface_finish", "")


def check_build_job_references(ctx):
    """检查 BuildJob 引用的 process 和 part 存在且 Family 正确。"""
    for job in ctx.query("build_jobs"):
        process = ctx.find_instance(job.resolved.process_id)
        assert process is not None, f"工单 {job.id} 引用的工艺 {job.resolved.process_id} 不存在"
        assert process.family == "ManufacturingProcessFamily", (
            f"工单 {job.id} 引用的 {job.resolved.process_id} 不是制造工艺"
        )
        part = ctx.find_instance(job.resolved.part_id)
        assert part is not None, f"工单 {job.id} 引用的零件 {job.resolved.part_id} 不存在"


def check_part_fits_machine(ctx):
    """检查零件外形尺寸不超过工艺设备加工范围。"""
    for part, process in _iter_part_process_pairs(ctx):
        dims = {
            "x": getattr(part.resolved, "length_mm", 0),
            "y": getattr(part.resolved, "width_mm", 0),
            "z": getattr(part.resolved, "height_mm", 0),
        }
        limits = {
            "x": process.max_part_size_x_mm,
            "y": process.max_part_size_y_mm,
            "z": process.max_part_size_z_mm,
        }
        for axis in ("x", "y", "z"):
            limit = limits[axis]
            if limit <= 0:
                continue
            assert dims[axis] <= limit, (
                f"零件 {part.id} {axis} 方向尺寸 "
                f"{dims[axis]}mm 超过工艺 {process.id} 限制 {limit}mm"
            )


def check_wall_thickness(ctx):
    """检查零件壁厚在工艺允许范围内。"""
    for part, process in _iter_part_process_pairs(ctx):
        wall = getattr(part.resolved, "wall_thickness_mm", 0)
        if wall <= 0:
            continue
        if process.min_wall_thickness_mm > 0:
            assert wall >= process.min_wall_thickness_mm, (
                f"零件 {part.id} 壁厚 {wall}mm 小于工艺 "
                f"{process.id} 最小要求 {process.min_wall_thickness_mm}mm"
            )
        if process.max_wall_thickness_mm > 0:
            assert wall <= process.max_wall_thickness_mm, (
                f"零件 {part.id} 壁厚 {wall}mm 大于工艺 "
                f"{process.id} 最大要求 {process.max_wall_thickness_mm}mm"
            )


def check_draft_angle(ctx):
    """检查注塑/压铸零件满足拔模角要求。"""
    molding_processes = {"injection_molding", "die_casting"}
    for part, process in _iter_part_process_pairs(ctx):
        if process.process_type not in molding_processes:
            continue
        draft = getattr(part.resolved, "draft_angle_deg", 0)
        if process.draft_angle_min_deg > 0:
            assert draft >= process.draft_angle_min_deg, (
                f"零件 {part.id} 拔模角 {draft}° 小于工艺 "
                f"{process.id} 最小要求 {process.draft_angle_min_deg}°"
            )


def check_surface_finish(ctx):
    """检查零件表面处理在工艺可用列表中。"""
    for part, process in _iter_part_process_pairs(ctx):
        finish = getattr(part.resolved, "surface_finish", "")
        if not finish:
            continue
        if not process.available_surface_finishes:
            ctx.set_suggestion(f"工艺 {process.id} 未声明可用表面处理，无法校验 {finish}")
            continue
        assert finish in process.available_surface_finishes, (
            f"零件 {part.id} 表面处理 {finish} 不在工艺 {process.id} 可用列表中"
        )
