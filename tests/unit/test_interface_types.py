"""单元测试：Telecom 接口类型体系 (RFC-001)."""

from __future__ import annotations

import warnings

from piki.extensions.telecom.types import (
    COMPATIBILITY,
    INTERFACE_CABLE_MAP,
    InterfaceType,
    are_compatible,
    is_valid_interface_type,
    known_interface_types,
)


class TestInterfaceTypeEnum:
    """InterfaceType 枚举完整性。"""

    def test_all_members_have_string_values(self) -> None:
        for member in InterfaceType:
            assert isinstance(member.value, str)
            assert len(member.value) > 0

    def test_port_types_present(self) -> None:
        # 光纤网络端口
        assert InterfaceType.SFP == "SFP"
        assert InterfaceType.SFP_PLUS == "SFP+"
        assert InterfaceType.SFP28 == "SFP28"
        assert InterfaceType.QSFP_PLUS == "QSFP+"
        assert InterfaceType.QSFP28 == "QSFP28"
        assert InterfaceType.QSFP_DD == "QSFP-DD"
        assert InterfaceType.OSFP == "OSFP"

    def test_power_types_present(self) -> None:
        assert InterfaceType.IEC_C13 == "IEC-C13"
        assert InterfaceType.IEC_C14 == "IEC-C14"
        assert InterfaceType.IEC_C19 == "IEC-C19"
        assert InterfaceType.IEC_C20 == "IEC-C20"

    def test_rf_types_present(self) -> None:
        assert InterfaceType.N_TYPE == "N-type"
        assert InterfaceType.SMA == "SMA"
        assert InterfaceType.DIN_7_16 == "7/16 DIN"
        assert InterfaceType.DIN_4_3_10 == "4.3-10"

    def test_combo_type_present(self) -> None:
        assert InterfaceType.COMBO_SFP_RJ45 == "COMBO-SFP-RJ45"


