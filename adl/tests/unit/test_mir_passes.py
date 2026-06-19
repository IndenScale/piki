"""Unit tests for MIR passes: SymbolResolvePass and ModelMergePass."""

from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from adl.compiler.compile import compile_and_get_project, compile_project
from adl.compiler.pass_manager import PassStage
from adl.compiler.type_system import TypeSystem
from adl.types import TypeRegistry


class SampleFamily(BaseModel):
    id: str
    name: str = ""
    width_mm: float = Field(default=0, ge=0, json_schema_extra={"piki_non_overridable": True})
    height_mm: float = Field(default=0)


def _make_registry() -> TypeRegistry:
    reg = TypeRegistry()
    reg.add_family("SampleFamily", SampleFamily)
    return reg


def _write_project(tmp_path: Path) -> Path:
    (tmp_path / "piki.toml").write_text("[project]\nname = \"test\"\n")
    inst_dir = tmp_path / "instances" / "parts"
    inst_dir.mkdir(parents=True)
    (inst_dir / "PART-A.yaml").write_text(
        "id: PART-A\nfamily: SampleFamily\nname: A\nheight_mm: 10\n"
    )
    (inst_dir / "PART-B.yaml").write_text(
        "id: PART-B\nfamily: SampleFamily\nmodel: MODEL-1\nname: B\nheight_mm: 20\n"
    )
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    (model_dir / "MODEL-1.yaml").write_text(
        "id: MODEL-1\nfamily: SampleFamily\nname: Default B\nwidth_mm: 100\n"
    )
    mates_dir = tmp_path / "mates" / "face"
    mates_dir.mkdir(parents=True)
    (mates_dir / "A-B.yaml").write_text(
        "type: face\nparent: PART-A/face\nchild: PART-B/face\n"
    )
    layouts_dir = tmp_path / "layouts"
    layouts_dir.mkdir()
    (layouts_dir / "layout.yaml").write_text(
        "- instance: PART-A\n  position_x_mm: 1\n  position_y_mm: 2\n  position_z_mm: 3\n"
    )
    return tmp_path


def test_model_merge_with_model_defaults(tmp_path: Path) -> None:
    root = _write_project(tmp_path)
    reg = _make_registry()
    project = compile_and_get_project(root, type_registry=reg)

    assert project is not None
    assert "PART-A" in project.instances
    assert "PART-B" in project.instances

    part_b = project.instances["PART-B"]
    # Model default
    assert part_b._resolved.get("width_mm") == 100
    # Instance override
    assert part_b._resolved.get("height_mm") == 20
    # Instance override of name
    assert part_b._resolved.get("name") == "B"


def test_model_merge_non_overridable_field_dropped(tmp_path: Path) -> None:
    root = _write_project(tmp_path)
    # Override width_mm (non-overridable) on PART-A
    (tmp_path / "instances" / "parts" / "PART-A.yaml").write_text(
        "id: PART-A\nfamily: SampleFamily\nname: A\nwidth_mm: 999\nheight_mm: 10\n"
    )
    reg = _make_registry()
    project = compile_and_get_project(root, type_registry=reg)

    assert project is not None
    part_a = project.instances["PART-A"]
    # width_mm is non-overridable: instance override should be dropped, default 0 remains
    assert part_a._resolved.get("width_mm") == 0


def test_layout_cycle_detected(tmp_path: Path) -> None:
    root = _write_project(tmp_path)
    (tmp_path / "layouts" / "layout.yaml").write_text(
        "- instance: PART-A\n  parent: PART-B\n"
        "- instance: PART-B\n  parent: PART-A\n"
    )
    reg = _make_registry()
    _, diagnostics = compile_project(root, type_system=TypeSystem.from_type_registry(reg), up_to=PassStage.MIR)
    codes = {d.code for d in diagnostics}
    assert "LAYOUT-004" in codes


def test_interface_incompat_detected(tmp_path: Path) -> None:
    root = _write_project(tmp_path)
    (tmp_path / "instances" / "parts" / "PART-A.yaml").write_text(
        "id: PART-A\nfamily: SampleFamily\ninterfaces:\n"
        "  - id: face\n    interface_type: IEC-C13\n"
    )
    (tmp_path / "instances" / "parts" / "PART-B.yaml").write_text(
        "id: PART-B\nfamily: SampleFamily\ninterfaces:\n"
        "  - id: face\n    interface_type: USB-C-plug\n"
    )
    (tmp_path / "mates" / "face" / "A-B.yaml").write_text(
        "type: face\nparent: PART-A/face\nchild: PART-B/face\n"
    )
    reg = _make_registry()
    _, diagnostics = compile_project(root, type_system=TypeSystem.from_type_registry(reg), up_to=PassStage.MIR)
    codes = {d.code for d in diagnostics}
    assert "MATE-005" in codes


def test_fqid_duplicate_detected(tmp_path: Path) -> None:
    from types import SimpleNamespace
    from adl.compiler.mir import ResolvedCompilation, ResolvedInstanceIR
    from adl.compiler.passes.mir_validation import FQIDDedupPass

    resolved = ResolvedCompilation(hir=None)
    resolved.resolved_instances["ns1.PART-A"] = ResolvedInstanceIR(
        id="PART-A", fqid="ns1.PART-A", namespace="ns1"
    )
    resolved.resolved_instances["ns2.PART-A"] = ResolvedInstanceIR(
        id="PART-A", fqid="ns2.PART-A", namespace="ns2"
    )

    diagnostics: list[Any] = []
    ctx = SimpleNamespace(
        root=tmp_path,
        resolved=resolved,
        emit=lambda d: diagnostics.append(d),
    )
    FQIDDedupPass().run(ctx)  # type: ignore[arg-type]
    codes = {d.code for d in diagnostics}
    assert "REFS-002" in codes
