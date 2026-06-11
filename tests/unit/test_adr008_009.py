"""ADR-008 / ADR-009 新功能的单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from piki.core.engine.checker import Checker, CheckReport, rule
from piki.core.engine.context import Context
from piki.core.engine.registry import Registry
from piki.core.models.base import get_non_overridable_fields, NON_OVERRIDABLE_KEY
from piki.core.models.tags import Tags
from piki.extensions.telecom.plugin import ServerFamily, RackFamily, PduFamily
from piki.core.models.diagnostic import Severity


class TestOverrideWhitelist:
    """ADR-008 §1.2: 覆盖白名单。"""

    def test_get_non_overridable_fields(self) -> None:
        fields = get_non_overridable_fields(ServerFamily)
        assert "depth_mm" in fields
        assert "width_mm" in fields
        assert "height_mm" in fields
        assert "weight_kg" in fields
        # 可覆盖字段不应在白名单中
        assert "tdp_w" not in fields
        assert "height_u" not in fields

    def test_blocked_override_generates_diagnostic(self, tmp_path: Path) -> None:
        registry = Registry()
        registry.add_family("ServerFamily", ServerFamily)

        lib = tmp_path / "library" / "devices"
        lib.mkdir(parents=True)
        (lib / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\ntdp_w: 300\n"
            "depth_mm: 700\nwidth_mm: 438\n",
            encoding="utf-8",
        )
        registry.load_library(lib.parent)

        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "BAD.yaml").write_text(
            "id: BAD\nmodel: generic-server\n"
            "rack_id: RACK-A01\nposition_u: 1\npdu_id: PDU-A\n"
            "depth_mm: 999\nwidth_mm: 999\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        # 应产生 SCHEMA-002 诊断
        schema002 = [d for d in registry.diagnostics if d.code == "SCHEMA-002"]
        assert len(schema002) == 2  # depth_mm + width_mm
        assert "depth_mm" in schema002[0].message
        assert "width_mm" in schema002[1].message

        # Instance 应该被解析，但物理尺寸来自 Model
        inst = registry.find_instance("BAD")
        assert inst is not None
        assert inst.resolved.depth_mm == 700  # Model 默认值
        assert inst.resolved.width_mm == 438   # Model 默认值

    def test_allowed_override_still_works(self, tmp_path: Path) -> None:
        """可覆盖字段仍可被 Instance 覆盖。"""
        registry = Registry()
        registry.add_family("ServerFamily", ServerFamily)

        lib = tmp_path / "library" / "devices"
        lib.mkdir(parents=True)
        (lib / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\ntdp_w: 300\n",
            encoding="utf-8",
        )
        registry.load_library(lib.parent)

        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV.yaml").write_text(
            "id: SRV\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 1\npdu_id: PDU-A\n"
            "tdp_w: 250\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        inst = registry.find_instance("SRV")
        assert inst.resolved.tdp_w == 250  # Instance 覆盖生效

        # 不应有 SCHEMA-002
        schema002 = [d for d in registry.diagnostics if d.code == "SCHEMA-002"]
        assert len(schema002) == 0


class TestReferenceIntegrity:
    """ADR-008: L2 引用完整性检查。"""

    def test_missing_instance_in_layout_reported(self, tmp_path: Path) -> None:
        registry = Registry()
        registry.add_family("ServerFamily", ServerFamily)

        layouts = tmp_path / "layouts"
        layouts.mkdir()
        (layouts / "layout.yaml").write_text(
            "- instance: GHOST-01\n  rack_id: RACK-A01\n  position_u: 10\n",
            encoding="utf-8",
        )
        registry.load_layout(tmp_path)

        checker = Checker()
        ctx = Context(registry, {})

        with pytest.raises(AssertionError, match="GHOST-01"):
            checker.check_reference_integrity(ctx)

    def test_valid_layout_passes(self, tmp_path: Path) -> None:
        registry = Registry()
        registry.add_family("ServerFamily", ServerFamily)

        lib = tmp_path / "library" / "devices"
        lib.mkdir(parents=True)
        (lib / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\ntdp_w: 300\n",
            encoding="utf-8",
        )
        registry.load_library(lib.parent)

        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV-01.yaml").write_text(
            "id: SRV-01\nmodel: generic-server\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        layouts = tmp_path / "layouts"
        layouts.mkdir()
        (layouts / "layout.yaml").write_text(
            "- instance: SRV-01\n  rack_id: RACK-A01\n  position_u: 10\n",
            encoding="utf-8",
        )
        registry.load_layout(tmp_path)

        checker = Checker()
        ctx = Context(registry, {})
        checker.check_reference_integrity(ctx)  # 不应抛异常


class TestTags:
    """ADR-009: Tag Schema 支持。"""

    def test_tags_model_known_keys(self) -> None:
        tags = Tags(discipline="hvac", security_zone="containment")
        assert tags.discipline == "hvac"
        assert tags.security_zone == "containment"

    def test_tags_model_extra_keys(self) -> None:
        tags = Tags(discipline="hvac", custom_key="custom_value")
        assert tags.extra["custom_key"] == "custom_value"
        assert tags.discipline == "hvac"

    def test_tags_as_flat_dict(self) -> None:
        tags = Tags(discipline="hvac", system="fire-alarm", extra={"foo": "bar"})
        flat = tags.as_flat_dict()
        assert flat["discipline"] == "hvac"
        assert flat["system"] == "fire-alarm"
        assert flat["foo"] == "bar"

    def test_tags_in_instance(self, tmp_path: Path) -> None:
        registry = Registry()
        registry.add_family("ServerFamily", ServerFamily)

        lib = tmp_path / "library" / "devices"
        lib.mkdir(parents=True)
        (lib / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\n",
            encoding="utf-8",
        )
        registry.load_library(lib.parent)

        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV.yaml").write_text(
            "id: SRV\nmodel: generic-server\n"
            "rack_id: RACK-A01\nposition_u: 1\npdu_id: PDU-A\n"
            "tags:\n  discipline: compute\n  security_zone: red\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        inst = registry.find_instance("SRV")
        assert inst is not None
        # Tags are in _resolved as a nested structure
        resolved = inst.resolved
        assert resolved.tags.discipline == "compute"
        assert resolved.tags.security_zone == "red"

    def test_tags_query_filter(self, tmp_path: Path) -> None:
        """tags__discipline=hvac query works."""
        registry = Registry()
        registry.add_family("ServerFamily", ServerFamily)

        lib = tmp_path / "library" / "devices"
        lib.mkdir(parents=True)
        (lib / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\n",
            encoding="utf-8",
        )
        registry.load_library(lib.parent)

        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV-A.yaml").write_text(
            "id: SRV-A\nmodel: generic-server\n"
            "rack_id: RACK-A01\nposition_u: 1\npdu_id: PDU-A\n"
            "tags:\n  discipline: hvac\n",
            encoding="utf-8",
        )
        (devices / "SRV-B.yaml").write_text(
            "id: SRV-B\nmodel: generic-server\n"
            "rack_id: RACK-A01\nposition_u: 2\npdu_id: PDU-A\n"
            "tags:\n  discipline: electrical\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        ctx = Context(registry, {})
        hvac_devices = ctx.query("devices", tags__discipline="hvac")
        assert hvac_devices.count() == 1
        assert hvac_devices.first().id == "SRV-A"

    def test_tag_schema_check_allows_known_keys(self, tmp_path: Path) -> None:
        registry = Registry()
        registry.add_family("ServerFamily", ServerFamily)
        registry.set_allowed_tags(["discipline", "security_zone"])

        lib = tmp_path / "library" / "devices"
        lib.mkdir(parents=True)
        (lib / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\n",
            encoding="utf-8",
        )
        registry.load_library(lib.parent)

        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV.yaml").write_text(
            "id: SRV\nmodel: generic-server\n"
            "rack_id: RACK-A01\nposition_u: 1\npdu_id: PDU-A\n"
            "tags:\n  discipline: hvac\n  security_zone: red\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        checker = Checker()
        ctx = Context(registry, {})
        checker.check_tag_schema(ctx)  # 不应抛异常

    def test_tag_schema_check_blocks_unknown_keys(self, tmp_path: Path) -> None:
        registry = Registry()
        registry.add_family("ServerFamily", ServerFamily)
        registry.set_allowed_tags(["discipline"])

        lib = tmp_path / "library" / "devices"
        lib.mkdir(parents=True)
        (lib / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\n",
            encoding="utf-8",
        )
        registry.load_library(lib.parent)

        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV.yaml").write_text(
            "id: SRV\nmodel: generic-server\n"
            "rack_id: RACK-A01\nposition_u: 1\npdu_id: PDU-A\n"
            "tags:\n  discipline: hvac\n  bad_tag: nope\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        checker = Checker()
        ctx = Context(registry, {})
        with pytest.raises(AssertionError, match="bad_tag"):
            checker.check_tag_schema(ctx)


class TestFQID:
    """ADR-009: 全限定 Instance ID。"""

    def test_fqid_simple_project(self) -> None:
        reg = Registry()
        reg.set_project_name("my-project")
        assert reg.fqid("SRV-01") == "my-project/SRV-01"

    def test_fqid_nested_project(self) -> None:
        parent = Registry()
        parent.set_project_name("厂区")

        child = Registry()
        child.set_parent(parent)
        child.set_project_name("安全壳内")

        grandchild = Registry()
        grandchild.set_parent(child)
        grandchild.set_project_name("1号楼")

        assert grandchild.fqid("PUMP-01") == "厂区/安全壳内/1号楼/PUMP-01"

    def test_all_instances_with_fqid(self, tmp_path: Path) -> None:
        parent = Registry()
        parent.set_project_name("parent")
        child = Registry()
        child.set_parent(parent)
        child.set_project_name("child")

        # Add instances to both
        plib = tmp_path / "plib" / "devices"
        plib.mkdir(parents=True)
        (plib / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\n",
            encoding="utf-8",
        )
        parent.add_family("ServerFamily", ServerFamily)
        parent.load_library(plib.parent)
        parent_devs = tmp_path / "pdevs"
        parent_devs.mkdir()
        (parent_devs / "P-01.yaml").write_text(
            "id: P-01\nmodel: generic-server\n",
            encoding="utf-8",
        )
        parent.load_collection(parent_devs)

        child_devs = tmp_path / "cdevs"
        child_devs.mkdir()
        (child_devs / "C-01.yaml").write_text(
            "id: C-01\nmodel: generic-server\n",
            encoding="utf-8",
        )
        child.add_family("ServerFamily", ServerFamily)
        child.load_library(plib.parent)
        child.load_collection(child_devs)

        fqid_map = child.all_instances_with_fqid()
        assert "parent/P-01" in fqid_map
        assert "parent/child/C-01" in fqid_map


class TestPathResolver:
    """ADR-009: 跨仓库 Instance 引用。"""

    def test_resolve_simple_id_delegates(self) -> None:
        resolver = Registry()._make_path_resolver(Path("/tmp"))
        # 简单 ID 返回 None（由 Registry.find_instance 处理）
        assert resolver.resolve_instance("SRV-01") is None

    def test_resolve_project_root_var(self, tmp_path: Path) -> None:
        resolver = Registry()._make_path_resolver(tmp_path)
        assert resolver.resolve_instance("$PROJECT_ROOT/instances/SRV-01.yaml") is None
        # 文件不存在时的行为

    def test_resolve_external_alias(self, tmp_path: Path) -> None:
        ext = tmp_path / "external-project"
        ext.mkdir()
        instances = ext / "instances"
        instances.mkdir()
        (instances / "SRV-01.yaml").write_text(
            "id: SRV-01\nmodel: generic-server\n",
            encoding="utf-8",
        )

        resolver = Registry()._make_path_resolver(
            tmp_path,
            externals={"vendor-a": ext},
        )
        # path exists but returns None because cross-repo resolve needs Registry
        result = resolver.resolve_instance("vendor-a/SRV-01")
        assert result is None  # cross-repo requires Registry context


class TestExternalProjectRegistration:
    """ADR-009 §5.3: piki.toml [external] 配置。"""

    def test_register_external(self) -> None:
        reg = Registry()
        reg.register_external("vendor-models", Path("/fake/path"))
        assert "vendor-models" in reg.externals
        assert reg.externals["vendor-models"] == Path("/fake/path")
