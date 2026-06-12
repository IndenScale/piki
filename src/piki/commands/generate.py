"""piki generate — 运行生成器。

根据配置运行指定的生成器，导出 BOM、面板图、标签等产物。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from piki.core.engine.generator_registry import GeneratorResult
from piki.core.project import Project


def _print_result(result: GeneratorResult) -> None:
    """格式化打印 GeneratorResult。"""
    if result.success:
        if result.content:
            print(result.content)
        if result.file_path:
            print(f"Output: {result.file_path}")
    else:
        print(f"Generator '{result.generator_id}' failed: {result.error}")


def cmd_generate(path: str | None, generator: str | None, output: str | None) -> int:
    """执行 generate 命令。

    Args:
        path: 项目目录路径，None 表示当前目录（向上扫描 piki.toml）。
        generator: 生成器 ID，None 则运行所有在 piki.toml 中启用的生成器。
        output: 输出文件路径，None 则由生成器根据 dist/ 约定自行决定。

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
    gen_registry = project.generator_registry

    gen_list = gen_registry.list_all()
    gen_map = {gid: (name, fn) for gid, name, fn in gen_list}

    if generator is None:
        # 运行所有启用的生成器
        enabled = project.enabled_generators()
        if not enabled:
            print(
                "No generators enabled. Specify a generator ID or configure "
                "[generators] enabled in piki.toml"
            )
            print("Available generators:")
            for gid, name, _fn in gen_list:
                print(f"  {gid:<20} {name}")
            return 1
        targets = enabled
    else:
        targets = [generator]

    # ── dist/ 目录解析 ──
    out_path = Path(output) if output else None
    dist_config = project.config.get("generators", {}).get("dist", {})
    dist_root = dist_config.get("root", "dist")
    dist_targets: dict[str, str] = dist_config.get("targets", {})

    # 预创建 dist/ 根目录（如果启用 dist 约定）
    if not out_path and dist_root:
        (project.root / dist_root).mkdir(parents=True, exist_ok=True)

    failed: list[str] = []
    for gen_id in targets:
        gen_entry = gen_map.get(gen_id)
        if gen_entry is None:
            print(f"Unknown generator: {gen_id}")
            failed.append(gen_id)
            continue

        gen_name, gen_fn = gen_entry

        # 构建 config：如果 --output 指定，优先级最高；
        # 否则使用 dist/ 约定路径
        config: dict[str, Any] = {}
        if out_path is not None:
            config["output"] = str(out_path)
        elif dist_root:
            config["dist_dir"] = str(project.root / dist_root)
            # 按生成器映射到场景子目录
            target_dir = dist_targets.get(gen_id, "")
            if target_dir:
                target_path = project.root / dist_root / target_dir
                target_path.mkdir(parents=True, exist_ok=True)
                config["target_dir"] = str(target_path)
        try:
            result = gen_registry.generate(gen_id, ctx, config)
            _print_result(result)
            if not result.success:
                failed.append(gen_id)
        except Exception as exc:  # pragma: no cover
            print(f"Generator {gen_id} failed: {exc}")
            failed.append(gen_id)

    return 1 if failed else 0
