"""CSG 布尔运算引擎 —— 基于 Manifold3D。

Manifold 是 NVIDIA 开源的鲁棒几何库，支持布尔运算和三角网格生成。
如果未安装 manifold3d，CSG 功能将不可用，但基础 AABB 仍正常工作。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adl.geometry import Vec3

if TYPE_CHECKING:
    from adl.geometry import CSGNode, InlineGeometry, Transform


def _has_manifold() -> bool:
    try:
        import manifold3d  # noqa: F401

        return True
    except ImportError:
        return False


def _inline_to_manifold(
    geom: InlineGeometry, transform: Transform | None = None
) -> "manifold3d.Manifold":
    """将 InlineGeometry 转换为 Manifold 对象。"""
    import manifold3d as m3d

    t = transform.translation if transform else Vec3(x=0.0, y=0.0, z=0.0)
    s = transform.scale if transform else Vec3(x=1.0, y=1.0, z=1.0)

    if geom.type == "box":
        if geom.size is None:
            raise ValueError("box requires size")
        # Manifold cube 以原点为中心，尺寸为 (x, y, z)
        size = (geom.size.x * s.x, geom.size.y * s.y, geom.size.z * s.z)
        mesh = m3d.Manifold.cube(*size)
    elif geom.type == "cylinder":
        if geom.radius is None or geom.height is None:
            raise ValueError("cylinder requires radius and height")
        r = geom.radius * max(s.x, s.z)
        h = geom.height * s.y
        mesh = m3d.Manifold.cylinder(h, r)
    elif geom.type == "sphere":
        if geom.radius is None:
            raise ValueError("sphere requires radius")
        r = geom.radius * max(s.x, s.y, s.z)
        mesh = m3d.Manifold.sphere(r, 32)
    elif geom.type == "capsule":
        if geom.radius is None or geom.height is None:
            raise ValueError("capsule requires radius and height")
        r = geom.radius * max(s.x, s.z)
        h = geom.height * s.y
        # capsule = cylinder + 两个半球
        cyl = m3d.Manifold.cylinder(max(0.0, h - 2 * r), r)
        top = m3d.Manifold.sphere(r, 16).translate((0, h / 2 - r, 0))
        bot = m3d.Manifold.sphere(r, 16).translate((0, -(h / 2 - r), 0))
        mesh = cyl + top + bot
    else:
        raise ValueError(f"Unknown geometry type: {geom.type}")

    # 应用平移
    mesh = mesh.translate((t.x, t.y, t.z))
    return mesh


def eval_csg(node: CSGNode) -> "manifold3d.Manifold":
    """求值 CSG 树，返回 Manifold 对象。

    Raises:
        ImportError: 如果 manifold3d 未安装。
        ValueError: 如果 CSG 树结构无效。
    """
    if not _has_manifold():
        raise ImportError(
            "manifold3d is required for CSG evaluation. Install with: pip install manifold3d"
        )

    if node.type == "primitive":
        if node.primitive is None:
            raise ValueError("primitive node missing 'primitive'")
        return _inline_to_manifold(node.primitive, node.transform)

    if not node.operands or len(node.operands) < 2:
        raise ValueError(f"{node.type} requires at least 2 operands")

    # 递归求值所有操作数
    meshes = [eval_csg(op) for op in node.operands]
    result = meshes[0]

    if node.type == "union":
        for m in meshes[1:]:
            result = result + m
    elif node.type == "intersection":
        for m in meshes[1:]:
            result = result ^ m
    elif node.type == "difference":
        for m in meshes[1:]:
            result = result - m
    else:
        raise ValueError(f"Unknown CSG operation: {node.type}")

    # 应用节点级变换
    t = node.transform.translation if node.transform else Vec3(x=0.0, y=0.0, z=0.0)
    if t.x != 0 or t.y != 0 or t.z != 0:
        result = result.translate((t.x, t.y, t.z))

    return result


def csg_to_mesh(manifold: "manifold3d.Manifold") -> tuple[list[Vec3], list[int]]:
    """将 Manifold 转为顶点列表和索引列表。

    Returns:
        (vertices, indices) —— vertices 是 Vec3 列表，indices 是三角形索引列表
    """
    mesh = manifold.to_mesh()
    verts = [Vec3(x=v[0], y=v[1], z=v[2]) for v in mesh.vert_properties[:, :3]]
    indices = mesh.tri_verts.flatten().tolist()
    return verts, indices


def eval_csg_aabb(node: CSGNode) -> "AABB":
    """求值 CSG 树并返回 AABB 包围盒。"""
    from . import AABB

    manifold = eval_csg(node)
    mesh = manifold.to_mesh()
    if len(mesh.vert_properties) == 0:
        return AABB(min=Vec3(x=0, y=0, z=0), max=Vec3(x=0, y=0, z=0))

    verts = mesh.vert_properties[:, :3]
    return AABB(
        min=Vec3(
            x=float(verts[:, 0].min()), y=float(verts[:, 1].min()), z=float(verts[:, 2].min())
        ),
        max=Vec3(
            x=float(verts[:, 0].max()), y=float(verts[:, 1].max()), z=float(verts[:, 2].max())
        ),
    )
