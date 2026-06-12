"""Mate 数据模型 —— 物理配合关系建模 (ADR-008).

Mate 表达两个实体之间的物理配合关系，与 Instance、Layout、Connection 并列。
三层配合粒度：
  L1: 机械配合（裸 Instance 引用，如 rack-mount-19inch）
  L2: 接口配合（Interface 引用，如 power-iec-c14-c13）
  L3: 跨配合链的链路（保留为 Connection，但通过光链路 Mate 表达）
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Mate 引用格式
# ---------------------------------------------------------------------------


def parse_mate_ref(ref: str) -> tuple[str, str | None]:
    """解析 Mate 的 parent/child 引用。

    支持两种格式：
      - 裸 Instance ID:  "RACK-A01" → ("RACK-A01", None)
      - Interface 引用:  "SRV-01/power-a" → ("SRV-01", "power-a")

    Args:
        ref: Mate 的 parent 或 child 引用字符串。

    Returns:
        (instance_id, interface_id) —— interface_id 在裸引用时为 None。

    Raises:
        ValueError: 引用字符串为空。
    """
    stripped = ref.strip()
    if not stripped:
        raise ValueError("Mate reference cannot be empty")
    if "/" in stripped:
        parts = stripped.split("/", 1)
        return parts[0].strip(), parts[1].strip() or None
    return stripped, None


def is_interface_ref(ref: str) -> bool:
    """判断是否是 Interface 级引用（含 /）。"""
    return "/" in ref.strip()


# ---------------------------------------------------------------------------
# 运算符
# ---------------------------------------------------------------------------


class MateConstraintOperator(str, Enum):
    """配合约束的比较运算符。"""

    LTE = "<="
    GTE = ">="
    LT = "<"
    GT = ">"
    EQ = "=="
    NE = "!="
    IN = "in"
    CONTAINS = "contains"


_OPERATOR_FNS = {
    MateConstraintOperator.LTE: lambda a, b: a <= b,
    MateConstraintOperator.GTE: lambda a, b: a >= b,
    MateConstraintOperator.LT: lambda a, b: a < b,
    MateConstraintOperator.GT: lambda a, b: a > b,
    MateConstraintOperator.EQ: lambda a, b: a == b,
    MateConstraintOperator.NE: lambda a, b: a != b,
    MateConstraintOperator.IN: lambda a, b: a in b if b is not None else False,
    MateConstraintOperator.CONTAINS: lambda a, b: (
        b in a if a is not None and b is not None else False
    ),
}


def evaluate_operator(
    left: Any,
    operator: MateConstraintOperator,
    right: Any,
) -> bool:
    """评估二元比较。

    Args:
        left: 左侧值（通常来自 child 的字段）。
        operator: 比较运算符。
        right: 右侧值（通常来自 parent 的字段或固定值）。

    Returns:
        比较结果。如果 any operand 为 None 且操作符需要非 None 值，返回 False。
    """
    fn = _OPERATOR_FNS.get(operator)
    if fn is None:
        raise ValueError(f"Unknown operator: {operator}")
    try:
        return fn(left, right)
    except TypeError:
        return False


# ---------------------------------------------------------------------------
# 约束模型
# ---------------------------------------------------------------------------


class MateConstraint(BaseModel):
    """配合引入的固有约束。

    引擎在加载 Mate 时自动验证。约束的 field 和 value_ref 的解析方式
    取决于 Mate 引用格式：
      - 裸 Instance 引用: field 对应 Pydantic 模型字段 (如 depth_mm)
      - Interface 引用:    field 对应 InterfaceSpec.specs 中的 key
    """

    field: str = Field(
        ...,
        description="被约束的字段名。L1: Pydantic 字段名; L2: InterfaceSpec.specs key。",
    )
    operator: MateConstraintOperator = Field(
        default=MateConstraintOperator.LTE,
        description="比较运算符",
    )
    value_ref: str = Field(
        ...,
        description="参照字段名 (parent 侧) 或固定值。引擎先尝试从 parent 取值，"
        "取不到时按字面量理解。",
    )
    message: str = Field(
        default="",
        description="违反时的错误描述。空时自动生成。",
    )


# ---------------------------------------------------------------------------
# 接口配对
# ---------------------------------------------------------------------------


class InterfacePairing(BaseModel):
    """依托于 Mate 的接口级配对 (L2)。

    InterfacePairing 不创建新的 Mate，而是在已有 L1 Mate 中记录
    该配合引入了哪些接口连接。这些配对应在 engine 验证时做兼容性检查。
    """

    from_ref: str = Field(
        ...,
        alias="from",
        description="配合一端的 Interface 引用: 'SRV-01/power-a'",
    )
    to_ref: str = Field(
        ...,
        alias="to",
        description="配合另一端的 Interface 引用: 'PDU-A/out-3'",
    )
    pairing_type: str = Field(
        default="",
        description="配对类型: power-iec-c14-c13, sfp28-cage, copper-rj45-cat6a",
    )

    @model_validator(mode="after")
    def _check_refs_contain_slash(self):
        """确保两端都是 Interface 级引用（含 /）。"""
        for name, value in [("from_ref", self.from_ref), ("to_ref", self.to_ref)]:
            if "/" not in value:
                raise ValueError(
                    f"InterfacePairing.{name}='{value}' 必须包含 '/' "
                    f"(格式: instance_id/interface_id)"
                )
        return self


# ---------------------------------------------------------------------------
# Mate 规格
# ---------------------------------------------------------------------------


class MateSpec(BaseModel):
    """一个物理配合关系。

    代表两个实体之间的物理配合。parent 和 child 支持两种引用格式：
      - 裸 Instance ID:        "RACK-A01"
      - Instance/Interface:    "PDU-A/out-3"

    配合检查的策略由引擎根据引用格式自动选择：
      - 两端都是裸 Instance → 查 Instance.resolved 的 Pydantic 字段
      - 任一端是 Interface → 查 InterfaceSpec.specs
    """

    type: str = Field(
        ...,
        description="配合类型: rack-mount-19inch, grid-mount, power-iec-c14-c13, optical-link",
    )
    parent: str = Field(
        ...,
        description="配合方引用 (承载物): 'RACK-A01' 或 'PDU-A/out-3'",
    )
    child: str = Field(
        ...,
        description="被配合方引用: 'SRV-01' 或 'SRV-01/power-a'",
    )
    at: dict[str, Any] = Field(
        default_factory=dict,
        description="配合锚点参数: {u_start: 10, u_span: 2} 或 {grid_id: 'B-3'}",
    )
    media: str = Field(
        default="",
        description="线缆/介质类型: OM4-LC-LC, Cat6A-RJ45",
    )
    length_m: float = Field(
        default=0.0,
        ge=0,
        description="线缆/管道长度 (m)",
    )

    constrains: list[MateConstraint] = Field(
        default_factory=list,
        description="配合的固有约束。加载时自动验证。为空时使用 Mate type 默认约束。",
    )

    pairings: list[InterfacePairing] = Field(
        default_factory=list,
        description="通过此 Mate 建立的接口配对 (L2)。",
    )

    @model_validator(mode="after")
    def _check_not_self(self):
        if self.parent == self.child:
            raise ValueError(f"Mate 两端不能相同: parent={self.parent}, child={self.child}")
        return self


# ---------------------------------------------------------------------------
# Mate 类型注册
# ---------------------------------------------------------------------------


class MateTypeMeta(BaseModel):
    """Mate 类型的元信息（由插件注册）。"""

    type: str = Field(..., description="Mate 类型标识符")
    description: str = Field(default="")
    default_constrains: list[MateConstraint] = Field(
        default_factory=list,
        description="此类型的默认约束。用户不写 constrains 时自动应用。",
    )
    applicable_parent_families: set[str] = Field(
        default_factory=set,
        description="允许作为 parent 的 Family 名称集合。空集表示不限制。",
    )
    applicable_child_families: set[str] = Field(
        default_factory=set,
        description="允许作为 child 的 Family 名称集合。空集表示不限制。",
    )


# ---------------------------------------------------------------------------
# Mate 图（引擎构建）
# ---------------------------------------------------------------------------


class MateGraph:
    """配合图：引擎加载所有 Mate 后构建的双向索引。

    不持久化，每次 `piki check` 时重建。

    属性:
        _by_parent:  {parent_ref: [MateSpec, ...]}     "我承载了什么"
        _by_child:   {child_ref: [MateSpec, ...]}      "我被谁承载"
        _by_instance: {instance_id: set[MateSpec]}     "涉及某 Instance 的所有 Mate"
    """

    def __init__(self) -> None:
        self._by_parent: dict[str, list[MateSpec]] = {}
        self._by_child: dict[str, list[MateSpec]] = {}
        self._by_instance: dict[str, list[MateSpec]] = {}
        self._all: list[MateSpec] = []

    def add(self, mate: MateSpec) -> None:
        """注册一个 Mate 到双向索引。"""
        self._all.append(mate)

        # Parent 索引
        self._by_parent.setdefault(mate.parent, []).append(mate)

        # Child 索引
        self._by_child.setdefault(mate.child, []).append(mate)

        # Instance 级索引（从 ref 提取 Instance ID）
        parent_inst, _ = parse_mate_ref(mate.parent)
        child_inst, _ = parse_mate_ref(mate.child)
        for inst_id in (parent_inst, child_inst):
            lst = self._by_instance.setdefault(inst_id, [])
            if mate not in lst:
                lst.append(mate)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def parents_of(self, ref: str) -> list[MateSpec]:
        """返回承载该引用的所有 Mate（"谁承载了我"）。"""
        return list(self._by_child.get(ref, []))

    def children_of(self, ref: str) -> list[MateSpec]:
        """返回被该引用承载的所有 Mate（"我承载了什么"）。"""
        return list(self._by_parent.get(ref, []))

    def related_to(self, instance_id: str) -> list[MateSpec]:
        """返回涉及某 Instance 的所有 Mate。"""
        return list(self._by_instance.get(instance_id, []))

    def chain(self, instance_id: str) -> list[list[MateSpec]]:
        """返回从该 Instance 到根承载物的所有配合路径。

        每条路径是从该 Instance 出发，沿 Mate 的 child→parent 方向
        追溯直到没有更多 parent 为止的完整配合链。
        """
        mates = self._by_child.get(instance_id, [])
        if not mates:
            return []

        chains: list[list[MateSpec]] = []
        for mate in mates:
            parent_inst, _ = parse_mate_ref(mate.parent)
            parent_chains = self.chain(parent_inst)
            if parent_chains:
                for pc in parent_chains:
                    chains.append([mate] + pc)
            else:
                chains.append([mate])
        return chains

    # ------------------------------------------------------------------
    # 聚合
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._all)

    def __iter__(self):
        return iter(self._all)

    def list(self) -> list[MateSpec]:
        return list(self._all)
