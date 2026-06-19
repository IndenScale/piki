"""Baseline integration tests: every ADL example must compile and build.

These tests capture the current behavior of the compiler + geometry backend.
They will be expanded as the implementation catches up to the design docs.
"""

from pathlib import Path

import pytest

from adl.compiler.compile import compile_and_get_project
from adl.geometry.assembly_builder import AssemblyBuilder


EXAMPLES = [
    "01-face-gasket",
    "02-shaft-bushing",
    "03-dovetail-slide",
    "04-spur-gears",
    "05-worm-drive",
    "06-fiber-connectors",
    "07-usb-interfaces",
]


@pytest.mark.parametrize("example_name", EXAMPLES)
def test_example_compiles(example_name: str, examples_dir: Path) -> None:
    root = examples_dir / example_name
    assert root.exists(), f"Example directory missing: {root}"

    project = compile_and_get_project(root)
    assert project is not None, f"compile_and_get_project returned None for {example_name}"
    assert project.instances, f"No instances loaded for {example_name}"
    assert project.mates, f"No mates loaded for {example_name}"


@pytest.mark.parametrize("example_name", EXAMPLES)
def test_example_builds_scene(example_name: str, examples_dir: Path) -> None:
    root = examples_dir / example_name
    project = compile_and_get_project(root)
    assert project is not None

    scene = AssemblyBuilder(project).build()
    assert scene is not None
    assert scene.entities, f"No entities in built scene for {example_name}"
