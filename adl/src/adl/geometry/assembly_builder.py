"""AssemblyBuilder —— 从 ADL Project 构建 AssemblyScene。

使用 ``GeometryProvider`` 和 ``constraint_solver`` 计算实例位姿，
把 Project 转换为轻量、可序列化的 ``AssemblyScene``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from adl.diagnostics import Diagnostic, Severity
from adl.geometry.assembly_scene import (
    AssemblyControl,
    AssemblyEntity,
    AssemblyMaterial,
    AssemblyScene,
    InterfacePose,
)
from adl.geometry.constraint_solver import (
    FaceConstraintParams,
    FaceName,
    ReferenceFace,
    SlotConstraintParams,
    solve_face_mate,
    solve_slot_mate,
)
from adl.geometry.interface_signature import (
    InterfaceSignature,
    SignatureCoupling,
    couple_signatures,
    get_signature,
)
from adl.geometry.models import (
    AssetReference,
    BBox,
    GeometryAssets,
    InlineGeometry,
    Transform,
    Vec3,
    bbox_from_resolved,
    compose_transforms,
)
from adl.geometry.provider import GeometryProvider
# Mate vs Layout 位姿冲突的检测阈值
_CONFLICT_TRANSLATION_THRESHOLD_MM: float = 0.5
_CONFLICT_ROTATION_THRESHOLD_DEG: float = 0.1


if TYPE_CHECKING:
    from adl.models import MateSpec
    from adl.project import Project


@dataclass
class _BuildContext:
    """构建过程中的可变上下文。"""

    scene: AssemblyScene = field(default_factory=AssemblyScene)
    # entity_id -> transform 覆盖（由 mate 求解器产出）
    overrides: dict[str, Transform] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)


class AssemblyBuilder:
    """从 ADL Project 构建 AssemblyScene。"""

    def __init__(self, project: Project) -> None:
        self.project = project
        self.provider = GeometryProvider(project)
        self.ctx = _BuildContext()

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def build(self) -> AssemblyScene:
        """构建并返回 ``AssemblyScene``。"""
        self.ctx.scene.name = self.project.config.get("project", {}).get(
            "name", self.project.root.name
        )

        # 1. 基础位姿
        self._build_base_entities()

        # 2. 根据 Mate 重新求解 child 位姿
        self._apply_mates()

        # 3. 提取 DOF / 离散状态控件
        self._extract_controls()

        # 4. 碰撞检测
        self._detect_collisions()

        self.ctx.scene.diagnostics.extend(self.ctx.diagnostics)
        return self.ctx.scene

    # ------------------------------------------------------------------
    # 基础实体
    # ------------------------------------------------------------------

    def _build_base_entities(self) -> None:
        from adl.models import get_interfaces_from_resolved

        for inst_id, inst in self.project.instances.items():
            if inst.family == "_invalid":
                continue

            geom = self.provider.resolve(inst_id)
            transform = geom.transform if geom else Transform()
            bbox = geom.bbox if geom else None

            geometry = self._resolve_geometry(inst, bbox)
            material = self._resolve_material(inst)
            interfaces = self._resolve_interfaces(inst, transform)

            entity = AssemblyEntity(
                id=inst_id,
                label=inst._resolved.get("name", inst_id),
                family=inst.family,
                transform=transform,
                geometry=geometry,
                material=material,
                interfaces=interfaces,
                resolved=dict(inst._resolved),
            )
            self.ctx.scene.entities.append(entity)

    def _resolve_geometry(
        self,
        inst: Any,
        bbox: BBox | None,
    ) -> InlineGeometry | AssetReference:
        """解析实体的几何表示：优先 assets，其次 bbox 代理 Box。"""
        assets = self._get_assets(inst)
        if assets and assets.usd:
            ref = assets.usd
            if ref.inline:
                return ref.inline
            if ref.reference or ref.usdz or ref.procedural:
                return ref

        # 降级：从 bbox 生成 Box 代理几何
        if bbox is None:
            bbox = bbox_from_resolved(inst._resolved)

        size = Vec3(
            x=bbox.width,
            y=bbox.height,
            z=bbox.depth,
        )
        if size.x <= 0 or size.y <= 0 or size.z <= 0:
            # 无尺寸时给一个 1mm 占位体，避免 viewer 崩溃
            size = Vec3(x=1.0, y=1.0, z=1.0)

        return InlineGeometry(type="box", size=size)

    def _resolve_material(self, inst: Any) -> AssemblyMaterial:
        """从 resolved 字段解析材质/颜色。"""
        resolved = inst._resolved
        color = resolved.get("color", "#888888")
        if not isinstance(color, str):
            color = "#888888"
        wireframe = bool(resolved.get("wireframe", False))
        opacity = float(resolved.get("opacity", 1.0) or 1.0)
        return AssemblyMaterial(
            color=color,
            wireframe=wireframe,
            opacity=opacity,
        )

    def _resolve_interfaces(
        self,
        inst: Any,
        global_transform: Transform,
    ) -> list[InterfacePose]:
        """计算实例所有接口的全局位姿。"""
        from adl.models import get_interfaces_from_resolved

        result: list[InterfacePose] = []
        for iface in get_interfaces_from_resolved(inst):
            iface_global = compose_transforms(global_transform, iface.local_transform)
            result.append(
                InterfacePose(
                    id=iface.id,
                    interface_type=iface.interface_type,
                    active_type=iface.active_type,
                    direction=iface.direction,
                    description=iface.description,
                    specs=dict(iface.specs),
                    transform=iface_global,
                    local_transform=iface.local_transform,
                    mating_kind=iface.mating_kind.value if hasattr(iface.mating_kind, "value") else str(iface.mating_kind),
                    mating_params=dict(iface.mating_params),
                )
            )
        return result

    def _get_assets(self, inst: Any) -> GeometryAssets | None:
        raw = inst._resolved.get("assets")
        if raw is None:
            return None
        if isinstance(raw, GeometryAssets):
            return raw
        if isinstance(raw, dict):
            try:
                return GeometryAssets.model_validate(raw)
            except Exception:
                pass
        return None

    # ------------------------------------------------------------------
    # Mate 求解
    # ------------------------------------------------------------------

    def _apply_mates(self) -> None:
        from adl.models import parse_mate_ref

        # 记录 Mate 处理前每个 child 的位姿（来自 Layout 级联）
        # key=child_id, value=覆盖前的 Transform 副本
        _pre_mate_transforms: dict[str, Transform] = {}

        # 记录已经被之前 Mate 声明过的 child，用于检测 Mate vs Mate 冲突
        _mate_claimed_children: set[str] = set()

        for mate in self.project.mates:
            _, child_ref = parse_mate_ref(mate.parent), parse_mate_ref(mate.child)
            child_id, _ = child_ref

            # 首次遭遇该 child 时保存其 Layout 位姿作为基线
            if child_id not in _pre_mate_transforms:
                child_entity = self.ctx.scene.entity_by_id(child_id)
                if child_entity is not None:
                    _pre_mate_transforms[child_id] = Transform(
                        translation=Vec3(
                            x=child_entity.transform.translation.x,
                            y=child_entity.transform.translation.y,
                            z=child_entity.transform.translation.z,
                        ),
                        rotation=Vec3(
                            x=child_entity.transform.rotation.x,
                            y=child_entity.transform.rotation.y,
                            z=child_entity.transform.rotation.z,
                        ),
                    )

            # Mate vs Mate 冲突：当前 Mate 的 child 已被前面的 Mate 认领过
            if child_id in _mate_claimed_children:
                self._emit_mate_mate_warning(mate, child_id)

            try:
                self._apply_mate(mate)
            except Exception as exc:
                self.ctx.diagnostics.append(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=f"Mate '{mate.type}' 求解失败: {exc}",
                        code="ASSEMBLY-001",
                        source="adl.geometry.assembly_builder",
                    )
                )
            else:
                # Mate 求解成功：检测 Layout vs Mate 冲突
                self._check_layout_mate_conflict(mate, child_id, _pre_mate_transforms)

            _mate_claimed_children.add(child_id)

    def _apply_mate(self, mate: MateSpec) -> None:
        from adl.models import parse_mate_ref

        mtype = mate.type
        parent_id, parent_iface_id = parse_mate_ref(mate.parent)
        child_id, child_iface_id = parse_mate_ref(mate.child)

        parent_geom = self.provider.resolve(parent_id)
        child_geom = self.provider.resolve(child_id)
        if parent_geom is None or child_geom is None:
            return

        parent_entity = self.ctx.scene.entity_by_id(parent_id)
        child_entity = self.ctx.scene.entity_by_id(child_id)
        if parent_entity is None or child_entity is None:
            return

        new_transform: Transform | None = None

        if mtype == "slot":
            new_transform = self._solve_slot(
                mate,
                parent_geom.transform,
                child_geom.transform,
                parent_entity,
                child_entity,
            )
        elif mtype in ("face-on-face", "face"):
            new_transform = self._solve_face_on_face(
                mate,
                parent_geom.transform,
                child_geom.transform,
                parent_geom.bbox,
                child_geom.bbox,
            )
        elif mtype in ("axis", "axis-on-axis"):
            # 当前 constraint_solver 的 axis 求解需要额外轴信息，暂不支持完整求解
            # 退化为 GeometryProvider 结果
            new_transform = child_geom.transform
        else:
            # 其他 mate 类型：尝试用 GeometryProvider 的 mate_transform
            new_transform = self.provider.mate_transform(mate)

        if new_transform is not None:
            self.ctx.overrides[child_id] = new_transform
            child_entity.transform = new_transform
            # 重新计算接口位姿
            child_entity.interfaces = self._recompute_interfaces_for_entity(child_entity)

    def _solve_slot(
        self,
        mate: MateSpec,
        parent_global: Transform,
        child_global: Transform,
        parent_entity: AssemblyEntity,
        child_entity: AssemblyEntity,
    ) -> Transform | None:
        at = mate.at if mate.at else {}

        # 默认从接口 local_transform 读取
        parent_iface_id, child_iface_id = self._mate_interface_ids(mate)
        default_slot_origin = self._interface_translation(parent_entity, parent_iface_id)
        default_child_offset = self._interface_translation(child_entity, child_iface_id)

        # 优先 mate.at 显式覆盖
        slot_origin = at.get("slot_origin") or at.get("parent_slot_origin") or default_slot_origin
        slot_dir = at.get("slot_dir") or at.get("parent_slot_dir") or [0, 0, 1]
        child_offset = at.get("child_interface_offset") or default_child_offset

        # 从接口 mating_params 读取 slot_dir
        if isinstance(slot_dir, list) and slot_dir == [0, 0, 1] and parent_iface_id:
            iface = self._find_interface(parent_entity, parent_iface_id)
            if iface:
                d = iface.mating_params.get("slot_dir")
                if d:
                    slot_dir = d

        t = _numeric_param(at, "t", 0.0)

        slot_origin_v = _vec3_from_value(slot_origin)
        slot_dir_v = _normalize(_vec3_from_value(slot_dir))
        child_local = Transform(translation=_vec3_from_value(child_offset))

        return solve_slot_mate(
            parent_global,
            slot_origin_v,
            slot_dir_v,
            child_local,
            SlotConstraintParams(t=t),
        )

    def _mate_interface_ids(self, mate: MateSpec) -> tuple[str | None, str | None]:
        """解析 mate parent/child 中的接口 ID。"""
        from adl.models import parse_mate_ref

        parent_id, parent_iface_id = parse_mate_ref(mate.parent)
        child_id, child_iface_id = parse_mate_ref(mate.child)
        return parent_iface_id, child_iface_id

    def _find_interface(self, entity: AssemblyEntity, iface_id: str | None) -> InterfacePose | None:
        if iface_id is None:
            return None
        for iface in entity.interfaces:
            if iface.id == iface_id:
                return iface
        return None

    def _interface_translation(
        self,
        entity: AssemblyEntity,
        iface_id: str | None,
    ) -> list[float]:
        iface = self._find_interface(entity, iface_id)
        if iface is None:
            return [0, 0, 0]
        t = iface.local_transform.translation
        return [t.x, t.y, t.z]

    def _solve_face_on_face(
        self,
        mate: MateSpec,
        parent_global: Transform,
        child_global: Transform,
        parent_bbox: BBox | None,
        child_bbox: BBox | None,
    ) -> Transform | None:
        at = mate.at if mate.at else {}
        parent_face_name = _face_name_from_value(at.get("parent_face", "top"))
        child_face_name = _face_name_from_value(at.get("child_face", "bottom"))

        if parent_bbox is None or child_bbox is None:
            return None

        parent_face = ReferenceFace.from_bbox(parent_bbox, parent_face_name)
        child_face = ReferenceFace.from_bbox(child_bbox, child_face_name)

        u = _numeric_param(at, "u", 0.0)
        v = _numeric_param(at, "v", 0.0)
        theta = _numeric_param(at, "theta_deg", 0.0)
        distance = _numeric_param(at, "distance", 0.0)

        return solve_face_mate(
            parent_global,
            parent_face,
            child_face,
            FaceConstraintParams(u=u, v=v, theta_deg=theta, distance=distance),
        )

    def _recompute_interfaces_for_entity(self, entity: AssemblyEntity) -> list[InterfacePose]:
        """实体 transform 被覆盖后，重新计算其接口全局位姿。"""
        resolved = entity.resolved
        # 从 resolved 重新解析接口
        from adl.models import get_interfaces_from_resolved
        from adl.models.base import ResolvedInstance

        dummy = ResolvedInstance(
            id=entity.id,
            family=entity.family,
            raw={},
            _resolved=resolved,
            source=None,
        )
        return self._resolve_interfaces(dummy, entity.transform)


    # ------------------------------------------------------------------
    # 冲突检测
    # ------------------------------------------------------------------

    def _emit_mate_mate_warning(self, mate: "MateSpec", child_id: str) -> None:
        """当一个 child 被多个 Mate 认领时发出警告。"""
        self.ctx.diagnostics.append(
            Diagnostic(
                severity=Severity.WARNING,
                message=(
                    f"'{child_id}' 被多个 Mate 声明控制权。"
                    f"Mate 类型='{mate.type}' 的位姿结果将被采纳，"
                    f"前置 Mate 的结果已丢弃。"
                    f"建议: 检查 '{child_id}' 的 Mate 声明是否冗余或冲突。"
                ),
                code="ASSEMBLY-003",
                source="adl.geometry.assembly_builder",
            )
        )

    def _check_layout_mate_conflict(
        self,
        mate: "MateSpec",
        child_id: str,
        pre_mate_transforms: dict[str, Transform],
    ) -> None:
        """检测 Layout 分配的位姿与 Mate 解算结果之间是否存在显著差异。

        仅在 child 有显式 Layout 声明时报告冲突——纯 Mate 驱动（无 Layout entry、
        或 entry 为 fallback 零位姿）的 child 是合法的设计意图，不需要警告。
        """
        # 检查 child 是否有显式 Layout 声明
        layout = self.project.layout
        has_explicit_layout = False
        if layout is not None:
            entry = layout.get(child_id)
            if entry is not None:
                # 有 entry 且有实际坐标（非全零 fallback）
                has_explicit_layout = (
                    entry.position_x_mm is not None
                    or entry.position_y_mm is not None
                    or entry.position_z_mm is not None
                    or entry.parent is not None
                    or entry.rack_id is not None
                )

        if not has_explicit_layout:
            # 纯 Mate 驱动：没有 Layout 声明，不会冲突
            return

        child_entity = self.ctx.scene.entity_by_id(child_id)
        if child_entity is None:
            return

        pre_tf = pre_mate_transforms.get(child_id)
        if pre_tf is None:
            return

        post_tf = child_entity.transform

        dx = post_tf.translation.x - pre_tf.translation.x
        dy = post_tf.translation.y - pre_tf.translation.y
        dz = post_tf.translation.z - pre_tf.translation.z
        dist = (dx * dx + dy * dy + dz * dz) ** 0.5

        drx = post_tf.rotation.x - pre_tf.rotation.x
        dry = post_tf.rotation.y - pre_tf.rotation.y
        drz = post_tf.rotation.z - pre_tf.rotation.z
        angle_diff = abs(drx) + abs(dry) + abs(drz)

        if dist > _CONFLICT_TRANSLATION_THRESHOLD_MM or angle_diff > _CONFLICT_ROTATION_THRESHOLD_DEG:
            self.ctx.diagnostics.append(
                Diagnostic(
                    severity=Severity.WARNING,
                    message=(
                        f"'{child_id}' 的位姿由 Mate '{mate.type}' 重新计算，"
                        f"与 Layout 声明存在差异: "
                        f"平移 Δ=({dx:+.1f}, {dy:+.1f}, {dz:+.1f})mm, "
                        f"欧拉角 Δ≈({drx:+.1f}, {dry:+.1f}, {drz:+.1f})°"
                    ),
                    code="ASSEMBLY-002",
                    source="adl.geometry.assembly_builder",
                )
            )

    def _check_mate_mate_conflict(self, mate: "MateSpec", child_id: str) -> None:
        """检测同一个 child 是否被多个 Mate 声明控制权。

        当多个 Mate 都认领同一个 child 时，只保留最后一个生效，
        产生警告通知用户存在冗余或冲突声明。

        注意：此检查由 _apply_mates 在 _apply_mate 调用前通过 _mate_claimed_children
        集合控制，避免将同一 Mate 的自身写入误判为冲突。
        """
        # 实际检查在外层 _apply_mates 循环中完成，
        # 通过 _mate_claimed_children 集合判断。
        # 此方法为占位，保留接口一致性。
        pass

    # ------------------------------------------------------------------
    # 控件提取
    # ------------------------------------------------------------------

    def _extract_controls(self) -> None:
        """从 Mate 的 at 参数和接口签名中提取前端控件。"""
        for mate in self.project.mates:
            self._extract_mate_controls(mate)

    def _extract_mate_controls(self, mate: MateSpec) -> None:
        from adl.models import parse_mate_ref

        at = mate.at if mate.at else {}
        child_id, _ = parse_mate_ref(mate.child)

        # Mate 直接声明的连续参数
        for param_name in ("t", "u", "v", "theta_deg", "theta", "distance"):
            spec = at.get(param_name)
            if spec is None:
                continue
            if isinstance(spec, dict):
                ctrl = AssemblyControl(
                    id=f"{mate.type}:{mate.parent}->{mate.child}:{param_name}",
                    type="slider",
                    target=f"{mate.parent}→{mate.child}",
                    param=param_name,
                    label=spec.get("label", param_name),
                    min=float(spec.get("min", 0)),
                    max=float(spec.get("max", 0)),
                    default=float(spec.get("default", 0)),
                    step=float(spec.get("step", 1)),
                )
            else:
                # 简单数值，默认范围
                ctrl = AssemblyControl(
                    id=f"{mate.type}:{mate.parent}->{mate.child}:{param_name}",
                    type="slider",
                    target=f"{mate.parent}→{mate.child}",
                    param=param_name,
                    label=param_name,
                    min=0.0,
                    max=float(spec) * 2 if spec else 100.0,
                    default=float(spec) if spec else 0.0,
                    step=1.0,
                )
            self.ctx.scene.controls.append(ctrl)

        # 接口签名中的离散状态
        parent_id, parent_iface_id = parse_mate_ref(mate.parent)
        child_id, child_iface_id = parse_mate_ref(mate.child)
        sig_coupling = self._resolve_signature_coupling(
            parent_id, parent_iface_id, child_id, child_iface_id
        )
        sig_states = sig_coupling.allowed_states if sig_coupling else []

        # mate 显式 stages 中提到的 required_state 也加入离散状态
        stage_states: set[str] = set()
        for stage in mate.at.get("stages", []):
            rs = stage.get("required_state")
            if rs:
                stage_states.add(rs)
        if stage_states:
            stage_states.add("removed")  # 默认拔出态

        all_states = sorted(set(sig_states) | stage_states)
        if all_states:
            default_state = "inserted" if "inserted" in all_states else all_states[0]
            ctrl = AssemblyControl(
                id=f"{mate.type}:{mate.parent}->{mate.child}:state",
                type="button",
                target=f"{mate.parent}→{mate.child}",
                param="state",
                label=f"{mate.type} 状态",
                states=all_states,
                current_state=default_state,
            )
            self.ctx.scene.controls.append(ctrl)

    def _resolve_signature_coupling(
        self,
        parent_id: str,
        parent_iface_id: str | None,
        child_id: str,
        child_iface_id: str | None,
    ) -> SignatureCoupling | None:
        parent_sig: InterfaceSignature | None = None
        child_sig: InterfaceSignature | None = None

        parent_entity = self.ctx.scene.entity_by_id(parent_id)
        if parent_entity and parent_iface_id:
            for iface in parent_entity.interfaces:
                if iface.id == parent_iface_id:
                    # 从 interface_type 查默认签名
                    from adl.geometry import get_signature

                    parent_sig = get_signature(iface.interface_type)
                    break

        child_entity = self.ctx.scene.entity_by_id(child_id)
        if child_entity and child_iface_id:
            for iface in child_entity.interfaces:
                if iface.id == child_iface_id:
                    from adl.geometry import get_signature

                    child_sig = get_signature(iface.interface_type)
                    break

        if parent_sig is None and child_sig is None:
            return None
        return couple_signatures(parent_sig, child_sig)

    # ------------------------------------------------------------------
    # 碰撞检测
    # ------------------------------------------------------------------

    def _detect_collisions(self) -> None:
        """使用 GeometryProvider 检测碰撞并记录。"""
        self.ctx.scene.collisions = self.provider.collisions()


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _vec3_from_value(value: Any) -> Vec3:
    """把 [x, y, z] 列表或 dict 转成 Vec3。"""
    if isinstance(value, Vec3):
        return value
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return Vec3(x=float(value[0]), y=float(value[1]), z=float(value[2]))
    if isinstance(value, dict):
        return Vec3(
            x=float(value.get("x", 0)),
            y=float(value.get("y", 0)),
            z=float(value.get("z", 0)),
        )
    return Vec3(x=0, y=0, z=0)


def _normalize(v: Vec3) -> Vec3:
    """归一化向量。"""
    import math

    length = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)
    if length == 0:
        return Vec3(x=0, y=0, z=1)
    return Vec3(x=v.x / length, y=v.y / length, z=v.z / length)


def _face_name_from_value(value: Any) -> FaceName:
    """把字符串转成 FaceName，容错。"""
    if isinstance(value, FaceName):
        return value
    text = str(value).lower().strip()
    mapping = {
        "top": FaceName.TOP,
        "bottom": FaceName.BOTTOM,
        "front": FaceName.FRONT,
        "rear": FaceName.REAR,
        "back": FaceName.REAR,
        "left": FaceName.LEFT,
        "right": FaceName.RIGHT,
    }
    return mapping.get(text, FaceName.TOP)


def _numeric_param(at: dict[str, Any], key: str, default: float) -> float:
    """从 mate.at 读取数值参数，支持直接数值或 {default: ...} dict。"""
    value = at.get(key)
    if value is None:
        return default
    if isinstance(value, dict):
        return float(value.get("default", value.get("value", default)))
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
