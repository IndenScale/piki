"""Context：规则运行时数据访问。

支持：
- 集合查询（query）
- Layout 查询（layout）
- Mating 图遍历（mated_children, mated_parents, mated_chain）
- Tag 过滤（tags__discipline=hvac）
- 跨项目 Instance 查找
"""

from __future__ import annotations

from typing import Any

from adl.diagnostics import Location, RelatedInformation
from adl.models import Layout, LayoutEntry, MateGraph, MateSpec, Transform, parse_mate_ref

from .query import QuerySet, make_query_set
from .registry import Registry


class Context:
    """规则函数通过 Context 访问数据和配置。"""

    def __init__(self, registry: Registry, config: dict[str, Any]) -> None:
        self._registry = registry
        self._config = config
        self._current_file: str = ""
        self._files_filter: set[str] | None = None
        self._related_info: list[RelatedInformation] = []
        self._suggestion: str = ""

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    # ------------------------------------------------------------------
    # 集合查询
    # ------------------------------------------------------------------

    def query(self, collection: str, **filters: Any) -> QuerySet:
        """查询某个集合，支持增强过滤语法和 Tag 过滤。

        支持 Django-style 双下划线后缀：
          __eq, __ne, __gt, __gte, __lt, __lte, __in, __contains,
          __startswith, __endswith

        支持 Tag 过滤：
          tags__discipline=hvac  → 自动查找 Instance 的 tags 字段
        """
        qs = self._registry.query(collection, **filters)
        if self._files_filter is not None:
            allowed = self._files_filter
            items = [item for item in qs if str(getattr(item, "source", "")) in allowed]
            qs = make_query_set(items)
        return qs

    def instances(self) -> QuerySet:
        """返回所有 Instance（项目树范围）。

        返回 QuerySet，支持链式操作。
        """
        items = list(self._registry.all_instances_tree().values())
        qs = make_query_set(items)
        if self._files_filter is not None:
            allowed = self._files_filter
            items = [item for item in qs if str(getattr(item, "source", "")) in allowed]
            qs = make_query_set(items)
        return qs

    # ------------------------------------------------------------------
    # Layout 查询（ADR-001）
    # ------------------------------------------------------------------

    @property
    def layout(self) -> Layout | None:
        """获取当前项目的 Layout。"""
        return self._registry.layout

    def layout_entry(self, instance_id: str) -> LayoutEntry | None:
        """获取指定 Instance 的 Layout 条目。"""
        return self._registry.get_layout_entry(instance_id)

    def layout_parent(self, instance_id: str) -> str | None:
        """返回实例在空间装配树中的直接父级（ADR-013）。"""
        layout = self._registry.layout
        if layout is None:
            return None
        return layout.layout_parent(instance_id)

    def layout_children(self, instance_id: str) -> list[str]:
        """返回实例在空间装配树中的直接子级（ADR-013）。"""
        layout = self._registry.layout
        if layout is None:
            return []
        return layout.layout_children(instance_id)

    def layout_ancestors(self, instance_id: str) -> list[str]:
        """返回从根到该实例的父级路径（ADR-013）。"""
        layout = self._registry.layout
        if layout is None:
            return []
        return layout.layout_ancestors(instance_id)

    def layout_descendants(self, instance_id: str) -> list[str]:
        """返回该实例下的所有后代实例（ADR-013）。"""
        layout = self._registry.layout
        if layout is None:
            return []
        return layout.layout_descendants(instance_id)

    def resolved_transform(self, instance_id: str) -> Transform | None:
        """返回实例在项目全局坐标系下的解析后位姿（ADR-013）。"""
        layout = self._registry.layout
        if layout is None:
            return None
        return layout.resolved_transform(instance_id)

    # ------------------------------------------------------------------
    # Instance 查找（跨项目，ADR-001）
    # ------------------------------------------------------------------

    def find_instance(self, instance_id: str):
        """在项目树中查找 Instance。"""
        return self._registry.find_instance(instance_id)

    def instance_family(self, instance_id: str) -> str | None:
        """返回指定 Instance 的 Family 名称，不存在则返回 None。"""
        inst = self.find_instance(instance_id)
        if inst is None:
            return None
        return inst.family

    def find_model(self, model_id: str):
        """在项目树中查找 Model（替代内部 ctx._registry.find_model 的公开 API）。"""
        return self._registry.find_model(model_id)

    # ------------------------------------------------------------------
    # Mating 图遍历（ADR-006）
    # ------------------------------------------------------------------

    @property
    def mate_graph(self) -> MateGraph:
        """获取当前项目的 MateGraph。"""
        return self._registry.mate_graph

    def mated_children(self, ref: str) -> list[MateSpec]:
        """返回被该引用承载的所有 Mate（"我承载了什么"）。

        Args:
            ref: Instance ID (如 "RACK-A01") 或 Interface 引用 (如 "PDU-A/out-3")。

        Returns:
            该引用作为 parent 的所有 MateSpec 列表。
        """
        return self._registry.mate_graph.children_of(ref)

    def mated_parents(self, ref: str) -> list[MateSpec]:
        """返回承载该引用的所有 Mate（"谁承载了我"）。

        Args:
            ref: Instance ID 或 Interface 引用。

        Returns:
            该引用作为 child 的所有 MateSpec 列表。
        """
        return self._registry.mate_graph.parents_of(ref)

    def mated_chain(self, instance_id: str) -> list[list[MateSpec]]:
        """返回从该 Instance 到根承载物的所有配合路径。

        每条路径是从该 Instance 出发，沿 Mate 的 child→parent 方向
        追溯到根节点为止的完整配合链。

        Args:
            instance_id: Instance ID。

        Returns:
            配合路径列表，每条路径是一个 MateSpec 列表（从近到远）。
        """
        return self._registry.mate_graph.chain(instance_id)

    def mate_parent_instance(self, mate: MateSpec):
        """返回 Mate 中 parent 对应的 ResolvedInstance。"""
        parent_id, _ = parse_mate_ref(mate.parent)
        return self.find_instance(parent_id)

    def mate_child_instance(self, mate: MateSpec):
        """返回 Mate 中 child 对应的 ResolvedInstance。"""
        child_id, _ = parse_mate_ref(mate.child)
        return self.find_instance(child_id)

    def mated_descendants(self, instance_id: str) -> list[str]:
        """返回该 Instance 通过 Mate 承载的所有后代实例 ID（递归）。

        沿 Mate 的 parent→child 方向遍历，直到叶子节点。
        """
        result: list[str] = []
        visited: set[str] = set()

        def dfs(current: str) -> None:
            for mate in self.mated_children(current):
                child_inst = self.mate_child_instance(mate)
                if child_inst is None:
                    continue
                child_id = child_inst.id
                if child_id in visited:
                    continue
                visited.add(child_id)
                result.append(child_id)
                dfs(child_id)

        dfs(instance_id)
        return result

    def mated_ancestors(self, instance_id: str) -> list[str]:
        """返回承载该 Instance 的所有祖先实例 ID（递归，直到根）。

        沿 Mate 的 child→parent 方向遍历。
        """
        result: list[str] = []
        visited: set[str] = set()

        def dfs(current: str) -> None:
            for mate in self.mated_parents(current):
                parent_inst = self.mate_parent_instance(mate)
                if parent_inst is None:
                    continue
                parent_id = parent_inst.id
                if parent_id in visited:
                    continue
                visited.add(parent_id)
                result.append(parent_id)
                dfs(parent_id)

        dfs(instance_id)
        return result

    # ------------------------------------------------------------------
    # 文件过滤
    # ------------------------------------------------------------------

    def set_files_filter(self, files: list[str] | None) -> None:
        if files:
            self._files_filter = set(files)
        else:
            self._files_filter = None

    def set_current_file(self, path: str) -> None:
        self._current_file = path

    def clear_current_file(self) -> None:
        self._current_file = ""
        self._related_info.clear()
        self._suggestion = ""

    # ------------------------------------------------------------------
    # 关联信息与建议
    # ------------------------------------------------------------------

    def add_related_info(self, location: Location, message: str) -> None:
        self._related_info.append(RelatedInformation(location=location, message=message))

    def set_suggestion(self, suggestion: str) -> None:
        self._suggestion = suggestion

    def pop_related_info(self) -> list[RelatedInformation]:
        info = list(self._related_info)
        self._related_info.clear()
        return info

    def pop_suggestion(self) -> str:
        suggestion = self._suggestion
        self._suggestion = ""
        return suggestion
