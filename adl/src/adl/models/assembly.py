"""Assembly 数据模型 —— 层级装配体抽象。

提供跨领域的通用 AssemblyFamily，用于表达“子装配体可独立复用”的层级结构。
插件可继承此 Family 或直接使用，配合 Context 的层级遍历 API 实现装配树检查。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .tags import Tags


class AssemblyFamily(BaseModel):
    """通用装配体定义。

    一个 Assembly 可以包含若干子 Instance（children）和子装配体（sub_assemblies）。
    子装配体本身也是 Assembly，可独立复用、独立校验。
    """

    id: str = Field(...)
    name: str = Field(default="")
    # 直接子组件（非装配体），例如 PCB 上的电阻、键盘上的单颗轴体
    children: list[str] = Field(default_factory=list)
    # 子装配体引用，例如 PCB+轴体+键帽组成的子模块
    sub_assemblies: list[str] = Field(default_factory=list)
    # 装配体类型标记，便于规则按类型处理
    assembly_type: str = Field(default="generic")
    # 顶层父装配引用（可选），用于向上追溯
    parent_assembly_id: str = Field(default="")
    tags: Tags = Field(default_factory=Tags)
