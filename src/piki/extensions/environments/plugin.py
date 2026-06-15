"""piki-environments 内置插件：环境适应性规则库。

提供跨产品域共享的 Family 和 Rule：
- OperatingEnvironmentFamily：使用环境谱
- MaterialFamily：材料耐候性规格
- 环境-材料匹配规则
"""

from __future__ import annotations

from pathlib import Path

from adl.diagnostics import Severity
from adl.models import Tags
from adl.types import TypeRegistry
from pydantic import BaseModel, Field

from piki.core.engine.checker import Checker
from piki.core.plugin import Plugin


class OperatingEnvironmentFamily(BaseModel):
    """使用环境谱：描述产品预期运行的环境条件。"""

    id: str = Field(...)
    name: str = Field(default="")
    temperature_min_c: float = Field(default=-20)
    temperature_max_c: float = Field(default=60)
    humidity_min_pct: float = Field(default=0, ge=0, le=100)
    humidity_max_pct: float = Field(default=95, ge=0, le=100)
    uv_exposure_hours_per_year: float = Field(default=0, ge=0)
    salt_spray: bool = Field(default=False)
    ip_rating_required: str = Field(default="")  # IP65, IP67
    fire_rating_required: str = Field(default="")  # UL94-V0
    description: str = Field(default="")
    tags: Tags = Field(default_factory=Tags)


class MaterialFamily(BaseModel):
    """材料耐候性规格。

    用于检查材料/组件是否适应指定的使用环境。
    """

    id: str = Field(...)
    name: str = Field(default="")
    material_type: str = Field(
        default="",
        description="材料大类：plastic, metal, ceramic, composite, coating",
    )
    # 温度范围
    min_temperature_c: float = Field(default=-40)
    max_temperature_c: float = Field(default=85)
    # 耐候性
    uv_resistant: bool = Field(default=False)
    salt_spray_resistant: bool = Field(default=False)
    waterproof: bool = Field(default=False)
    compatible_ip_ratings: list[str] = Field(default_factory=list)
    # 可燃性
    fire_rating: str = Field(default="")  # UL94-HB, UL94-V0, etc.
    description: str = Field(default="")
    tags: Tags = Field(default_factory=Tags)


class EnvironmentsPlugin(Plugin):
    name = "environments"
    version = "0.1.0"

    @property
    def model_dir(self) -> Path:
        return Path(__file__).parent / "models"

    def register_types(self, type_registry: TypeRegistry) -> None:
        type_registry.add_family("OperatingEnvironmentFamily", OperatingEnvironmentFamily)
        type_registry.add_family("MaterialFamily", MaterialFamily)

    def register_rules(self, checker: Checker) -> None:
        checker.add_rule(
            "ENV-001",
            "装配体引用的使用环境必须存在",
            check_environment_reference,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "ENV-MAT-001",
            "材料温度范围覆盖使用环境",
            check_material_temperature_range,
            priority=5,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "ENV-MAT-002",
            "材料满足 UV/盐雾/防水要求",
            check_material_environmental_resistance,
            priority=5,
            severity=Severity.WARNING,
        )
        checker.add_rule(
            "ENV-MAT-003",
            "材料满足 IP 等级要求",
            check_material_ip_rating,
            priority=5,
            severity=Severity.ERROR,
        )

    def register_generators(self, checker: Checker) -> None:
        pass


# ---------------------------------------------------------------------------
# 规则实现
# ---------------------------------------------------------------------------


def _get_environment(ctx, env_id: str) -> OperatingEnvironmentFamily | None:
    inst = ctx.find_instance(env_id)
    if inst is None or inst.family != "OperatingEnvironmentFamily":
        return None
    return OperatingEnvironmentFamily.model_validate(inst._resolved)


def _get_material(ctx, material_id: str) -> MaterialFamily | None:
    inst = ctx.find_instance(material_id)
    if inst is None or inst.family != "MaterialFamily":
        return None
    return MaterialFamily.model_validate(inst._resolved)


