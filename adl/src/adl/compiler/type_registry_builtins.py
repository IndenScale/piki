"""内置类型注册 —— 将接口类型、签名、mating 默认值集中注册。

编译器核心不包含任何领域知识。领域数据通过此模块在应用启动时注册。
piki 的 main() 或插件 register_types() 调用此模块的函数。
"""

from __future__ import annotations

from adl.compiler.mating_kinds import register_mating_defaults, reset_mating_defaults
from adl.geometry import (
    DOF,
    DiscreteState,
    DOFType,
    InterfaceSignature,
    SignatureStage,
    register_signature,
    reset_signatures,
)
from adl.models.interface import register_interface_types, reset_known_interface_types


def register_all_builtins() -> None:
    """注册所有内置接口类型、签名和 mating 默认值。

    这些是通用机械/电子领域的基础类型。
    领域特定的类型（电信、键盘等）由对应插件注册。

    每次调用先清空全局注册表，确保编译器初始状态确定。
    """
    reset_known_interface_types()
    reset_mating_defaults()
    reset_signatures()
    _register_interface_types()
    _register_mating_defaults()
    _register_signatures()


def _register_interface_types() -> None:
    """注册已知接口类型。"""
    # 电源
    register_interface_types(["IEC-C13", "IEC-C14"])
    # 光模块
    register_interface_types(["SFP28-cage", "SFP28-module", "QSFP28-cage", "QSFP28-module"])
    # 网络
    register_interface_types(["RJ45-jack", "RJ45-plug"])
    # USB
    register_interface_types(["USB-C-receptacle", "USB-C-plug"])
    # 音频
    register_interface_types(["TRS-3.5mm-jack", "TRS-3.5mm-plug"])
    # 机械
    register_interface_types([
        "rack-mount-rail", "rack-mount-ear", "screw-hole", "standoff",
        "drawer-slide-female", "drawer-slide-male",
        "hinge-frame", "hinge-leaf",
    ])
    # 键盘（基础机械轴体）
    register_interface_types(["mx-stem", "mx-socket", "plate-cutout"])
    # 光纤
    register_interface_types(["FC-fiber-plug", "FC-fiber-adapter"])


def _register_mating_defaults() -> None:
    """注册接口类型的默认 mating_kind。"""
    # 电源
    register_mating_defaults("IEC-C14", "face")
    register_mating_defaults("IEC-C13", "face")
    # 光模块
    register_mating_defaults("SFP28-cage", "slot")
    register_mating_defaults("SFP28-module", "slot")
    register_mating_defaults("QSFP28-cage", "slot")
    register_mating_defaults("QSFP28-module", "slot")
    # 网络
    register_mating_defaults("RJ45-jack", "slot")
    register_mating_defaults("RJ45-plug", "slot")
    # 机械
    register_mating_defaults("rack-mount-rail", "rail")
    register_mating_defaults("rack-mount-ear", "face")
    register_mating_defaults("screw-hole", "axis")
    register_mating_defaults("standoff", "face")
    # 键盘
    register_mating_defaults("mx-stem", "axis")
    register_mating_defaults("mx-socket", "axis")
    register_mating_defaults("plate-cutout", "face")
    # 光纤
    register_mating_defaults("FC-fiber-plug", "slot")
    register_mating_defaults("FC-fiber-adapter", "slot")
    # USB
    register_mating_defaults("USB-C-receptacle", "slot")
    register_mating_defaults("USB-C-plug", "slot")
    # 音频
    register_mating_defaults("TRS-3.5mm-jack", "axis")
    register_mating_defaults("TRS-3.5mm-plug", "axis")


