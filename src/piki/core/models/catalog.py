"""Catalog 数据模型（ADR-011）。

Catalog 是连接设计模型（Model）与真实世界权威规格的中间层。
它本身不是第六个维度，而是跨维度的引用层：
- ComponentCatalogEntry：可采购器件的真实料号、生命周期、datasheet。
- ServiceMethodCatalogEntry：安装/服务工法的前提条件（DFM/DFC）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Pydantic Family 定义
# ---------------------------------------------------------------------------


class DatasheetRef(BaseModel):
    """CatalogEntry 中 datasheet 引用。"""

    url: str | None = None
    hash: str | None = None
    revision: str | None = None


class ComponentCatalogFamily(BaseModel):
    """物料型录条目：真实世界可采购器件。"""

    model_config = ConfigDict(extra="allow")

    catalog_id: str = Field(..., description="型录条目唯一标识")
    family: str = "ComponentCatalogFamily"

    manufacturer: str | None = Field(default=None, description="制造商")
    mpn: str | None = Field(default=None, description="制造商料号")
    sku: str | None = Field(default=None, description="SKU")
    lifecycle: str = Field(
        default="active",
        description="生命周期：active / preferred / restricted / nrnd / eol",
    )
    revision: str | None = Field(default=None, description="版本/修订")
    certifications: list[str] = Field(default_factory=list, description="认证列表")

    model_ref: str | None = Field(default=None, description="指向的 Model ID")
    datasheet: DatasheetRef | None = Field(default=None, description="Datasheet 引用")
    service_methods: list[str] = Field(
        default_factory=list,
        description="引用的 ServiceMethodCatalogEntry ID 列表",
    )


class ServiceMethodCatalogFamily(BaseModel):
    """工法/服务型录条目：实施服务所需的前提条件（DFM/DFC）。"""

    model_config = ConfigDict(extra="allow")

    catalog_id: str = Field(..., description="型录条目唯一标识")
    family: str = "ServiceMethodCatalogFamily"

    service_type: str | None = Field(default=None, description="服务类型描述")
    applicable_to_families: list[str] = Field(
        default_factory=list, description="适用的 Instance Family 列表"
    )

    workspace: dict[str, Any] = Field(default_factory=dict, description="作业空间要求")
    safety: dict[str, Any] = Field(default_factory=dict, description="安全要求")
    temporary_works: list[dict[str, Any]] = Field(
        default_factory=list, description="临时工程/机械需求"
    )
    labor: list[dict[str, Any]] = Field(default_factory=list, description="人工需求")
    standard_ref: str | None = Field(default=None, description="参考标准")


# ---------------------------------------------------------------------------
# 运行时容器
# ---------------------------------------------------------------------------


@dataclass
class CatalogEntry:
    """运行时型录条目容器。"""

    id: str
    family: str
    source: str
    model_ref: str | None
    data: dict[str, Any]
    source_path: Path | None = None

    @property
    def service_methods(self) -> list[str]:
        """返回 ComponentCatalogEntry 引用的服务工法 ID 列表。"""
        if self.family != "ComponentCatalogFamily":
            return []
        value = self.data.get("service_methods")
        if isinstance(value, list):
            return [str(x) for x in value]
        return []


# ---------------------------------------------------------------------------
# 服务工法合并工具
# ---------------------------------------------------------------------------


def merge_service_methods(methods: list[CatalogEntry]) -> dict[str, Any]:
    """把多个 ServiceMethodCatalogEntry 合并成一个统一的要求字典。

    合并语义（DFC 检查取最严格值）：
    - 布尔字段：任意为 True 则结果为 True。
    - 数值字段（以 _mm, _lux 等结尾）：取最大值。
    - 列表字段（ppe, temporary_works, labor）：取并集。
    - 其他字段：保留第一个非空值。

    Args:
        methods: 已解析的 ServiceMethodCatalogEntry 列表。

    Returns:
        扁平化的合并要求字典，可直接被 QuerySet 通过 service_method__* 查询。
    """
    workspace: dict[str, Any] = {}
    safety: dict[str, Any] = {}
    temporary_works: list[Any] = []
    labor: list[Any] = []
    standard_refs: list[str] = []

    for method in methods:
        data = method.data
        ws = data.get("workspace") or {}
        sf = data.get("safety") or {}

        # workspace / safety 合并
        for target, source in [(workspace, ws), (safety, sf)]:
            if not isinstance(source, dict):
                continue
            for key, value in source.items():
                target[key] = _merge_value(target.get(key), value, key)

        # 列表取并集
        for key, target in [("temporary_works", temporary_works), ("labor", labor)]:
            source = data.get(key)
            if isinstance(source, list):
                for item in source:
                    if item not in target:
                        target.append(item)

        ref = data.get("standard_ref")
        if ref and ref not in standard_refs:
            standard_refs.append(ref)

    merged: dict[str, Any] = {}
    if workspace:
        merged["workspace"] = workspace
    if safety:
        merged["safety"] = safety
    if temporary_works:
        merged["temporary_works"] = temporary_works
    if labor:
        merged["labor"] = labor
    if standard_refs:
        merged["standard_ref"] = standard_refs[0]

    # 为了规则查询方便，同时把 workspace.* / safety.* 提升到顶层
    _flatten_into(merged, workspace, "workspace")
    _flatten_into(merged, safety, "safety")

    return merged


def _merge_value(current: Any, new: Any, key: str) -> Any:
    """合并单个字段值。"""
    # 布尔：OR
    if isinstance(new, bool):
        if isinstance(current, bool):
            return current or new
        return new if new else current

    # 数值：取最大（更严格）
    if isinstance(new, (int, float)) and not isinstance(new, bool):
        if isinstance(current, (int, float)) and not isinstance(current, bool):
            return max(current, new)
        return new if current is None else current

    # 默认：保留第一个非空值
    if current is None:
        return new
    return current


def _flatten_into(target: dict[str, Any], source: dict[str, Any], prefix: str) -> None:
    """把 source 中的字段扁平化到 target，键名为 prefix.key。"""
    if not isinstance(source, dict):
        return
    for key, value in source.items():
        target[f"{prefix}.{key}"] = value
