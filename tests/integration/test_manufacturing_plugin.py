"""Manufacturing 插件集成测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from piki.core.engine.checker import Checker
from piki.core.engine.context import Context
from piki.core.engine.registry import Registry
from piki.extensions.manufacturing.plugin import (
    ManufacturingPlugin,
    check_build_job_references,
    check_part_fits_machine,
    check_surface_finish,
    check_wall_thickness,
)


class CaseFamily(BaseModel):
    """测试用零件 Family：键盘外壳。"""

    id: str = Field(...)
    length_mm: float = Field(default=0)
    width_mm: float = Field(default=0)
    height_mm: float = Field(default=0)
    wall_thickness_mm: float = Field(default=0)
    surface_finish: str = Field(default="")
    process_id: str = Field(default="")


@pytest.fixture
def mfg_ctx(tmp_path: Path) -> Context:
    """构造一个带制造工艺和零件的 Context。"""
    registry = Registry()
    ManufacturingPlugin().register_families(registry)
    registry.add_family("CaseFamily", CaseFamily)

    processes = tmp_path / "manufacturing_processes"
    processes.mkdir()
    (processes / "CNC-ALU.yaml").write_text(
        "id: CNC-ALU\nfamily: ManufacturingProcessFamily\n"
        "process_type: cnc\nmin_wall_thickness_mm: 1.5\n"
        "max_wall_thickness_mm: 6.0\nmax_part_size_x_mm: 400\n"
        "max_part_size_y_mm: 200\nmax_part_size_z_mm: 80\n"
        "available_surface_finishes:\n  - anodized-black\n"
        "compatible_material_types:\n  - aluminum\n",
        encoding="utf-8",
    )
    (processes / "INJECTION.yaml").write_text(
        "id: INJECTION\nfamily: ManufacturingProcessFamily\n"
        "process_type: injection_molding\nmin_wall_thickness_mm: 1.0\n"
        "draft_angle_min_deg: 1.0\n",
        encoding="utf-8",
    )
    registry.load_collection(processes)

    cases = tmp_path / "cases"
    cases.mkdir()
    (cases / "CASE-01.yaml").write_text(
        "id: CASE-01\nfamily: CaseFamily\n"
        "length_mm: 320\nwidth_mm: 112\nheight_mm: 35\n"
        "wall_thickness_mm: 3.0\nprocess_id: CNC-ALU\n"
        "surface_finish: anodized-black\n",
        encoding="utf-8",
    )
    registry.load_collection(cases)

    return Context(registry, {})


class TestPartFitsMachine:
    """测试零件尺寸在设备加工范围内。"""

    def test_passes(self, mfg_ctx: Context) -> None:
        check_part_fits_machine(mfg_ctx)

    def test_fails_too_large(self, mfg_ctx: Context, tmp_path: Path) -> None:
        cases = tmp_path / "cases"
        cases.mkdir(exist_ok=True)
        (cases / "CASE-TOOBIG.yaml").write_text(
            "id: CASE-TOOBIG\nfamily: CaseFamily\n"
            "length_mm: 500\nwidth_mm: 112\nheight_mm: 35\n"
            "wall_thickness_mm: 3.0\nprocess_id: CNC-ALU\n",
            encoding="utf-8",
        )
        mfg_ctx._registry.load_collection(cases)

        with pytest.raises(AssertionError, match="CASE-TOOBIG"):
            check_part_fits_machine(mfg_ctx)


class TestWallThickness:
    """测试壁厚。"""

    def test_passes(self, mfg_ctx: Context) -> None:
        check_wall_thickness(mfg_ctx)

    def test_fails_too_thin(self, mfg_ctx: Context, tmp_path: Path) -> None:
        cases = tmp_path / "cases"
        cases.mkdir(exist_ok=True)
        (cases / "CASE-THIN.yaml").write_text(
            "id: CASE-THIN\nfamily: CaseFamily\n"
            "length_mm: 320\nwidth_mm: 112\nheight_mm: 35\n"
            "wall_thickness_mm: 0.5\nprocess_id: CNC-ALU\n",
            encoding="utf-8",
        )
        mfg_ctx._registry.load_collection(cases)

        with pytest.raises(AssertionError, match="CASE-THIN"):
            check_wall_thickness(mfg_ctx)


class TestDraftAngle:
    """测试拔模角。"""

    def test_fails_insufficient_draft(self, mfg_ctx: Context, tmp_path: Path) -> None:
        from piki.extensions.manufacturing.plugin import check_draft_angle

        cases = tmp_path / "cases"
        cases.mkdir(exist_ok=True)
        (cases / "CASE-PLASTIC.yaml").write_text(
            "id: CASE-PLASTIC\nfamily: CaseFamily\n"
            "length_mm: 320\nwidth_mm: 112\nheight_mm: 35\n"
            "wall_thickness_mm: 2.0\nprocess_id: INJECTION\n"
            "draft_angle_deg: 0.5\n",
            encoding="utf-8",
        )
        mfg_ctx._registry.load_collection(cases)

        with pytest.raises(AssertionError, match="CASE-PLASTIC"):
            check_draft_angle(mfg_ctx)


class TestSurfaceFinish:
    """测试表面处理。"""

    def test_passes(self, mfg_ctx: Context) -> None:
        check_surface_finish(mfg_ctx)

    def test_fails_unavailable_finish(self, mfg_ctx: Context, tmp_path: Path) -> None:
        cases = tmp_path / "cases"
        cases.mkdir(exist_ok=True)
        (cases / "CASE-BAD-FINISH.yaml").write_text(
            "id: CASE-BAD-FINISH\nfamily: CaseFamily\n"
            "length_mm: 320\nwidth_mm: 112\nheight_mm: 35\n"
            "wall_thickness_mm: 3.0\nprocess_id: CNC-ALU\n"
            "surface_finish: powder-coat-white\n",
            encoding="utf-8",
        )
        mfg_ctx._registry.load_collection(cases)

        with pytest.raises(AssertionError, match="powder-coat-white"):
            check_surface_finish(mfg_ctx)


class TestBuildJobReferences:
    """测试 BuildJob 引用。"""

    def test_passes(self, mfg_ctx: Context, tmp_path: Path) -> None:
        jobs = tmp_path / "build_jobs"
        jobs.mkdir()
        (jobs / "JOB-01.yaml").write_text(
            "id: JOB-01\nfamily: BuildJobFamily\n"
            "process_id: CNC-ALU\npart_id: CASE-01\nquantity: 1\n",
            encoding="utf-8",
        )
        mfg_ctx._registry.load_collection(jobs)

        check_build_job_references(mfg_ctx)

    def test_fails_missing_process(self, mfg_ctx: Context, tmp_path: Path) -> None:
        jobs = tmp_path / "build_jobs"
        jobs.mkdir()
        (jobs / "JOB-BAD.yaml").write_text(
            "id: JOB-BAD\nfamily: BuildJobFamily\n"
            "process_id: MISSING\npart_id: CASE-01\nquantity: 1\n",
            encoding="utf-8",
        )
        mfg_ctx._registry.load_collection(jobs)

        with pytest.raises(AssertionError, match="工艺 MISSING 不存在"):
            check_build_job_references(mfg_ctx)


class TestCheckerIntegration:
    """测试 Checker 运行 manufacturing 规则。"""

    def test_checker_runs_rules(self, mfg_ctx: Context) -> None:
        checker = Checker()
        checker.add_rule("DFX-002", "尺寸", check_part_fits_machine)
        checker.add_rule("DFX-003", "壁厚", check_wall_thickness)

        report = checker.run(mfg_ctx)
        assert report.passed is True
        assert report.error_count == 0
