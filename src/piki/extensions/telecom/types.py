"""Telecom 接口类型体系 (RFC-001).

定义通信行业典型的接口类型枚举、兼容性矩阵和接口→线缆映射。
"""

from __future__ import annotations

from enum import StrEnum


class InterfaceType(StrEnum):
    """通信行业典型可连接接口类型。

    光纤网络端口
    """

    # ── 光纤网络端口 ──
    SFP = "SFP"  # 1G SFP
    SFP_PLUS = "SFP+"  # 10G SFP+
    SFP28 = "SFP28"  # 25G SFP28
    QSFP_PLUS = "QSFP+"  # 40G QSFP+
    QSFP28 = "QSFP28"  # 100G QSFP28
    QSFP_DD = "QSFP-DD"  # 200G/400G QSFP-DD
    OSFP = "OSFP"  # 400G/800G OSFP
    CFP2 = "CFP2"  # 100G CFP2
    LC = "LC"  # LC 光纤连接器（裸口，如光配线架）
    SC = "SC"  # SC 光纤连接器（裸口）
    MPO_MTP = "MPO/MTP"  # MPO/MTP 多芯连接器
    CS = "CS"  # CS 双芯连接器

    # ── 铜缆网络端口 ──
    RJ45 = "RJ45"  # 1000BASE-T / 10GBASE-T
    SFP_RJ45 = "SFP-RJ45"  # 1000BASE-T SFP 电口模块
    DAC_SFP = "DAC-SFP"  # SFP 直连铜缆 (Twinax)
    DAC_QSFP = "DAC-QSFP"  # QSFP 直连铜缆

    # ── 光电两用口（Combo Port）──
    COMBO_SFP_RJ45 = "COMBO-SFP-RJ45"  # 同一端口可插 SFP 系列模块或 RJ45，互斥

    # ── 电源端口 ──
    IEC_C13 = "IEC-C13"  # 设备端母座（10A）
    IEC_C14 = "IEC-C14"  # PDU 端公头（10A）
    IEC_C19 = "IEC-C19"  # 设备端母座（16A）
    IEC_C20 = "IEC-C20"  # PDU 端公头（16A）
    NEMA_5_15 = "NEMA-5-15"  # 北美标准 15A

    # ── 射频端口 ──
    N_TYPE = "N-type"  # N 型射频连接器
    SMA = "SMA"  # SMA 射频连接器
    DIN_7_16 = "7/16 DIN"  # 7/16 DIN 射频连接器
    DIN_4_3_10 = "4.3-10"  # 4.3-10 小型射频连接器

    # ── 背板 / 扩展端口 ──
    PCIE = "PCIe"  # PCI Express 插槽
    OCP = "OCP"  # OCP 网卡插槽


# ---------------------------------------------------------------------------
# 兼容性矩阵
#
# COMPATIBILITY[port_type] = frozenset of compatible module types
# 含义：port_type 这种笼子/母口可以插入哪些类型的模块/公头。
# 兼容性是单向的：SFP28 笼子可插 SFP+ 模块，但 SFP+ 笼子不可插 SFP28 模块。
# ---------------------------------------------------------------------------

COMPATIBILITY: dict[str, frozenset[str]] = {
    # ── SFP 家族：大笼子兼容小模块 ──
    InterfaceType.SFP28: frozenset(
        {
            InterfaceType.SFP28,
            InterfaceType.SFP_PLUS,
            InterfaceType.SFP,
        }
    ),
    InterfaceType.SFP_PLUS: frozenset(
        {
            InterfaceType.SFP_PLUS,
            InterfaceType.SFP,
        }
    ),
    InterfaceType.SFP: frozenset(
        {
            InterfaceType.SFP,
        }
    ),
    # ── QSFP 家族 ──
    InterfaceType.QSFP_DD: frozenset(
        {
            InterfaceType.QSFP_DD,
            InterfaceType.QSFP28,
            InterfaceType.QSFP_PLUS,
        }
    ),
    InterfaceType.QSFP28: frozenset(
        {
            InterfaceType.QSFP28,
            InterfaceType.QSFP_PLUS,
        }
    ),
    InterfaceType.QSFP_PLUS: frozenset(
        {
            InterfaceType.QSFP_PLUS,
        }
    ),
    # ── OSFP：物理尺寸不兼容 QSFP ──
    InterfaceType.OSFP: frozenset({InterfaceType.OSFP}),
    InterfaceType.CFP2: frozenset({InterfaceType.CFP2}),
    # ── 裸光纤连接器（光配线架等）─ 自洽
    InterfaceType.LC: frozenset({InterfaceType.LC}),
    InterfaceType.SC: frozenset({InterfaceType.SC}),
    InterfaceType.MPO_MTP: frozenset({InterfaceType.MPO_MTP}),
    InterfaceType.CS: frozenset({InterfaceType.CS}),
    # ── 电源公母配对 ──
    InterfaceType.IEC_C14: frozenset({InterfaceType.IEC_C14, InterfaceType.IEC_C13}),
    InterfaceType.IEC_C13: frozenset({InterfaceType.IEC_C13, InterfaceType.IEC_C14}),
    InterfaceType.IEC_C20: frozenset({InterfaceType.IEC_C20, InterfaceType.IEC_C19}),
    InterfaceType.IEC_C19: frozenset({InterfaceType.IEC_C19, InterfaceType.IEC_C20}),
    # ── 铜缆 ──
    InterfaceType.RJ45: frozenset({InterfaceType.RJ45}),
    InterfaceType.SFP_RJ45: frozenset({InterfaceType.SFP_RJ45}),
    InterfaceType.DAC_SFP: frozenset({InterfaceType.DAC_SFP}),
    InterfaceType.DAC_QSFP: frozenset({InterfaceType.DAC_QSFP}),
    # ── 光电两用口：支持 SFP 家族与 RJ45 互斥 ──
    InterfaceType.COMBO_SFP_RJ45: frozenset(
        {
            InterfaceType.SFP,
            InterfaceType.SFP_PLUS,
            InterfaceType.SFP28,
            InterfaceType.RJ45,
        }
    ),
    # ── 射频 ──
    InterfaceType.N_TYPE: frozenset({InterfaceType.N_TYPE}),
    InterfaceType.SMA: frozenset({InterfaceType.SMA}),
    InterfaceType.DIN_7_16: frozenset({InterfaceType.DIN_7_16}),
    InterfaceType.DIN_4_3_10: frozenset({InterfaceType.DIN_4_3_10}),
    # ── 背板 ──
    InterfaceType.PCIE: frozenset({InterfaceType.PCIE}),
    InterfaceType.OCP: frozenset({InterfaceType.OCP}),
    # ── 通用 NEMA ──
    InterfaceType.NEMA_5_15: frozenset({InterfaceType.NEMA_5_15}),
}


