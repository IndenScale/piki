"""Assembly 演示项目集成测试。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from piki.core.project import Project

DEMO_ROOT = Path(__file__).parents[2] / "assembly"
DEMOS = ["sfp28-module", "fire-extinguisher", "fc-fiber-connector"]


@pytest.mark.parametrize("demo_name", DEMOS)
def test_demo_generates_json_and_usd(demo_name: str, tmp_path: Path) -> None:
    """每个 demo 都能通过 piki generate assembly-viewer 产出 JSON 与 USDA。"""
    demo_root = DEMO_ROOT / demo_name
    dist_dir = demo_root / "dist"

    # 清理旧产物，确保测试生成
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    project = Project.discover(demo_root)
    project.load()
    ctx = project.make_context()

    assert "assembly-viewer" in project.generator_registry.ids

    result = project.generator_registry.generate("assembly-viewer", ctx, {})
    assert result.success, f"Generator failed: {result.error}"

    assert (dist_dir / "scene.json").exists()
    assert (dist_dir / "scene.usda").exists()
    assert (dist_dir / "index.html").exists()
    assert (dist_dir / "viewer.js").exists()
    assert (dist_dir / "viewer.css").exists()

    # scene.json 可解析且包含实体
    data = json.loads((dist_dir / "scene.json").read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert len(data["entities"]) >= 2
    assert len(data["controls"]) >= 1


@pytest.mark.parametrize("demo_name", DEMOS)
def test_demo_passes_check(demo_name: str) -> None:
    """每个 demo 都能通过 piki check。"""
    demo_root = DEMO_ROOT / demo_name
    project = Project.discover(demo_root)
    project.load()
    report = project.run_check()

    errors = [r for r in report.results if not r.passed]
    diagnostics = [d for d in report.diagnostics if d.severity.value == "error"]
    assert not errors, f"Check errors: {errors}"
    assert not diagnostics, f"ADL diagnostics: {diagnostics}"
