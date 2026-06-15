"""Project 类：piki 编排入口。

piki 不再直接解析 YAML 或合并 Model/Instance。这些工作交给 ``adl.project.ProjectLoader``。
piki 的职责是：
1. 发现插件
2. 让插件向 ADL 注册类型
3. 调用 ADL 加载项目
4. 让插件向 piki 注册规则和生成器
5. 运行规则 / 生成器
6. 格式化报告
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from adl.project import ProjectLoader
from adl.types import TypeRegistry
from adl.validation import ADLValidator

from .engine.checker import Checker, register_module_rules
from .engine.context import Context
from .engine.registry import Registry
from .plugin import Plugin, discover_plugins

logger = logging.getLogger(__name__)


class Project:
    """piki 项目，支持嵌套（ADR-001）。"""

    def __init__(
        self,
        root: Path,
        config: dict[str, Any],
        parent: "Project | None" = None,
    ) -> None:
        self.root = root
        self.config = config
        self.registry = Registry()
        self.checker = Checker()
        self._plugins: list[Plugin] = []
        self._parent = parent
        self._children: dict[str, "Project"] = {}

        # 设置项目名称用于 FQID
        project_name = config.get("project", {}).get("name", root.name)
        self.registry.set_project_name(project_name)
        if parent:
            self.registry.set_parent(parent.registry)

    # ------------------------------------------------------------------
    # 发现与工厂
    # ------------------------------------------------------------------

    @classmethod
    def discover(
        cls,
        start: Path | str | None = None,
        recurse: bool = True,
    ) -> "Project":
        """从当前目录向上查找 piki.toml。"""
        if start is None:
            start = Path.cwd()
        else:
            start = Path(start)

        current = start.resolve()
        while True:
            candidate = current / "piki.toml"
            if candidate.exists():
                config = ProjectLoader._load_config(current)
                project = cls(current, config)
                if recurse:
                    project._discover_children()
                return project
            if current.parent == current:
                raise FileNotFoundError(f"Could not find piki.toml from {start}")
            current = current.parent

    def _discover_children(self) -> None:
        """递归发现子项目目录。"""
        for entry in sorted(self.root.iterdir()):
            if not entry.is_dir():
                continue
            child_toml = entry / "piki.toml"
            if not child_toml.exists():
                continue
            if entry.name in (
                "models",
                "instances",
                "layouts",
                "rules",
                "mates",
                ".git",
                "__pycache__",
                ".piki",
            ):
                continue
            try:
                child_config = ProjectLoader._load_config(entry)
                child_project = Project(
                    root=entry,
                    config=child_config,
                    parent=self,
                )
                child_project._discover_children()
                self._children[entry.name] = child_project
            except Exception as exc:
                logger.warning("Failed to load sub-project %s: %s", entry.name, exc)

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------

    def load(self) -> None:
        """加载插件、型号库、Catalog、实例数据、Layout、Mate。"""
        self._load_plugins()
        self._load_project_data()
        self._load_rules()
        self._load_tag_config()
        # 加载子项目
        for child in self._children.values():
            child.load()

    def _load_plugins(self) -> None:
        plugin_classes = discover_plugins()
        enabled = self._plugin_names()
        for name in enabled:
            if name not in plugin_classes:
                raise ValueError(f"Unknown plugin: {name}")
            plugin = plugin_classes[name]()
            self._plugins.append(plugin)

    def _load_project_data(self) -> None:
        """通过 ADL ProjectLoader 加载项目数据。"""
        type_registry = TypeRegistry()

        # 插件注册 ADL 类型
        for plugin in self._plugins:
            plugin.register_types(type_registry)

        extra_model_dirs: list[Path] = []
        extra_catalog_dirs: list[Path] = []
        for plugin in self._plugins:
            model_dir = getattr(plugin, "model_dir", None)
            if model_dir:
                extra_model_dirs.append(Path(model_dir))
            catalog_dir = getattr(plugin, "catalog_dir", None)
            if catalog_dir:
                extra_catalog_dirs.append(Path(catalog_dir))

        self.registry.load_project(
            root=self.root,
            type_registry=type_registry,
            config=self.config,
            extra_model_dirs=extra_model_dirs,
            extra_catalog_dirs=extra_catalog_dirs,
        )

        # 插件注册规则和生成器
        for plugin in self._plugins:
            plugin.register_rules(self.checker)
            plugin.register_generators(self.checker)

    def _load_rules(self) -> None:
        """加载项目 rules/ 目录下的 Python 规则。"""
        rules_dir = self.root / "rules"
        if rules_dir.exists():
            self._load_project_rules(rules_dir)

        # 从父项目继承规则
        if self._parent:
            for rule_id, name, prio, severity, func in self._parent.checker._rules:
                if not any(r[0] == rule_id for r in self.checker._rules):
                    self.checker.add_rule(rule_id, name, func, prio, severity)

    def _load_tag_config(self) -> None:
        """从 piki.toml 读取允许的 Tag 键。"""
        tag_config = self.config.get("tags", {})
        allowed = tag_config.get("allowed", [])
        if isinstance(allowed, list):
            self.registry.set_allowed_tags(allowed)

    def _plugin_names(self) -> list[str]:
        plugins_config = self.config.get("plugins", {})
        enabled = plugins_config.get("enabled", [])
        if isinstance(enabled, str):
            enabled = [enabled]
        return enabled

    def _load_project_rules(self, rules_dir: Path) -> None:
        import importlib.util
        import sys

        for path in sorted(rules_dir.rglob("*.py")):
            if path.name.startswith("_"):
                continue
            module_name = (
                f"piki_project_rules."
                f"{path.relative_to(rules_dir).with_suffix('').as_posix().replace('/', '.')}"
            )
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            except Exception as exc:
                logger.warning("Failed to load project rule %s: %s", path, exc)
                continue
            register_module_rules(self.checker, module)

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------

    @property
    def parent(self) -> "Project | None":
        return self._parent

    @property
    def children(self) -> dict[str, "Project"]:
        return dict(self._children)

    @property
    def generator_registry(self):
        """获取项目的 GeneratorRegistry 实例。"""
        return self.checker.generator_registry

    def plugin_config(self, name: str) -> dict[str, Any]:
        plugins = self.config.get("plugins", {})
        return plugins.get(name, {})

    def make_context(self) -> Context:
        base: dict[str, Any] = {}
        base.update(self.config.get("rules", {}))
        for plugin in self._plugins:
            base.update(self.plugin_config(plugin.name))
        return Context(self.registry, base)

    def enabled_generators(self) -> list[str]:
        generators_config = self.config.get("generators", {})
        enabled = generators_config.get("enabled", [])
        if isinstance(enabled, str):
            enabled = [enabled]
        return enabled

    # ------------------------------------------------------------------
    # 检查
    # ------------------------------------------------------------------

    def _expand_files_filter(self, files: list[str]) -> set[str] | None:
        if not files:
            return None
        direct = {str((self.root / f).resolve()) for f in files}
        allowed = set(direct)
        id_map: dict[str, Any] = {}
        for inst in self.registry.all_instances().values():
            id_map[inst.id] = inst

        changed = True
        while changed:
            changed = False
            current_instances = [
                inst
                for inst in self.registry.all_instances().values()
                if str(inst.source) in allowed
            ]
            for inst in current_instances:
                for field, value in inst._resolved.items():
                    if field.endswith("_id") and isinstance(value, str):
                        if value in id_map:
                            ref_source = str(id_map[value].source)
                            if ref_source not in allowed:
                                allowed.add(ref_source)
                                changed = True
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
        recurse: bool = True,
    ) -> Any:
        """运行检查。

        流程：
        1. ADL 层验证（引用完整性、Mate 约束等）
        2. piki 插件规则
        3. 收集 Registry 诊断和 Schema 失败实例
        """
        from .engine.checker import CheckReport, RuleResult

        ctx = self.make_context()
        resolved_files = self._expand_files_filter(files)
        rules_config = self.config.get("rules", {})

        report = CheckReport()

        # 1. ADL 层验证
        if self.registry.project is not None:
            adl_validator = ADLValidator(self.registry.project)
            report.diagnostics.extend(adl_validator.validate())

        # 2. 插件规则
        rule_report = self.checker.run(
            ctx,
            skip=skip,
            only=only,
            files=resolved_files,
            rules_config=rules_config,
        )
        report.results.extend(rule_report.results)
        report.diagnostics.extend(rule_report.diagnostics)

        # 3. Registry 诊断
        report.diagnostics.extend(self.registry.diagnostics)

        # 4. Schema 校验失败的实例
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

        # 递归检查子项目
        if recurse:
            for child in self._children.values():
                child_report = child.run_check(
                    skip=skip,
                    only=only,
                    files=None,
                    recurse=True,
                )
                report.results.extend(child_report.results)
                report.diagnostics.extend(child_report.diagnostics)

        return report
