"""Loaders 单元测试 —— 覆盖 YAML/TOML 加载。"""

from __future__ import annotations

from pathlib import Path

import pytest
from adl.parsing.loaders import load_toml, load_yaml, save_yaml


class TestLoadYaml:
    """测试 load_yaml。"""

    def test_basic(self, tmp_path: Path) -> None:
        f = tmp_path / "test.yaml"
        f.write_text("id: test\nname: hello\n", encoding="utf-8")
        data = load_yaml(f)
        assert data == {"id": "test", "name": "hello"}

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.yaml"
        f.write_text("", encoding="utf-8")
        data = load_yaml(f)
        assert data == {}

    def test_not_dict_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "list.yaml"
        f.write_text("- a\n- b\n", encoding="utf-8")
        with pytest.raises(ValueError, match="must contain a mapping"):
            load_yaml(f)


class TestSaveYaml:
    """测试 save_yaml。"""

    def test_basic(self, tmp_path: Path) -> None:
        f = tmp_path / "out.yaml"
        save_yaml(f, {"id": "test", "name": "hello"})
        assert f.exists()
        content = f.read_text(encoding="utf-8")
        assert "id: test" in content
        assert "name: hello" in content

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        f = tmp_path / "a" / "b" / "out.yaml"
        save_yaml(f, {"x": 1})
        assert f.exists()


class TestLoadToml:
    """测试 load_toml。"""

    def test_basic(self, tmp_path: Path) -> None:
        f = tmp_path / "test.toml"
        f.write_text(
            '[project]\nname = "my-project"\nversion = "1.0.0"\n',
            encoding="utf-8",
        )
        data = load_toml(f)
        assert data["project"]["name"] == "my-project"
        assert data["project"]["version"] == "1.0.0"

    def test_plugins_section(self, tmp_path: Path) -> None:
        f = tmp_path / "piki.toml"
        f.write_text(
            '[plugins]\nenabled = ["telecom"]\n\n[plugins.telecom]\npower_threshold = 0.4\n',
            encoding="utf-8",
        )
        data = load_toml(f)
        assert data["plugins"]["enabled"] == ["telecom"]
        # TOML 中 [plugins.telecom] 是嵌套表，标准解析器会展开为 plugins -> telecom
        assert data["plugins"]["telecom"]["power_threshold"] == 0.4
