"""几何资产与基础几何类型。

本模块原本位于 adl.models.geometry，现已迁移到 adl.geometry。
ADL 核心不再默认导出这些类型；生成器与几何后端按需导入。
"""

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


# ---------------------------------------------------------------------------
# ADR-014: 机房基础设施与可达性分析的基础空间抽象
# ---------------------------------------------------------------------------


class KinematicEnvelope(BaseModel):
    """运动包络：描述一个刚体在特定运动下的扫掠空间。

    当前主要支持铰链门/盖板，后续可扩展到旋转门、滑动门、机器人臂等。
    """

    type: Literal["hinged-door", "sliding-door", "revolving", "custom"] = "hinged-door"
    hinge_axis: Vec3 = Field(default_factory=lambda: Vec3(x=0.0, y=0.0, z=1.0))
    hinge_position: Vec3 = Field(default_factory=Vec3)
    swing_range_deg: tuple[float, float] = (0.0, 110.0)
    sweep_segments: int = Field(default=8, ge=2, le=64)

    @model_validator(mode="before")
    @classmethod
    def _accept_list_vectors(cls, data: Any) -> Any:
        """允许用 ``[x, y, z]`` 列表简写初始化 hinge_axis / hinge_position。"""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if isinstance(data.get("hinge_axis"), (list, tuple)):
            data["hinge_axis"] = _vec3_from_value(data["hinge_axis"])
        if isinstance(data.get("hinge_position"), (list, tuple)):
            data["hinge_position"] = _vec3_from_value(data["hinge_position"])
        return data

    @model_validator(mode="after")
    def _check_swing_range(self):
        start, end = self.swing_range_deg
        if end < start:
            raise ValueError("swing_range_deg end must be >= start")
        return self


def _vec3_from_value(value: Any) -> Any:
    """把 ``[x, y, z]`` 列表简写转换为 Vec3 dict。"""
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return {"x": value[0], "y": value[1], "z": value[2]}
    return value


class Space(BaseModel):
    """无形空间区域，用于表达虚拟动线、净空区、地垫等设计元素。

    与 InlineGeometry 不同，Space 不表示可视化的实体几何，而是参与 DRC 的约束区域。
    """

    type: Literal["box", "corridor", "waypoints", "cylinder"] = "box"
    # box: size
    size: Vec3 | None = None
    # corridor: 中心线 + 宽度 + 高度
    centerline: list[Vec3] | None = None
    corridor_width_mm: float | None = None
    corridor_height_mm: float | None = None
    # waypoints: 路径点 + 半径
    waypoints: list[Vec3] | None = None
    waypoint_radius_mm: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_list_vectors(cls, data: Any) -> Any:
        """允许用 ``[x, y, z]`` 列表简写初始化 size / centerline / waypoints。"""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if isinstance(data.get("size"), (list, tuple)):
            data["size"] = _vec3_from_value(data["size"])
        if isinstance(data.get("centerline"), list):
            data["centerline"] = [_vec3_from_value(v) for v in data["centerline"]]
        if isinstance(data.get("waypoints"), list):
            data["waypoints"] = [_vec3_from_value(v) for v in data["waypoints"]]
        return data

    @model_validator(mode="after")
    def _check_params(self):
        t = self.type
        if t == "box":
            if self.size is None:
                raise ValueError("box space requires 'size'")
        elif t == "corridor":
            if not self.centerline or len(self.centerline) < 2:
                raise ValueError("corridor space requires at least 2 centerline points")
            if self.corridor_width_mm is None or self.corridor_height_mm is None:
                raise ValueError("corridor space requires 'corridor_width_mm' and 'corridor_height_mm'")
        elif t == "waypoints":
            if not self.waypoints or len(self.waypoints) < 2:
                raise ValueError("waypoints space requires at least 2 waypoints")
            if self.waypoint_radius_mm is None:
                raise ValueError("waypoints space requires 'waypoint_radius_mm'")
        elif t == "cylinder":
            if self.centerline is None or len(self.centerline) != 1:
                raise ValueError("cylinder space requires exactly 1 centerline point")
            if self.corridor_width_mm is None:
                raise ValueError("cylinder space requires 'corridor_width_mm' as radius")
        return self


class LoadCapacity(BaseModel):
    """承重能力：用于地板、楼板、货架等承载实体。"""

    uniform_load_kg_m2: float = Field(default=0.0, ge=0.0)
    point_load_kg: float = Field(default=0.0, ge=0.0)
    max_concentrated_load_kg: float = Field(default=0.0, ge=0.0)
    dynamic_factor: float = Field(default=1.0, ge=1.0)

    def effective_uniform_load(self) -> float:
        """考虑动态系数后的等效均布载荷。"""
        return self.uniform_load_kg_m2 * self.dynamic_factor

    def effective_point_load(self) -> float:
        """考虑动态系数后的等效集中载荷。"""
        return self.point_load_kg * self.dynamic_factor


# ---------------------------------------------------------------------------
# ADL constraint-based assembly: BBox
# ---------------------------------------------------------------------------

class BBox(BaseModel):
    """轴对齐包围盒（毫米），用于约束装配求解。

    半尺寸（half-extents）而非全尺寸——方便 face-to-face / edge-to-face 计算。
    """

    hw: float = Field(default=0.0, description="半宽 (X轴), mm")
    hh: float = Field(default=0.0, description="半高 (Y轴), mm")
    hd: float = Field(default=0.0, description="半深 (Z轴), mm")

    @property
    def width(self) -> float:
        return self.hw * 2.0

    @property
    def height(self) -> float:
        return self.hh * 2.0

    @property
    def depth(self) -> float:
        return self.hd * 2.0

    def face_coord(self, face: str) -> float:
        """面在对应轴上的局部坐标。"""
        if face == "front":
            return self.hd
        if face == "rear":
            return -self.hd
        if face == "right":
            return self.hw
        if face == "left":
            return -self.hw
        if face == "top":
            return self.hh
        if face == "bottom":
            return -self.hh
        return 0.0


def bbox_from_resolved(resolved: dict) -> BBox:
    """从 ResolvedInstance._resolved (扁平 dict) 提取包围盒。

    字段映射: piki mm → BBox half-extents (mm).
    YAML: width_mm / height_mm / depth_mm → X(hw) / Y(hh) / Z(hd)

    特殊处理:
      - total_u: 如果没有 height_mm, 从 total_u * 44.45 推算高度
      - RackFamily: depth_mm/width_mm 从 model 继承
    """
    w = float(resolved.get("width_mm", 0) or 0)
    h = float(resolved.get("height_mm", 0) or 0)
    d = float(resolved.get("depth_mm", 0) or 0)
    # 部分领域使用 length_mm 表示深度（Z 轴），例如方舱/设备
    if d == 0:
        d = float(resolved.get("length_mm", 0) or 0)

    # 机柜/设备用 total_u 推算高度
    if h == 0:
        total_u = resolved.get("total_u")
        height_u = resolved.get("height_u")
        if total_u is not None:
            h = float(total_u) * 44.45
        elif height_u is not None:
            h = float(height_u) * 44.45

    # 抬高地板等设施: 用 floor_height_mm
    if h == 0:
        fh = resolved.get("floor_height_mm")
        if fh is not None:
            h = float(fh)

    return BBox(hw=w / 2.0, hh=h / 2.0, hd=d / 2.0)
