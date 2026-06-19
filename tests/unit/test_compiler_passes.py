"""ADL 编译器 Pass 单元测试。

覆盖：YAMLParsePass、LoweringPass、MateSugarResolvePass、BackCompatEmitPass、
      PassManager 依赖环检测与错误恢复。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from adl.compiler.pass_manager import (
    DependencyCycleError,
    Pass,
    PassContext,
    PassManager,
    PassResult,
    PassStage,
)
from adl.compiler.passes.back_compat import BackCompatEmitPass
from adl.compiler.passes.lowering import LoweringPass
from adl.compiler.passes.mate_sugar import MateSugarResolvePass
from adl.compiler.passes.yaml_parse import YAMLParsePass
from adl.compiler.symbols import SymbolTable
from adl.compiler.type_registry_builtins import register_all_builtins
from adl.compiler.type_system import TypeSystem


# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────

def _write_yaml(root: Path, rel_path: str, content: str) -> None:
    """在临时项目目录中写入 YAML 文件。"""
    fpath = root / rel_path
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(content)


def _make_ctx(root: Path) -> PassContext:
    """构建测试用 PassContext。"""
    register_all_builtins()
    return PassContext(
        root=root,
        type_system=TypeSystem(),
        symbol_table=SymbolTable(),
    )


# ────────────────────────────────────────────────────────────────
# YAMLParsePass
# ────────────────────────────────────────────────────────────────


class TestYAMLParsePass:
    """YAML → AST 解析 Pass 测试。"""

    def test_parses_instance_yaml(self):
        """解析简单的 Instance YAML 文件。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_yaml(root, "instances/PART-A.yaml", """\
id: PART-A
family: AssemblyPartFamily
name: 测试零件
width_mm: 100
interfaces:
  - id: face-a
    interface_type: generic-face
""")
            ctx = _make_ctx(root)
            p = YAMLParsePass()
            result = p.run(ctx)

            assert result.modified
            assert len(ctx.source_files) == 1
            sf = list(ctx.source_files.values())[0]
            assert sf.kind.value == "instance"
            assert len(sf.declarations) == 1
            decl = sf.declarations[0]
            assert decl.name == "PART-A"

    def test_parses_mate_yaml(self):
        """解析 Mate YAML 文件。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_yaml(root, "mates/face/A-B.yaml", """\
type: face-on-face
parent: PART-A
child: PART-B
""")
            ctx = _make_ctx(root)
            p = YAMLParsePass()
            result = p.run(ctx)

            assert result.modified
            assert len(ctx.source_files) == 1
            sf = list(ctx.source_files.values())[0]
            assert sf.kind.value == "mate"

    def test_parses_layout_yaml(self):
        """解析 Layout YAML。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_yaml(root, "layouts/layout.yaml", """\
- instance: ROOT
  position_x_mm: 0
  position_y_mm: 0
""")
            ctx = _make_ctx(root)
            p = YAMLParsePass()
            result = p.run(ctx)

            assert result.modified
            assert len(ctx.source_files) == 1
            sf = list(ctx.source_files.values())[0]
            assert sf.kind.value == "layout"


# ────────────────────────────────────────────────────────────────
# LoweringPass
# ────────────────────────────────────────────────────────────────


class TestLoweringPass:
    """AST → HIR Lowering Pass 测试。"""

    def test_lowers_instance_with_interfaces(self):
        """降级带 interfaces 的 Instance。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_yaml(root, "instances/PART-A.yaml", """\
id: PART-A
family: AssemblyPartFamily
name: 法兰
width_mm: 100
interfaces:
  - id: face-a
    interface_type: generic-face
    mating_kind: face
    local_transform:
      translation: [0, 0, 50]
  - id: hole-1
    interface_type: screw-hole
    mating_kind: axis
    local_transform:
      translation: [62.5, 62.5, 0]
""")
            ctx = _make_ctx(root)
            # Run parse + lowering
            YAMLParsePass().run(ctx)
            LoweringPass().run(ctx)

            comp = ctx.compilation
            assert comp is not None
            assert "PART-A" in comp.instances
            unit = comp.instances["PART-A"]
            assert len(unit.interfaces) == 2
            assert unit.interfaces[0].id == "face-a"
            assert unit.interfaces[0].interface_type == "generic-face"
            assert unit.interfaces[1].id == "hole-1"

    def test_lowers_instance_with_tags(self):
        """Instance tags 正确降级。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_yaml(root, "instances/DEV-01.yaml", """\
id: DEV-01
family: ServerFamily
tags:
  role: compute
  tier: production
""")
            ctx = _make_ctx(root)
            YAMLParsePass().run(ctx)
            LoweringPass().run(ctx)

            unit = ctx.compilation.instances["DEV-01"]
            assert unit.tags == {"role": "compute", "tier": "production"}

    def test_symbol_table_populated(self):
        """降级后符号表应包含所有定义。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_yaml(root, "instances/PART-A.yaml", """\
