"""SpatialCollisionPass — AABB 碰撞检测（L4）。

本 Pass 已从 adl.compiler 默认管线迁移到 adl.geometry。
它不再默认运行；只有在目标输出阶段或 piki 规则显式启用时才注册。

输入为 ``Project`` 对象（从 PassContext.extra["project"] 获取），
输出为 SPATIAL-00x 诊断。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adl.diagnostics import Diagnostic, Location, Severity
from adl.geometry.provider import GeometryProvider

if TYPE_CHECKING:
    from adl.compiler.pass_manager import Pass, PassContext, PassResult
else:
    # 避免循环导入：运行时才从 adl.compiler 导入 Pass 基类
    from adl.compiler.pass_manager import Pass, PassContext, PassResult, PassStage


class SpatialCollisionPass(Pass):
    """AABB 碰撞检测 Pass（可选）。"""

    name = "spatial-collision"
    stage = PassStage.MIR
    description = "AABB 碰撞检测，产出空间碰撞诊断（可选）"

    def run(self, ctx: PassContext) -> PassResult:
        result = PassResult()
        project = ctx.extra.get("project")
        if project is None:
            return result

        provider = GeometryProvider(project)
        for id_a, id_b in provider.collisions():
            ctx.emit(
                Diagnostic(
                    severity=Severity.WARNING,
                    message=(
                        f"空间碰撞: {id_a} 与 {id_b} 的包围盒重叠。"
                        f" 如非预期，请检查 Layout 位姿或 Mate 约束。"
                    ),
                    location=Location(uri=str(project.root)),
                    code="SPATIAL-001",
                    source="adl.geometry.spatial_collision",
                )
            )
        return result
