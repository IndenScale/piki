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

    # 额外目录（插件提供的型号库 / 公共 Catalog）
    extra_model_dirs: list[Path] = field(default_factory=list)
    extra_catalog_dirs: list[Path] = field(default_factory=list)

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


class DependencyCycleError(Exception):
    """Pass 依赖图中存在环。"""
    pass


class PassManager:
    """Pass 管理器。

    用法:
        pm = PassManager()
        pm.register(YAMLParsePass())
        pm.register(LoweringPass(), after=["YAMLParsePass"])
        ctx = pm.run(ctx, up_to=PassStage.HIR)

    支持：
    - 依赖声明与串行调度
    - 依赖环检测
    - 错误恢复（单个 Pass 失败后继续执行后续 Pass）
    - 命名空间级并行调度桩（当前为串行，预留 parallel=True 接口）
    """

    _STAGE_ORDER = {PassStage.AST: 0, PassStage.HIR: 1, PassStage.MIR: 2}

    def __init__(self) -> None:
        self._passes: list[tuple[Pass, set[str]]] = []  # (pass, dependencies)
        self._failed_passes: set[str] = set()

    def register(self, p: Pass, *, after: list[str] | None = None) -> None:
        """注册一个 Pass。

        Args:
            p: Pass 实例
            after: 依赖的 Pass name 列表

        Raises:
            DependencyCycleError: 注册导致依赖环。
        """
        deps = set(after) if after else set()

        # 依赖环检测：新 Pass 的依赖不能包含自身
        if p.name in deps:
            raise DependencyCycleError(
                f"Pass '{p.name}' 不能依赖自身"
            )

        # 检查是否与已注册 Pass 形成环（简化检测：BFS 反向可达）
        self._passes.append((p, deps))
        if self._detect_cycle():
            self._passes.pop()
            raise DependencyCycleError(
                f"注册 Pass '{p.name}' 导致依赖环。依赖: {sorted(deps)}"
            )

    def run(
        self,
        ctx: PassContext,
        *,
        up_to: PassStage | None = None,
        parallel: bool = False,
    ) -> PassContext:
        """按依赖顺序运行所有注册的 Pass。

        Args:
            ctx: 编译上下文
            up_to: 如果指定，只运行到此阶段（含）
            parallel: 是否启用命名空间级并行（当前为串行桩）。

        Returns:
            更新后的 PassContext。
        """
        executed: set[str] = set()
        self._failed_passes.clear()

        if parallel:
            # 命名空间级并行桩：当前仅记录意图，实际串行执行
            ctx.emit(self._make_info_diag(
                "PASS-INFO-001",
                "PassManager: parallel=True 当前为串行桩，命名空间级并行尚未实现。",
            ))

        max_iterations = len(self._passes) * 2  # 安全上限

        for _ in range(max_iterations):
            ready = self._find_ready(executed, up_to)
            if not ready:
                break
            # 取第一个就绪的 pass（多个就绪时按注册顺序）
            p, deps = ready[0]
            try:
                result = p.run(ctx)
                ctx.diagnostics.extend(result.diagnostics)
            except Exception as exc:
                # 错误恢复：记录失败，继续执行后续 Pass
                self._failed_passes.add(p.name)
                from adl.diagnostics import Diagnostic, Location, Severity
                ctx.emit(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=f"Pass '{p.name}' 执行失败: {exc}",
                        location=Location(uri=str(ctx.root)),
                        code="PASS-ERROR-001",
                        source="adl.compiler.pass_manager",
                    )
                )
            executed.add(p.name)

        # 报告未执行的 Pass（依赖未满足）
        remaining = [(p, deps) for p, deps in self._passes if p.name not in executed]
        if remaining:
            unmet = []
            for p, deps in remaining:
                missing = deps - executed
                if missing:
                    unmet.append(f"{p.name} (缺少依赖: {sorted(missing)})")
            if unmet:
                ctx.emit(self._make_info_diag(
                    "PASS-INFO-002",
                    f"以下 Pass 因依赖未满足而未执行: {'; '.join(unmet)}",
                ))

        return ctx

    def _detect_cycle(self) -> bool:
        """检测当前 Pass 图中是否存在依赖环（Kahn 算法）。"""
        # 构建入度表和邻接表
        in_degree: dict[str, int] = {}
        adj: dict[str, list[str]] = {}

        for p, deps in self._passes:
            if p.name not in in_degree:
                in_degree[p.name] = 0
            if p.name not in adj:
                adj[p.name] = []
            for dep in deps:
                adj.setdefault(dep, []).append(p.name)
                in_degree[p.name] = in_degree.get(p.name, 0) + 1
                if dep not in in_degree:
                    in_degree[dep] = 0

        # Kahn 拓扑排序
        queue = [name for name, deg in in_degree.items() if deg == 0]
        visited = 0
        while queue:
            node = queue.pop(0)
            visited += 1
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return visited != len(in_degree)

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
            if p.name in self._failed_passes:
                continue  # 已失败的 Pass 不再重试
            if up_to is not None:
                if self._STAGE_ORDER.get(p.stage, 99) > self._STAGE_ORDER.get(up_to, 99):
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
                "failed": p.name in self._failed_passes,
            }
            for p, deps in self._passes
        ]

    @property
    def has_failures(self) -> bool:
        """是否有 Pass 执行失败。"""
        return len(self._failed_passes) > 0

    @staticmethod
    def _make_info_diag(code: str, message: str):
        """创建信息级诊断。"""
        from adl.diagnostics import Diagnostic, Location, Severity
        return Diagnostic(
            severity=Severity.INFO,
            message=message,
            location=Location(uri=""),
            code=code,
            source="adl.compiler.pass_manager",
        )