class TestCompatibilityMatrix:
    """兼容性矩阵测试。"""

    # ── SFP 家族：大笼子兼容小模块 ──

    def test_sfp28_accepts_sfp28(self) -> None:
        assert are_compatible(InterfaceType.SFP28, InterfaceType.SFP28) is True

    def test_sfp28_accepts_sfp_plus(self) -> None:
        """SFP28 笼子可插 SFP+ 模块。"""
        assert are_compatible(InterfaceType.SFP28, InterfaceType.SFP_PLUS) is True

    def test_sfp28_accepts_sfp(self) -> None:
        """SFP28 笼子可插 SFP 模块。"""
        assert are_compatible(InterfaceType.SFP28, InterfaceType.SFP) is True

    def test_sfp_plus_rejects_sfp28(self) -> None:
        """SFP+ 笼子不可插 SFP28 模块（单向）。"""
        assert are_compatible(InterfaceType.SFP_PLUS, InterfaceType.SFP28) is False

    def test_sfp_plus_accepts_sfp(self) -> None:
        assert are_compatible(InterfaceType.SFP_PLUS, InterfaceType.SFP) is True

    # ── QSFP 家族 ──

    def test_qsfp_dd_accepts_qsfp28(self) -> None:
        assert are_compatible(InterfaceType.QSFP_DD, InterfaceType.QSFP28) is True

    def test_qsfp_dd_accepts_qsfp_plus(self) -> None:
        assert are_compatible(InterfaceType.QSFP_DD, InterfaceType.QSFP_PLUS) is True

    def test_qsfp28_rejects_qsfp_dd(self) -> None:
        """QSFP28 笼子不可插 QSFP-DD 模块（尺寸更大）。"""
        assert are_compatible(InterfaceType.QSFP28, InterfaceType.QSFP_DD) is False

    # ── 跨家族不兼容 ──

    def test_sfp28_rejects_qsfp28(self) -> None:
        """SFP28 和 QSFP28 物理尺寸不同。"""
        assert are_compatible(InterfaceType.SFP28, InterfaceType.QSFP28) is False

    def test_qsfp28_rejects_sfp28(self) -> None:
        assert are_compatible(InterfaceType.QSFP28, InterfaceType.SFP28) is False

    def test_osfp_rejects_qsfp28(self) -> None:
        """OSFP 物理尺寸不兼容 QSFP。"""
        assert are_compatible(InterfaceType.OSFP, InterfaceType.QSFP28) is False

    # ── 电源公母配对 ──

    def test_iec_c14_accepts_c13(self) -> None:
        """PDU 端 C14 口接受设备端 C13。"""
        assert are_compatible(InterfaceType.IEC_C14, InterfaceType.IEC_C13) is True

    def test_iec_c13_accepts_c14(self) -> None:
        """设备端 C13 口接受 PDU 端 C14。"""
        assert are_compatible(InterfaceType.IEC_C13, InterfaceType.IEC_C14) is True

    def test_iec_c20_accepts_c19(self) -> None:
        assert are_compatible(InterfaceType.IEC_C20, InterfaceType.IEC_C19) is True

    def test_iec_c14_rejects_c20(self) -> None:
        """C14(10A) 和 C20(16A) 互不兼容。"""
        assert are_compatible(InterfaceType.IEC_C14, InterfaceType.IEC_C20) is False

    # ── 铜缆 ──

    def test_rj45_only_self(self) -> None:
        assert are_compatible(InterfaceType.RJ45, InterfaceType.RJ45) is True
        assert are_compatible(InterfaceType.RJ45, InterfaceType.SFP) is False

    def test_dac_sfp_only_self(self) -> None:
        assert are_compatible(InterfaceType.DAC_SFP, InterfaceType.DAC_SFP) is True
        assert are_compatible(InterfaceType.DAC_SFP, InterfaceType.SFP28) is False

    # ── 光电两用口 ──

    def test_combo_accepts_sfp(self) -> None:
        """COMBO 口可插 SFP 模块。"""
        assert are_compatible(InterfaceType.COMBO_SFP_RJ45, InterfaceType.SFP) is True

    def test_combo_accepts_sfp_plus(self) -> None:
        assert are_compatible(InterfaceType.COMBO_SFP_RJ45, InterfaceType.SFP_PLUS) is True

    def test_combo_accepts_sfp28(self) -> None:
        assert are_compatible(InterfaceType.COMBO_SFP_RJ45, InterfaceType.SFP28) is True

    def test_combo_accepts_rj45(self) -> None:
        assert are_compatible(InterfaceType.COMBO_SFP_RJ45, InterfaceType.RJ45) is True

    def test_combo_rejects_qsfp28(self) -> None:
        """COMBO 口不支持 QSFP28（物理尺寸不同）。"""
        assert are_compatible(InterfaceType.COMBO_SFP_RJ45, InterfaceType.QSFP28) is False

    def test_sfp_does_not_accept_combo(self) -> None:
        """普通 SFP 口不能作为 COMBO 口的对端（单向兼容性）。"""
        assert are_compatible(InterfaceType.SFP, InterfaceType.COMBO_SFP_RJ45) is False


class TestIsValidInterfaceType:
    """类型校验函数测试。"""

    def test_known_types_valid(self) -> None:
        assert is_valid_interface_type("SFP28") is True
        assert is_valid_interface_type("IEC-C14") is True
        assert is_valid_interface_type("N-type") is True

    def test_unknown_misspelling(self) -> None:
        """常见拼写错误应返回 False。"""
        assert is_valid_interface_type("SFP-28") is False
        assert is_valid_interface_type("sfp28") is False
        assert is_valid_interface_type("SSFP28") is False
        assert is_valid_interface_type("QSFP28+") is False

    def test_empty_string(self) -> None:
        assert is_valid_interface_type("") is False

    def test_arbitrary_string(self) -> None:
        assert is_valid_interface_type("custom-connector-v2") is False

    def test_known_interface_types_list(self) -> None:
        """known_interface_types() 返回排序列表。"""
        types = known_interface_types()
        assert isinstance(types, list)
        assert "SFP28" in types
        assert "IEC-C14" in types
        assert types == sorted(types)
        # 每个已知类型都在 COMPATIBILITY 中
        for t in types:
            assert t in COMPATIBILITY


