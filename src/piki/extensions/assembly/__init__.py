"""piki-assembly 内置插件：装配体演示与可视化。

把 ADL 项目解析为可交互的装配体场景，输出 JSON（浏览器 viewer）
和 OpenUSD（下游工具链）。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from adl.diagnostics import Severity
from adl.geometry import (
    AssemblyBuilder,
    GeometryAssets,
    InlineGeometry,
    Transform,
    Vec3,
)
from adl.models import InterfaceSpec, MateTypeMeta, Tags
from adl.models.interface import register_interface_types
from adl.project import Project
from adl.types import TypeRegistry
from pydantic import BaseModel, Field

from piki.core.engine.checker import Checker
from piki.core.engine.context import Context
from piki.core.engine.generator_registry import GeneratorResult, generator
from piki.core.plugin import Plugin

# ---------------------------------------------------------------------------
# Family 定义
# ---------------------------------------------------------------------------


class AssemblyPartFamily(BaseModel):
    """装配体演示中的通用部件。

    用于表达可配合、可展示、可驱动的零件或子装配体。
    """

    id: str = Field(...)
    name: str = Field(default="")
    part_type: str = Field(default="generic")

    # 物理尺寸（毫米），参与 BBox / 代理几何
    width_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    height_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    depth_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})

    # 空间定位（毫米），允许 Layout 覆盖
    position_x_mm: float = Field(default=0)
    position_y_mm: float = Field(default=0)
    position_z_mm: float = Field(default=0)

    # 外观
    color: str = Field(default="#888888")
    wireframe: bool = Field(default=False)
    opacity: float = Field(default=1.0, ge=0, le=1)

    # 接口：用于 L2 配合
    interfaces: list[InterfaceSpec] = Field(default_factory=list)

    # 几何资产（可选，优先于 BBox 代理）
    assets: GeometryAssets | None = Field(default=None)

    tags: Tags = Field(default_factory=Tags)


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class AssemblyPlugin(Plugin):
    name = "assembly"
    version = "0.1.0"

    def register_types(self, type_registry: TypeRegistry) -> None:
        type_registry.add_family("AssemblyPartFamily", AssemblyPartFamily)

        # 注册装配演示常用接口类型
        register_interface_types([
            "SFP28-cage",
            "SFP28-module",
            "generic-face",
            "generic-slot",
            "generic-axis",
        ])

        # 注册装配演示常用 Mate 类型
        type_registry.add_mate_type(
            "slot",
            MateTypeMeta(
                type="slot",
                description="槽配合：child 沿 parent 槽方向推入",
            ),
        )
        type_registry.add_mate_type(
            "face-on-face",
            MateTypeMeta(
                type="face-on-face",
                description="面面配合：child 某个面贴合到 parent 某个面",
            ),
        )
        type_registry.add_mate_type(
            "face",
            MateTypeMeta(
                type="face",
                description="面面配合简写别名",
            ),
        )
        type_registry.add_mate_type(
            "axis",
            MateTypeMeta(
                type="axis",
                description="轴轴配合：child 轴对齐到 parent 轴",
            ),
        )
        type_registry.add_mate_type(
            "placed-on",
            MateTypeMeta(
                type="placed-on",
                description="放置在表面上",
            ),
        )

    def register_rules(self, checker: Checker) -> None:
        # 当前阶段不添加专用规则；ADL 层引用完整性、碰撞检测已覆盖。
        pass

    def register_generators(self, checker: Checker) -> None:
        import piki.extensions.assembly as assembly_module

        checker.generator_registry.register_from_module(assembly_module)


# ---------------------------------------------------------------------------
# 生成器
# ---------------------------------------------------------------------------


@generator("assembly-json", "装配体 JSON 场景")
def generate_assembly_json(ctx: Context, config: dict[str, Any]) -> GeneratorResult:
    """生成浏览器 viewer 可用的 JSON 场景。"""
    try:
        project = _project_from_context(ctx)
        scene = AssemblyBuilder(project).build()
        data = _scene_to_dict(scene)
        content = json.dumps(data, ensure_ascii=False, indent=2, default=_json_default)
        file_path = _output_path(project, config, "scene.json")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return GeneratorResult.ok(
            "assembly-json",
            "装配体 JSON 场景",
            content=content,
            file_path=file_path,
            content_type="application/json",
        )
    except Exception as exc:
        return GeneratorResult.fail("assembly-json", "装配体 JSON 场景", str(exc))


@generator("assembly-usd", "装配体 USD 场景")
def generate_assembly_usd(ctx: Context, config: dict[str, Any]) -> GeneratorResult:
    """生成 OpenUSD 场景（USDA 文本格式）。"""
    try:
        project = _project_from_context(ctx)
        scene = AssemblyBuilder(project).build()
        file_path = _output_path(project, config, "scene.usda")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        content = _write_usda(scene, file_path)
        return GeneratorResult.ok(
            "assembly-usd",
            "装配体 USD 场景",
            content=content,
            file_path=file_path,
            content_type="text/plain",
        )
    except Exception as exc:
        return GeneratorResult.fail("assembly-usd", "装配体 USD 场景", str(exc))


@generator("assembly-viewer", "装配体交互演示")
def generate_assembly_viewer(ctx: Context, config: dict[str, Any]) -> GeneratorResult:
    """生成完整浏览器演示包：JSON + USD + viewer。"""
    try:
        project = _project_from_context(ctx)
        scene = AssemblyBuilder(project).build()

        dist_dir = _dist_dir(project, config)
        dist_dir.mkdir(parents=True, exist_ok=True)

        # 1. JSON
        json_path = dist_dir / "scene.json"
        data = _scene_to_dict(scene)
        json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )

        # 2. USD
        usd_path = dist_dir / "scene.usda"
        _write_usda(scene, usd_path)

        # 3. viewer 静态文件
        viewer_src = Path(__file__).parents[4] / "assembly" / "viewer"
        if viewer_src.exists():
            for fname in ("index.html", "viewer.js", "viewer.css"):
                src = viewer_src / fname
                if src.exists():
                    shutil.copy2(src, dist_dir / fname)

        return GeneratorResult.ok(
            "assembly-viewer",
            "装配体交互演示",
            content=f"Generated {json_path}, {usd_path}, viewer files",
            file_path=dist_dir,
            content_type="text/plain",
        )
    except Exception as exc:
        return GeneratorResult.fail("assembly-viewer", "装配体交互演示", str(exc))


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _project_from_context(ctx: Context) -> Project:
    """从 piki Context 中提取 ADL Project。"""
    project = getattr(ctx._registry, "project", None)
    if isinstance(project, Project):
        return project
    raise RuntimeError("Context does not contain an ADL Project")


def _dist_dir(project: Project, config: dict[str, Any]) -> Path:
    if config.get("target_dir"):
        return Path(config["target_dir"])
    if config.get("dist_dir"):
        return Path(config["dist_dir"])
    return project.root / "dist"


def _output_path(project: Project, config: dict[str, Any], filename: str) -> Path:
    if config.get("output"):
        return Path(config["output"])
    return _dist_dir(project, config) / filename


def _json_default(obj: Any) -> Any:
    """JSON 序列化兜底。"""
    if isinstance(obj, Transform):
        return {
            "translation": [obj.translation.x, obj.translation.y, obj.translation.z],
            "rotation": [obj.rotation.x, obj.rotation.y, obj.rotation.z],
            "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
        }
    if isinstance(obj, Vec3):
        return [obj.x, obj.y, obj.z]
    if isinstance(obj, InlineGeometry):
        return obj.model_dump()
    if isinstance(obj, AssetReference):
        return obj.model_dump()
    if isinstance(obj, Severity):
        return obj.value
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _scene_to_dict(scene: Any) -> dict[str, Any]:
    """把 AssemblyScene 转成可 JSON 序列化的 dict。"""
    return {
        "version": 1,
        "name": scene.name,
        "description": scene.description,
        "entities": [
            {
                "id": e.id,
                "label": e.label,
                "family": e.family,
                "transform": _json_default(e.transform),
                "geometry": _json_default(e.geometry),
                "material": {
                    "color": e.material.color,
                    "wireframe": e.material.wireframe,
                    "opacity": e.material.opacity,
                    "roughness": e.material.roughness,
                    "metalness": e.material.metalness,
                },
                "interfaces": [
                    {
                        "id": i.id,
                        "interface_type": i.interface_type,
                        "active_type": i.active_type,
                        "direction": i.direction,
                        "description": i.description,
                        "specs": i.specs,
                        "mating_kind": i.mating_kind,
                        "mating_params": i.mating_params,
                        "transform": _json_default(i.transform),
                        "local_transform": _json_default(i.local_transform),
                    }
                    for i in e.interfaces
                ],
            }
            for e in scene.entities
        ],
        "controls": [
            {
                "id": c.id,
                "type": c.type,
                "target": c.target,
                "param": c.param,
                "label": c.label,
                "min": c.min,
                "max": c.max,
                "default": c.default,
                "step": c.step,
                "states": c.states,
                "current_state": c.current_state,
            }
            for c in scene.controls
        ],
        "collisions": [list(pair) for pair in scene.collisions],
        "diagnostics": [
            {
                "severity": d.severity.value,
                "message": d.message,
                "code": d.code,
                "source": d.source,
            }
            for d in scene.diagnostics
        ],
    }


def _write_usda(scene: Any, path: Path) -> str:
    """手写 USDA 文本（不依赖 usd-core，避免可选依赖问题）。"""
    lines: list[str] = [
        '#usda 1.0',
        '(',
        '    defaultPrim = "World"',
        '    metersPerUnit = 1.0',
        '    upAxis = "Y"',
        ')',
        '',
        'def Xform "World"',
        '{',
    ]

    for e in scene.entities:
        tf = e.transform
        tx, ty, tz = tf.translation.x / 1000.0, tf.translation.y / 1000.0, tf.translation.z / 1000.0
        rx, ry, rz = tf.rotation.x, tf.rotation.y, tf.rotation.z
        sx, sy, sz = tf.scale.x, tf.scale.y, tf.scale.z

        lines.append(f'    def Xform "{e.id}"')
        lines.append("    {")
        lines.append(f'        string adl:family = "{e.family}"')
        lines.append(f'        string adl:label = "{e.label}"')
        lines.append(
            '        matrix4d xformOp:transform = (('
            f'{sx:.6f}, 0, 0, 0), '
            f'(0, {sy:.6f}, 0, 0), '
            f'(0, 0, {sz:.6f}, 0), '
            f'({tx:.6f}, {ty:.6f}, {tz:.6f}, 1))'
        )
        lines.append('        uniform token[] xformOpOrder = ["xformOp:transform"]')

        geom = e.geometry
        if isinstance(geom, InlineGeometry):
            if geom.type == "box" and geom.size:
                size_x = geom.size.x / 1000.0
                size_y = geom.size.y / 1000.0
                size_z = geom.size.z / 1000.0
                lines.append('        def Cube "mesh"')
                lines.append("        {")
                lines.append(f'            double size = {max(size_x, size_y, size_z):.6f}')
                lines.append(f'            vec3f[] extent = [(-{size_x/2:.6f}, -{size_y/2:.6f}, -{size_z/2:.6f}), ({size_x/2:.6f}, {size_y/2:.6f}, {size_z/2:.6f})]')
                lines.append("        }")
            elif geom.type == "cylinder" and geom.radius and geom.height:
                r = geom.radius / 1000.0
                h = geom.height / 1000.0
                lines.append('        def Cylinder "mesh"')
                lines.append("        {")
                lines.append(f'            double radius = {r:.6f}')
                lines.append(f'            double height = {h:.6f}')
                lines.append("        }")
            elif geom.type == "sphere" and geom.radius:
                r = geom.radius / 1000.0
                lines.append('        def Sphere "mesh"')
                lines.append("        {")
                lines.append(f'            double radius = {r:.6f}')
                lines.append("        }")

        lines.append("    }")
        lines.append("")

    lines.append("}")
    content = "\n".join(lines)
    path.write_text(content, encoding="utf-8")
    return content
