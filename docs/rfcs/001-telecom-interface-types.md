# RFC-001: Telecom 接口类型体系

> 状态：提案中
> 日期：2026-06-12
> 作者：piki 核心团队
> 依赖：ADR-007 (Connection 与 Interface 模型)

## 摘要

`InterfaceSpec.interface_type` 目前在框架层和 telecom 插件中均为**自由字符串**——
无枚举约束、无拼写校验、无兼容性知识库。
通信工程师写 `SFP28` 还是 `SFP-28` 全凭记忆，`INTERFACE-COMPAT-001` 只做严格相等比较。

本 RFC 在 telecom 插件内建**接口类型枚举**、**兼容性矩阵**、**接口→线缆类型映射**，
让通信工程师在 YAML 中得到拼写校验和智能提示，让 `INTERFACE-COMPAT-001` 能做真正的兼容性判断。

---

## 动机

### 现状问题

| 问题                    | 具体表现                                                                              | 影响                                 |
| ----------------------- | ------------------------------------------------------------------------------------- | ------------------------------------ |
| 无类型约束              | `interface_type: str`，写 `SFP-28`、`sfp28`、`SSFP28` 都能通过 Schema 校验            | 拼写错误到连接阶段才暴露             |
| 严格相等比较            | `INTERFACE-COMPAT-001` 只做 `==`，不知道 `SFP28` 口兼容 `SFP+` 模块                   | 合法连接误报错误                     |
| 无 cable_type 映射      | `FiberConnectionFamily.cable_type` 和 `InterfaceSpec.interface_type` 是两个独立自由字符串 | 写 `SFP28` 口配 `OM3-SC-SC` 跳线可通过校验 |
| 无领域知识              | IDE 不提示有效值，工程师需查手册或靠记忆                                                | 新人上手慢                           |
| datacenter 无 Interface | `datacenter` 插件的 `ConnectionFamily` 用 `from_container/to_container`，不参与接口兼容检查 | 方舱间连接失去自动校验               |
| 零测试覆盖              | `InterfaceSpec` 和 `INTERFACE-COMPAT-001` 无任何测试                                  | 回归风险                             |

### 期望状态

```yaml
# instances/devices/SRV-01.yaml
interfaces:
  - id: eth0
    interface_type: SFP28 # ← 拼写错误在 piki check 时报错
    direction: bidirectional
  - id: power-a
    interface_type: IEC-C14 # ← IDE 有自动补全
```

```python
# INTERFACE-COMPAT-001 增强后
# SFP28 ↔ SFP+  → 兼容（SFP28 口可插 SFP+ 模块）
# SFP28 ↔ QSFP28 → 不兼容（物理尺寸不同）
# IEC-C14 ↔ IEC-C13 → 兼容（公母配对）
```

---

## 设计方案

### 1. 接口类型枚举

在 `piki.extensions.telecom` 中新增 `types.py`，定义通信行业典型接口类型：

```python
from enum import StrEnum

class InterfaceType(StrEnum):
    # ── 光纤网络端口 ──
    SFP = "SFP"                  # 1G SFP
    SFP_PLUS = "SFP+"            # 10G SFP+
    SFP28 = "SFP28"              # 25G SFP28
    QSFP_PLUS = "QSFP+"          # 40G QSFP+
    QSFP28 = "QSFP28"            # 100G QSFP28
    QSFP_DD = "QSFP-DD"          # 200G/400G QSFP-DD
    OSFP = "OSFP"                # 400G/800G OSFP
    CFP2 = "CFP2"                # 100G CFP2
    LC = "LC"                    # LC 光纤连接器（裸口，如光配线架）
    SC = "SC"                    # SC 光纤连接器（裸口）
    MPO_MTP = "MPO/MTP"          # MPO/MTP 多芯连接器
    CS = "CS"                    # CS 双芯连接器

    # ── 铜缆网络端口 ──
    RJ45 = "RJ45"                # 1000BASE-T / 10GBASE-T
    SFP_RJ45 = "SFP-RJ45"        # 1000BASE-T SFP 电口模块
    DAC_SFP = "DAC-SFP"          # SFP 直连铜缆 (Twinax)
    DAC_QSFP = "DAC-QSFP"        # QSFP 直连铜缆

    # ── 电源端口 ──
    IEC_C13 = "IEC-C13"          # 设备端母座（10A）
    IEC_C14 = "IEC-C14"          # PDU 端公头（10A）
    IEC_C19 = "IEC-C19"          # 设备端母座（16A）
    IEC_C20 = "IEC-C20"          # PDU 端公头（16A）
    NEMA_5_15 = "NEMA-5-15"      # 北美标准 15A

    # ── 射频端口 ──
    N_TYPE = "N-type"            # N 型射频连接器
    SMA = "SMA"                  # SMA 射频连接器
    DIN_7_16 = "7/16 DIN"        # 7/16 DIN 射频连接器
    DIN_4_3_10 = "4.3-10"        # 4.3-10 小型射频连接器

    # ── 背板 / 扩展端口 ──
    PCIE = "PCIe"                # PCI Express 插槽
    OCP = "OCP"                  # OCP 网卡插槽
```

