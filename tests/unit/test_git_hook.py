"""Git pre-commit hook 单元测试。"""

from __future__ import annotations

from pathlib import Path

from piki.commands.init import _install_git_hook


class TestInstallGitHook:
    """测试 pre-commit hook 安装。"""

    def test_installs_hook_when_git_exists(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir()

        _install_git_hook(tmp_path)

        hook = hooks_dir / "pre-commit"
        assert hook.exists()
        assert hook.stat().st_mode & 0o111  # 可执行
        content = hook.read_text(encoding="utf-8")
        assert "piki check" in content

    def test_skips_when_no_git(self, tmp_path: Path) -> None:
        _install_git_hook(tmp_path)
        assert not (tmp_path / ".git" / "hooks" / "pre-commit").exists()

    def test_does_not_overwrite_existing(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir()
        hook = hooks_dir / "pre-commit"
        hook.write_text("existing hook", encoding="utf-8")

        _install_git_hook(tmp_path)

        assert hook.read_text(encoding="utf-8") == "existing hook"
