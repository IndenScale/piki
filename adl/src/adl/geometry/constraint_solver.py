"""约束求解器 — 基于 mating_kind 的统一几何约束求解。

本模块已从 adl.compiler 迁移到 adl.geometry。
ADL 核心只负责声明式 Mate 加载；几何解释与求解在目标输出阶段进行。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from adl.geometry.models import BBox, Transform, Vec3, compose_transforms

# ---------------------------------------------------------------------------
# 几何面
# ---------------------------------------------------------------------------


class FaceName(str, Enum):
    """BBox 的六个面。"""
    TOP = "top"
    BOTTOM = "bottom"
    FRONT = "front"
    REAR = "rear"
    LEFT = "left"
    RIGHT = "right"


_FACE_NORMAL: dict[FaceName, Vec3] = {
    FaceName.TOP:    Vec3(x=0, y=1, z=0),
    FaceName.BOTTOM: Vec3(x=0, y=-1, z=0),
    FaceName.FRONT:  Vec3(x=0, y=0, z=1),
    FaceName.REAR:   Vec3(x=0, y=0, z=-1),
    FaceName.LEFT:   Vec3(x=-1, y=0, z=0),
    FaceName.RIGHT:  Vec3(x=1, y=0, z=0),
}

_FACE_U_AXIS: dict[FaceName, Vec3] = {
    # U 轴：面上的第一个方向（垂直边方向）
    FaceName.TOP:    Vec3(x=1, y=0, z=0),
    FaceName.BOTTOM: Vec3(x=1, y=0, z=0),
    FaceName.FRONT:  Vec3(x=1, y=0, z=0),
    FaceName.REAR:   Vec3(x=1, y=0, z=0),
    FaceName.LEFT:   Vec3(x=0, y=1, z=0),
    FaceName.RIGHT:  Vec3(x=0, y=1, z=0),
}

_FACE_V_AXIS: dict[FaceName, Vec3] = {
    # V 轴：面上的第二个方向（法向 × U）
    FaceName.TOP:    Vec3(x=0, y=0, z=1),
    FaceName.BOTTOM: Vec3(x=0, y=0, z=1),
    FaceName.FRONT:  Vec3(x=0, y=1, z=0),
    FaceName.REAR:   Vec3(x=0, y=1, z=0),
    FaceName.LEFT:   Vec3(x=0, y=0, z=1),
    FaceName.RIGHT:  Vec3(x=0, y=0, z=1),
}


@dataclass
class ReferenceFace:
    """一个配合面（从 BBox 或 Interface 推导）。

    用于配合求解：parent 侧作为基准面，child 侧作为配合面。
    """

    name: FaceName                     # 面名称
    normal: Vec3                       # 法向（局部坐标）
    u_axis: Vec3                       # 面上的 U 方向
    v_axis: Vec3                       # 面上的 V 方向
    center: Vec3                       # 面中心（局部坐标）
    u_half: float                      # U 向半尺寸
    v_half: float                      # V 向半尺寸
    offset: float                      # 面沿法向到 BBox 中心的距离

    @classmethod
    def from_bbox(cls, bbox: BBox, face: FaceName) -> "ReferenceFace":
        """从 BBox 推导一个面。"""
        normal = _FACE_NORMAL[face]
        u_axis = _FACE_U_AXIS[face]
        v_axis = _FACE_V_AXIS[face]

        # 面中心 = BBox 中心 + 沿法向偏移
        # face_coord 返回带符号坐标，所以取绝对值后乘以法向
        offset = bbox.face_coord(face.value)
        half_extent = abs(offset)
        center = Vec3(
            x=normal.x * half_extent,
            y=normal.y * half_extent,
            z=normal.z * half_extent,
        )

        # 面上的半尺寸
        if face in (FaceName.TOP, FaceName.BOTTOM):
            u_half, v_half = bbox.hw, bbox.hd
        elif face in (FaceName.FRONT, FaceName.REAR):
            u_half, v_half = bbox.hw, bbox.hh
        else:
            u_half, v_half = bbox.hh, bbox.hd

        return cls(
            name=face, normal=normal, u_axis=u_axis, v_axis=v_axis,
            center=center, u_half=u_half, v_half=v_half, offset=offset,
        )

    @classmethod
    def from_interface(cls, iface_local: Transform, face: FaceName | None = None) -> "ReferenceFace":
        """从接口的 local_transform 推导配合面（简化：接口位姿的 Z 轴朝外）。

        如果指定了 face，则用 face 的法向覆盖。
        """
        normal = _FACE_NORMAL[face] if face else Vec3(z=1)
        u_axis = _FACE_U_AXIS[face] if face else Vec3(x=1)
        v_axis = _FACE_V_AXIS[face] if face else Vec3(y=1)

        return cls(
            name=face or FaceName.TOP,
            normal=normal,
            u_axis=u_axis,
            v_axis=v_axis,
            center=iface_local.translation,
            u_half=50.0,   # 默认接口面半尺寸
            v_half=50.0,
            offset=0.0,
        )

    def point_at(self, u: float, v: float) -> Vec3:
        """面上的 (u, v) 坐标 → 局部 3D 坐标。"""
        return Vec3(
            x=self.center.x + self.u_axis.x * u + self.v_axis.x * v,
            y=self.center.y + self.u_axis.y * u + self.v_axis.y * v,
            z=self.center.z + self.u_axis.z * u + self.v_axis.z * v,
        )

    def clamp_uv(self, u: float, v: float) -> tuple[float, float]:
        """将 (u, v) 限制在面范围内。"""
        return (
            max(-self.u_half, min(self.u_half, u)),
            max(-self.v_half, min(self.v_half, v)),
        )


# ---------------------------------------------------------------------------
# 约束参数
# ---------------------------------------------------------------------------


@dataclass
class FaceConstraintParams:
    """面面配合的参数。"""
    u: float = 0.0        # 基准面上的 U 坐标
    v: float = 0.0        # 基准面上的 V 坐标
    theta_deg: float = 0.0  # 绕法向的旋转角度
    distance: float = 0.0   # 沿法向的距离


@dataclass
class AxisConstraintParams:
    """轴轴配合的参数。"""
    z: float = 0.0        # 沿轴平移
    theta_deg: float = 0.0  # 绕轴旋转


@dataclass
class SlotConstraintParams:
    """槽配合的参数。"""
    t: float = 0.0        # 沿槽方向的推入距离


# ---------------------------------------------------------------------------
# 求解器
# ---------------------------------------------------------------------------


def solve_face_mate(
    parent_global: Transform,
    parent_face: ReferenceFace,
    child_face: ReferenceFace,
    params: FaceConstraintParams | None = None,
) -> Transform:
    """求解面面配合下 child 的全局位姿。

    公式：
      P_child = parent_global
              × T_parent_face (基准面位姿)
              × T_u_v (面上的偏移)
              × R_n(θ) (绕法向旋转)
              × T_n(d) (沿法向偏移)
              × T_child_face⁻¹ (child 配合面位姿的逆)

    其中 child 配合面的法向需要与 parent 基准面的法向相反（面面相对）。
    """
    if params is None:
        params = FaceConstraintParams()

    tf = parent_global

    # 1. 到基准面中心
    tf_face = Transform(translation=parent_face.center)
    tf = compose_transforms(tf, tf_face)

    # 2. 面上的偏移 (u, v)
    u, v = parent_face.clamp_uv(params.u, params.v)
    tf_uv = Transform(translation=Vec3(
        x=parent_face.u_axis.x * u + parent_face.v_axis.x * v,
        y=parent_face.u_axis.y * u + parent_face.v_axis.y * v,
        z=parent_face.u_axis.z * u + parent_face.v_axis.z * v,
    ))
    tf = compose_transforms(tf, tf_uv)

    # 3. 绕法向旋转 θ
    n = parent_face.normal
    tf_rot = Transform(rotation=Vec3(
        x=n.x * params.theta_deg,
        y=n.y * params.theta_deg,
        z=n.z * params.theta_deg,
    ))
    tf = compose_transforms(tf, tf_rot)

    # 4. 沿法向偏移（child 面贴在 parent 面上）
    # parent 法向朝外，child 法向也需要朝外——两面相对
    # 所以 child 的位移 = parent 法向 × distance + child 面到中心的偏移
    tf_dist = Transform(translation=Vec3(
        x=parent_face.normal.x * params.distance,
        y=parent_face.normal.y * params.distance,
        z=parent_face.normal.z * params.distance,
    ))
    tf = compose_transforms(tf, tf_dist)

    # 5. child 配合面位姿的逆（child 面贴在 parent 面上）
    # 简化：child 面法向与 parent 面法向相反
    # 如果 child 的局部法向和 parent 的局部法向不是正好相反，需要旋转校正
    inv_child = _invert_transform(Transform(translation=child_face.center))
    tf = compose_transforms(tf, inv_child)

    return tf


def solve_axis_mate(
    parent_global: Transform,
    parent_axis_origin: Vec3,
    parent_axis_dir: Vec3,
    child_axis_origin: Vec3,
    child_axis_dir: Vec3,
    params: AxisConstraintParams | None = None,
) -> Transform:
    """求解轴轴配合下 child 的全局位姿。

    参数 (z, θ)：沿轴平移 + 绕轴旋转。
    """
    if params is None:
        params = AxisConstraintParams()

    # 将 child 的轴对齐到 parent 的轴
    # 需要旋转校正：child_axis_dir → parent_axis_dir 的反向
    rot_correction = _align_axis_rotation(child_axis_dir, parent_axis_dir)

    tf = parent_global

    # 平移到 parent 轴原点
    tf_origin = Transform(translation=parent_axis_origin)
    tf = compose_transforms(tf, tf_origin)

    # 旋转对齐
    tf = compose_transforms(tf, rot_correction)

    # 绕轴旋转
    tf_rot = Transform(rotation=Vec3(
        x=parent_axis_dir.x * params.theta_deg,
        y=parent_axis_dir.y * params.theta_deg,
        z=parent_axis_dir.z * params.theta_deg,
    ))
    tf = compose_transforms(tf, tf_rot)

    # 沿轴平移
    tf_trans = Transform(translation=Vec3(
        x=parent_axis_dir.x * params.z,
        y=parent_axis_dir.y * params.z,
        z=parent_axis_dir.z * params.z,
    ))
    tf = compose_transforms(tf, tf_trans)

    # 逆 child 轴原点
    inv_child = Transform(translation=Vec3(
        x=-child_axis_origin.x,
        y=-child_axis_origin.y,
        z=-child_axis_origin.z,
    ))
    tf = compose_transforms(tf, inv_child)

    return tf


def solve_slot_mate(
    parent_global: Transform,
    parent_slot_origin: Vec3,
    parent_slot_dir: Vec3,
    child_interface_local: Transform,
    params: SlotConstraintParams | None = None,
) -> Transform:
    """求解槽配合下 child 的全局位姿。

    参数 t：沿槽方向的推入距离。
    用于光模块插入、RJ45 插入等。
    """
    if params is None:
        params = SlotConstraintParams()

    tf = parent_global

    # 到槽原点
    tf = compose_transforms(tf, Transform(translation=parent_slot_origin))

    # 沿槽方向推入
    tf_push = Transform(translation=Vec3(
        x=parent_slot_dir.x * params.t,
        y=parent_slot_dir.y * params.t,
        z=parent_slot_dir.z * params.t,
    ))
    tf = compose_transforms(tf, tf_push)

    # child 接口的逆
    inv = _invert_transform(child_interface_local)
    tf = compose_transforms(tf, inv)

    return tf


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


def _invert_transform(tf: Transform) -> Transform:
    """Transform 的逆（近似）。"""
    return Transform(
        translation=Vec3(x=-tf.translation.x, y=-tf.translation.y, z=-tf.translation.z),
        rotation=Vec3(x=-tf.rotation.x, y=-tf.rotation.y, z=-tf.rotation.z),
        scale=Vec3(x=1.0, y=1.0, z=1.0),
    )


def _align_axis_rotation(from_dir: Vec3, to_dir: Vec3) -> Transform:
    """计算将 from_dir 旋转到 to_dir 的最小旋转角。

    简化：假设轴都是主轴方向 (X/Y/Z)。
    """
    # 如果方向相同或相反，不需要旋转
    if (from_dir.x == to_dir.x and from_dir.y == to_dir.y and from_dir.z == to_dir.z):
        return Transform()

    # 主轴间旋转：X→Y, Y→Z, Z→X 等
    # 简化实现：对主轴方向用 90° 旋转
    fx, fy, fz = abs(from_dir.x), abs(from_dir.y), abs(from_dir.z)
    tx, ty, tz = abs(to_dir.x), abs(to_dir.y), abs(to_dir.z)

    if fx > 0.5 and ty > 0.5:
        return Transform(rotation=Vec3(z=90))
    elif fx > 0.5 and tz > 0.5:
        return Transform(rotation=Vec3(y=90))
    elif fy > 0.5 and tx > 0.5:
        return Transform(rotation=Vec3(z=-90))
    elif fy > 0.5 and tz > 0.5:
        return Transform(rotation=Vec3(x=90))
    elif fz > 0.5 and tx > 0.5:
        return Transform(rotation=Vec3(y=-90))
    elif fz > 0.5 and ty > 0.5:
        return Transform(rotation=Vec3(x=-90))

    return Transform()