id: PART-A
family: AssemblyPartFamily
""")
            _write_yaml(root, "models/my-model.yaml", """\
model: my-model
family: AssemblyPartFamily
height_mm: 50
""")
            ctx = _make_ctx(root)
            YAMLParsePass().run(ctx)
            LoweringPass().run(ctx)

            sym_a = ctx.symbol_table.lookup("PART-A")
            assert sym_a is not None
            assert sym_a.kind.value == "instance"

            sym_m = ctx.symbol_table.lookup("my-model")
            assert sym_m is not None
            assert sym_m.kind.value == "model"


# ────────────────────────────────────────────────────────────────
# MateSugarResolvePass
# ────────────────────────────────────────────────────────────────


class TestMateSugarResolvePass:
    """Mate 语法糖消解 Pass 测试。"""

    def test_resolves_single_candidate(self):
        """裸 Instance ID 有唯一兼容接口对时自动消解。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_yaml(root, "instances/PLUG.yaml", """\
id: PLUG
family: AssemblyPartFamily
interfaces:
  - id: plug-face
    interface_type: IEC-C13
""")
            _write_yaml(root, "instances/SOCKET.yaml", """\
id: SOCKET
family: AssemblyPartFamily
interfaces:
  - id: socket-face
    interface_type: IEC-C14
""")
            _write_yaml(root, "mates/power/connect.yaml", """\
type: power-cable
parent: PLUG
child: SOCKET
""")
            ctx = _make_ctx(root)
            # IEC-C13 ↔ IEC-C14 互相兼容
            ctx.type_system.register_interface_type("IEC-C13", compatible_with={"IEC-C14"})
            ctx.type_system.register_interface_type("IEC-C14", compatible_with={"IEC-C13"})
            YAMLParsePass().run(ctx)
            LoweringPass().run(ctx)
            MateSugarResolvePass().run(ctx)

            # 检查消解结果
            mate = ctx.compilation.mates.get("PLUG→SOCKET")
            assert mate is not None
            assert "/" in mate.parent_ref.text
            assert "/" in mate.child_ref.text

    def test_errors_on_no_compatible_pair(self):
        """无兼容接口对时产生 MATE-003 诊断。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_yaml(root, "instances/PLUG.yaml", """\
id: PLUG
family: AssemblyPartFamily
interfaces:
  - id: plug-face
    interface_type: generic-face
""")
            _write_yaml(root, "instances/SOCKET.yaml", """\
id: SOCKET
family: AssemblyPartFamily
interfaces:
  - id: socket-face
    interface_type: RJ45-jack
""")
            _write_yaml(root, "mates/power/connect.yaml", """\
type: power-cable
parent: PLUG
child: SOCKET
""")
            ctx = _make_ctx(root)
            YAMLParsePass().run(ctx)
            LoweringPass().run(ctx)
            MateSugarResolvePass().run(ctx)

            # 应产生 MATE-003 或类似诊断
            mate_diags = [d for d in ctx.diagnostics if d.code.startswith("MATE-")]
            assert len(mate_diags) > 0

    def test_skips_already_resolved_refs(self):
        """已是接口引用的 Mate 不做消解。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_yaml(root, "instances/PLUG.yaml", """\
id: PLUG
family: AssemblyPartFamily
interfaces:
  - id: plug-face
    interface_type: IEC-C13
""")
            _write_yaml(root, "instances/SOCKET.yaml", """\
id: SOCKET
family: AssemblyPartFamily
interfaces:
  - id: socket-face
    interface_type: IEC-C14
""")
            _write_yaml(root, "mates/power/connect.yaml", """\
type: power-cable
parent: PLUG/plug-face
child: SOCKET/socket-face
""")
            ctx = _make_ctx(root)
            YAMLParsePass().run(ctx)
            LoweringPass().run(ctx)
            MateSugarResolvePass().run(ctx)

            mate = ctx.compilation.mates.get("PLUG/plug-face→SOCKET/socket-face")
            assert mate is not None
            # 应该保持原样
            assert mate.parent_ref.text == "PLUG/plug-face"
            assert mate.child_ref.text == "SOCKET/socket-face"


# ────────────────────────────────────────────────────────────────
# BackCompatEmitPass
# ────────────────────────────────────────────────────────────────


class TestBackCompatEmitPass:
    """HIR → Project 向后兼容 Pass 测试。"""

    def test_emits_project_with_instances(self):
        """验证生成包含 Instance 的 Project 对象。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_yaml(root, "instances/PART-A.yaml", """\
id: PART-A
family: AssemblyPartFamily
name: 零件A
width_mm: 100
interfaces:
  - id: face-a
    interface_type: generic-face
    local_transform:
      translation: [0, 0, 10]
