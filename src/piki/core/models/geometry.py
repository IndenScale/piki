"""几何资产 Schema —— 支持代理几何、USD 引用、CSG 布尔运算。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Vec3(BaseModel):
    """三维向量。"""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __iter__(self):
        return iter((self.x, self.y, self.z))

    def __getitem__(self, index: int) -> float:
        return (self.x, self.y, self.z)[index]

    def __len__(self) -> int:
        return 3


class Transform(BaseModel):
    """三维变换：平移 + 旋转（欧拉角，度）+ 缩放。"""

    translation: Vec3 = Field(default_factory=lambda: Vec3(x=0.0, y=0.0, z=0.0))
    rotation: Vec3 = Field(default_factory=lambda: Vec3(x=0.0, y=0.0, z=0.0))
    scale: Vec3 = Field(default_factory=lambda: Vec3(x=1.0, y=1.0, z=1.0))


class InlineGeometry(BaseModel):
    """内联简单几何体（代理几何）。"""

    type: Literal["box", "cylinder", "sphere", "capsule"]
    size: Vec3 | None = None          # box: width, height, depth
    radius: float | None = None       # cylinder / sphere / capsule
    height: float | None = None       # cylinder / capsule
    transform: Transform = Field(default_factory=Transform)

    @model_validator(mode="after")
    def _check_params(self):
        t = self.type
        if t == "box":
            if self.size is None:
                raise ValueError("box type requires 'size'")
        elif t in ("cylinder", "capsule"):
            if self.radius is None or self.height is None:
                raise ValueError(f"{t} type requires 'radius' and 'height'")
        elif t == "sphere":
            if self.radius is None:
                raise ValueError("sphere type requires 'radius'")
        return self


class CSGNode(BaseModel):
    """CSG 树节点 —— 支持程序化布尔运算。"""

    type: Literal["primitive", "union", "intersection", "difference"]
    primitive: InlineGeometry | None = None
    operands: list["CSGNode"] | None = None
    transform: Transform = Field(default_factory=Transform)

    @model_validator(mode="after")
    def _check_node(self):
        if self.type == "primitive":
            if self.primitive is None:
                raise ValueError("primitive node requires 'primitive'")
        else:
            if not self.operands or len(self.operands) < 2:
                raise ValueError(
                    f"{self.type} node requires at least 2 operands"
                )
        return self


class AssetReference(BaseModel):
    """USD 资产引用 —— 四种方式任选其一。"""

    reference: str | None = None      # 外部 USD 文件路径/URL
    inline: InlineGeometry | None = None
    usdz: str | None = None           # 厂商 USDZ URL
    procedural: CSGNode | None = None  # CSG 程序化几何

    @model_validator(mode="after")
    def _check_one_source(self):
        sources = [
            self.reference is not None,
            self.inline is not None,
            self.usdz is not None,
            self.procedural is not None,
        ]
        if sum(sources) > 1:
            raise ValueError(
                "Only one of 'reference', 'inline', 'usdz', 'procedural' can be set"
            )
        return self


class GeometryAssets(BaseModel):
    """几何资产集合。"""

    usd: AssetReference | None = None
