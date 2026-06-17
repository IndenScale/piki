"""符号表 — 多命名空间作用域。

提供编译期间的符号定义、消解和跨命名空间查询。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .span import Span

# ---------------------------------------------------------------------------
# 符号类型
# ---------------------------------------------------------------------------


class SymbolKind(Enum):
    INSTANCE = "instance"
    MODEL = "model"
    FAMILY = "family"
    CATALOG = "catalog"
    LAYOUT = "layout"
    MATE = "mate"
    GRID = "grid"
    INTERFACE = "interface"
    NAMESPACE = "namespace"
    MATE_TYPE = "mate_type"
    INTERFACE_TYPE = "interface_type"


# ---------------------------------------------------------------------------
# 符号引用（未消解）
# ---------------------------------------------------------------------------


class RefKind(Enum):
    INSTANCE = "instance"
    INSTANCE_INTERFACE = "instance_interface"  # "SRV-01/eth0"
    MODEL = "model"
    FAMILY = "family"
    CATALOG = "catalog"
    MATE_TYPE = "mate_type"
    GRID = "grid"
    RACK = "rack"
    PDU = "pdu"


@dataclass(frozen=True)
class SymbolRef:
    """编译过程中的未消解引用。"""
    text: str
    kind: RefKind
    span: Span = field(default_factory=Span.synthetic)


# ---------------------------------------------------------------------------
# 符号
# ---------------------------------------------------------------------------


@dataclass
class Symbol:
    """符号表中的条目。"""
    name: str
    kind: SymbolKind
    namespace: str  # 所属命名空间 id
    definition_node: Any = None  # 指向 HIR SemanticUnit 或 AST Declaration
    is_public: bool = True
    span: Span = field(default_factory=Span.synthetic)


# ---------------------------------------------------------------------------
# 作用域
# ---------------------------------------------------------------------------


@dataclass
class Scope:
    """一个命名空间的作用域。"""
    namespace: str
    symbols: dict[str, Symbol] = field(default_factory=dict)
    children: list[str] = field(default_factory=list)

    def define(self, symbol: Symbol) -> None:
        key = (symbol.name, symbol.kind)
        existing = self.symbols.get(symbol.name)
        # Allow same name with different symbol kinds
        if existing is not None and existing.kind == symbol.kind:
            raise NameError(
                f"Duplicate symbol '{symbol.name}' ({symbol.kind.value}) in namespace '{self.namespace}'. "
                f"Previous: {existing.span}"
            )
        self.symbols[symbol.name] = symbol
        symbol.namespace = self.namespace

    def lookup(self, name: str, kind: SymbolKind | None = None) -> Symbol | None:
        sym = self.symbols.get(name)
        if sym is not None and (kind is None or sym.kind == kind):
            return sym
        return None

    def lookup_by_kind(self, name: str, kind: SymbolKind) -> Symbol | None:
        sym = self.symbols.get(name)
        if sym is not None and sym.kind == kind:
            return sym
        return None


# ---------------------------------------------------------------------------
# 符号表
# ---------------------------------------------------------------------------


@dataclass
class SymbolTable:
    """多层符号表。

    命名空间是分层的：根命名空间 "" 是祖先，子项目命名空间是后代。
    消解时从当前命名空间开始，沿命名空间链向上查找。
    """

    scopes: dict[str, Scope] = field(default_factory=dict)
    namespace_hierarchy: dict[str, str | None] = field(default_factory=dict)  # ns → parent_ns

    # ------------------------------------------------------------------
    # 命名空间管理
    # ------------------------------------------------------------------

    def create_namespace(self, ns: str, parent: str | None = None) -> Scope:
        scope = Scope(namespace=ns)
        self.scopes[ns] = scope
        self.namespace_hierarchy[ns] = parent
        if parent is not None and parent in self.scopes:
            self.scopes[parent].children.append(ns)
        return scope

    def ensure_namespace(self, ns: str, parent: str | None = None) -> Scope:
        if ns in self.scopes:
            return self.scopes[ns]
        return self.create_namespace(ns, parent)

    def parent_namespace(self, ns: str) -> str | None:
        return self.namespace_hierarchy.get(ns)

    # ------------------------------------------------------------------
    # 符号操作
    # ------------------------------------------------------------------

    def define(self, symbol: Symbol) -> None:
        scope = self.ensure_namespace(symbol.namespace)
        scope.define(symbol)

    def lookup(
        self,
        name: str,
        kind: SymbolKind | None = None,
    ) -> Symbol | None:
        """在根命名空间中查找（全局查找）。"""
        root = self.scopes.get("")
        if root is None:
            return None
        sym = root.symbols.get(name)
        if sym is not None and (kind is None or sym.kind == kind):
            return sym
        return None

    def resolve(
        self,
        ref: SymbolRef,
        from_namespace: str,
    ) -> Symbol | None:
        """在给定命名空间链中消解引用。

        查找顺序：from_namespace → parent → ... → root
        """
        current: str | None = from_namespace
        while current is not None:
            scope = self.scopes.get(current)
            if scope is not None:
                sym = scope.symbols.get(ref.text)
                if sym is not None:
                    # 检查符号类型是否匹配引用类型
                    expected = _ref_to_symbol_kind(ref.kind)
                    if expected is None or sym.kind == expected:
                        return sym
            current = self.namespace_hierarchy.get(current)
        return None

    def resolve_interface(
        self,
        instance_name: str,
        interface_name: str,
        from_namespace: str,
    ) -> Symbol | None:
        """消解 Instance 的 Interface 引用（"SRV-01/eth0"）。

        先消解 Instance，然后在该 Instance 的 interfaces 中查找。
        """
        inst_ref = SymbolRef(instance_name, RefKind.INSTANCE)
        inst_sym = self.resolve(inst_ref, from_namespace)
        if inst_sym is None:
            return None
        # Interface 符号的命名约定: instance_id/interface_id
        qname = f"{instance_name}/{interface_name}"
        return self.resolve(SymbolRef(qname, RefKind.INSTANCE_INTERFACE), from_namespace)

    def all_symbols(self, namespace: str = "") -> dict[str, Symbol]:
        """返回指定命名空间中的所有符号（含递归子空间）。"""
        result: dict[str, Symbol] = {}
        scope = self.scopes.get(namespace)
        if scope is None:
            return result
        result.update(scope.symbols)
        for child in scope.children:
            result.update(self.all_symbols(child))
        return result

    def iter_namespaces(self) -> list[str]:
        """返回所有命名空间 id（拓扑排序：父在前）。"""
        visited: set[str] = set()
        order: list[str] = []

        def visit(ns: str):
            if ns in visited:
                return
            visited.add(ns)
            parent = self.namespace_hierarchy.get(ns)
            if parent is not None and parent not in visited:
                visit(parent)
            order.append(ns)

        for ns in self.scopes:
            visit(ns)
        return order


def _ref_to_symbol_kind(ref_kind: RefKind) -> SymbolKind | None:
    """引用类型 → 符号类型映射。"""
    _MAP: dict[RefKind, SymbolKind] = {
        RefKind.INSTANCE: SymbolKind.INSTANCE,
        RefKind.MODEL: SymbolKind.MODEL,
        RefKind.FAMILY: SymbolKind.FAMILY,
        RefKind.CATALOG: SymbolKind.CATALOG,
        RefKind.MATE_TYPE: SymbolKind.MATE_TYPE,
        RefKind.GRID: SymbolKind.GRID,
        RefKind.RACK: SymbolKind.INSTANCE,
        RefKind.PDU: SymbolKind.INSTANCE,
    }
    return _MAP.get(ref_kind)