""")
            ctx = _make_ctx(root)
            YAMLParsePass().run(ctx)
            LoweringPass().run(ctx)
            MateSugarResolvePass().run(ctx)
            BackCompatEmitPass().run(ctx)

            project = ctx.extra.get("project")
            assert project is not None
            assert "PART-A" in project.instances
            inst = project.instances["PART-A"]
            assert inst.family == "AssemblyPartFamily"

    def test_interface_data_preserved(self):
        """验证 interface 的 local_transform 等几何数据被正确保留。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_yaml(root, "instances/PART-A.yaml", """\
id: PART-A
family: AssemblyPartFamily
interfaces:
  - id: face-a
    interface_type: generic-face
    local_transform:
      translation: [1, 2, 3]
      rotation: [0, 90, 0]
    mating_kind: face
""")
            ctx = _make_ctx(root)
            YAMLParsePass().run(ctx)
            LoweringPass().run(ctx)
            MateSugarResolvePass().run(ctx)
            BackCompatEmitPass().run(ctx)

            from adl.models.interface import get_interfaces_from_resolved
            project = ctx.extra["project"]
            inst = project.instances["PART-A"]
            ifaces = get_interfaces_from_resolved(inst)
            assert len(ifaces) == 1
            assert ifaces[0].id == "face-a"
            assert ifaces[0].local_transform.translation.x == 1.0
            assert ifaces[0].local_transform.translation.y == 2.0
            assert ifaces[0].local_transform.rotation.y == 90.0

    def test_mates_emitted(self):
        """验证 Mate 数据被正确输出。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_yaml(root, "instances/PLUG.yaml", """\
id: PLUG
family: AssemblyPartFamily
interfaces:
  - id: plug-face
    interface_type: IEC-C13
""")
            _write_yaml(root, "instances/SOCKET.yaml", """\
id: SOCKET
family: AssemblyPartFamily
interfaces:
  - id: socket-face
    interface_type: IEC-C14
""")
            _write_yaml(root, "mates/power/connect.yaml", """\
type: power-cable
parent: PLUG
child: SOCKET
""")
            ctx = _make_ctx(root)
            YAMLParsePass().run(ctx)
            LoweringPass().run(ctx)
            MateSugarResolvePass().run(ctx)
            BackCompatEmitPass().run(ctx)

            project = ctx.extra["project"]
            assert len(project.mates) >= 1


# ────────────────────────────────────────────────────────────────
# PassManager
# ────────────────────────────────────────────────────────────────


class _DummyPass(Pass):
    """测试用 Pass。"""
    def __init__(self, name: str, stage: PassStage = PassStage.AST, should_fail: bool = False):
        self.name = name
        self.stage = stage
        self.description = f"Test pass {name}"
        self.should_fail = should_fail
        self.executed = False

    def run(self, ctx: PassContext) -> PassResult:
        self.executed = True
        if self.should_fail:
            raise RuntimeError(f"Pass {self.name} intentional failure")
        return PassResult(success=True, modified=True)


class TestPassManager:
    """PassManager 调度测试。"""

    def test_runs_passes_in_order(self):
        pm = PassManager()
        p1 = _DummyPass("p1")
        p2 = _DummyPass("p2")
        pm.register(p1)
        pm.register(p2, after=["p1"])

        ctx = _make_ctx(Path("."))
        pm.run(ctx)
        assert p1.executed
        assert p2.executed

    def test_detects_self_cycle(self):
        pm = PassManager()
        with pytest.raises(DependencyCycleError, match="不能依赖自身"):
            pm.register(_DummyPass("p1"), after=["p1"])

    def test_detects_mutual_cycle(self):
        pm = PassManager()
        pm.register(_DummyPass("p1"), after=["p2"])
        with pytest.raises(DependencyCycleError):
            pm.register(_DummyPass("p2"), after=["p1"])

    def test_error_recovery_continues(self):
        """一个 Pass 失败后，后续无依赖的 Pass 仍应执行。"""
        pm = PassManager()
        p_fail = _DummyPass("fail", should_fail=True)
        p_ok = _DummyPass("ok")
        pm.register(p_fail)
        pm.register(p_ok)  # 无依赖于 fail

        ctx = _make_ctx(Path("."))
        pm.run(ctx)

        assert p_fail.executed
        assert p_ok.executed
        assert pm.has_failures

    def test_list_passes(self):
        pm = PassManager()
        pm.register(_DummyPass("a"))
        pm.register(_DummyPass("b"), after=["a"])

        info = pm.list_passes()
        assert len(info) == 2
        assert info[0]["name"] == "a"
        assert info[1]["dependencies"] == ["a"]

    def test_up_to_stage_filter(self):
        """up_to 参数应过滤掉后续阶段的 Pass。"""
        pm = PassManager()
        p_ast = _DummyPass("ast", PassStage.AST)
        p_mir = _DummyPass("mir", PassStage.MIR)
        pm.register(p_ast)
        pm.register(p_mir)

        ctx = _make_ctx(Path("."))
        pm.run(ctx, up_to=PassStage.HIR)

        assert p_ast.executed
        assert not p_mir.executed
