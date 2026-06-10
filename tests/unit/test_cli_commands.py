"""CLI 命令单元测试 —— 直接调用命令函数，不经过 subprocess。"""

from __future__ import annotations

from pathlib import Path

import pytest

from piki.commands.init import cmd_init
from piki.commands.check import cmd_check
from piki.commands.plugins import cmd_plugins_list


class TestCmdInit:
    """测试 piki init 命令。"""

    def test_init_creates_project(self, tmp_path: Path) -> None:
        target = tmp_path / "new-project"
        ret = cmd_init(str(target), "telecom")
        assert ret == 0
        assert (target / "piki.toml").exists()
        assert (target / ".gitignore").exists()

    def test_init_refuses_overwrite(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        (tmp_path / "piki.toml").write_text("[project]\nname = x\n", encoding="utf-8")
        ret = cmd_init(str(tmp_path), "telecom")
        assert ret == 1
        out = capsys.readouterr().out
        assert "already initialized" in out

    def test_init_unknown_plugin(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        ret = cmd_init(str(tmp_path), "nonexistent")
        assert ret == 1
        out = capsys.readouterr().out
        assert "Unknown plugin" in out


class TestCmdCheck:
    """测试 piki check 命令。"""

    def test_check_passes(self, tmp_path: Path) -> None:
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

        ret = cmd_check(str(tmp_path), "human")
        assert ret == 0

    def test_check_no_project(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        ret = cmd_check(str(tmp_path), "human")
        assert ret == 1
        out = capsys.readouterr().out
        assert "piki.toml" in out

    def test_check_json_format(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
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

        ret = cmd_check(str(tmp_path), "json")
        assert ret == 0
        out = capsys.readouterr().out
        assert '"passed": true' in out


class TestCmdPluginsList:
    """测试 piki plugins list 命令。"""

    def test_list_plugins(self, capsys: pytest.CaptureFixture[str]) -> None:
        ret = cmd_plugins_list()
        assert ret == 0
        out = capsys.readouterr().out
        assert "telecom" in out
