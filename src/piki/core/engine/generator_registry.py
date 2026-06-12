"""GeneratorRegistry：独立的生成器注册与执行引擎。

从 Checker 中分离 Generator 管理，单一职责。
引入结构化的 GeneratorResult 以支持 SDK 调用。
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .context import Context

# ---------------------------------------------------------------------------
# Generator 结果类型
# ---------------------------------------------------------------------------


@dataclass
class GeneratorResult:
    """生成器执行结果 —— 结构化返回值。

    替代 side-effect（print / 写文件），让 SDK 调用者可以
    程序化消费生成器输出，再自行决定如何呈现。
    """

    generator_id: str
    """生成器 ID，如 'bom-csv'。"""

    generator_name: str
    """生成器显示名称，如 'BOM CSV 导出'。"""

    success: bool
    """生成是否成功。"""

    content: str = ""
    """文本产物（CSV / 面板图文本等）。"""

    file_path: Path | None = None
    """如果写入了文件，返回文件路径。"""

    content_type: str = "text/plain"
    """内容 MIME 类型提示（如 'text/csv'）。"""

    error: str = ""
    """失败时的错误信息。"""

    @classmethod
    def ok(
        cls,
        generator_id: str,
        generator_name: str,
        content: str,
        file_path: Path | None = None,
        content_type: str = "text/plain",
    ) -> "GeneratorResult":
        return cls(
            generator_id=generator_id,
            generator_name=generator_name,
            success=True,
            content=content,
            file_path=file_path,
            content_type=content_type,
        )

    @classmethod
    def fail(
        cls,
        generator_id: str,
        generator_name: str,
        error: str,
    ) -> "GeneratorResult":
        return cls(
            generator_id=generator_id,
            generator_name=generator_name,
            success=False,
            error=error,
        )


# ---------------------------------------------------------------------------
# 函数签名
# ---------------------------------------------------------------------------

GenFunc = Callable[[Context, dict[str, Any]], None]
"""生成器函数签名（传统 side-effect 模式，向后兼容）。"""

GenFuncV2 = Callable[[Context, dict[str, Any]], GeneratorResult]
"""生成器函数签名（新模式：返回 GeneratorResult）。"""


# ---------------------------------------------------------------------------
# 装饰器
# ---------------------------------------------------------------------------

_GEN_ATTR = "__piki_gen_meta__"


def generator(gen_id: str, name: str) -> Callable[[GenFunc], GenFunc]:
    """标记一个函数为 piki 生成器。

    装饰器将元数据附加到函数对象上，不写入全局列表。
    register_module_rules 会扫描模块中所有带有该标记的函数。
    """

    def decorator(func: GenFunc) -> GenFunc:
        setattr(func, _GEN_ATTR, (gen_id, name))
        return func

    return decorator


# ---------------------------------------------------------------------------
# GeneratorRegistry
# ---------------------------------------------------------------------------


class GeneratorRegistry:
    """生成器注册表 —— 管理生成器的注册、发现、执行。

    从 Checker 中独立出来，单一职责。
    """

    def __init__(self) -> None:
        self._generators: dict[str, tuple[str, GenFunc]] = {}

    # ── 注册 ──

    def register(self, gen_id: str, name: str, func: GenFunc) -> None:
        """注册一个生成器。

        Args:
            gen_id: 生成器唯一 ID。
            name: 显示名称。
            func: 生成器函数 (Context, dict) -> None 或 -> GeneratorResult。
        """
        self._generators[gen_id] = (name, func)

    def register_many(self, *specs: tuple[str, str, GenFunc]) -> None:
        """批量注册生成器。"""
        for gen_id, name, func in specs:
            self.register(gen_id, name, func)

    def register_from_module(self, module: Any) -> None:
        """从模块中扫描 @generator 装饰器并注册。

        Args:
            module: Python 模块对象。
        """
        if module is None:
            return

        for _name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj):
                gen_meta = getattr(obj, _GEN_ATTR, None)
                if gen_meta is not None:
                    gen_id, name = gen_meta
                    self.register(gen_id, name, obj)

    # ── 查询 ──

    def list_all(self) -> list[tuple[str, str, GenFunc]]:
        """列出所有已注册的生成器 (id, name, func)。"""
        return [(gid, name, fn) for gid, (name, fn) in self._generators.items()]

    def get(self, gen_id: str) -> tuple[str, GenFunc] | None:
        """获取指定生成器的 (name, func)，不存在返回 None。"""
        entry = self._generators.get(gen_id)
        if entry is None:
            return None
        return entry

    def has(self, gen_id: str) -> bool:
        """检查生成器是否已注册。"""
        return gen_id in self._generators

    @property
    def ids(self) -> list[str]:
        """所有已注册的生成器 ID 列表。"""
        return list(self._generators.keys())

    # ── 执行 ──

    def generate(
        self,
        gen_id: str,
        ctx: Context,
        config: dict[str, Any],
    ) -> GeneratorResult:
        """执行一个生成器，返回结构化的 GeneratorResult。

        同时支持旧模式（return None / side-effect）和新模式（return GeneratorResult）。
        旧模式下，生成器通过 print 或写文件产生输出，此时 GeneratorResult.content 为空，
        仅用 success=True 表示执行成功。
        """
        entry = self.get(gen_id)
        if entry is None:
            return GeneratorResult.fail(gen_id, gen_id, f"Unknown generator: {gen_id}")

        name, func = entry
        try:
            result = func(ctx, config)

            # 新模式：返回了 GeneratorResult
            if isinstance(result, GeneratorResult):
                # 补全缺失的 ID/name 字段
                if not result.generator_id:
                    result.generator_id = gen_id
                if not result.generator_name:
                    result.generator_name = name
                return result

            # 旧模式：返回 None（side-effect 如 print / 写文件）
            return GeneratorResult.ok(gen_id, name, "", content_type="application/octet-stream")

        except Exception as exc:
            return GeneratorResult.fail(gen_id, name, str(exc))


# ---------------------------------------------------------------------------
# 向后兼容：重导出到 checker 使用
# ---------------------------------------------------------------------------


# 保留 register_module_rules 作为 delegate
def register_module_rules(registry: "GeneratorRegistry | Any", module: Any) -> None:
    """扫描模块中的 @generator 并注册到 GeneratorRegistry。

    同时支持传入 Checker（向后兼容），此时委托给 Checker 的 GeneratorRegistry。
    """
    # 延迟导入避免循环
    from .checker import Checker

    if isinstance(registry, Checker):
        registry.generator_registry.register_from_module(module)
    elif isinstance(registry, GeneratorRegistry):
        registry.register_from_module(module)
