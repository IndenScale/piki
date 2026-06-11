"""Registry 单元测试 —— 覆盖加载、解析、查询、边界情况。"""

from __future__ import annotations

from pathlib import Path

import pytest

from piki.core.engine.registry import Registry
from piki.extensions.telecom.plugin import PduFamily, RackFamily, ServerFamily


class TestLoadAndResolve:
    """测试基本的加载和解析流程。"""

    def test_load_and_resolve(self, tmp_path: Path) -> None:
        registry = Registry()
        registry.add_family("RackFamily", RackFamily)
        registry.add_family("PduFamily", PduFamily)
        registry.add_family("ServerFamily", ServerFamily)

        # 型号库
        lib = tmp_path / "library" / "devices"
        lib.mkdir(parents=True)
        (lib / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\nheight_u: 2\ntdp_w: 300\n",
            encoding="utf-8",
        )
        registry.load_library(lib.parent)

        # 机柜
        racks = tmp_path / "racks"
        racks.mkdir()
        (racks / "RACK-A01.yaml").write_text(
            "id: RACK-A01\nfamily: RackFamily\ntotal_u: 42\n",
            encoding="utf-8",
        )
        registry.load_collection(racks)

        # PDU
        pdus = tmp_path / "pdus"
        pdus.mkdir()
        (pdus / "PDU-A.yaml").write_text(
            "id: PDU-A\nfamily: PduFamily\nrack_id: RACK-A01\ncapacity_w: 2000\n",
            encoding="utf-8",
        )
        registry.load_collection(pdus)

        # 设备
        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV-01.yaml").write_text(
            "id: SRV-01\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 10\npdu_id: PDU-A\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        srv = registry.query("devices", id="SRV-01").first()
        assert srv is not None
        assert srv.resolved.height_u == 2
        assert srv.resolved.tdp_w == 300
        assert srv.rack_id == "RACK-A01"
        assert srv.pdu_id == "PDU-A"

    def test_model_override(self, tmp_path: Path) -> None:
        """测试 Instance 覆盖 Model 默认值。"""
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
            "id: SRV-01\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 1\npdu_id: PDU-A\ntdp_w: 250\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        srv = registry.query("devices", id="SRV-01").first()
        assert srv.resolved.tdp_w == 250  # Instance 覆盖 Model
        assert srv.resolved.height_u == 2  # Model 默认值


