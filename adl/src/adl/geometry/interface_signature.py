"""InterfaceSignature — 接口运动自由度签名系统 (ADL-004)。

本模块已从 adl.compiler 迁移到 adl.geometry。
ADL 核心只处理接口声明；运动学签名的解释与计算属于几何后端。
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum

from adl.geometry.models import Transform, Vec3, compose_transforms

# ---------------------------------------------------------------------------
# DOF 类型
# ---------------------------------------------------------------------------

class DOFType(str, Enum):
    """连续自由度类型。"""
    TRANSLATE = "translate"  # 沿轴平移 (mm)
    ROTATE = "rotate"        # 绕轴旋转 (度)
    SCREW = "screw"          # 螺旋运动（平移 + 旋转耦合）(mm/度)


# ---------------------------------------------------------------------------
# 连续自由度
# ---------------------------------------------------------------------------

@dataclass
class DOF:
    """一个连续运动自由度。

    描述配合后接口沿/绕某轴可以连续运动。"""

    type: DOFType
    axis: Vec3                           # 运动轴方向（局部坐标，单位向量）
    range: tuple[float, float] = (0.0, 0.0)  # (min, max)，平移 mm，旋转 度
    default_value: float = 0.0           # 默认参数值
    label: str = ""                      # 人类可读标签

    @property
    def is_limited(self) -> bool:
        """是否有有限范围。"""
        lo, hi = self.range
        return lo != hi

    def clamp(self, value: float) -> float:
        """将值限制在范围内。"""
        lo, hi = self.range
        if lo == hi:
            return value
        return max(lo, min(hi, value))

    def transform_at(self, value: float) -> Transform:
        """计算此自由度在给定参数值下的局部位移变换。

        TRANSLATE: 沿 axis 移动 value mm
        ROTATE:    绕 axis 旋转 value 度
        SCREW:     绕 axis 旋转 value 度 + 沿 axis 移动 value * pitch mm
        """
        v = self.clamp(value)
        if self.type == DOFType.TRANSLATE:
            return Transform(
                translation=Vec3(
                    x=self.axis.x * v,
                    y=self.axis.y * v,
                    z=self.axis.z * v,
                )
            )
        elif self.type == DOFType.ROTATE:
            # 绕任意轴的旋转矩阵 → 欧拉角近似
            # 简化：仅支持主轴旋转 (X/Y/Z)
            ax, ay, az = self.axis.x, self.axis.y, self.axis.z
            if abs(ax - 1.0) < 1e-6:
                return Transform(rotation=Vec3(x=v))
            elif abs(ay - 1.0) < 1e-6:
                return Transform(rotation=Vec3(y=v))
            elif abs(az - 1.0) < 1e-6:
                return Transform(rotation=Vec3(z=v))
            else:
                # 任意轴：返回 identity（TODO：完整 Rodrigues 变换）
                return Transform()
        elif self.type == DOFType.SCREW:
            # 螺旋 = 旋转 + 平移同时（假设 pitch = 1mm/度）
            return Transform(
                translation=Vec3(
                    x=self.axis.x * v,
                    y=self.axis.y * v,
                    z=self.axis.z * v,
                ),
                rotation=Vec3(
                    x=self.axis.x * v,
                    y=self.axis.y * v,
                    z=self.axis.z * v,
                ),
            )
        return Transform()


# ---------------------------------------------------------------------------
# 离散状态
# ---------------------------------------------------------------------------

@dataclass
class DiscreteState:
    """接口的一个离散位置状态。

    如 USB-C 的"正插"和"反插"是两个离散状态。
    状态之间不可连续过渡（没有中间状态）。
    """

    name: str                            # "inserted", "removed", "reversed"
    label: str = ""                      # 人类可读标签
    transform_delta: Transform | None = None  # 相对于默认配合位置的变换，None = 不配合
    is_default: bool = False

    @property
    def is_mated(self) -> bool:
        """此状态下接口是否处于配合状态。"""
        return self.transform_delta is not None


# ---------------------------------------------------------------------------
# 参数化阶段（留待后续）
# ---------------------------------------------------------------------------

@dataclass
class SignatureStage:
    """配合的一个阶段。每个阶段激活一组 DOF 和/或离散状态。"""
    order: int                           # 阶段顺序（0-based）
    name: str                            # "insert", "rotate-lock", "torque"
    label: str = ""
    required_state: str | None = None    # 需要的前置离散状态
    activates_dofs: list[str] = field(default_factory=list)   # 本阶段激活的 DOF（名）
    deactivates_dofs: list[str] = field(default_factory=list) # 本阶段停用的 DOF


# ---------------------------------------------------------------------------
# 接口签名
# ---------------------------------------------------------------------------

@dataclass
class InterfaceSignature:
    """接口的运动自由度签名。

    声明此接口配合后，所在部件允许的运动。

    如果两端都是 None（默认），则配合是完全刚性的——与 ADL-003 行为一致。
    """

    discrete_states: list[DiscreteState] = field(default_factory=list)
    continuous_dofs: list[DOF] = field(default_factory=list)
    stages: list[SignatureStage] = field(default_factory=list)

    # 兼容性：签名可以按 interface_type 标注"兼容对方签名"
    compatible_with: set[str] = field(default_factory=set)

    @classmethod
    def rigid(cls) -> "InterfaceSignature":
        """完全刚性配合：只有一个默认的 'inserted' 状态，无自由度。"""
        return cls(
            discrete_states=[
                DiscreteState("inserted", "插入", Transform(), is_default=True),
            ],
        )

    @classmethod
    def pluggable(cls, *extra_states: DiscreteState) -> "InterfaceSignature":
        """可插拔配合：有 inserted 和 removed，可选额外状态。"""
        states = [
            DiscreteState("removed", "拔出", None),
            DiscreteState("inserted", "插入", Transform(), is_default=True),
        ]
        states.extend(extra_states)
        return cls(discrete_states=states)

    @property
    def default_state(self) -> DiscreteState | None:
        for s in self.discrete_states:
            if s.is_default:
                return s
        return None

    @property
    def has_continuous_dof(self) -> bool:
        return len(self.continuous_dofs) > 0

    def get_state(self, name: str) -> DiscreteState | None:
        for s in self.discrete_states:
            if s.name == name:
                return s
        return None

    def get_dof(self, index: int) -> DOF | None:
        if 0 <= index < len(self.continuous_dofs):
            return self.continuous_dofs[index]
        return None

    def state_names(self) -> list[str]:
        return [s.name for s in self.discrete_states]

    @property
    def dof_count(self) -> int:
        return len(self.continuous_dofs)


# ---------------------------------------------------------------------------
# 签名耦合结果
# ---------------------------------------------------------------------------

@dataclass
class SignatureCoupling:
    """两个接口签名耦合后的结果。

    包含：
    - 允许的离散状态交集
    - 连续的 DOF 参数向量
    - 多阶段约束（如有）
    """

    # 离散
    allowed_states: list[str]          # 两端都支持的离散状态名
    default_state: str = ""            # 默认状态名

    # 连续自由度（从 child 接口提取）
    continuous_dofs: list[DOF] = field(default_factory=list)

    # 阶段
    stages: list[SignatureStage] = field(default_factory=list)

    # 当前参数值
    state: str = ""                    # 当前离散状态
    dof_values: list[float] = field(default_factory=list)  # 当前 DOF 参数值

    def set_state(self, name: str) -> None:
        if name in self.allowed_states:
            self.state = name

    def set_dof(self, index: int, value: float) -> None:
        if 0 <= index < len(self.dof_values):
            dof = self.continuous_dofs[index]
            self.dof_values[index] = dof.clamp(value)

    def is_dof_active(self, index: int) -> bool:
        """检查给定索引的 DOF 是否在当前阶段激活。

        如果阶段列表为空，所有 DOF 始终激活。
        否则，检查当前状态是否满足阶段的 required_state，
        以及该 DOF 是否在 activates_dofs/deactivates_dofs 列表中。
        """
        if not self.stages:
            return True
        if index < 0 or index >= len(self.continuous_dofs):
            return False

        # 按顺序应用阶段规则，后续阶段覆盖前面的
        dof = self.continuous_dofs[index]
        dof_name = dof.label or f"dof_{index}"
        is_active: bool = True  # 默认所有 DOF 活跃

        for stage in sorted(self.stages, key=lambda s: s.order):
            if stage.required_state is not None and stage.required_state != self.state:
                continue
            # 后续阶段可以覆盖前面的决定
            if dof_name in stage.deactivates_dofs:
                is_active = False
            if dof_name in stage.activates_dofs:
                is_active = True

        return is_active

    def active_dofs(self) -> list[int]:
        """返回当前激活的 DOF 索引列表。"""
        return [i for i in range(len(self.continuous_dofs)) if self.is_dof_active(i)]

    def compute_child_transform(
        self,
        parent_global: Transform,
        parent_iface_local: Transform,
        child_iface_local: Transform,
    ) -> Transform | None:
        """计算 child 部件的全局 Transform。

        公式：
          P_child = parent_global
                  × T_parent_iface_local
                  × T_discrete(state)
                  × T_dof(d1) × T_dof(d2) × ...
                  × T_child_iface_local⁻¹

        其中 T_child_iface_local⁻¹ 是 child 接口局部位姿的逆。
        """
        # 离散状态检查
        if self.state not in self.allowed_states:
            return None  # 未配合

        tf = parent_global

        # Parent 接口的局部变换
        tf = compose_transforms(tf, parent_iface_local)

        # 离散状态的变换（如反插旋转）
        # 注：原始签名的 transform_delta 需由调用方传入；此处保留接口占位

        # 连续 DOF 变换（仅活跃的 DOF）
        for i, dof in enumerate(self.continuous_dofs):
            if i < len(self.dof_values) and self.is_dof_active(i):
                dof_tf = dof.transform_at(self.dof_values[i])
                tf = compose_transforms(tf, dof_tf)

        # Child 接口局部位姿的逆
        inv = _invert_transform(child_iface_local)
        tf = compose_transforms(tf, inv)

        return tf

    def compute_child_transform_full(
        self,
        parent_global: Transform,
        parent_iface_local: Transform,
        child_iface_local: Transform,
        parent_sig: InterfaceSignature,
    ) -> Transform | None:
        """完整版：包含离散状态 delta 的位姿计算。"""
        if self.state not in self.allowed_states:
            return None

        tf = parent_global
        tf = compose_transforms(tf, parent_iface_local)

        # 离散状态变换
        state_obj = parent_sig.get_state(self.state)
        if state_obj and state_obj.transform_delta:
            tf = compose_transforms(tf, state_obj.transform_delta)

        # 连续 DOF 变换（仅活跃的 DOF）
        for i, dof in enumerate(self.continuous_dofs):
            if i < len(self.dof_values) and self.is_dof_active(i):
                dof_tf = dof.transform_at(self.dof_values[i])
                tf = compose_transforms(tf, dof_tf)

        # Child 接口局部位姿的逆
        inv = _invert_transform(child_iface_local)
        tf = compose_transforms(tf, inv)

        return tf


# ---------------------------------------------------------------------------
# 签名耦合函数
# ---------------------------------------------------------------------------

def couple_signatures(
    parent_sig: InterfaceSignature | None,
    child_sig: InterfaceSignature | None,
) -> SignatureCoupling:
    """耦合两个接口签名，产出一个 SignatureCoupling。

    规则：
    1. 离散状态取交集
    2. 连续自由度以 child 的签名为准
    3. 阶段以 parent 的签名为准（如有）
    """
    # 默认：刚性配合
    if parent_sig is None:
        parent_sig = InterfaceSignature.rigid()
    if child_sig is None:
        child_sig = InterfaceSignature.rigid()

    # 离散状态交集
    parent_states = set(parent_sig.state_names())
    child_states = set(child_sig.state_names())
    allowed = list(parent_states & child_states)

    # 默认状态：优先取名为 "inserted" 的，否则取第一个
    default = "inserted" if "inserted" in allowed else (allowed[0] if allowed else "")

    # 连续自由度：取 child 的
    dofs = deepcopy(child_sig.continuous_dofs)
    dof_vals = [d.default_value for d in dofs]

    # 阶段：取 parent 的
    stages = deepcopy(parent_sig.stages) if parent_sig.stages else []

    return SignatureCoupling(
        allowed_states=allowed,
        default_state=default,
        continuous_dofs=dofs,
        stages=stages,
        state=default,
        dof_values=dof_vals,
    )


# ---------------------------------------------------------------------------
# 默认签名注册表
# ---------------------------------------------------------------------------

_SIGNATURE_REGISTRY: dict[str, InterfaceSignature] = {}


def build_default_signatures() -> None:
    """构建内置的默认接口签名。"""

    # ── USB-C ──
    usb_c_states = [
        DiscreteState("removed", "拔出", None),
        DiscreteState("inserted", "正插", Transform(), is_default=True),
        DiscreteState("reversed", "反插",
                      Transform(rotation=Vec3(z=180))),
    ]
    register_signature("USB-C-receptacle", InterfaceSignature(discrete_states=usb_c_states))
    register_signature("USB-C-plug", InterfaceSignature(discrete_states=[
        DiscreteState("removed", "拔出", None),
        DiscreteState("inserted", "正插", Transform(), is_default=True),
        DiscreteState("reversed", "反插", Transform(rotation=Vec3(z=180))),
    ]))

    # ── 3.5mm TRS 音频 ──
    trs_states = [
        DiscreteState("removed", "拔出", None),
        DiscreteState("inserted", "插入", Transform(), is_default=True),
    ]
    trs_dofs = [DOF(DOFType.ROTATE, Vec3(z=1), (0, 360), default_value=0, label="绕轴线旋转")]
    register_signature("TRS-3.5mm-jack", InterfaceSignature(
        discrete_states=trs_states, continuous_dofs=trs_dofs,
    ))
    register_signature("TRS-3.5mm-plug", InterfaceSignature(
        discrete_states=trs_states, continuous_dofs=trs_dofs,
    ))

    # ── IEC-C13/C14 电源 ──
    iec_states = [
        DiscreteState("removed", "拔出", None),
        DiscreteState("inserted", "插入", Transform(), is_default=True),
    ]
    register_signature("IEC-C13", InterfaceSignature(discrete_states=iec_states))
    register_signature("IEC-C14", InterfaceSignature(discrete_states=iec_states))

    # ── 抽屉滑轨 ──
    drawer_states = [
        DiscreteState("closed", "闭合", Transform(), is_default=True),
    ]
    drawer_dofs = [
        DOF(DOFType.TRANSLATE, Vec3(z=1), (0, 300), default_value=0, label="拉出距离"),
    ]
    register_signature("drawer-slide-female", InterfaceSignature(
        discrete_states=drawer_states, continuous_dofs=drawer_dofs,
    ))
    register_signature("drawer-slide-male", InterfaceSignature(
        discrete_states=drawer_states, continuous_dofs=drawer_dofs,
    ))

    # ── 铰链门 ──
    hinge_states = [
        DiscreteState("closed", "闭合", Transform(), is_default=True),
    ]
    hinge_dofs = [
        DOF(DOFType.ROTATE, Vec3(y=1), (0, 180), default_value=0, label="开门角度"),
    ]
    register_signature("hinge-frame", InterfaceSignature(
        discrete_states=hinge_states, continuous_dofs=hinge_dofs,
    ))
    register_signature("hinge-leaf", InterfaceSignature(
        discrete_states=hinge_states, continuous_dofs=hinge_dofs,
    ))

    # ── SFP28 光模块（推入式，无连续自由度）──
    sfp_states = [
        DiscreteState("removed", "拔出", None),
        DiscreteState("inserted", "插入", Transform(), is_default=True),
    ]
    register_signature("SFP28-cage", InterfaceSignature(discrete_states=sfp_states))
    register_signature("SFP28-module", InterfaceSignature(discrete_states=sfp_states))

    # ── RJ45 网口（推入式）──
    register_signature("RJ45-jack", InterfaceSignature(discrete_states=[
        DiscreteState("removed", "拔出", None),
        DiscreteState("inserted", "插入", Transform(), is_default=True),
    ]))
    register_signature("RJ45-plug", InterfaceSignature(discrete_states=[
        DiscreteState("removed", "拔出", None),
        DiscreteState("inserted", "插入", Transform(), is_default=True),
    ]))

    # ── 螺丝孔（螺旋运动）──
    screw_states = [
        DiscreteState("removed", "拔出", None),
        DiscreteState("seated", "旋入到接触面", Transform(), is_default=True),
    ]
    screw_dofs = [
        DOF(DOFType.SCREW, Vec3(z=1), (0, 25), default_value=0, label="旋入深度"),
    ]
    register_signature("screw-hole", InterfaceSignature(
        discrete_states=screw_states, continuous_dofs=screw_dofs,
    ))
    register_signature("screw-thread", InterfaceSignature(
        discrete_states=screw_states, continuous_dofs=screw_dofs,
    ))


# ---------------------------------------------------------------------------
# 辅助：Transform 求逆
# ---------------------------------------------------------------------------

def _invert_transform(tf: Transform) -> Transform:
    """计算 Transform 的逆。

    简化：仅逆平移 + 逆旋转（欧拉角近似）。
    对于正交接口位姿（无缩放），这个近似足够。
    """
    return Transform(
        translation=Vec3(x=-tf.translation.x, y=-tf.translation.y, z=-tf.translation.z),
        rotation=Vec3(x=-tf.rotation.x, y=-tf.rotation.y, z=-tf.rotation.z),
        scale=Vec3(x=1.0, y=1.0, z=1.0),
    )


# ---------------------------------------------------------------------------
# 签名注册表
# ---------------------------------------------------------------------------

def register_signature(interface_type: str, sig: InterfaceSignature) -> None:
    """注册接口类型的默认签名。"""
    _SIGNATURE_REGISTRY[interface_type] = sig


def get_signature(interface_type: str) -> InterfaceSignature | None:
    """获取接口类型的默认签名。"""
    return _SIGNATURE_REGISTRY.get(interface_type)


def reset_signatures() -> None:
    """清空签名注册表。仅供测试或编译器初始化使用。"""
    _SIGNATURE_REGISTRY.clear()