def _register_signatures() -> None:
    """注册接口类型的默认 INS。"""

    # ── USB-C ──
    usb_states = [
        DiscreteState("removed", "拔出", None),
        DiscreteState("inserted", "正插", None, is_default=True),
        DiscreteState("reversed", "反插", None),
    ]
    # 正插 transform=identity, 反插 transform=rotate 180° about Z
    from adl.geometry import Transform, Vec3
    usb_states[1].transform_delta = Transform()
    usb_states[2].transform_delta = Transform(rotation=Vec3(z=180))

    register_signature("USB-C-receptacle", InterfaceSignature(discrete_states=usb_states))
    register_signature("USB-C-plug", InterfaceSignature(discrete_states=[
        DiscreteState("removed", "拔出", None),
        DiscreteState("inserted", "正插", Transform(), is_default=True),
        DiscreteState("reversed", "反插", Transform(rotation=Vec3(z=180))),
    ]))

    # ── 3.5mm TRS ──
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

    # ── IEC-C13/C14 ──
    iec_states = [
        DiscreteState("removed", "拔出", None),
        DiscreteState("inserted", "插入", Transform(), is_default=True),
    ]
    register_signature("IEC-C13", InterfaceSignature(discrete_states=iec_states))
    register_signature("IEC-C14", InterfaceSignature(discrete_states=iec_states))

    # ── 抽屉 ──
    drawer_states = [
        DiscreteState("closed", "闭合", Transform(), is_default=True),
    ]
    drawer_dofs = [DOF(DOFType.TRANSLATE, Vec3(z=1), (0, 300), default_value=0, label="拉出距离")]
    register_signature("drawer-slide-female", InterfaceSignature(
        discrete_states=drawer_states, continuous_dofs=drawer_dofs,
    ))
    register_signature("drawer-slide-male", InterfaceSignature(
        discrete_states=drawer_states, continuous_dofs=drawer_dofs,
    ))

    # ── 铰链 ──
    hinge_states = [
        DiscreteState("closed", "闭合", Transform(), is_default=True),
    ]
    hinge_dofs = [DOF(DOFType.ROTATE, Vec3(y=1), (0, 180), default_value=0, label="开门角度")]
    register_signature("hinge-frame", InterfaceSignature(
        discrete_states=hinge_states, continuous_dofs=hinge_dofs,
    ))
    register_signature("hinge-leaf", InterfaceSignature(
        discrete_states=hinge_states, continuous_dofs=hinge_dofs,
    ))

    # ── SFP28 ──
    sfp_states = [
        DiscreteState("removed", "拔出", None),
        DiscreteState("inserted", "插入", Transform(), is_default=True),
    ]
    register_signature("SFP28-cage", InterfaceSignature(discrete_states=sfp_states))
    register_signature("SFP28-module", InterfaceSignature(discrete_states=sfp_states))
    register_signature("QSFP28-cage", InterfaceSignature(discrete_states=sfp_states))
    register_signature("QSFP28-module", InterfaceSignature(discrete_states=sfp_states))

    # ── RJ45 ──
    register_signature("RJ45-jack", InterfaceSignature(discrete_states=sfp_states))
    register_signature("RJ45-plug", InterfaceSignature(discrete_states=sfp_states))

    # ── 螺丝 ──
    screw_states = [
        DiscreteState("removed", "拔出", None),
        DiscreteState("seated", "旋入到接触面", Transform(), is_default=True),
    ]
    screw_dofs = [DOF(DOFType.SCREW, Vec3(z=1), (0, 25), default_value=0, label="旋入深度")]
    register_signature("screw-hole", InterfaceSignature(
        discrete_states=screw_states, continuous_dofs=screw_dofs,
    ))
    register_signature("screw-thread", InterfaceSignature(
        discrete_states=screw_states, continuous_dofs=screw_dofs,
    ))

    # ── FC 光纤 ──
    # 两阶段装配：先插入到底，再旋转锁紧
    # 旋转自由度仅在 "inserted"（插入到底）或 "removed"（拔出）状态激活
    fc_states = [
        DiscreteState("removed", "拔出", None),
        DiscreteState("inserted", "插入到底", Transform(), is_default=True),
    ]
    fc_dofs = [
        DOF(DOFType.TRANSLATE, Vec3(z=1), (0, 15), default_value=15, label="插入深度"),
        DOF(DOFType.ROTATE, Vec3(z=1), (0, 30), default_value=0, label="旋转角度"),
    ]
    fc_stages = [
        SignatureStage(order=0, name="free", label="自由阶段",
                       required_state=None,
                       activates_dofs=["插入深度"],
                       deactivates_dofs=["旋转角度"]),
        SignatureStage(order=1, name="locked", label="锁紧阶段",
                       required_state="inserted",
                       activates_dofs=["旋转角度"],
                       deactivates_dofs=[]),
    ]
    register_signature("FC-fiber-plug", InterfaceSignature(
        discrete_states=fc_states, continuous_dofs=fc_dofs, stages=fc_stages,
    ))
    register_signature("FC-fiber-adapter", InterfaceSignature(
        discrete_states=fc_states, continuous_dofs=fc_dofs, stages=fc_stages,
    ))
