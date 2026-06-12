"""端到端集成测试：验证文档中的电信机房示例。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PIKI = [sys.executable, "-m", "piki.cli"]


@pytest.fixture
def demo_project(tmp_path: Path) -> Path:
    """初始化一个 telecom 示例项目。"""
    result = subprocess.run(
        [*PIKI, "init", "--plugin", "telecom", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Initialized" in result.stdout
    return tmp_path


def _run_check(project_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*PIKI, "check", str(project_dir)],
        capture_output=True,
        text=True,
    )


def _add_device(
    project_dir: Path, inst_id: str, rack_id: str, position_u: int, pdu_id: str, tdp_w: int = 400
) -> None:
    """创建一个 Instance 文件并追加到 Layout。

    物理尺寸字段不可被 Instance 覆盖（ADR-008），应在 Model 中设置。
    """
    # Instance 文件
    inst = project_dir / "instances" / "devices" / f"{inst_id}.yaml"
    inst.write_text(
        f"id: {inst_id}\n"
        f"name: 服务器-{inst_id[-2:]}\n"
        f"model: generic-server\n"
        f"status: planned\n"
        f"tdp_w: {tdp_w}\n",
        encoding="utf-8",
    )
    # 追加 Layout entry
    layout_path = project_dir / "layouts" / "layout.yaml"
    with open(layout_path, "a", encoding="utf-8") as f:
        f.write(
            f"\n- instance: {inst_id}\n"
            f"  rack_id: {rack_id}\n"
            f"  position_u: {position_u}\n"
            f"  pdu_id: {pdu_id}\n"
        )


def test_initial_check_passes(demo_project: Path) -> None:
    result = _run_check(demo_project)
    assert result.returncode == 0
    assert "[PASS] TELECOM-POWER-001" in result.stdout
    assert "[PASS] TELECOM-RACK-001" in result.stdout


def test_pdu_overload_detected(demo_project: Path) -> None:
    _add_device(demo_project, "SRV-03", "RACK-A01", 6, "PDU-A", tdp_w=400)
    result = _run_check(demo_project)
    assert result.returncode == 1
    assert "PDU-A 负载率 47.5%" in result.stdout
    assert "超过项目阈值 40.0%" in result.stdout


def test_pdu_overload_fixed(demo_project: Path) -> None:
    _add_device(demo_project, "SRV-03", "RACK-A01", 6, "PDU-B", tdp_w=400)
    result = _run_check(demo_project)
    assert result.returncode == 0
    assert "[PASS]" in result.stdout


def test_rack_u_conflict_detected(demo_project: Path) -> None:
    _add_device(demo_project, "SRV-03", "RACK-A01", 10, "PDU-B", tdp_w=400)
    result = _run_check(demo_project)
    assert result.returncode == 1
    assert "U10-U11 冲突" in result.stdout


def test_plugins_list() -> None:
    result = subprocess.run(
        [*PIKI, "plugins", "list"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "telecom" in result.stdout


def test_json_format(demo_project: Path) -> None:
    result = subprocess.run(
        [*PIKI, "check", "--format", "json", str(demo_project)],
        capture_output=True,
        text=True,
        check=True,
    )
    import json

    data = json.loads(result.stdout)
    assert data["passed"] is True
    assert data["error_count"] == 0
    assert len(data["results"]) == 7


def test_init_refuses_overwrite(tmp_path: Path) -> None:
    """初始化已存在的项目应拒绝。"""
    (tmp_path / "piki.toml").write_text("[project]\nname = x\n", encoding="utf-8")
    result = subprocess.run(
        [*PIKI, "init", "--plugin", "telecom", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "already initialized" in result.stdout


def test_check_no_project(tmp_path: Path) -> None:
    """在没有 piki.toml 的目录运行 check 应报错。"""
    result = subprocess.run(
        [*PIKI, "check", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Could not find piki.toml" in result.stdout or "piki.toml" in result.stdout


def test_multiple_failures_reported(demo_project: Path) -> None:
    """同时触发功率和 U 位冲突，应报告两个失败。"""
    _add_device(demo_project, "SRV-03", "RACK-A01", 10, "PDU-A", tdp_w=400)
    result = _run_check(demo_project)
    assert result.returncode == 1
    assert "PDU-A 负载率" in result.stdout
    assert "U10-U11 冲突" in result.stdout


def test_version_flag() -> None:
    result = subprocess.run(
        [*PIKI, "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "piki" in result.stdout


def test_check_files_filter(demo_project: Path) -> None:
    """--files 只检查指定文件，不加载未指定文件中的实例。"""
    # 创建 SRV-03 接 PDU-A 导致功率超载
    _add_device(demo_project, "SRV-03", "RACK-A01", 6, "PDU-A", tdp_w=400)

    # 只检查 SRV-03.yaml（不指定其他文件）
    result = subprocess.run(
        [*PIKI, "check", str(demo_project), "--files", "instances/devices/SRV-03.yaml"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[PASS] TELECOM-POWER-001" in result.stdout

    # 不指定 --files，加载所有实例，功率规则应失败（950W / 2000W = 47.5%）
    result2 = subprocess.run(
        [*PIKI, "check", str(demo_project)],
        capture_output=True,
        text=True,
    )
    assert result2.returncode == 1
    assert "PDU-A 负载率" in result2.stdout
