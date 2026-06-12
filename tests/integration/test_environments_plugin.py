"""Environments 插件集成测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from piki.core.engine.checker import Checker
from piki.core.engine.context import Context
from piki.core.engine.registry import Registry
from piki.extensions.environments.plugin import (
    EnvironmentsPlugin,
    check_environment_reference,
    check_material_ip_rating,
    check_material_temperature_range,
)


class PartFamily(BaseModel):
    """测试用零件 Family，用于关联环境和材料。"""

    id: str = Field(...)
    environment_id: str = Field(default="")
    material_id: str = Field(default="")


@pytest.fixture
def env_ctx(tmp_path: Path) -> Context:
    """构造一个带环境和材料的 Context。"""
    registry = Registry()
    EnvironmentsPlugin().register_families(registry)
    registry.add_family("PartFamily", PartFamily)

    envs = tmp_path / "operating_environments"
    envs.mkdir()
    (envs / "OUTDOOR.yaml").write_text(
        "id: OUTDOOR\nfamily: OperatingEnvironmentFamily\n"
        "temperature_min_c: -20\ntemperature_max_c: 60\n"
        "uv_exposure_hours_per_year: 1000\nsalt_spray: true\n"
        "ip_rating_required: IP65\n",
        encoding="utf-8",
    )
    registry.load_collection(envs)

    materials = tmp_path / "materials"
    materials.mkdir()
    (materials / "PBT.yaml").write_text(
        "id: PBT\nfamily: MaterialFamily\n"
        "material_type: plastic\nmin_temperature_c: -20\nmax_temperature_c: 80\n"
        "uv_resistant: true\nsalt_spray_resistant: false\n"
        "waterproof: false\ncompatible_ip_ratings: []\n",
        encoding="utf-8",
    )
    (materials / "ABS.yaml").write_text(
        "id: ABS\nfamily: MaterialFamily\n"
        "material_type: plastic\nmin_temperature_c: -10\nmax_temperature_c: 60\n"
        "uv_resistant: false\nsalt_spray_resistant: false\n"
        "waterproof: false\ncompatible_ip_ratings: []\n",
        encoding="utf-8",
    )
    (materials / "IP65-RUBBER.yaml").write_text(
        "id: IP65-RUBBER\nfamily: MaterialFamily\n"
        "material_type: rubber\nmin_temperature_c: -40\nmax_temperature_c: 100\n"
        "uv_resistant: true\nsalt_spray_resistant: true\n"
        "waterproof: true\ncompatible_ip_ratings: [IP65, IP67]\n",
        encoding="utf-8",
    )
    registry.load_collection(materials)

    parts = tmp_path / "parts"
    parts.mkdir()
    (parts / "SEAL.yaml").write_text(
        "id: SEAL\nfamily: PartFamily\nenvironment_id: OUTDOOR\nmaterial_id: IP65-RUBBER\n",
        encoding="utf-8",
    )
    registry.load_collection(parts)

    return Context(registry, {})


class TestEnvironmentReference:
    """测试环境引用存在性。"""

    def test_passes(self, env_ctx: Context) -> None:
        check_environment_reference(env_ctx)

    def test_fails_missing_environment(self, env_ctx: Context, tmp_path: Path) -> None:
        parts = tmp_path / "parts"
        parts.mkdir(exist_ok=True)
        (parts / "BAD.yaml").write_text(
            "id: BAD\nfamily: PartFamily\nenvironment_id: MISSING\nmaterial_id: PBT\n",
            encoding="utf-8",
        )
        env_ctx._registry.load_collection(parts)

        with pytest.raises(AssertionError, match="MISSING 不存在"):
            check_environment_reference(env_ctx)


class TestMaterialTemperature:
    """测试材料温度范围。"""

    def test_pbt_passes(self, env_ctx: Context) -> None:
        check_material_temperature_range(env_ctx)

    def test_abs_fails(self, env_ctx: Context, tmp_path: Path) -> None:
        parts = tmp_path / "parts"
        parts.mkdir(exist_ok=True)
        (parts / "KEYCAP-ABS.yaml").write_text(
            "id: KEYCAP-ABS\nfamily: PartFamily\nenvironment_id: OUTDOOR\nmaterial_id: ABS\n",
            encoding="utf-8",
        )
        env_ctx._registry.load_collection(parts)

        with pytest.raises(AssertionError, match="最低耐温 .* 高于环境最低温"):
            check_material_temperature_range(env_ctx)


class TestMaterialIpRating:
    """测试材料 IP 等级匹配。"""

    def test_ip65_rubber_passes(self, env_ctx: Context) -> None:
        # fixture 中的 SEAL 已关联 OUTDOOR + IP65-RUBBER
        check_material_ip_rating(env_ctx)

    def test_pbt_fails_ip65(self, env_ctx: Context, tmp_path: Path) -> None:
        # 添加关联 OUTDOOR + PBT 的零件，PBT 不兼容 IP65
        parts = tmp_path / "parts"
        parts.mkdir(exist_ok=True)
        (parts / "KEYCAP-PBT.yaml").write_text(
            "id: KEYCAP-PBT\nfamily: PartFamily\nenvironment_id: OUTDOOR\nmaterial_id: PBT\n",
            encoding="utf-8",
        )
        env_ctx._registry.load_collection(parts)

        with pytest.raises(AssertionError, match="不兼容 IP 等级 IP65"):
            check_material_ip_rating(env_ctx)


class TestCheckerIntegration:
    """测试 Checker 运行 environments 规则。"""

    def test_checker_runs_rules(self, env_ctx: Context) -> None:
        checker = Checker()
        checker.add_rule("ENV-001", "环境引用", check_environment_reference)
        checker.add_rule("ENV-MAT-001", "温度", check_material_temperature_range)

        report = checker.run(env_ctx)
        assert report.passed is True
        assert report.error_count == 0
