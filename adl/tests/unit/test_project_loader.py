"""Tests that ProjectLoader delegates to the new compiler pipeline."""

from pathlib import Path

import pytest

from adl.project import ProjectLoader
from adl.types import TypeRegistry


def test_project_loader_uses_compiler_pipeline(examples_dir: Path) -> None:
    root = examples_dir / "01-face-gasket"
    loader = ProjectLoader(root, type_registry=TypeRegistry())
    project = loader.load()

    assert project is not None
    assert "PUMP-FLANGE" in project.instances
    assert "GASKET-PTFE" in project.instances
    assert project.mates
    assert project.mate_graph is not None