class TestQuery:
    """测试 Registry.query 的增强语法。"""

    @pytest.fixture
    def registry(self, tmp_path: Path) -> Registry:
        r = Registry()
        r.add_family("ServerFamily", ServerFamily)
        r.add_family("PduFamily", PduFamily)

        # 型号库
        lib = tmp_path / "library" / "devices"
        lib.mkdir(parents=True)
        (lib / "generic-server.yaml").write_text(
            "model: generic-server\nfamily: ServerFamily\ntdp_w: 300\n",
            encoding="utf-8",
        )
        r.load_library(lib.parent)

        # PDU
        pdus = tmp_path / "pdus"
        pdus.mkdir()
        (pdus / "PDU-A.yaml").write_text(
            "id: PDU-A\nfamily: PduFamily\nrack_id: RACK-A01\ncapacity_w: 2000\n",
            encoding="utf-8",
        )
        (pdus / "PDU-B.yaml").write_text(
            "id: PDU-B\nfamily: PduFamily\nrack_id: RACK-A01\ncapacity_w: 2000\n",
            encoding="utf-8",
        )
        r.load_collection(pdus)

        # 设备
        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "SRV-01.yaml").write_text(
            "id: SRV-01\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 10\npdu_id: PDU-A\n",
            encoding="utf-8",
        )
        (devices / "SRV-02.yaml").write_text(
            "id: SRV-02\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 8\npdu_id: PDU-A\ntdp_w: 250\n",
            encoding="utf-8",
        )
        (devices / "SRV-03.yaml").write_text(
            "id: SRV-03\nmodel: generic-server\nrack_id: RACK-A01\nposition_u: 6\npdu_id: PDU-B\ntdp_w: 400\n",
            encoding="utf-8",
        )
        r.load_collection(devices)
        return r

    def test_query_eq(self, registry: Registry) -> None:
        assert registry.query("devices", pdu_id="PDU-A").count() == 2

    def test_query_gt(self, registry: Registry) -> None:
        assert registry.query("devices", tdp_w__gt=300).count() == 1
        assert registry.query("devices", tdp_w__gt=300).first().id == "SRV-03"

    def test_query_in(self, registry: Registry) -> None:
        result = registry.query("devices", pdu_id__in=["PDU-A", "PDU-B"])
        assert result.count() == 3

    def test_query_order_by(self, registry: Registry) -> None:
        result = registry.query("devices").order_by("-tdp_w").list()
        assert [d.id for d in result] == ["SRV-03", "SRV-01", "SRV-02"]

    def test_query_chain(self, registry: Registry) -> None:
        result = (
            registry.query("devices")
            .filter(pdu_id="PDU-A")
            .order_by("position_u")
            .list()
        )
        assert [d.id for d in result] == ["SRV-02", "SRV-01"]

    def test_query_empty_collection(self, registry: Registry) -> None:
        assert registry.query("nonexistent").count() == 0

    def test_list_collections(self, registry: Registry) -> None:
        cols = registry.list_collections()
        assert set(cols) >= {"devices", "pdus"}

    def test_all_instances(self, registry: Registry) -> None:
        insts = registry.all_instances()
        assert len(insts) == 5  # 3 devices + 2 pdus


class TestEdgeCases:
    """测试边界情况。"""

    def test_instance_without_family_no_model(self, tmp_path: Path) -> None:
        """没有 family 也没有 model 的 instance 应该退化为无校验数据。"""
        registry = Registry()
        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "orphan.yaml").write_text(
            "id: orphan\nfoo: bar\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        inst = registry.query("devices", id="orphan").first()
        assert inst is not None
        assert inst.id == "orphan"
        assert inst.family == "_invalid"

    def test_instance_unknown_family(self, tmp_path: Path) -> None:
        """有 family 但 family 未注册，应退化。"""
        registry = Registry()
        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "unknown.yaml").write_text(
            "id: unknown\nfamily: NonExistentFamily\nfoo: bar\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)

        inst = registry.query("devices", id="unknown").first()
        assert inst is not None
        assert inst.family == "_invalid"

    def test_load_library_missing_dir(self, tmp_path: Path) -> None:
        """library 目录不存在时不应报错。"""
        registry = Registry()
        registry.load_library(tmp_path / "nonexistent")
        # 不抛异常即通过

    def test_load_collection_skips_no_id(self, tmp_path: Path) -> None:
        """没有 id 的 YAML 应被跳过。"""
        registry = Registry()
        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "bad.yaml").write_text(
            "name: no-id\n",
            encoding="utf-8",
        )
        registry.load_collection(devices)
        assert registry.query("devices").count() == 0

    def test_load_collection_skips_bad_yaml(self, tmp_path: Path) -> None:
        """非 dict 的 YAML 应被跳过或报错。"""
        registry = Registry()
        devices = tmp_path / "devices"
        devices.mkdir()
        (devices / "bad.yaml").write_text(
            "- just\n- a\n- list\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="must contain a mapping"):
            registry.load_collection(devices)

    def test_model_without_model_or_family(self, tmp_path: Path) -> None:
        """型号库 YAML 缺少 model/family 字段应被跳过。"""
        registry = Registry()
        lib = tmp_path / "library"
        lib.mkdir()
        (lib / "bad.yaml").write_text(
            "name: something\n",
            encoding="utf-8",
        )
        registry.load_library(lib)
        # 不抛异常即通过
