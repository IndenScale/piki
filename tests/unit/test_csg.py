"""CSG 布尔运算单元测试 —— 需要 manifold3d 可选依赖。"""

from __future__ import annotations

import pytest
from adl.geometry import CSGNode, InlineGeometry, Transform, Vec3

from piki.ext.geometry.csg import _has_manifold, eval_csg_aabb

pytestmark = pytest.mark.skipif(
    not _has_manifold(),
    reason="manifold3d not installed",
)


class TestCSGEvaluation:
    """测试 CSG 树求值。"""

    def test_primitive_box(self) -> None:
        node = CSGNode(
            type="primitive",
            primitive=InlineGeometry(
                type="box",
                size=Vec3(x=2.0, y=3.0, z=4.0),
            ),
        )
        aabb = eval_csg_aabb(node)
        assert aabb.min == pytest.approx(Vec3(x=-1.0, y=-1.5, z=-2.0), abs=1e-3)
        assert aabb.max == pytest.approx(Vec3(x=1.0, y=1.5, z=2.0), abs=1e-3)

    def test_difference_two_boxes(self) -> None:
        """大盒子减去小盒子 = 空心盒子（类似防火门）。"""
        node = CSGNode(
            type="difference",
            operands=[
                CSGNode(
                    type="primitive",
                    primitive=InlineGeometry(
                        type="box",
                        size=Vec3(x=2.0, y=2.0, z=0.1),
                    ),
                ),
                CSGNode(
                    type="primitive",
                    primitive=InlineGeometry(
                        type="box",
                        size=Vec3(x=1.5, y=1.5, z=0.12),
                    ),
                    transform=Transform(translation=Vec3(x=0.1, y=0.0, z=0.0)),
                ),
            ],
        )
        aabb = eval_csg_aabb(node)
        # 差集的外包围盒应等于大盒子
        assert aabb.min.x == pytest.approx(-1.0, abs=1e-3)
        assert aabb.max.x == pytest.approx(1.0, abs=1e-3)

    def test_union_two_boxes(self) -> None:
        node = CSGNode(
            type="union",
            operands=[
                CSGNode(
                    type="primitive",
                    primitive=InlineGeometry(
                        type="box",
                        size=Vec3(x=1.0, y=1.0, z=1.0),
                    ),
                ),
                CSGNode(
                    type="primitive",
                    primitive=InlineGeometry(
                        type="box",
                        size=Vec3(x=1.0, y=1.0, z=1.0),
                    ),
                    transform=Transform(translation=Vec3(x=1.0, y=0.0, z=0.0)),
                ),
            ],
        )
        aabb = eval_csg_aabb(node)
        # 并集应覆盖两个盒子的范围
        assert aabb.min.x == pytest.approx(-0.5, abs=1e-3)
        assert aabb.max.x == pytest.approx(1.5, abs=1e-3)

    def test_intersection_two_boxes(self) -> None:
        node = CSGNode(
            type="intersection",
            operands=[
                CSGNode(
                    type="primitive",
                    primitive=InlineGeometry(
                        type="box",
                        size=Vec3(x=2.0, y=2.0, z=2.0),
                    ),
                ),
                CSGNode(
                    type="primitive",
                    primitive=InlineGeometry(
                        type="box",
                        size=Vec3(x=2.0, y=2.0, z=2.0),
                    ),
                    transform=Transform(translation=Vec3(x=1.0, y=0.0, z=0.0)),
                ),
            ],
        )
        aabb = eval_csg_aabb(node)
        # 交集应只在重叠区域
        assert aabb.min.x == pytest.approx(0.0, abs=1e-3)
        assert aabb.max.x == pytest.approx(1.0, abs=1e-3)


class TestCSGValidation:
    """测试 CSG 节点校验。"""

    def test_primitive_without_primitive_raises(self) -> None:
        with pytest.raises(ValueError, match="primitive node requires"):
            CSGNode(type="primitive")

    def test_difference_with_one_operand_raises(self) -> None:
        with pytest.raises(ValueError, match="difference requires at least 2"):
            CSGNode(
                type="difference",
                operands=[
                    CSGNode(
                        type="primitive",
                        primitive=InlineGeometry(type="box", size=Vec3(x=1, y=1, z=1)),
                    ),
                ],
            )