### 2. 兼容性矩阵

`interface_type` 的兼容不是等价关系，而是**有向图**。
例如 `SFP28` 端口（母口）可以插入 `SFP+` 光模块（公头），但反过来不行。

```python
# 兼容规则：(port_type, module_type) → bool
# 即「XX 端口能否插入 YY 模块」
COMPATIBILITY: dict[str, frozenset[str]] = {
    # SFP28 笼子兼容 SFP28 / SFP+ / SFP 模块
    InterfaceType.SFP28: frozenset({
        InterfaceType.SFP28, InterfaceType.SFP_PLUS, InterfaceType.SFP
    }),
    # SFP+ 笼子兼容 SFP+ / SFP 模块
    InterfaceType.SFP_PLUS: frozenset({
        InterfaceType.SFP_PLUS, InterfaceType.SFP
    }),
    # QSFP28 笼子兼容 QSFP28 / QSFP+ 模块
    InterfaceType.QSFP28: frozenset({
        InterfaceType.QSFP28, InterfaceType.QSFP_PLUS
    }),
    # QSFP-DD 笼子向后兼容 QSFP28 / QSFP+
    InterfaceType.QSFP_DD: frozenset({
        InterfaceType.QSFP_DD, InterfaceType.QSFP28, InterfaceType.QSFP_PLUS
    }),
    # OSFP 笼子不兼容 QSFP（物理尺寸不同）
    InterfaceType.OSFP: frozenset({InterfaceType.OSFP}),
    # 电源公母配对
    InterfaceType.IEC_C14: frozenset({
        InterfaceType.IEC_C14, InterfaceType.IEC_C13
    }),  # PDU 口可插设备端
    InterfaceType.IEC_C13: frozenset({
        InterfaceType.IEC_C13, InterfaceType.IEC_C14
    }),  # 设备口接受 PDU 端
    InterfaceType.IEC_C20: frozenset({
        InterfaceType.IEC_C20, InterfaceType.IEC_C19
    }),
    InterfaceType.IEC_C19: frozenset({
        InterfaceType.IEC_C19, InterfaceType.IEC_C20
    }),
    # 电口 SFP 笼子
    InterfaceType.SFP_RJ45: frozenset({InterfaceType.SFP_RJ45}),
    # DAC 直连（两端必须同类型）
    InterfaceType.DAC_SFP: frozenset({InterfaceType.DAC_SFP}),
    InterfaceType.DAC_QSFP: frozenset({InterfaceType.DAC_QSFP}),
}


def are_compatible(type_a: str, type_b: str) -> bool:
    """检查两个接口类型是否兼容。

    兼容是双向的：A 兼容 B 或 B 兼容 A 都返回 True。
    """
    compat_a = COMPATIBILITY.get(type_a, frozenset())
    return type_b in compat_a


def is_valid_interface_type(value: str) -> bool:
    """检查给定的字符串是否为已知的接口类型。"""
    return value in COMPATIBILITY
```

### 3. Interface → Cable 映射

每种接口类型有对应的物理介质。此映射用于 Connection 校验：
光纤端口不应配铜缆跳线。

```python
# 接口类型 → 合法的 cable_type 集合
INTERFACE_CABLE_MAP: dict[str, frozenset[str]] = {
    InterfaceType.SFP: frozenset({
        "OM1-LC-LC", "OM2-LC-LC", "OM3-LC-LC", "OM4-LC-LC", "OM5-LC-LC",
        "SM-LC-LC", "DAC-SFP",
    }),
    InterfaceType.SFP_PLUS: frozenset({
        "OM3-LC-LC", "OM4-LC-LC", "SM-LC-LC", "DAC-SFP+",
    }),
    InterfaceType.SFP28: frozenset({
        "OM4-LC-LC", "OM5-LC-LC", "SM-LC-LC", "DAC-SFP28",
    }),
    InterfaceType.QSFP_PLUS: frozenset({
        "OM3-MPO-MPO", "OM4-MPO-MPO", "SM-MPO-MPO", "DAC-QSFP+",
    }),
    InterfaceType.QSFP28: frozenset({
        "OM4-MPO-MPO", "SM-MPO-MPO", "DAC-QSFP28",
    }),
    InterfaceType.RJ45: frozenset({
        "Cat5e-RJ45", "Cat6-RJ45", "Cat6A-RJ45", "Cat7-RJ45",
    }),
    InterfaceType.IEC_C14: frozenset({"IEC-C13-C14-10A", "IEC-C13-C14-16A"}),
    InterfaceType.IEC_C20: frozenset({"IEC-C19-C20-16A"}),
    InterfaceType.N_TYPE: frozenset({"LMR400-N-N", '1/2"-N-N'}),
}
```

