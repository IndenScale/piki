"""几何资产 Schema —— 支持代理几何、USD 引用、CSG 布尔运算。"""

from __future__ import annotations

from typing import Any, Literal

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

    @model_validator(mode="before")
    @classmethod
    def _accept_list_vectors(cls, data: Any) -> Any:
        """允许用 ``[x, y, z]`` 列表简写初始化 translation / rotation / scale。"""
        if not isinstance(data, dict):
            return data
        for key in ("translation", "rotation", "scale"):
            value = data.get(key)
            if isinstance(value, (list, tuple)) and len(value) == 3:
                data = {**data, key: {"x": value[0], "y": value[1], "z": value[2]}}
        return data


def _rotation_matrix_zyx(rotation: Vec3) -> list[list[float]]:
    """将 Z-Y-X（Yaw-Pitch-Roll，单位度）欧拉角转换为 3x3 旋转矩阵。"""
    import math

    yaw = math.radians(rotation.z)
    pitch = math.radians(rotation.y)
    roll = math.radians(rotation.x)

    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)

    # R = Rz(yaw) @ Ry(pitch) @ Rx(roll)
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ]


def _matrix_mult(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    """3x3 矩阵乘法。"""
    result: list[list[float]] = [[0.0, 0.0, 0.0] for _ in range(3)]
    for i in range(3):
        for j in range(3):
            result[i][j] = sum(a[i][k] * b[k][j] for k in range(3))
    return result


def _matrix_vector_mult(m: list[list[float]], v: Vec3) -> Vec3:
    """3x3 矩阵乘以三维向量。"""
    return Vec3(
        x=m[0][0] * v.x + m[0][1] * v.y + m[0][2] * v.z,
        y=m[1][0] * v.x + m[1][1] * v.y + m[1][2] * v.z,
        z=m[2][0] * v.x + m[2][1] * v.y + m[2][2] * v.z,
    )


def _euler_zyx_from_matrix(m: list[list[float]]) -> Vec3:
    """从旋转矩阵提取 Z-Y-X 欧拉角（单位度）。"""
    import math

    r31 = m[2][0]
    # 限制 asin 定义域，避免浮点误差
    pitch = math.asin(max(-1.0, min(1.0, -r31)))

    if abs(math.cos(pitch)) > 1e-6:
        roll = math.atan2(m[2][1], m[2][2])
        yaw = math.atan2(m[1][0], m[0][0])
    else:
        # 万向节锁：约定 yaw = 0
        yaw = 0.0
        roll = math.atan2(-m[0][1], m[1][1])

    return Vec3(x=math.degrees(roll), y=math.degrees(pitch), z=math.degrees(yaw))


def compose_transforms(parent: Transform, child: Transform) -> Transform:
    """级联两个 Transform：先父变换，再子变换。

    返回 ``parent @ child``，即子坐标经父坐标系变换到全局。
    """
    r_parent = _rotation_matrix_zyx(parent.rotation)
    r_child = _rotation_matrix_zyx(child.rotation)
    r_composed = _matrix_mult(r_parent, r_child)

    t_composed = _matrix_vector_mult(r_parent, child.translation)
    t_composed.x += parent.translation.x
    t_composed.y += parent.translation.y
    t_composed.z += parent.translation.z

    return Transform(
        translation=t_composed,
        rotation=_euler_zyx_from_matrix(r_composed),
        scale=Vec3(x=1.0, y=1.0, z=1.0),
    )


def transform_from_absolute(
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
) -> Transform:
    """从绝对坐标字段构造 Transform。"""
    return Transform(
        translation=Vec3(
            x=x if x is not None else 0.0,
            y=y if y is not None else 0.0,
            z=z if z is not None else 0.0,
        ),
        rotation=Vec3(x=0.0, y=0.0, z=0.0),
        scale=Vec3(x=1.0, y=1.0, z=1.0),
    )


class InlineGeometry(BaseModel):
    """内联简单几何体（代理几何）。"""

    type: Literal["box", "cylinder", "sphere", "capsule"]
    size: Vec3 | None = None  # box: width, height, depth
    radius: float | None = None  # cylinder / sphere / capsule
    height: float | None = None  # cylinder / capsule
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
                raise ValueError(f"{self.type} node requires at least 2 operands")
        return self


class AssetReference(BaseModel):
    """USD 资产引用 —— 四种方式任选其一。"""

    reference: str | None = None  # 外部 USD 文件路径/URL
    inline: InlineGeometry | None = None
    usdz: str | None = None  # 厂商 USDZ URL
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
            raise ValueError("Only one of 'reference', 'inline', 'usdz', 'procedural' can be set")
        return self


class GeometryAssets(BaseModel):
    """几何资产集合。"""

    usd: AssetReference | None = None
