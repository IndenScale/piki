"""Catalog 相关生成器集成测试（ADR-011）。"""

from __future__ import annotations

from pathlib import Path

from piki.core.project import Project


def _build_project(tmp_path: Path) -> Project:
    """构建一个带 Catalog 的最小 telecom 项目。"""
    (tmp_path / "piki.toml").write_text(
        '[project]\nname = "catalog-demo"\n\n[plugins]\nenabled = ["telecom"]\n',
        encoding="utf-8",
    )
    racks = tmp_path / "instances" / "racks"
    racks.mkdir(parents=True)
    (racks / "RACK-A01.yaml").write_text(
        "id: RACK-A01\nfamily: RackFamily\ntotal_u: 42\n",
        encoding="utf-8",
    )
    devices = tmp_path / "instances" / "devices"
    devices.mkdir(parents=True)
    (devices / "SRV-01.yaml").write_text(
        "id: SRV-01\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 10\n",
        encoding="utf-8",
    )
    models = tmp_path / "models"
    models.mkdir()
    (models / "generic-server.yaml").write_text(
        "model: generic-server\nfamily: ServerFamily\nheight_u: 2\ntdp_w: 300\n",
        encoding="utf-8",
    )
    catalogs = tmp_path / "catalogs" / "components"
    catalogs.mkdir(parents=True)
    (catalogs / "generic-server.yaml").write_text(
        "catalog_id: generic-server-catalog\n"
        "family: ComponentCatalogFamily\n"
        "manufacturer: Generic\n"
        "mpn: GENERIC-2U\n"
        "lifecycle: active\n"
        "model_ref: generic-server\n",
        encoding="utf-8",
    )

    project = Project.discover(tmp_path)
    project.load()
    return project


def test_procurement_bom_generator(tmp_path: Path) -> None:
    project = _build_project(tmp_path)
    ctx = project.make_context()

    result = project.generator_registry.generate("procurement-bom", ctx, {})
    assert result.success
    assert "Generic" in result.content
    assert "GENERIC-2U" in result.content
    assert "active" in result.content
    assert "SRV-01" in result.content
