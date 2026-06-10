"""Project 单元测试 —— 覆盖项目发现、加载、规则执行。"""

from __future__ import annotations

from pathlib import Path

import pytest

from piki.core.project import Project
from piki.core.engine.checker import rule
from piki.extensions.telecom.plugin import RackFamily, PduFamily, ServerFamily


class TestProjectDiscover:
    """测试 Project.discover 向上查找 piki.toml。"""

    def test_discover_from_child_dir(self, tmp_path: Path) -> None:
        root = tmp_path / "project"
        root.mkdir()
        (root / "piki.toml").write_text(
            '[project]\nname = "test"\n\n[plugins]\nenabled = ["telecom"]\n',
            encoding="utf-8",
        )
        child = root / "sub" / "deep"
        child.mkdir(parents=True)

        project = Project.discover(child)
        assert project.root == root
        assert project.config["project"]["name"] == "test"

    def test_discover_from_current_dir(self, tmp_path: Path) -> None:
        (tmp_path / "piki.toml").write_text(
            '[project]\nname = "here"\n\n[plugins]\nenabled = ["telecom"]\n',
            encoding="utf-8",
        )
        project = Project.discover(tmp_path)
        assert project.root == tmp_path

    def test_discover_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Could not find piki.toml"):
            Project.discover(tmp_path)


class TestProjectLoad:
    """测试 Project.load 加载数据。"""

    def test_load_telecom_plugin(self, tmp_path: Path) -> None:
        (tmp_path / "piki.toml").write_text(
            '[project]\nname = "demo"\n\n[plugins]\nenabled = ["telecom"]\n'
            '[plugins.telecom]\npower_threshold = 0.4\n',
            encoding="utf-8",
        )
        racks = tmp_path / "racks"
        racks.mkdir()
        (racks / "RACK-A01.yaml").write_text(
            "id: RACK-A01\nfamily: RackFamily\ntotal_u: 42\n",
            encoding="utf-8",
        )
        pdus = tmp_path / "pdus"
        pdus.mkdir()
        (pdus / "PDU-A.yaml").write_text(
            "id: PDU-A\nfamily: PduFamily\nrack_id: RACK-A01\ncapacity_w: 2000\n",
            encoding="utf-8",
        )

        project = Project.discover(tmp_path)
        project.load()

        assert "racks" in project.registry.list_collections()
        assert "pdus" in project.registry.list_collections()
        assert project.registry.query("racks", id="RACK-A01").first() is not None

    def test_load_unknown_plugin_raises(self, tmp_path: Path) -> None:
        (tmp_path / "piki.toml").write_text(
            '[project]\nname = "bad"\n\n[plugins]\nenabled = ["nonexistent"]\n',
            encoding="utf-8",
        )
        project = Project.discover(tmp_path)
        with pytest.raises(ValueError, match="Unknown plugin"):
            project.load()

    def test_load_project_rules(self, tmp_path: Path) -> None:
        (tmp_path / "piki.toml").write_text(
            '[project]\nname = "demo"\n\n[plugins]\nenabled = ["telecom"]\n',
            encoding="utf-8",
        )
        racks = tmp_path / "racks"
        racks.mkdir()
        (racks / "RACK-A01.yaml").write_text(
            "id: RACK-A01\nfamily: RackFamily\ntotal_u: 42\n",
            encoding="utf-8",
        )
        rules = tmp_path / "rules"
        rules.mkdir()
        (rules / "custom.py").write_text(
            "from piki.core.engine.checker import rule\n"
            "@rule('CUSTOM-001', '自定义规则')\n"
            "def custom_rule(ctx):\n"
            "    pass\n",
            encoding="utf-8",
        )

        project = Project.discover(tmp_path)
        project.load()
        rule_ids = [r[0] for r in project.checker._rules]
        assert "CUSTOM-001" in rule_ids


class TestProjectRunCheck:
    """测试 Project.run_check 端到端。"""

    def test_run_check_passes(self, tmp_path: Path) -> None:
        (tmp_path / "piki.toml").write_text(
            '[project]\nname = "demo"\n\n[plugins]\nenabled = ["telecom"]\n'
            '[plugins.telecom]\npower_threshold = 0.8\n',
            encoding="utf-8",
        )
        racks = tmp_path / "racks"
        racks.mkdir()
        (racks / "RACK-A01.yaml").write_text(
            "id: RACK-A01\nfamily: RackFamily\ntotal_u: 42\n",
            encoding="utf-8",
        )
        pdus = tmp_path / "pdus"
        pdus.mkdir()
        (pdus / "PDU-A.yaml").write_text(
            "id: PDU-A\nfamily: PduFamily\nrack_id: RACK-A01\ncapacity_w: 2000\n",
            encoding="utf-8",
        )
        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV-01.yaml").write_text(
            "id: SRV-01\nmodel: generic-server\nrack_id: RACK-A01\n"
            "position_u: 10\npdu_id: PDU-A\n",
            encoding="utf-8",
        )

        project = Project.discover(tmp_path)
        project.load()
        report = project.run_check()
        assert report.passed is True
        assert report.pass_count >= 2

    def test_run_check_fails_schema(self, tmp_path: Path) -> None:
        (tmp_path / "piki.toml").write_text(
            '[project]\nname = "demo"\n\n[plugins]\nenabled = ["telecom"]\n',
            encoding="utf-8",
        )
        racks = tmp_path / "racks"
        racks.mkdir()
        # total_u 超出范围，会导致 Schema 校验失败
        (racks / "RACK-A01.yaml").write_text(
            "id: RACK-A01\nfamily: RackFamily\ntotal_u: 100\n",
            encoding="utf-8",
        )

        project = Project.discover(tmp_path)
        project.load()
        report = project.run_check()
        assert report.passed is False
        schema_results = [r for r in report.results if r.rule_id == "SCHEMA-001"]
        assert len(schema_results) == 1
        assert "RACK-A01" in schema_results[0].message
        # 验证报告中包含具体的 pydantic 校验错误详情
        assert "total_u" in schema_results[0].message or "Input should be" in schema_results[0].message
