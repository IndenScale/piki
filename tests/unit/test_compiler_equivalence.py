"""新旧编译器路径等价性测试。

验证 compile_and_get_project() 与 ProjectLoader.load() 产生相同的 Project。
覆盖所有 ADL examples。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from adl.compiler.compile import compile_and_get_project
from adl.models.interface import get_interfaces_from_resolved
from adl.project import ProjectLoader
from adl.types import TypeRegistry

# 所有 ADL 示例项目
EXAMPLES_DIR = Path(__file__).parent.parent.parent / "adl" / "examples"
EXAMPLE_NAMES = [
    "01-face-gasket",
    "02-shaft-bushing",
    "03-dovetail-slide",
    "04-spur-gears",
    "05-worm-drive",
    "06-fiber-connectors",
    "07-usb-interfaces",
]


@pytest.mark.parametrize("example_name", EXAMPLE_NAMES)
def test_old_new_equivalence(example_name: str):
    """验证旧 ProjectLoader 和新编译器产生相同数量和 ID 的实例、接口。"""
    root = EXAMPLES_DIR / example_name
    if not root.exists():
        pytest.skip(f"示例目录不存在: {root}")

    # Old path
    reg = TypeRegistry()
    loader = ProjectLoader(root, reg)
    project_old = loader.load()

    # New path
    project_new = compile_and_get_project(root)

    # Instance ID 集合必须一致
    old_ids = set(project_old.instances.keys())
    new_ids = set(project_new.instances.keys())
    assert old_ids == new_ids, (
        f"实例 ID 不一致。仅在旧路径: {old_ids - new_ids}, "
        f"仅在新路径: {new_ids - old_ids}"
    )

    # Mate 数量一致
    assert len(project_old.mates) == len(project_new.mates), (
        f"Mate 数量不一致: 旧={len(project_old.mates)}, 新={len(project_new.mates)}"
    )

    # Model 数量一致
    assert len(project_old.models) == len(project_new.models), (
        f"Model 数量不一致: 旧={len(project_old.models)}, 新={len(project_new.models)}"
    )

    # 每个 Instance 的接口数量和 ID 一致
    for inst_id in old_ids:
        old_inst = project_old.instances[inst_id]
        new_inst = project_new.instances[inst_id]

        old_ifaces = get_interfaces_from_resolved(old_inst)
        new_ifaces = get_interfaces_from_resolved(new_inst)

        old_iface_ids = {i.id for i in old_ifaces}
        new_iface_ids = {i.id for i in new_ifaces}
        assert old_iface_ids == new_iface_ids, (
            f"Instance '{inst_id}' 接口 ID 不一致: "
            f"旧={old_iface_ids}, 新={new_iface_ids}"
        )

        # 对每个接口，验证关键几何字段存在
        for oi, ni in zip(
            sorted(old_ifaces, key=lambda x: x.id),
            sorted(new_ifaces, key=lambda x: x.id),
        ):
            assert oi.interface_type == ni.interface_type, (
                f"接口 '{inst_id}/{oi.id}' interface_type 不一致"
            )
            # local_transform 不应为纯默认值（证明数据已被正确传递）
            # 注意：local_transform 可以为 identity，但只要新旧一致即可
            assert oi.local_transform == ni.local_transform, (
                f"接口 '{inst_id}/{oi.id}' local_transform 不一致: "
                f"旧={oi.local_transform}, 新={ni.local_transform}"
            )


def test_telecom_sample_equivalence():
    """验证 telecom 示例项目新旧路径等价。"""
    root = Path(__file__).parent.parent.parent / "samples" / "01-telecom-expansion"
    if not root.exists():
        pytest.skip("telecom 示例目录不存在")

    reg = TypeRegistry()
    loader = ProjectLoader(root, reg)
    project_old = loader.load()

    project_new = compile_and_get_project(root)

    old_ids = set(project_old.instances.keys())
    new_ids = set(project_new.instances.keys())
    assert old_ids == new_ids


def test_keyboard_sample_equivalence():
    """验证键盘示例项目新旧路径等价。"""
    root = Path(__file__).parent.parent.parent / "samples" / "03-mechanical-keyboard"
    if not root.exists():
        pytest.skip("keyboard 示例目录不存在")

    reg = TypeRegistry()
    loader = ProjectLoader(root, reg)
    project_old = loader.load()

    project_new = compile_and_get_project(root)

    old_ids = set(project_old.instances.keys())
    new_ids = set(project_new.instances.keys())
    assert old_ids == new_ids
