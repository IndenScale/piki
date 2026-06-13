"""Project 类：加载 piki.toml、扫描目录、管理嵌套项目。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .engine.checker import Checker, CheckReport, RuleResult, register_module_rules
from .engine.context import Context
from .engine.generator_registry import GeneratorRegistry
from .engine.registry import Registry
from .parsing.loaders import load_toml
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

        # 从父项目继承 Registry
        if parent:
            self.registry.set_parent(parent.registry)
        # 设置项目名称用于 FQID
        project_name = config.get("project", {}).get("name", root.name)
        self.registry.set_project_name(project_name)

    # ------------------------------------------------------------------
    # 发现与工厂
    # ------------------------------------------------------------------

    @classmethod
    def discover(
        cls,
        start: Path | str | None = None,
        recurse: bool = True,
    ) -> "Project":
        """从当前目录向上查找 piki.toml。

        Args:
            start: 起始目录，默认为当前工作目录
            recurse: 是否递归加载子项目
        """
        if start is None:
            start = Path.cwd()
        else:
            start = Path(start)

        current = start.resolve()
        while True:
            candidate = current / "piki.toml"
            if candidate.exists():
                config = load_toml(candidate)
                project = cls(current, config)
                if recurse:
                    project._discover_children()
                return project
            if current.parent == current:
                raise FileNotFoundError(f"Could not find piki.toml from {start}")
            current = current.parent

    def _discover_children(self) -> None:
        """递归发现子项目目录。

        子项目是含有 piki.toml 且不是当前项目根的直接子目录。
        """
        for entry in sorted(self.root.iterdir()):
            if not entry.is_dir():
                continue
            child_toml = entry / "piki.toml"
            if not child_toml.exists():
                continue
            # 跳过特殊目录
            if entry.name in (
                "models",
                "instances",
                "layouts",
                "rules",
                ".git",
                "__pycache__",
                ".piki",
            ):
                continue
            try:
                child_config = load_toml(child_toml)
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
        """加载插件、型号库、Catalog、实例数据、Layout。"""
        self._load_plugins()
        self._load_models()
        self._load_catalogs()  # Catalog 必须在 Instance 之前加载（ADR-011）
        self._load_layout()  # Layout 必须在 Instance 之前加载（_resolve 依赖它）
        self._load_instances()
        self._load_mates()
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
            plugin.register_families(self.registry)
            plugin.register_rules(self.checker)
            plugin.register_generators(self.checker)
            self._plugins.append(plugin)

    def _load_models(self) -> None:
        """加载项目本地型号库和插件型号库。"""
        # 项目本地型号库
        self.registry.load_models(self.root / "models")
        # 插件自带型号库
        for plugin in self._plugins:
            plugin_lib = getattr(plugin, "model_dir", None)
            if plugin_lib:
                self.registry.load_models(Path(plugin_lib))

    def _load_catalogs(self) -> None:
        """加载项目本地 Catalog、企业 Catalog、插件公共 Catalog（ADR-011）。

        来源优先级：Project > Parent > Enterprise > Public。
        父项目 Catalog 通过 Registry.set_parent() 自动继承。
        """
        # 1. 项目本地 catalogs/（source=project）
        self.registry.load_catalogs(self.root, source="project")

        # 2. 企业 Catalog（source=enterprise）
        catalogs_config = self.config.get("catalogs", {})
        enterprise_path = catalogs_config.get("enterprise")
        if isinstance(enterprise_path, str):
            self.registry.load_catalogs(Path(enterprise_path), source="enterprise")

        # 3. 插件公共 Catalog（source=public）
        for plugin in self._plugins:
            catalog_dir = getattr(plugin, "catalog_dir", None)
            if catalog_dir:
                self.registry.load_catalogs(Path(catalog_dir), source="public")

    def _load_instances(self) -> None:
        """扫描 instances/ 目录，子目录作为独立集合加载。

        结构：
          instances/
            devices/           → collection "devices"
            racks/             → collection "racks"
            pdus/              → collection "pdus"
            containers/        → collection "containers"
            equipment/         → collection "equipment"
            power/             → collection "power"
            connections/       → collection "connections"
          instances/srv.yaml   → collection "devices" (裸文件)
        """
        instances_dir = self.root / "instances"
        if not instances_dir.exists():
            return

        has_subdirs = False
        for entry in sorted(instances_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                if any(entry.rglob("*.yaml")):
                    self.registry.load_collection(entry, collection_name=entry.name)
                    has_subdirs = True

        if not has_subdirs:
            raise FileNotFoundError(
                "instances/ 目录下没有子目录。请按类型创建子目录，"
                "例如 instances/devices/、instances/racks/、instances/pdus/"
            )

    def _load_mates(self) -> None:
        """扫描 mates/ 目录、加载 Mate 定义、构建 MateGraph。"""
        self.registry.load_mates(self.root)
        if self.registry.mates:
            logger.debug(
                "Loaded %d mate(s) across %d type(s)",
                len(self.registry.mates),
                len(self.registry.mate_types),
            )
        # 插件注册 Mate types
        for plugin in self._plugins:
            try:
                register_fn = getattr(plugin, "register_mate_types", None)
                if register_fn:
                    register_fn(self.registry)
            except Exception as exc:
                logger.warning(
                    "Failed to register mate types from plugin %s: %s",
                    getattr(plugin, "name", plugin.__class__.__name__),
                    exc,
                )

    def _load_layout(self) -> None:
        """加载项目 Layout 文件。"""
        layout = self.registry.load_layout(self.root)
        if layout is None:
            logger.debug("No layout file found in %s", self.root)

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
        """从 piki.toml 读取允许的 Tag 键和外部项目注册。"""
        tag_config = self.config.get("tags", {})
        allowed = tag_config.get("allowed", [])
        if isinstance(allowed, list):
            self.registry.set_allowed_tags(allowed)

        # 加载外部项目注册（ADR-001）
        externals_config = self.config.get("external", {})
        if isinstance(externals_config, dict):
            for alias, path_str in externals_config.items():
                if isinstance(path_str, str):
                    self.registry.register_external(alias, Path(path_str))

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
    def generator_registry(self) -> GeneratorRegistry:
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
    ) -> CheckReport:
        """运行检查。

        Args:
            skip: 跳过的规则 ID 列表
            only: 仅运行的规则 ID 列表
            files: 仅检查的文件列表
            recurse: 是否递归检查子项目
        """
        ctx = self.make_context()
        resolved_files = self._expand_files_filter(files)
        rules_config = self.config.get("rules", {})
        report = self.checker.run(
            ctx,
            skip=skip,
            only=only,
            files=resolved_files,
            rules_config=rules_config,
        )

        # 收集 Registry 诊断
        report.diagnostics.extend(self.registry.diagnostics)

        # 收集 Schema 校验失败的实例
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
