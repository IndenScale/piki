"""ADL 类型注册表。

类型注册表由编排框架（如 piki）或插件填充，ADL 核心在加载项目时使用它：
- Family Schema 用于校验 Instance
- MateTypeMeta 用于校验 Mate 类型和提供默认约束
- 已知接口类型用于在 InterfaceSpec 校验时给出未知类型警告
"""

from __future__ import annotations

from pydantic import BaseModel

from adl.models.interface import register_interface_type, register_interface_types
from adl.models.mating import MateTypeMeta


class TypeRegistry:
    """ADL 类型注册表。

    注意：已知接口类型使用模块级全局注册表（向后兼容），
    因此多个 TypeRegistry 实例共享同一套已知接口类型集合。
    """

    def __init__(self) -> None:
        self._families: dict[str, type[BaseModel]] = {}
        self._mate_types: dict[str, MateTypeMeta] = {}

    # ------------------------------------------------------------------
    # Family
    # ------------------------------------------------------------------

    def add_family(self, name: str, cls: type[BaseModel]) -> None:
        """注册一个 Family Schema。"""
        self._families[name] = cls

    def get_family(self, name: str) -> type[BaseModel] | None:
        """按名称获取 Family Schema。"""
        return self._families.get(name)

    @property
    def families(self) -> dict[str, type[BaseModel]]:
        """返回所有已注册 Family 的副本。"""
        return dict(self._families)

    # ------------------------------------------------------------------
    # Mate type
    # ------------------------------------------------------------------

    def add_mate_type(self, name: str, meta: MateTypeMeta) -> None:
        """注册一个 Mate type 元数据。"""
        self._mate_types[name] = meta

    def get_mate_type(self, name: str) -> MateTypeMeta | None:
        """按名称获取 Mate type 元数据。"""
        return self._mate_types.get(name)

    @property
    def mate_types(self) -> dict[str, MateTypeMeta]:
        """返回所有已注册 Mate type 的副本。"""
        return dict(self._mate_types)

    # ------------------------------------------------------------------
    # Interface type
    # ------------------------------------------------------------------

    def add_interface_type(self, type_name: str) -> None:
        """注册一个已知接口类型。"""
        register_interface_type(type_name)

    def add_interface_types(self, type_names: list[str]) -> None:
        """批量注册已知接口类型。"""
        register_interface_types(type_names)