# ---------------------------------------------------------------------------
# 接口 → 线缆类型映射
#
# 每种接口类型有对应的合法物理介质。
# 光纤端口不应配铜缆跳线。
# 未列出的接口类型不校验 cable_type。
# ---------------------------------------------------------------------------

INTERFACE_CABLE_MAP: dict[str, frozenset[str]] = {
    InterfaceType.SFP: frozenset(
        {
            "OM1-LC-LC",
            "OM2-LC-LC",
            "OM3-LC-LC",
            "OM4-LC-LC",
            "OM5-LC-LC",
            "SM-LC-LC",
            "DAC-SFP",
        }
    ),
    InterfaceType.SFP_PLUS: frozenset(
        {
            "OM3-LC-LC",
            "OM4-LC-LC",
            "SM-LC-LC",
            "DAC-SFP+",
        }
    ),
    InterfaceType.SFP28: frozenset(
        {
            "OM4-LC-LC",
            "OM5-LC-LC",
            "SM-LC-LC",
            "DAC-SFP28",
        }
    ),
    InterfaceType.QSFP_PLUS: frozenset(
        {
            "OM3-MPO-MPO",
            "OM4-MPO-MPO",
            "SM-MPO-MPO",
            "DAC-QSFP+",
        }
    ),
    InterfaceType.QSFP28: frozenset(
        {
            "OM4-MPO-MPO",
            "SM-MPO-MPO",
            "DAC-QSFP28",
        }
    ),
    InterfaceType.RJ45: frozenset(
        {
            "Cat5e-RJ45",
            "Cat6-RJ45",
            "Cat6A-RJ45",
            "Cat7-RJ45",
        }
    ),
    # ── 光电两用口：未指定 active_type 时允许光/电两类线缆 ──
    # 实际检查时会优先使用 active_type；本表作为 fallback 保留设计灵活性。
    InterfaceType.COMBO_SFP_RJ45: frozenset(
        {
            # SFP 家族光/DAC 线缆
            "OM1-LC-LC",
            "OM2-LC-LC",
            "OM3-LC-LC",
            "OM4-LC-LC",
            "OM5-LC-LC",
            "SM-LC-LC",
            "DAC-SFP",
            "DAC-SFP+",
            "DAC-SFP28",
            # RJ45 铜缆
            "Cat5e-RJ45",
            "Cat6-RJ45",
            "Cat6A-RJ45",
            "Cat7-RJ45",
        }
    ),
    InterfaceType.IEC_C14: frozenset({"IEC-C13-C14-10A", "IEC-C13-C14-16A"}),
    InterfaceType.IEC_C20: frozenset({"IEC-C19-C20-16A"}),
    InterfaceType.N_TYPE: frozenset({"LMR400-N-N", '1/2"-N-N'}),
}


# ---------------------------------------------------------------------------
# 查询函数
# ---------------------------------------------------------------------------


def are_compatible(type_a: str, type_b: str) -> bool:
    """检查两个接口类型是否兼容。

    单向兼容性查询：type_a 是否兼容 type_b。
    对 INTERFACE-COMPAT-001，调用方做双向检查。
    """
    compat_set = COMPATIBILITY.get(type_a, frozenset())
    return type_b in compat_set


def is_valid_interface_type(value: str) -> bool:
    """检查给定的字符串是否为已知的接口类型。"""
    return value in COMPATIBILITY


def known_interface_types() -> list[str]:
    """返回所有已知接口类型字符串（排序）。"""
    return sorted(COMPATIBILITY.keys())


# ---------------------------------------------------------------------------
# 注册到核心全局接口类型表
# ---------------------------------------------------------------------------

try:
    from adl.models.interface import register_interface_types

    register_interface_types(list(COMPATIBILITY.keys()))
except ImportError:  # pragma: no cover
    pass
