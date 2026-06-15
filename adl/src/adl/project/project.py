"""ADL 项目模型。

Project 是 ADL 加载器返回的核心对象，包含一个项目（含嵌套子项目）的完整声明数据：
Instance、Model、Layout、Mate、Catalog 以及加载过程中产生的 Diagnostic。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from adl.diagnostics import Diagnostic
from adl.models import CatalogEntry, Layout, MateGraph, MateSpec, Model, ResolvedInstance
from adl.types import TypeRegistry


@dataclass
class Project:
    """一个 ADL 项目（支持嵌套子项目）。"""

    root: Path
    config: dict[str, Any]
    type_registry: TypeRegistry

    # 数据
    instances: dict[str, ResolvedInstance] = field(default_factory=dict)
    collections: dict[str, dict[str, ResolvedInstance]] = field(default_factory=dict)
    models: dict[str, Model] = field(default_factory=dict)
    layout: Layout | None = None
    mates: list[MateSpec] = field(default_factory=list)
    mate_graph: MateGraph = field(default_factory=MateGraph)
    catalogs: dict[str, CatalogEntry] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    # 嵌套项目
    parent: Project | None = None
    children: dict[str, Project] = field(default_factory=dict)

    # 元数据
    project_name: str = ""
    allowed_tags: set[str] = field(default_factory=set)
    externals: dict[str, Path] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # 查询辅助
    # ------------------------------------------------------------------

    def find_instance(self, instance_id: str) -> ResolvedInstance | None:
        """在项目树中按简单 ID 查找 Instance。"""
        if instance_id in self.instances:
            return self.instances[instance_id]
        if self.parent:
            return self.parent.find_instance(instance_id)
        return None

    def find_model(self, model_id: str) -> Model | None:
        """在项目树中按 ID 查找 Model。"""
        if model_id in self.models:
            return self.models[model_id]
        if self.parent:
            return self.parent.find_model(model_id)
        return None

    def find_catalog(self, catalog_id: str) -> CatalogEntry | None:
        """在当前项目及祖先项目中按 ID 查找 CatalogEntry。"""
        current: Project | None = self
        while current is not None:
            entry = current.catalogs.get(catalog_id)
            if entry is not None:
                return entry
            current = current.parent
        return None

    def find_catalog_by_model(self, model_ref: str) -> CatalogEntry | None:
        """按 model_ref 从当前项目及祖先项目中查找生效的 CatalogEntry。

        来源优先级：Project > Parent > Enterprise > Public。
        """
        priority = {"project": 0, "parent": 1, "enterprise": 2, "public": 3}
        candidates: list[tuple[CatalogEntry, int]] = []
        current: Project | None = self
        distance = 0
        while current is not None:
            for entry in current.catalogs.values():
                if entry.model_ref == model_ref:
                    if distance == 0:
                        candidates.append((entry, distance))
                    else:
                        candidates.append(
                            (
                                CatalogEntry(
                                    id=entry.id,
                                    family=entry.family,
                                    source="parent",
                                    model_ref=entry.model_ref,
                                    data=entry.data,
                                    source_path=entry.source_path,
                                ),
                                distance,
                            )
                        )
            current = current.parent
            distance += 1

        if not candidates:
            return None

        candidates.sort(key=lambda x: (priority.get(x[0].source, 99), x[1]))
        return candidates[0][0]

    def all_instances_tree(self) -> dict[str, ResolvedInstance]:
        """返回当前项目及所有祖先项目中的 Instance（简单 ID）。"""
        result: dict[str, ResolvedInstance] = {}
        if self.parent:
            result.update(self.parent.all_instances_tree())
        result.update(self.instances)
        return result

    def all_models_tree(self) -> dict[str, Model]:
        """返回当前项目及所有祖先项目中的 Model。"""
        result: dict[str, Model] = {}
        if self.parent:
            result.update(self.parent.all_models_tree())
        result.update(self.models)
        return result

    def all_instances_with_fqid(self) -> dict[str, ResolvedInstance]:
        """返回所有 Instance 的全限定 ID 映射。"""
        result: dict[str, ResolvedInstance] = {}
        if self.parent:
            result.update(self.parent.all_instances_with_fqid())
        for iid, inst in self.instances.items():
            result[self.fqid(iid)] = inst
        return result

    def fqid(self, instance_id: str) -> str:
        """返回 Instance 的全限定 ID。"""
        parts: list[str] = []
        parent_prefix = self._build_parent_prefix()
        if parent_prefix:
            parts.append(parent_prefix)
        if self.project_name:
            parts.append(self.project_name)
        parts.append(instance_id)
        return "/".join(parts)

    def _build_parent_prefix(self) -> str:
        """构建祖先项目前缀（不含当前项目名）。"""
        if self.parent is None:
            return ""
        parts: list[str] = []
        grand_prefix = self.parent._build_parent_prefix()
        if grand_prefix:
            parts.append(grand_prefix)
        if self.parent.project_name:
            parts.append(self.parent.project_name)
        return "/".join(parts)
