"""Tag 数据模型（ADR-009 §3）。

Tag 是正交于物理空间/专业的维度标签，键值对形式：
- 键：如 discipline, security_zone, contract_package, system
- 值：如 hvac, containment, pkg-1, fire-alarm-system

Tag Schema 在 piki.toml 中定义允许的键集合，Tag 自身不限制值。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class Tags(BaseModel):
    """Instance / Model 的维度标签。

    所有键值均为字符串，额外键被保留但会触发 L2 检查警告。
    """

    # 常用标签键（可选）
    discipline: str = Field(default="")
    security_zone: str = Field(default="")
    contract_package: str = Field(default="")
    system: str = Field(default="")
    phase: str = Field(default="")

    # 额外标签
    extra: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_extra(cls, data: Any) -> Any:
        """将未命名的键值对移到 extra 中。"""
        if not isinstance(data, dict):
            return data
        known = {"discipline", "security_zone", "contract_package", "system", "phase", "extra"}
        extra = {}
        result = {}
        for k, v in data.items():
            if k in known:
                result[k] = v
            else:
                extra[k] = str(v) if v is not None else ""
        result["extra"] = {**data.get("extra", {}), **extra}
        return result

    def as_flat_dict(self) -> dict[str, str]:
        """返回扁平化的所有标签键值对（用于查询）。"""
        result: dict[str, str] = {}
        if self.discipline:
            result["discipline"] = self.discipline
        if self.security_zone:
            result["security_zone"] = self.security_zone
        if self.contract_package:
            result["contract_package"] = self.contract_package
        if self.system:
            result["system"] = self.system
        if self.phase:
            result["phase"] = self.phase
        result.update(self.extra)
        return result
