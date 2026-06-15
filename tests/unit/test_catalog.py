"""Catalog 机制单元测试（ADR-011）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from adl.validation import ADLValidator

from piki.core.engine.registry import Registry
from piki.core.project import Project
from piki.extensions.telecom.plugin import PduFamily, RackFamily, ServerFamily


class TestCatalogLoading:
    """测试 Catalog 加载与来源优先级。"""

    def _make_registry(self) -> Registry:
        registry = Registry()
        registry.add_family("RackFamily", RackFamily)
        registry.add_family("PduFamily", PduFamily)
        registry.add_family("ServerFamily", ServerFamily)
        return registry

    def test_load_component_catalog(self, tmp_path: Path) -> None:
        registry = self._make_registry()

        catalogs = tmp_path / "catalogs" / "components"
        catalogs.mkdir(parents=True)
        (catalogs / "generic-server.yaml").write_text(
            "catalog_id: generic-server-catalog\n"
            "family: ComponentCatalogFamily\n"
            "manufacturer: Generic\n"
            "mpn: GENERIC-2U\n"
            "lifecycle: active\n"
            "model_ref: generic-server\n",
            encoding="utf-8",
        )
        registry.load_catalogs(tmp_path, source="project")

        entry = registry.find_catalog(model_ref="generic-server")
        assert entry is not None
        assert entry.id == "generic-server-catalog"
        assert entry.data["manufacturer"] == "Generic"
        assert entry.data["mpn"] == "GENERIC-2U"

    def test_load_service_method_catalog(self, tmp_path: Path) -> None:
        registry = self._make_registry()

        catalogs = tmp_path / "catalogs" / "service-methods"
        catalogs.mkdir(parents=True)
        (catalogs / "install-server.yaml").write_text(
            "catalog_id: install-server\n"
            "family: ServiceMethodCatalogFamily\n"
            "service_type: 服务器安装\n"
            "workspace:\n"
            "  min_clearance_mm: 600\n"
            "  esd_required: true\n"
            "safety:\n"
            "  fire_watch_required: false\n"
            "  ppe:\n"
            "    - esd_wrist_strap\n",
            encoding="utf-8",
        )
        registry.load_catalogs(tmp_path, source="project")

        methods = registry.get_service_methods(["install-server"])
        assert len(methods) == 1
        assert methods[0].data["workspace"]["min_clearance_mm"] == 600

    def test_source_priority_project_beats_public(self, tmp_path: Path) -> None:
        registry = self._make_registry()

        # public catalog
        public = tmp_path / "public" / "catalogs" / "components"
        public.mkdir(parents=True)
        (public / "generic-server.yaml").write_text(
            "catalog_id: public-server\n"
            "family: ComponentCatalogFamily\n"
            "manufacturer: PublicVendor\n"
            "model_ref: generic-server\n",
            encoding="utf-8",
        )
        registry.load_catalogs(public.parent.parent, source="public")

        # project catalog
        project_root = tmp_path / "project"
        project = project_root / "catalogs" / "components"
        project.mkdir(parents=True)
        (project / "generic-server.yaml").write_text(
            "catalog_id: project-server\n"
            "family: ComponentCatalogFamily\n"
            "manufacturer: ProjectVendor\n"
            "model_ref: generic-server\n",
            encoding="utf-8",
        )
        registry.load_catalogs(project_root, source="project")

        entry = registry.find_catalog(model_ref="generic-server")
        assert entry is not None
        assert entry.id == "project-server"

    def test_explicit_catalog_id_and_source(self, tmp_path: Path) -> None:
        registry = self._make_registry()

        catalogs = tmp_path / "catalogs" / "components"
        catalogs.mkdir(parents=True)
        (catalogs / "a.yaml").write_text(
            "catalog_id: catalog-a\nfamily: ComponentCatalogFamily\nmodel_ref: model-a\n",
            encoding="utf-8",
        )
        registry.load_catalogs(tmp_path, source="project")

        entry = registry.find_catalog(catalog_id="catalog-a", source="project")
        assert entry is not None
        assert entry.id == "catalog-a"


class TestCatalogResolution:
    """测试 Instance 解析时 Catalog 注入。"""

    def _make_registry(self, tmp_path: Path) -> Registry:
        registry = Registry()
        registry.add_family("ServerFamily", ServerFamily)

        models = tmp_path / "models"
        models.mkdir()
        (models / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\nheight_u: 2\ntdp_w: 300\n",
            encoding="utf-8",
        )
        registry.load_models(models)

        catalogs = tmp_path / "catalogs" / "components"
        catalogs.mkdir(parents=True)
        (catalogs / "generic-server.yaml").write_text(
            "catalog_id: generic-server-catalog\n"
            "family: ComponentCatalogFamily\n"
            "manufacturer: Generic\n"
            "mpn: GENERIC-2U\n"
            "lifecycle: active\n"
            "model_ref: generic-server\n"
            "service_methods:\n"
            "  - install-server\n",
            encoding="utf-8",
        )
        service_methods = tmp_path / "catalogs" / "service-methods"
        service_methods.mkdir(parents=True)
        (service_methods / "install-server.yaml").write_text(
            "catalog_id: install-server\n"
            "family: ServiceMethodCatalogFamily\n"
            "workspace:\n"
            "  min_clearance_mm: 600\n"
            "  esd_required: true\n"
            "safety:\n"
            "  fire_watch_required: true\n",
            encoding="utf-8",
        )
        registry.load_catalogs(tmp_path, source="project")
        return registry

    def test_implicit_catalog_binding(self, tmp_path: Path) -> None:
        registry = self._make_registry(tmp_path)

        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV-01.yaml").write_text(
            "id: SRV-01\nmodel: generic-server\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        inst = registry.query("devices", id="SRV-01").first()
        assert inst is not None
        assert inst.resolved.catalog.manufacturer == "Generic"
        assert inst.resolved.catalog.mpn == "GENERIC-2U"

    def test_service_method_merge(self, tmp_path: Path) -> None:
        registry = self._make_registry(tmp_path)

        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV-01.yaml").write_text(
            "id: SRV-01\nmodel: generic-server\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        inst = registry.query("devices", id="SRV-01").first()
        assert inst is not None
        assert inst.resolved.service_method.workspace.min_clearance_mm == 600
        assert inst.resolved.service_method.safety.fire_watch_required is True

    def test_explicit_catalog_override(self, tmp_path: Path) -> None:
        registry = self._make_registry(tmp_path)

        # 再加一个 enterprise catalog
        enterprise_root = tmp_path / "enterprise"
        enterprise = enterprise_root / "catalogs" / "components"
        enterprise.mkdir(parents=True)
        (enterprise / "server.yaml").write_text(
            "catalog_id: enterprise-server\n"
            "family: ComponentCatalogFamily\n"
            "manufacturer: EnterpriseVendor\n"
            "model_ref: generic-server\n",
            encoding="utf-8",
        )
        registry.load_catalogs(enterprise_root, source="enterprise")

        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV-01.yaml").write_text(
            "id: SRV-01\n"
            "model: generic-server\n"
            "catalog:\n"
            "  id: enterprise-server\n"
            "  source: enterprise\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        inst = registry.query("devices", id="SRV-01").first()
        assert inst is not None
        assert inst.resolved.catalog.manufacturer == "EnterpriseVendor"


class TestCatalogQuery:
    """测试 Catalog 相关 QuerySet 过滤。"""

    @pytest.fixture
    def registry(self, tmp_path: Path) -> Registry:
        registry = Registry()
        registry.add_family("ServerFamily", ServerFamily)

        models = tmp_path / "models"
        models.mkdir()
        (models / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\nheight_u: 2\ntdp_w: 300\n",
            encoding="utf-8",
        )
        registry.load_models(models)

        catalogs = tmp_path / "catalogs" / "components"
        catalogs.mkdir(parents=True)
        (catalogs / "active.yaml").write_text(
            "catalog_id: active-catalog\n"
            "family: ComponentCatalogFamily\n"
            "manufacturer: A\n"
            "lifecycle: active\n"
            "model_ref: generic-server\n",
            encoding="utf-8",
        )
        (catalogs / "eol.yaml").write_text(
            "catalog_id: eol-catalog\n"
            "family: ComponentCatalogFamily\n"
            "manufacturer: B\n"
            "lifecycle: eol\n"
            "model_ref: generic-server\n",
            encoding="utf-8",
        )
        registry.load_catalogs(tmp_path, source="project")

        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV-ACTIVE.yaml").write_text(
            "id: SRV-ACTIVE\nmodel: generic-server\ncatalog:\n  id: active-catalog\n  source: project\n",
            encoding="utf-8",
        )
        (devices / "SRV-EOL.yaml").write_text(
            "id: SRV-EOL\nmodel: generic-server\ncatalog:\n  id: eol-catalog\n  source: project\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)
        return registry

    def test_query_catalog_lifecycle(self, registry: Registry) -> None:
        eol = registry.query("devices", catalog__lifecycle="eol")
        assert eol.count() == 1
        assert eol.first().id == "SRV-EOL"

    def test_query_catalog_manufacturer(self, registry: Registry) -> None:
        result = registry.query("devices", catalog__manufacturer="A")
        assert result.count() == 1
        assert result.first().id == "SRV-ACTIVE"


class TestCatalogChecks:
    """测试内置 Catalog L2 检查。"""

    def test_catalog_001_missing_explicit_catalog(self, tmp_path: Path) -> None:
        registry = Registry()
        registry.add_family("ServerFamily", ServerFamily)

        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV-01.yaml").write_text(
            "id: SRV-01\n"
            "family: ServerFamily\n"
            "catalog:\n"
            "  id: missing-catalog\n"
            "  source: project\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        # Catalog 引用完整性已迁移到 ADL 层验证器
        diagnostics = ADLValidator(registry.project).validate()
        catalog_diags = [d for d in diagnostics if d.code == "CATALOG-001"]
        assert any(not d.passed and "missing-catalog" in d.message for d in catalog_diags)

    def test_catalog_002_missing_service_method(self, tmp_path: Path) -> None:
        registry = Registry()
        registry.add_family("ServerFamily", ServerFamily)

        catalogs = tmp_path / "catalogs" / "components"
        catalogs.mkdir(parents=True)
        (catalogs / "bad.yaml").write_text(
            "catalog_id: bad-catalog\n"
            "family: ComponentCatalogFamily\n"
            "model_ref: generic-server\n"
            "service_methods:\n"
            "  - missing-method\n",
            encoding="utf-8",
        )
        registry.load_catalogs(tmp_path, source="project")

        # Service Method 引用完整性已迁移到 ADL 层验证器
        diagnostics = ADLValidator(registry.project).validate()
        catalog_diags = [d for d in diagnostics if d.code == "CATALOG-002"]
        assert any(not d.passed and "missing-method" in d.message for d in catalog_diags)


class TestCatalogProjectLoading:
    """测试 Project 级别 Catalog 加载。"""

    def test_project_loads_catalog(self, tmp_path: Path) -> None:
        (tmp_path / "piki.toml").write_text(
            '[project]\nname = "demo"\n\n[plugins]\nenabled = ["telecom"]\n',
            encoding="utf-8",
        )
        racks = tmp_path / "instances" / "racks"
        racks.mkdir(parents=True)
        (racks / "RACK-A01.yaml").write_text(
            "id: RACK-A01\nfamily: RackFamily\ntotal_u: 42\n",
            encoding="utf-8",
        )
        devices = tmp_path / "instances" / "devices"
        devices.mkdir(parents=True)
        (devices / "SRV-01.yaml").write_text(
            "id: SRV-01\nmodel: generic-server\n",
            encoding="utf-8",
        )
        models = tmp_path / "models"
        models.mkdir()
        (models / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\nheight_u: 2\ntdp_w: 300\n",
            encoding="utf-8",
        )
        catalogs = tmp_path / "catalogs" / "components"
        catalogs.mkdir(parents=True)
        (catalogs / "generic-server.yaml").write_text(
            "catalog_id: generic-server-catalog\n"
            "family: ComponentCatalogFamily\n"
            "manufacturer: Generic\n"
            "mpn: GENERIC-2U\n"
            "lifecycle: active\n"
            "model_ref: generic-server\n",
            encoding="utf-8",
        )

        project = Project.discover(tmp_path)
        project.load()

        inst = project.registry.query("devices", id="SRV-01").first()
        assert inst is not None
        assert inst.resolved.catalog.mpn == "GENERIC-2U"
