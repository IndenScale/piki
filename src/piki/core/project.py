"""Project 类：加载 piki.toml、扫描目录。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .engine.checker import Checker, CheckReport, RuleResult, register_module_rules
from .engine.context import Context
from .engine.registry import Registry
from .models.diagnostic import Severity
from .parsing.loaders import load_toml
from .plugin import Plugin, discover_plugins

logger = logging.getLogger(__name__)


class Project:
    """piki 项目。"""

    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self.root = root
        self.config = config
        self.registry = Registry()
        self.checker = Checker()
        self._plugins: list[Plugin] = []

    @classmethod
    def discover(cls, start: Path | str | None = None) -> "Project":
        """从当前目录向上查找 piki.toml。"""
        if start is None:
            start = Path.cwd()
        else:
            start = Path(start)

        current = start.resolve()
        while True:
            candidate = current / "piki.toml"
            if candidate.exists():
                config = load_toml(candidate)
                return cls(current, config)
            if current.parent == current:
                raise FileNotFoundError(f"Could not find piki.toml from {start}")
            current = current.parent

    def load(self) -> None:
        """加载插件、型号库、实例数据。"""
        # 1. 加载插件
        plugin_classes = discover_plugins()
        enabled = self._plugin_names()
        for name in enabled:
            if name not in plugin_classes:
                raise ValueError(f"Unknown plugin: {name}")
            plugin = plugin_classes[name]()
            plugin.register_families(self.registry)
            plugin.register_rules(self.checker)
            plugin.register_generators(self.checker)
            self._plugins.append(plugin)

        # 2. 加载项目本地型号库
        self.registry.load_library(self.root / "library")

        # 3. 加载插件自带型号库
        for plugin in self._plugins:
            plugin_lib = getattr(plugin, "library_dir", None)
            if plugin_lib:
                self.registry.load_library(Path(plugin_lib))

        # 4. 扫描数据目录
        for path in sorted(self.root.iterdir()):
            if path.is_dir() and path.name != "library":
                # 简单启发式：包含 yaml 文件的目录视为集合
                if any(path.rglob("*.yaml")):
                    self.registry.load_collection(path)

        # 5. 加载项目 rules/
        rules_dir = self.root / "rules"
        if rules_dir.exists():
            self._load_project_rules(rules_dir)

    def _plugin_names(self) -> list[str]:
        plugins_config = self.config.get("plugins", {})
        enabled = plugins_config.get("enabled", [])
        if isinstance(enabled, str):
            enabled = [enabled]
        return enabled

    def _load_project_rules(self, rules_dir: Path) -> None:
        """动态导入 rules/ 下的 Python 模块，收集 @rule 装饰器。"""
        import importlib.util
        import sys

        for path in sorted(rules_dir.rglob("*.py")):
            if path.name.startswith("_"):
                continue
            module_name = f"piki_project_rules.{path.relative_to(rules_dir).with_suffix('').as_posix().replace('/', '.')}"
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to load project rule %s: %s", path, exc)
                continue
            register_module_rules(self.checker, module)

    def plugin_config(self, name: str) -> dict[str, Any]:
        plugins = self.config.get("plugins", {})
        return plugins.get(name, {})

    def make_context(self) -> Context:
        # 合并全局配置 + 插件配置作为规则 ctx.config
        base: dict[str, Any] = {}
        base.update(self.config.get("rules", {}))
        for plugin in self._plugins:
            base.update(self.plugin_config(plugin.name))
        return Context(self.registry, base)

    def enabled_generators(self) -> list[str]:
        """从 piki.toml [generators] enabled 读取启用的生成器列表。"""
        generators_config = self.config.get("generators", {})
        enabled = generators_config.get("enabled", [])
        if isinstance(enabled, str):
            enabled = [enabled]
        return enabled

    def _expand_files_filter(self, files: list[str]) -> set[str] | None:
        """将文件列表解析为绝对路径集合，并递归包含被引用的实例文件。

        当 --files 指定变更文件时，规则可能通过外键引用其他实例（如 pdu_id、
        rack_id）。本方法自动追踪这些引用关系，确保被引用的实例文件也被包含
        在过滤集合中，避免外键完整性检查误报。
        """
        if not files:
            return None

        # 1. 解析为绝对路径
        direct = {str((self.root / f).resolve()) for f in files}
        allowed = set(direct)

        # 2. 构建 id -> instance 映射
        id_map: dict[str, Any] = {}
        for inst in self.registry.all_instances().values():
            id_map[inst.id] = inst

        # 3. 递归收集被引用的实例
        changed = True
        while changed:
            changed = False
            current_instances = [
                inst
                for inst in self.registry.all_instances().values()
                if str(inst.source) in allowed
            ]
            for inst in current_instances:
                # 检查 _resolved 中的外键字段
                for field, value in inst._resolved.items():
                    if field.endswith("_id") and isinstance(value, str):
                        if value in id_map:
                            ref_source = str(id_map[value].source)
                            if ref_source not in allowed:
                                allowed.add(ref_source)
                                changed = True
                # 检查 raw 中的外键字段
                for field, value in inst.raw.items():
                    if field.endswith("_id") and isinstance(value, str):
                        if value in id_map:
                            ref_source = str(id_map[value].source)
                            if ref_source not in allowed:
                                allowed.add(ref_source)
                                changed = True

        return allowed

    def run_check(
        self,
        skip: list[str] | None = None,
        only: list[str] | None = None,
        files: list[str] | None = None,
    ) -> CheckReport:
        ctx = self.make_context()
        # 将相对路径解析为基于项目根目录的绝对路径，并扩展引用
        resolved_files = self._expand_files_filter(files)
        rules_config = self.config.get("rules", {})
        report = self.checker.run(ctx, skip=skip, only=only, files=resolved_files, rules_config=rules_config)

        # 将 Registry 收集的 Diagnostic 加入报告
        report.diagnostics.extend(self.registry.diagnostics)

        # 向后兼容：将 Schema 校验失败的实例也加入 RuleResult
        for inst in self.registry.all_instances().values():
            if inst.family == "_invalid":
                detail = inst._validation_error or "未知错误"
                report.results.append(
                    RuleResult(
                        rule_id="SCHEMA-001",
                        name="Schema 校验",
                        passed=False,
                        message=f"实例 {inst.id} Schema 校验失败: {detail}",
                        file=str(inst.source),
                    )
                )

        return report