**默认规则**：若接口类型在映射表中缺失 → 不校验 cable_type（信任工程师）。

### 4. 改造 InterfaceSpec

`interface_type` 字段从 `str` 改为带校验的 Pydantic 字段：

```python
from pydantic import field_validator

class InterfaceSpec(BaseModel):
    id: str = Field(...)
    interface_type: str = Field(..., description="接口类型")
    direction: str = Field(default="bidirectional")
    description: str = Field(default="")
    specs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("interface_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if not is_valid_interface_type(v):
            import warnings
            warnings.warn(
                f"Unknown interface_type: '{v}'. "
                f"Known types: {', '.join(sorted(COMPATIBILITY.keys()))}",
                UserWarning,
            )
        return v
```

**设计决策：降级到 Warning 而非 Error。**

- 通信行业接口类型可能持续增加（新型连接器、专有接口）
- 不应阻止工程师使用枚举外的类型
- Warning 足够引起注意，Error 会造成阻断

### 5. 增强 INTERFACE-COMPAT-001

`Checker.check_interface_compatibility()` 从严格相等改为兼容性矩阵查询：

核心逻辑：

- 同类型 → 兼容（快速路径）
- 两个都是已知类型 → 查兼容性矩阵
- 至少一个未知类型 → 降级为 Warning（不做有罪推定）

```python
def check_interface_compatibility(self, ctx: Context) -> None:
    for inst in ctx.instances():
        from_ref = inst._resolved.get("from_interface")
        to_ref = inst._resolved.get("to_interface")
        if not from_ref or not to_ref:
            continue
        # ... 解析 from/to 引用（与现有代码相同）...

        if from_iface.interface_type == to_iface.interface_type:
            continue  # 同类型，肯定兼容

        if is_valid_interface_type(from_iface.interface_type) and \
           is_valid_interface_type(to_iface.interface_type):
            if are_compatible(from_iface.interface_type, to_iface.interface_type):
                continue  # 兼容矩阵判定通过

        # 两个都是已知类型但矩阵说不兼容 → Error
        if is_valid_interface_type(from_iface.interface_type) and \
           is_valid_interface_type(to_iface.interface_type):
            assert False, (
                f"接口类型不兼容: "
                f"{from_ref} (type={from_iface.interface_type}) vs "
                f"{to_ref} (type={to_iface.interface_type})"
            )

        # 至少一个未知类型 → Warning（通过 related_info）
        ctx.add_related_info(
            Location.from_path(str(inst.source)),
            f"接口类型兼容性无法判定（至少一方为未知类型）: "
            f"{from_ref} ({from_iface.interface_type}) vs "
            f"{to_ref} ({to_iface.interface_type})"
        )
    ctx.clear_current_file()
```

### 6. 新增规则：INTERFACE-CABLE-001

检查 Connection 的 `cable_type` 是否与两端接口类型匹配：

```python
# 新增 L2 内置规则
def check_cable_interface_match(self, ctx: Context) -> None:
    """检查线缆类型与接口类型是否匹配。

    光纤接口不应接铜缆，铜缆接口不应接光纤跳线。
    """
    for inst in ctx.instances():
        from_ref = inst._resolved.get("from_interface")
        to_ref = inst._resolved.get("to_interface")
        cable_type = inst._resolved.get("cable_type")
        if not from_ref or not to_ref or not cable_type:
            continue
        # ... 解析 from/to 引用 ...

        for iface, ref in [(from_iface, from_ref), (to_iface, to_ref)]:
            if not is_valid_interface_type(iface.interface_type):
                continue
            valid_cables = INTERFACE_CABLE_MAP.get(iface.interface_type, frozenset())
            if valid_cables and cable_type not in valid_cables:
                assert False, (
                    f"线缆类型不匹配: "
                    f"{ref} (type={iface.interface_type}) "
                    f"不支持 cable_type={cable_type}"
                )
```

---

## 影响范围

