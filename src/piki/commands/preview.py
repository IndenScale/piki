"""piki preview — 生成 USD 场景并启动预览器。"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from piki.core.project import Project


def cmd_preview(path: str | None, output: str, no_view: bool = False) -> int:
    """执行 preview 命令。

    Args:
        path: 项目目录路径，None 表示当前目录。
        output: USD 输出文件路径。
        no_view: 如果为 True，只生成文件不启动预览器。

    Returns:
        退出码：0 表示成功，1 表示失败。
    """
    try:
        project = Project.discover(path or ".")
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1

    project.load()
    ctx = project.make_context()

    # 注册 usd-scene 生成器（如果可用）
    try:
        from piki.ext.usd.generator import generate_usd_scene

        project.checker.add_generator("usd-scene", "USD 场景导出", generate_usd_scene)
    except ImportError as exc:
        print(f"Error: USD support not available. {exc}")
        print("Install with: pip install usd-core")
        return 1

    out_path = Path(output)
    config = {"output": str(out_path)}

    try:
        project.checker.generate("usd-scene", ctx, config)
    except Exception as exc:
        print(f"Error generating USD scene: {exc}")
        return 1

    if no_view:
        print(f"USD scene saved to: {out_path}")
        return 0

    # 尝试启动预览器
    usdview = shutil.which("usdview")
    if usdview:
        print(f"Launching usdview: {usdview} {out_path}")
        try:
            subprocess.run([usdview, str(out_path)], check=False)
        except KeyboardInterrupt:
            pass
        return 0

    # 回退：检查是否有浏览器可用的静态预览
    print(f"USD scene saved to: {out_path}")
    print("usdview not found in PATH. Install OpenUSD to preview.")
    print("Alternative: open the file in usdview, Blender, or Omniverse.")
    return 0
