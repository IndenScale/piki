"""Pass Pipeline — 编译 Pass 管理。

提供 Pass 抽象基类、PassContext、PassManager，
支持按阶段分组、依赖声明和串行调度。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .symbols import SymbolTable

# ---------------------------------------------------------------------------
# Pass 阶段
# ---------------------------------------------------------------------------


class PassStage(Enum):
    AST = "ast"
    HIR = "hir"
    MIR = "mir"


# ---------------------------------------------------------------------------
# PassContext
# ---------------------------------------------------------------------------


@dataclass
class PassContext:
    """编译上下文，在 Pass 之间传递。"""

    root: Path
    config: dict[str, Any] = field(default_factory=dict)
    type_system: Any = None  # TypeSystem（循环导入问题，用 Any）
    symbol_table: SymbolTable = field(default_factory=SymbolTable)

    # AST 阶段
    source_files: dict[Path, Any] = field(default_factory=dict)  # Path → SourceFile

    # HIR 阶段
    compilation: Any = None  # Compilation

    # MIR 阶段
    resolved: Any = None  # ResolvedCompilation

    # 贯穿
    diagnostics: list[Any] = field(default_factory=list)  # list[Diagnostic]

    # 额外数据
    extra: dict[str, Any] = field(default_factory=dict)

    def emit(self, diagnostic: Any) -> None:
        """添加一条诊断。"""
        self.diagnostics.append(diagnostic)


# ---------------------------------------------------------------------------
# Pass
# ---------------------------------------------------------------------------


class Pass(ABC):
    """单个编译 Pass。

    子类需实现：
    - name: Pass 标识
    - stage: 运行阶段
    - run(ctx) → PassResult
    """

    name: str
    stage: PassStage
    description: str = ""

    @abstractmethod
    def run(self, ctx: PassContext) -> PassResult:
        ...


# ---------------------------------------------------------------------------
# PassResult
# ---------------------------------------------------------------------------


@dataclass
class PassResult:
    success: bool = True
    diagnostics: list[Any] = field(default_factory=list)
    modified: bool = False
    artifacts: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# PassManager
# ---------------------------------------------------------------------------


class PassManager:
    """Pass 管理器。

    用法:
        pm = PassManager()
        pm.register(YAMLParsePass())
        pm.register(LoweringPass(), after=["YAMLParsePass"])
        ctx = pm.run(ctx, up_to=PassStage.HIR)
    """

    def __init__(self) -> None:
        self._passes: list[tuple[Pass, set[str]]] = []  # (pass, dependencies)

    def register(self, p: Pass, *, after: list[str] | None = None) -> None:
        """注册一个 Pass。

        Args:
            p: Pass 实例
            after: 依赖的 Pass name 列表
        """
        deps = set(after) if after else set()
        self._passes.append((p, deps))

    def run(
        self,
        ctx: PassContext,
        *,
        up_to: PassStage | None = None,
    ) -> PassContext:
        """按依赖顺序运行所有注册的 Pass。

        Args:
            ctx: 编译上下文
            up_to: 如果指定，只运行到此阶段（含）
        """
        executed: set[str] = set()

        while True:
            ready = self._find_ready(executed, up_to)
            if not ready:
                break
            # 取第一个就绪的 pass（多个就绪时按注册顺序）
            p, deps = ready[0]
            result = p.run(ctx)
            ctx.diagnostics.extend(result.diagnostics)
            executed.add(p.name)

        return ctx

    def _find_ready(
        self,
        executed: set[str],
        up_to: PassStage | None,
    ) -> list[tuple[Pass, set[str]]]:
        """找出所有依赖已满足、且阶段不超过 up_to 的 Pass。"""
        ready: list[tuple[Pass, set[str]]] = []
        for p, deps in self._passes:
            if p.name in executed:
                continue
            if up_to is not None:
                # 阶段顺序：AST < HIR < MIR
                stage_order = {PassStage.AST: 0, PassStage.HIR: 1, PassStage.MIR: 2}
                if stage_order.get(p.stage, 99) > stage_order.get(up_to, 99):
                    continue
            if deps <= executed:
                ready.append((p, deps))
        return ready

    def list_passes(self) -> list[dict[str, Any]]:
        return [
            {
                "name": p.name,
                "stage": p.stage.value,
                "description": p.description,
                "dependencies": sorted(deps),
            }
            for p, deps in self._passes
        ]