### 代码变更

| 文件                                         | 变更类型 | 说明                                                           |
| -------------------------------------------- | -------- | -------------------------------------------------------------- |
| `src/piki/extensions/telecom/types.py`       | **新增** | InterfaceType 枚举 + 兼容性矩阵 + 映射表                         |
| `src/piki/core/models/interface.py`          | 修改     | InterfaceSpec 增加 field_validator                               |
| `src/piki/core/engine/checker.py`            | 修改     | INTERFACE-COMPAT-001 替换为兼容性矩阵查询；新增 INTERFACE-CABLE-001 |
| `src/piki/extensions/telecom/plugin.py`      | 修改     | FiberConnectionFamily / CopperConnectionFamily 使用枚举          |
| `tests/unit/test_interface_types.py`         | **新增** | 接口类型测试                                                   |
| `tests/integration/test_interface_compat.py` | **新增** | 兼容性规则集成测试                                             |

### 向后兼容

| 场景                           | 处理                                  |
| ------------------------------ | ------------------------------------- |
| YAML 中使用已知枚举值          | 正常工作，无变化                      |
| YAML 中使用未知 interface_type | Warning（拼写检查），不阻断检查       |
| 旧 Instance 无 interfaces 字段 | 不受影响                              |
| datacenter 插件                | 暂不受影响（未使用 InterfaceSpec）    |
| 现有 sample 项目               | `SFP28`、`IEC-C14` 均在枚举中，零破坏 |

### 不在此 RFC 范围内

- ❌ 适配器建模（SFP28 → RJ45 光电转换模块作为独立 Instance）
- ❌ 接口物理位置/朝向/空间坐标
- ❌ PortFamily（设备端口号管理）—— 见 US-7
- ❌ datacenter 插件的 Interface 迁移（留给独立 RFC）
- ❌ 连续接口（焊缝、管道焊缝）

---

## 替代方案

### 方案 A：保持自由字符串 + 外部配置文件

将枚举和兼容性矩阵放在 YAML/TOML 配置文件中而非代码中。

**拒绝理由**：

- 通信接口类型是领域知识，不是项目配置
- 配置文件无法做 Pydantic field_validator
- 枚举在代码中 = IDE 自动补全和类型检查

### 方案 B：在框架层定义通用 InterfaceType

在 `piki.core.models.interface` 中定义所有行业的接口类型。

**拒绝理由**：

- 不同行业接口类型没有交集（建筑业的 M16 螺栓和通信的 SFP28 光口）
- ADR-007 已决策「连接基类不定义，领域自描述」
- 框架层定义通用类型会导致枚举膨胀和依赖污染

### 方案 C：不做任何约束，只改善文档

**拒绝理由**：文档无法在 `piki check` 时校验 YAML 拼写错误。
功能缺口不会因为文档而消失。

---

## 路线图位置

本 RFC 对应：

- **PRD (telecom)** 阶段 2 的前置依赖 — PortFamily / ConnectionFamily 的接口类型建模
- **ROADMAP** 「项目级 Family 定义」的补充 — telecom 插件内建接口领域知识
- **ADR-007** §7 「搜索路径与接口枚举」的落地 — ADR 明确说「留给后续 ADR 或领域插件」

---

## 测试计划

### 单元测试

- `InterfaceType` 枚举值是否存在
- `are_compatible(SFP28, SFP_PLUS)` → True
- `are_compatible(SFP28, QSFP28)` → False
- `are_compatible(IEC_C14, IEC_C13)` → True（公母配对）
- `is_valid_interface_type("SFP-28")` → False（拼写错误）
- `InterfaceSpec` field_validator 对未知类型发 Warning
- `INTERFACE_CABLE_MAP` 完整性和一致性

### 集成测试

- 两个 `SFP28` 接口连接 → 通过
- `SFP28` ↔ `SFP+` 连接 → 通过（兼容）
- `SFP28` ↔ `QSFP28` 连接 → 失败（不兼容）
- 未知 `interface_type` ↔ 已知类型 → Warning
- `IEC-C14` 口配 `LC-LC` 光纤 → 失败（线缆接口不匹配）

---

## 参考

- [ADR-007: Connection 与 Interface 模型](../adr/007-connection-as-instance.md)
- [Telecom PRD](../../samples/01-telecom-expansion/PRD.md)
- [IEC 60603-7: RJ45 连接器标准](https://en.wikipedia.org/wiki/IEC_60603-7)
- [SFF-8431: SFP+ 规范](https://members.snia.org/document/dl/25876)
- [QSFP-DD MSA 规范](http://www.qsfp-dd.com/)
