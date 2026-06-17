"""Compilation.compile() — 编译器入口。

提供与现有 ProjectLoader.load() 平行的 API。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .hir import Compilation
from .pass_manager import PassContext, PassManager, PassStage
from .passes.back_compat import BackCompatEmitPass
from .passes.lowering import LoweringPass
from .passes.mate_sugar import MateSugarResolvePass
from .passes.toml_parse import TOMLParsePass
from .passes.yaml_parse import YAMLParsePass
from .symbols import SymbolTable
from .type_system import TypeSystem


def compile_project(
    root: Path,
    type_system: TypeSystem | None = None,
    *,
    extra_model_dirs: list[Path] | None = None,
    extra_catalog_dirs: list[Path] | None = None,
    up_to: PassStage = PassStage.HIR,
) -> tuple[Compilation | None, list[Any]]:
    """编译一个 ADL 项目。

    Args:
        root: 项目根目录
        type_system: 类型系统（可选，用于 Family 校验）
        up_to: 编译到此阶段为止

    Returns:
        (compilation, diagnostics)
    """
    ctx = PassContext(
        root=root,
        type_system=type_system or TypeSystem(),
        symbol_table=SymbolTable(),
    )

    pm = PassManager()
    pm.register(TOMLParsePass())
    pm.register(YAMLParsePass(), after=["toml-parse"])
    pm.register(LoweringPass(), after=["yaml-parse", "toml-parse"])
    pm.register(MateSugarResolvePass(), after=["lowering"])
    pm.register(BackCompatEmitPass(), after=["mate-sugar-resolve"])

    ctx = pm.run(ctx, up_to=up_to)
    return ctx.compilation, ctx.diagnostics


def compile_and_get_project(
    root: Path,
    type_registry: Any = None,
) -> Any:
    """便捷方法：编译项目并返回向后兼容的 Project 对象。"""
    ts = TypeSystem.from_type_registry(type_registry) if type_registry else TypeSystem()
    ctx = PassContext(
        root=root,
        type_system=ts,
        symbol_table=SymbolTable(),
    )
    pm = PassManager()
    pm.register(TOMLParsePass())
    pm.register(YAMLParsePass(), after=["toml-parse"])
    pm.register(LoweringPass(), after=["yaml-parse", "toml-parse"])
    pm.register(MateSugarResolvePass(), after=["lowering"])
    pm.register(BackCompatEmitPass(), after=["mate-sugar-resolve"])
    pm.run(ctx)
    return ctx.extra.get("project")