class TestInterfaceCableMap:
    """接口→线缆映射测试。"""

    def test_sfp28_supports_om4_lc(self) -> None:
        cables = INTERFACE_CABLE_MAP.get(InterfaceType.SFP28, frozenset())
        assert "OM4-LC-LC" in cables

    def test_sfp28_supports_sm(self) -> None:
        cables = INTERFACE_CABLE_MAP.get(InterfaceType.SFP28, frozenset())
        assert "SM-LC-LC" in cables

    def test_qsfp28_supports_mpo(self) -> None:
        cables = INTERFACE_CABLE_MAP.get(InterfaceType.QSFP28, frozenset())
        assert "OM4-MPO-MPO" in cables

    def test_rj45_supports_cat6a(self) -> None:
        cables = INTERFACE_CABLE_MAP.get(InterfaceType.RJ45, frozenset())
        assert "Cat6A-RJ45" in cables

    def test_rj45_rejects_fiber_cable(self) -> None:
        """RJ45 口不应支持光纤跳线。"""
        cables = INTERFACE_CABLE_MAP.get(InterfaceType.RJ45, frozenset())
        assert "OM4-LC-LC" not in cables

    def test_sfp28_rejects_copper_cable(self) -> None:
        """SFP28 光口不应支持 Cat6A 铜缆。"""
        cables = INTERFACE_CABLE_MAP.get(InterfaceType.SFP28, frozenset())
        assert "Cat6A-RJ45" not in cables

    def test_iec_c14_power_cables(self) -> None:
        cables = INTERFACE_CABLE_MAP.get(InterfaceType.IEC_C14, frozenset())
        assert "IEC-C13-C14-10A" in cables

    def test_missing_type_returns_empty(self) -> None:
        """接口类型未在映射表 → 返回空 frozenset。"""
        cables = INTERFACE_CABLE_MAP.get("UNKNOWN-TYPE", frozenset())
        assert cables == frozenset()

    def test_combo_supports_fiber_and_copper(self) -> None:
        """COMBO 口未指定 active_type 时允许光/电两类线缆。"""
        cables = INTERFACE_CABLE_MAP.get(InterfaceType.COMBO_SFP_RJ45, frozenset())
        assert "OM4-LC-LC" in cables
        assert "Cat6A-RJ45" in cables


class TestEffectiveInterfaceType:
    """effective_interface_type 辅助函数测试。"""

    def test_no_active_type_fallback(self) -> None:
        from adl.models.interface import InterfaceSpec, effective_interface_type

        spec = InterfaceSpec(id="eth0", interface_type="SFP28")
        assert effective_interface_type(spec) == "SFP28"

    def test_active_type_takes_precedence(self) -> None:
        from adl.models.interface import InterfaceSpec, effective_interface_type

        spec = InterfaceSpec(id="eth0", interface_type="COMBO-SFP-RJ45", active_type="RJ45")
        assert effective_interface_type(spec) == "RJ45"


class TestInterfaceSpecValidator:
    """InterfaceSpec field_validator 测试 (RFC-001)."""

    def test_known_type_no_warning(self) -> None:
        from adl.models.interface import InterfaceSpec

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            spec = InterfaceSpec(id="eth0", interface_type="SFP28")
            assert spec.interface_type == "SFP28"
            assert len(w) == 0  # 已知类型无 Warning

    def test_unknown_type_emits_warning(self) -> None:
        from adl.models.interface import InterfaceSpec

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            spec = InterfaceSpec(id="custom-port", interface_type="SFP-28")
            assert spec.interface_type == "SFP-28"  # 仍接受值
            assert len(w) == 1
            assert "Unknown interface_type" in str(w[0].message)
            assert "SFP-28" in str(w[0].message)

    def test_active_type_optional(self) -> None:
        from adl.models.interface import InterfaceSpec

        spec = InterfaceSpec(id="eth0", interface_type="COMBO-SFP-RJ45", active_type="SFP28")
        assert spec.active_type == "SFP28"

    def test_active_type_defaults_to_none(self) -> None:
        from adl.models.interface import InterfaceSpec

        spec = InterfaceSpec(id="eth0", interface_type="SFP28")
        assert spec.active_type is None
