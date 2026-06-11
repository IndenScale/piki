"""USD 场景生成器 —— `piki generate usd-scene`。

支持：
- 外部 USD 引用（assets.usd.reference）
- 内联代理几何（assets.usd.inline）
- CSG 程序化几何（assets.usd.procedural）→ 烘焙为 Mesh
- 无资产时根据 physical 尺寸生成 Box 代理几何
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ...core.engine.checker import generator
from ...core.engine.context import Context
from ...core.models.geometry import (
    CSGNode,
    GeometryAssets,
    InlineGeometry,
    Vec3,
)

logger = logging.getLogger(__name__)


def _has_usd_core() -> bool:
    try:
        import pxr  # noqa: F401

        return True
    except ImportError:
        return False


def _mm_to_m(mm: float) -> float:
    return mm / 1000.0


def _build_proxy_box(
    width_mm: float,
    height_mm: float,
    depth_mm: float,
    stage: Any,
    prim_path: str,
    name: str,
    tx: float = 0.0,
    ty: float = 0.0,
    tz: float = 0.0,
) -> Any:
    """根据物理尺寸生成 Box 代理几何。"""
    from pxr import Gf, UsdGeom

    xform = UsdGeom.Xform.Define(stage, prim_path)
    xform.GetPrim().SetDisplayName(name)

    size = (_mm_to_m(width_mm), _mm_to_m(height_mm), _mm_to_m(depth_mm))
    cube = UsdGeom.Cube.Define(stage, prim_path + "/geometry")
    cube.CreateSizeAttr().Set(1.0)

    # 组合缩放 + 平移
    xf = Gf.Matrix4d()
    xf.SetScale(Gf.Vec3d(*size))
    xf.SetTranslateOnly(Gf.Vec3d(tx, ty, tz))
    cube.AddTransformOp().Set(xf)

    # 设置显示颜色（灰色代理）
    cube.CreateDisplayColorAttr().Set([(0.7, 0.7, 0.7)])

    return xform


def _build_inline_geometry(
    inline: InlineGeometry,
    stage: Any,
    prim_path: str,
    name: str,
) -> Any:
    """将 InlineGeometry 写入 USD。"""
    from pxr import Gf, UsdGeom

    xform = UsdGeom.Xform.Define(stage, prim_path)
    xform.GetPrim().SetDisplayName(name)

    t = inline.transform.translation if inline.transform else Vec3(x=0, y=0, z=0)
    inline.transform.rotation if inline.transform else Vec3(x=0, y=0, z=0)
    s = inline.transform.scale if inline.transform else Vec3(x=1, y=1, z=1)

    geom_path = prim_path + "/geometry"

    if inline.type == "box":
        if inline.size is None:
            raise ValueError("box requires size")
        cube = UsdGeom.Cube.Define(stage, geom_path)
        cube.CreateSizeAttr().Set(1.0)
        # 应用变换
        xf = Gf.Matrix4d()
        xf.SetScale(Gf.Vec3d(inline.size.x * s.x, inline.size.y * s.y, inline.size.z * s.z))
        xf.SetTranslateOnly(Gf.Vec3d(t.x, t.y, t.z))
        cube.AddTransformOp().Set(xf)
        cube.CreateDisplayColorAttr().Set([(0.5, 0.6, 0.8)])
        return xform

    if inline.type == "cylinder":
        if inline.radius is None or inline.height is None:
            raise ValueError("cylinder requires radius and height")
        cyl = UsdGeom.Cylinder.Define(stage, geom_path)
        cyl.CreateRadiusAttr().Set(inline.radius * max(s.x, s.z))
        cyl.CreateHeightAttr().Set(inline.height * s.y)
        cyl.AddTranslateOp().Set(Gf.Vec3d(t.x, t.y, t.z))
        cyl.CreateDisplayColorAttr().Set([(0.5, 0.6, 0.8)])
        return xform

    if inline.type == "sphere":
        if inline.radius is None:
            raise ValueError("sphere requires radius")
        sph = UsdGeom.Sphere.Define(stage, geom_path)
        sph.CreateRadiusAttr().Set(inline.radius * max(s.x, s.y, s.z))
        sph.AddTranslateOp().Set(Gf.Vec3d(t.x, t.y, t.z))
        sph.CreateDisplayColorAttr().Set([(0.5, 0.6, 0.8)])
        return xform

    if inline.type == "capsule":
        if inline.radius is None or inline.height is None:
            raise ValueError("capsule requires radius and height")
        cap = UsdGeom.Capsule.Define(stage, geom_path)
        cap.CreateRadiusAttr().Set(inline.radius * max(s.x, s.z))
        cap.CreateHeightAttr().Set(inline.height * s.y)
        cap.AddTranslateOp().Set(Gf.Vec3d(t.x, t.y, t.z))
        cap.CreateDisplayColorAttr().Set([(0.5, 0.6, 0.8)])
        return xform

    raise ValueError(f"Unknown inline geometry type: {inline.type}")


def _build_csg_mesh(
    node: CSGNode,
    stage: Any,
    prim_path: str,
    name: str,
) -> Any:
    """将 CSG 树烘焙为 USD Mesh。"""
    from pxr import Gf, UsdGeom

    from ..geometry.csg import csg_to_mesh, eval_csg

    manifold = eval_csg(node)
    verts, indices = csg_to_mesh(manifold)

    if not verts:
        logger.warning("CSG evaluation produced empty mesh for %s", name)
        return None

    xform = UsdGeom.Xform.Define(stage, prim_path)
    xform.GetPrim().SetDisplayName(name)

    mesh = UsdGeom.Mesh.Define(stage, prim_path + "/geometry")

    # 顶点
    mesh_points = [Gf.Vec3f(v.x, v.y, v.z) for v in verts]
    mesh.CreatePointsAttr().Set(mesh_points)

    # 面数
    face_count = len(indices) // 3
    mesh.CreateFaceVertexCountsAttr().Set([3] * face_count)
    mesh.CreateFaceVertexIndicesAttr().Set(indices)

    # 法线（简单计算）
    mesh.CreateNormalsAttr().Set([Gf.Vec3f(0, 1, 0)] * len(verts))
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)

    # 颜色
    mesh.CreateDisplayColorAttr().Set([(0.6, 0.7, 0.9)])

    return xform


def _build_reference(
    ref_path: str,
    stage: Any,
    prim_path: str,
    name: str,
) -> Any:
    """引用外部 USD 文件。"""
    from pxr import UsdGeom

    ref_prim = UsdGeom.Xform.Define(stage, prim_path)
    ref_prim.GetPrim().SetDisplayName(name)
    ref_prim.GetPrim().GetReferences().AddReference(ref_path)
    return ref_prim


def _write_instance(
    inst: Any,
    stage: Any,
    prim_path: str,
    racks: dict[str, Any] | None = None,
) -> Any | None:
    """将一个 ResolvedInstance 写入 USD 场景。

    Returns:
        创建的 prim，或 None（如果无几何信息）。
    """
    name = getattr(inst, "name", inst.id) or inst.id
    assets: GeometryAssets | None = getattr(inst, "assets", None)

    # 1. 外部引用
    if assets and assets.usd and assets.usd.reference:
        return _build_reference(assets.usd.reference, stage, prim_path, name)

    # 2. 内联代理几何
    if assets and assets.usd and assets.usd.inline:
        return _build_inline_geometry(assets.usd.inline, stage, prim_path, name)

    # 3. CSG 程序化几何
    if assets and assets.usd and assets.usd.procedural:
        return _build_csg_mesh(assets.usd.procedural, stage, prim_path, name)

    # 4. 根据 physical 尺寸生成代理 Box
    resolved = inst.resolved
    width_mm = getattr(resolved, "width_mm", 0.0) or 0.0
    depth_mm = getattr(resolved, "depth_mm", 0.0) or 0.0
    length_mm = getattr(resolved, "length_mm", 0.0) or 0.0
    height_mm = getattr(resolved, "height_mm", 0.0) or 0.0

    # 机柜高度可以从 total_u 推算（1U = 44.45mm）
    if height_mm <= 0:
        total_u = getattr(resolved, "total_u", 0) or 0
        if total_u > 0:
            height_mm = total_u * 44.45

    depth = depth_mm if depth_mm > 0 else length_mm
    height = height_mm
    width = width_mm

    if width > 0 and height > 0 and depth > 0:
        # 计算位置偏移（毫米 → 米）
        tx = getattr(resolved, "position_x_mm", 0.0) or 0.0
        ty = getattr(resolved, "position_y_mm", 0.0) or 0.0
        tz = getattr(resolved, "position_z_mm", 0.0) or 0.0

        # 如果是设备，根据 position_u 计算 Y 位置（1U = 44.45mm）
        position_u = getattr(resolved, "position_u", 0) or 0
        if position_u > 0:
            # 设备底部在 (position_u - 1) * 44.45mm 处
            ty = (position_u - 1) * 44.45
            # 简单偏移：让设备在机柜内稍微错开显示
            tx = 50  # 向 X 方向偏移 50mm
            tz = 50  # 向 Z 方向偏移 50mm

        return _build_proxy_box(
            width, height, depth, stage, prim_path, name, _mm_to_m(tx), _mm_to_m(ty), _mm_to_m(tz)
        )

    # 无几何信息
    return None


@generator("usd-scene", "USD 场景导出")
def generate_usd_scene(ctx: Context, config: dict[str, Any]) -> None:
    """生成 USD 场景文件。

    遍历所有 instance，根据 assets / physical 尺寸生成几何，
    输出为 .usda 或 .usdc 文件。
    """
    if not _has_usd_core():
        raise ImportError(
            "usd-core is required for USD scene generation. Install with: pip install usd-core"
        )

    from pxr import Usd, UsdGeom

    out_path_str = config.get("output")
    if out_path_str:
        out_path = Path(out_path_str)
    else:
        out_path = Path("scene.usda")

    # 创建舞台
    stage = Usd.Stage.CreateNew(str(out_path))
    # usd-core 26.5+ uses lowercase 'y', older versions use uppercase 'Y'
    up_axis = getattr(UsdGeom.Tokens, "y", getattr(UsdGeom.Tokens, "Y", None))
    if up_axis is None:
        up_axis = "Y"
    UsdGeom.SetStageUpAxis(stage, up_axis)
    stage.SetStartTimeCode(1)
    stage.SetEndTimeCode(1)

    # 根节点
    UsdGeom.Xform.Define(stage, "/piki")

    # 按集合分组
    collections = ctx._registry._collections

    # 先收集机柜信息（用于设备定位）
    racks: dict[str, Any] = {}
    if "racks" in collections:
        for rid, rinst in collections["racks"].items():
            racks[rid] = rinst

    for collection_name, instances in collections.items():
        UsdGeom.Xform.Define(stage, f"/piki/{collection_name}")

        for idx, (inst_id, inst) in enumerate(instances.items()):
            # USD prim path cannot contain '-', replace with '_'
            safe_id = inst_id.replace("-", "_")
            prim_path = f"/piki/{collection_name}/{safe_id}"
            try:
                prim = _write_instance(inst, stage, prim_path, racks)
                if prim is None:
                    logger.debug("No geometry for instance %s", inst_id)
            except Exception as exc:
                logger.warning("Failed to write instance %s: %s", inst_id, exc)

    # 保存
    stage.GetRootLayer().Save()
    print(f"USD scene saved to: {out_path}")