def check_environment_reference(ctx):
    """检查所有声明 environment_id 的装配体引用的环境存在。"""
    for collection in ctx._registry.list_collections():
        for inst in ctx.query(collection):
            env_id = getattr(inst.resolved, "environment_id", "")
            if not env_id:
                continue
            env = ctx.find_instance(env_id)
            assert env is not None, f"实例 {inst.id} 引用的使用环境 {env_id} 不存在"
            assert env.family == "OperatingEnvironmentFamily", (
                f"实例 {inst.id} 引用的 {env_id} 不是使用环境 (family={env.family})"
            )


def check_material_temperature_range(ctx):
    """检查声明 material_id 的实例，其材料温度范围覆盖使用环境。"""
    for env_inst in ctx.query("operating_environments"):
        env = OperatingEnvironmentFamily.model_validate(env_inst._resolved)
        for collection in ctx._registry.list_collections():
            for inst in ctx.query(collection):
                material_id = getattr(inst.resolved, "material_id", "")
                env_id = getattr(inst.resolved, "environment_id", "")
                if not material_id or env_id != env_inst.id:
                    continue
                material = _get_material(ctx, material_id)
                if material is None:
                    continue
                assert material.min_temperature_c <= env.temperature_min_c, (
                    f"{inst.id} 材料 {material_id} 最低耐温 "
                    f"{material.min_temperature_c}°C 高于环境最低温 {env.temperature_min_c}°C"
                )
                assert material.max_temperature_c >= env.temperature_max_c, (
                    f"{inst.id} 材料 {material_id} 最高耐温 "
                    f"{material.max_temperature_c}°C 低于环境最高温 {env.temperature_max_c}°C"
                )


def check_material_environmental_resistance(ctx):
    """检查材料满足 UV/盐雾/防水要求。"""
    for env_inst in ctx.query("operating_environments"):
        env = OperatingEnvironmentFamily.model_validate(env_inst._resolved)
        for collection in ctx._registry.list_collections():
            for inst in ctx.query(collection):
                material_id = getattr(inst.resolved, "material_id", "")
                env_id = getattr(inst.resolved, "environment_id", "")
                if not material_id or env_id != env_inst.id:
                    continue
                material = _get_material(ctx, material_id)
                if material is None:
                    continue
                if env.uv_exposure_hours_per_year > 0:
                    assert material.uv_resistant, (
                        f"{inst.id} 材料 {material_id} 不抗 UV，"
                        f"不适用于年 UV 暴露 {env.uv_exposure_hours_per_year}h 的环境"
                    )
                if env.salt_spray:
                    assert material.salt_spray_resistant, f"{inst.id} 材料 {material_id} 不耐盐雾"
                # 简单规则：需要 IP 等级时材料需防水
                if env.ip_rating_required and not material.waterproof:
                    ctx.set_suggestion(
                        f"环境 {env_inst.id} 要求 {env.ip_rating_required}，"
                        f"材料 {material_id} 未声明防水，请确认"
                    )


def check_material_ip_rating(ctx):
    """检查材料兼容环境要求的 IP 等级。"""
    for env_inst in ctx.query("operating_environments"):
        env = OperatingEnvironmentFamily.model_validate(env_inst._resolved)
        if not env.ip_rating_required:
            continue
        for collection in ctx._registry.list_collections():
            for inst in ctx.query(collection):
                material_id = getattr(inst.resolved, "material_id", "")
                env_id = getattr(inst.resolved, "environment_id", "")
                if not material_id or env_id != env_inst.id:
                    continue
                material = _get_material(ctx, material_id)
                if material is None:
                    continue
                assert env.ip_rating_required in material.compatible_ip_ratings, (
                    f"{inst.id} 材料 {material_id} 不兼容 IP 等级 {env.ip_rating_required}"
                )
