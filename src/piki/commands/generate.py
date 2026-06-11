"""piki generate — 运行生成器。

根据配置运行指定的生成器，导出 BOM、面板图、标签等产物。
"""

from __future__ import annotations

from pathlib import Path

from piki.core.project import Project


def cmd_generate(path: str | None, generator: str | None, output: str | None) -> int:
    """执行 generate 命令。

    Args:
        path: 项目目录路径，None 表示当前目录（向上扫描 piki.toml）。
        generator: 生成器 ID，None 则运行所有在 piki.toml 中启用的生成器。
        output: 输出文件路径，None 则由生成器自行决定。

    Returns:
        退出码：0 表示所有生成器成功，1 表示有生成器失败或发生错误。
    """
    try:
        project = Project.discover(path or ".")
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1

    project.load()
    ctx = project.make_context()

    gen_list = project.checker.list_generators()
    gen_map = {gid: (name, fn) for gid, name, fn in gen_list}

    if generator is None:
        # 运行所有启用的生成器
        enabled = project.enabled_generators()
        if not enabled:
            print(
                "No generators enabled. Specify a generator ID or configure [generators] enabled in piki.toml"
            )
            print("Available generators:")
            for gid, name, _fn in gen_list:
                print(f"  {gid:<20} {name}")
            return 1
        targets = enabled
    else:
        targets = [generator]

    out_path = Path(output) if output else None
    config: dict[str, str | None] = {"output": str(out_path) if out_path else None}

    failed = []
    for gen_id in targets:
        if gen_id not in gen_map:
            print(f"Unknown generator: {gen_id}")
            failed.append(gen_id)
            continue
        try:
            project.checker.generate(gen_id, ctx, config)
            if out_path:
                print(f"Generated: {out_path}")
        except Exception as exc:  # pragma: no cover
            print(f"Generator {gen_id} failed: {exc}")
            failed.append(gen_id)

    return 1 if failed else 0
