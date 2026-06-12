"""内部数据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Instance 覆盖白名单标记（ADR-001）
# ---------------------------------------------------------------------------
# 使用 Field(json_schema_extra={"piki_non_overridable": True}) 标记不可覆盖字段。
# 物理尺寸字段应标记为不可覆盖，防止 Instance 覆盖导致几何碰撞失效。

NON_OVERRIDABLE_KEY = "piki_non_overridable"


def get_non_overridable_fields(family_cls: type[BaseModel]) -> set[str]:
    """返回 Family Schema 中标记为不可覆盖的字段名集合。"""
    non_overridable: set[str] = set()
    for name, field_info in family_cls.model_fields.items():
        extra = field_info.json_schema_extra or {}
        if isinstance(extra, dict) and extra.get(NON_OVERRIDABLE_KEY):
            non_overridable.add(name)
    return non_overridable


# ---------------------------------------------------------------------------


def _make_namespace(data: dict[str, Any]) -> SimpleNamespace:
    """把 dict 转成支持属性访问的对象（嵌套）。"""
    kwargs: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            kwargs[key] = _make_namespace(value)
        elif isinstance(value, list):
            kwargs[key] = [
                _make_namespace(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            kwargs[key] = value
    return SimpleNamespace(**kwargs)


def _unflatten(data: dict[str, Any]) -> dict[str, Any]:
    """把扁平 dict 还原为嵌套 dict。"""
    out: dict[str, Any] = {}
    for key, value in data.items():
        parts = key.split(".")
        node = out
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return out


@dataclass
class Model:
    """型号库条目：厂商规格默认值。"""

    id: str
    family: str
    data: dict[str, Any]
    source: Path | None = None


@dataclass
class Instance:
    """原始实例数据（未合并 Model）。"""

    id: str
    model: str | None
    family: str | None
    data: dict[str, Any]
    source: Path


@dataclass
class ResolvedInstance:
    """已解析实例：Instance 覆盖 Model 后的完整对象。"""

    id: str
    family: str
    raw: dict[str, Any]  # 原始 instance 字段（扁平）
    _resolved: dict[str, Any]  # 合并 model 后的字段（扁平）
    source: Path
    model_id: str | None = None  # 引用的型号 ID（ADR-001 扩展）
    _validation_error: str = ""  # Schema 校验失败时的错误详情

    def __getattr__(self, name: str) -> Any:
        try:
            return self._resolved[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    @property
    def resolved(self) -> Any:
        """返回支持属性访问的嵌套命名空间对象（兼容文档中的 d.resolved.x）。"""
        return _make_namespace(_unflatten(self._resolved))

    @property
    def assets(self) -> "GeometryAssets | None":
        """返回解析后的几何资产对象（如果存在）。"""
        from .geometry import GeometryAssets

        raw_assets = self._resolved.get("assets")
        if raw_assets is None:
            return None
        if isinstance(raw_assets, dict):
            try:
                return GeometryAssets.model_validate(raw_assets)
            except Exception:
                return None
        return None
