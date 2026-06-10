"""内部数据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def _make_namespace(data: dict[str, Any]) -> SimpleNamespace:
    """把 dict 转成支持属性访问的对象（嵌套）。"""
    kwargs: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            kwargs[key] = _make_namespace(value)
        elif isinstance(value, list):
            kwargs[key] = [
                _make_namespace(item) if isinstance(item, dict) else item
                for item in value
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
    raw: dict[str, Any]          # 原始 instance 字段（扁平）
    _resolved: dict[str, Any]    # 合并 model 后的字段（扁平）
    source: Path
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
