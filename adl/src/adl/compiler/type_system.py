"""TypeSystem — 编译器类型系统。

从 adl.types.TypeRegistry 构建，提供编译时类型查询接口。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel


class PrimitiveType(Enum):
    STR = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    NULL = "null"
    ANY = "any"


@dataclass
class FieldDef:
    """字段定义。"""
    name: str
    type_primitive: PrimitiveType = PrimitiveType.ANY
    required: bool = False
    default: Any = None
    non_overridable: bool = False
    pydantic_field: Any = None  # pydantic FieldInfo

    @property
    def python_type(self) -> str:
        return self.type_primitive.value


@dataclass
class FamilyDef:
    """Family 类型定义。"""
    name: str
    fields: dict[str, FieldDef] = field(default_factory=dict)
    non_overridable: set[str] = field(default_factory=set)
    base_families: list[str] = field(default_factory=list)
    pydantic_model: type[BaseModel] | None = None
    description: str = ""

    def get_field(self, name: str) -> FieldDef | None:
        return self.fields.get(name)

    def has_field(self, name: str) -> bool:
        return name in self.fields


@dataclass
class MateTypeDef:
    """Mate 类型定义。"""
    name: str
    description: str = ""
    default_constraints: list[Any] = field(default_factory=list)
    applicable_parents: set[str] = field(default_factory=set)
    applicable_children: set[str] = field(default_factory=set)


@dataclass
class InterfaceTypeDef:
    """接口类型定义。"""
    name: str
    compatible_with: set[str] = field(default_factory=set)
    cable_types: list[str] = field(default_factory=list)


@dataclass
class TypeSystem:
    """编译器类型系统。

    从 TypeRegistry 和其他注册来源构建，提供编译时：
    - Family 字段查询
    - Mate 类型约束查询
    - 接口兼容性查询
    """

    families: dict[str, FamilyDef] = field(default_factory=dict)
    mate_types: dict[str, MateTypeDef] = field(default_factory=dict)
    interface_types: dict[str, InterfaceTypeDef] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------

    @classmethod
    def from_type_registry(cls, registry: Any) -> "TypeSystem":
        """从 adl.types.TypeRegistry 构建 TypeSystem。"""
        ts = cls()

        # Families
        for name, pydantic_cls in registry.families.items():
            fd = FamilyDef(name=name, pydantic_model=pydantic_cls)
            for fname, finfo in pydantic_cls.model_fields.items():
                extra = finfo.json_schema_extra or {}
                is_non_override = (
                    isinstance(extra, dict) and extra.get("piki_non_overridable", False)
                )
                fd.fields[fname] = FieldDef(
                    name=fname,
                    type_primitive=_py_type_to_primitive(finfo.annotation),
                    required=finfo.is_required(),
                    default=finfo.default,
                    non_overridable=is_non_override,
                    pydantic_field=finfo,
                )
                if is_non_override:
                    fd.non_overridable.add(fname)
            ts.families[name] = fd

        # Mate types
        for name, meta in registry.mate_types.items():
            ts.mate_types[name] = MateTypeDef(
                name=name,
                description=meta.description,
                default_constraints=[
                    {
                        "field": c.field,
                        "operator": c.operator.value,
                        "value_ref": c.value_ref,
                        "message": c.message,
                    }
                    for c in meta.default_constrains
                ],
                applicable_parents=meta.applicable_parent_families,
                applicable_children=meta.applicable_child_families,
            )

        return ts

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_family(self, name: str) -> FamilyDef | None:
        return self.families.get(name)

    def get_mate_type(self, name: str) -> MateTypeDef | None:
        return self.mate_types.get(name)

    def get_interface_type(self, name: str) -> InterfaceTypeDef | None:
        return self.interface_types.get(name)

    def is_compatible_interface(self, type_a: str, type_b: str) -> bool:
        """检查两个接口类型是否兼容。"""
        if type_a == type_b:
            return True
        it_a = self.interface_types.get(type_a)
        if it_a and type_b in it_a.compatible_with:
            return True
        it_b = self.interface_types.get(type_b)
        if it_b and type_a in it_b.compatible_with:
            return True
        return False

    def register_interface_type(self, name: str, *, compatible_with: set[str] | None = None) -> None:
        if name not in self.interface_types:
            self.interface_types[name] = InterfaceTypeDef(
                name=name, compatible_with=compatible_with or set()
            )


def _py_type_to_primitive(annotation: Any) -> PrimitiveType:
    """将 Python 类型注解映射到 PrimitiveType。"""
    if annotation is None:
        return PrimitiveType.ANY
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        # Optional[X] → X
        if origin is type(None) or str(origin).endswith(".NoneType"):
            return PrimitiveType.NULL
        args = getattr(annotation, "__args__", ())
        if str(origin) == "typing.Union" or origin is getattr(__builtins__, "Union", None):
            # Optional[X] = Union[X, None]
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return _py_type_to_primitive(non_none[0])
            return PrimitiveType.ANY
        return PrimitiveType.ANY

    if annotation is str:
        return PrimitiveType.STR
    elif annotation is int:
        return PrimitiveType.INT
    elif annotation is float:
        return PrimitiveType.FLOAT
    elif annotation is bool:
        return PrimitiveType.BOOL
    elif annotation is type(None):
        return PrimitiveType.NULL

    return PrimitiveType.ANY
