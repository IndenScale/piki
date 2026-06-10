"""Diagnostic 系统单元测试 —— 覆盖 Severity、Position、Range、Location、Diagnostic、DiagnosticReport。"""

from __future__ import annotations

from pathlib import Path

import pytest

from piki.core.models.diagnostic import (
    CodeDescription,
    Diagnostic,
    DiagnosticReport,
    Location,
    Position,
    Range,
    RelatedInformation,
    Severity,
)


class TestSeverity:
    """测试 Severity 枚举。"""

    def test_ordering(self) -> None:
        assert Severity.DEBUG < Severity.INFO < Severity.WARNING < Severity.ERROR < Severity.FATAL

    def test_labels(self) -> None:
        assert Severity.FATAL.label == "FATAL"
        assert Severity.ERROR.label == "ERROR"
        assert Severity.WARNING.label == "WARNING"
        assert Severity.INFO.label == "INFO"
        assert Severity.DEBUG.label == "DEBUG"

    def test_lsp_mapping(self) -> None:
        assert Severity.FATAL.lsp_value == 1
        assert Severity.ERROR.lsp_value == 1
        assert Severity.WARNING.lsp_value == 2
        assert Severity.INFO.lsp_value == 3
        assert Severity.DEBUG.lsp_value == 3

    def test_str(self) -> None:
        assert str(Severity.ERROR) == "ERROR"


class TestPosition:
    """测试 Position。"""

    def test_basic(self) -> None:
        p = Position(line=5, character=10)
        assert p.line == 5
        assert p.character == 10

    def test_lsp_format(self) -> None:
        p = Position(line=0, character=0)
        assert p.to_lsp() == {"line": 0, "character": 0}

    def test_str(self) -> None:
        p = Position(line=2, character=9)
        assert str(p) == "3:10"

    def test_negative_clamped(self) -> None:
        p = Position(line=-1, character=-5)
        assert p.line == 0
        assert p.character == 0


class TestRange:
    """测试 Range。"""

    def test_basic(self) -> None:
        r = Range(
            start=Position(line=1, character=5),
            end=Position(line=1, character=10),
        )
        assert r.start.line == 1
        assert r.end.character == 10

    def test_point(self) -> None:
        r = Range.point(line=3, character=10)
        assert r.start == r.end
        assert str(r) == "4:11"

    def test_from_line(self) -> None:
        r = Range.from_line(line=2, start_col=5, end_col=15)
        assert r.start == Position(line=2, character=5)
        assert r.end == Position(line=2, character=15)

    def test_from_line_default_end(self) -> None:
        r = Range.from_line(line=2, start_col=5)
        assert r.start == Position(line=2, character=5)
        assert r.end == Position(line=2, character=5)

    def test_lsp_format(self) -> None:
        r = Range.point(line=0, character=0)
        assert r.to_lsp() == {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}}


class TestLocation:
    """测试 Location。"""

    def test_from_path(self) -> None:
        loc = Location.from_path("/tmp/test.yaml", line=5, start_col=10)
        assert loc.path == Path("/tmp/test.yaml")
        assert loc.range.start.line == 5
        assert loc.range.start.character == 10

    def test_to_lsp(self) -> None:
        loc = Location.from_path("/tmp/test.yaml", line=0, start_col=0)
        lsp = loc.to_lsp()
        assert lsp["uri"] == "file:///tmp/test.yaml"
        assert lsp["range"]["start"] == {"line": 0, "character": 0}

    def test_str(self) -> None:
        loc = Location.from_path("/tmp/test.yaml", line=2, start_col=9)
        assert str(loc) == "/tmp/test.yaml:3:10"


class TestDiagnostic:
    """测试 Diagnostic。"""

    def test_passed_property(self) -> None:
        assert Diagnostic.error("err").passed is False
        assert Diagnostic.warning("warn").passed is True
        assert Diagnostic.info("info").passed is True
        assert Diagnostic.debug("debug").passed is True

    def test_is_fatal(self) -> None:
        assert Diagnostic.fatal("boom").is_fatal is True
        assert Diagnostic.error("err").is_fatal is False

    def test_factory_methods(self) -> None:
        d = Diagnostic.fatal("fatal msg", code="F-001")
        assert d.severity == Severity.FATAL
        assert d.message == "fatal msg"
        assert d.code == "F-001"

        d = Diagnostic.error("error msg")
        assert d.severity == Severity.ERROR

        d = Diagnostic.warning("warn msg")
        assert d.severity == Severity.WARNING

        d = Diagnostic.info("info msg")
        assert d.severity == Severity.INFO

        d = Diagnostic.debug("debug msg")
        assert d.severity == Severity.DEBUG

    def test_to_lsp(self) -> None:
        loc = Location.from_path("/tmp/test.yaml", line=0, character=0)
        d = Diagnostic.error("msg", location=loc, code="E-001")
        lsp = d.to_lsp()
        assert lsp["message"] == "msg"
        assert lsp["severity"] == 1
        assert lsp["code"] == "E-001"
        assert lsp["source"] == "piki"

    def test_to_dict(self) -> None:
        loc = Location.from_path("/tmp/test.yaml", line=2, start_col=5)
        d = Diagnostic.error("msg", location=loc, code="E-001", name="测试")
        data = d.to_dict()
        assert data["severity"] == "ERROR"
        assert data["message"] == "msg"
        assert data["code"] == "E-001"
        assert data["name"] == "测试"
        assert data["location"]["uri"] == "file:///tmp/test.yaml"

    def test_file_property(self) -> None:
        d = Diagnostic.error("msg", location=Location.from_path("/tmp/a.yaml"))
        assert d.file == "/tmp/a.yaml"

        d = Diagnostic.error("msg")
        assert d.file == ""

    def test_related_information(self) -> None:
        loc1 = Location.from_path("/tmp/a.yaml", line=0)
        loc2 = Location.from_path("/tmp/b.yaml", line=5)
        d = Diagnostic(
            severity=Severity.ERROR,
            message="main error",
            location=loc1,
            related_information=[
                RelatedInformation(location=loc2, message="related"),
            ],
        )
        assert len(d.related_information) == 1
        assert d.related_information[0].message == "related"
        lsp = d.to_lsp()
        assert "relatedInformation" in lsp

    def test_code_description(self) -> None:
        d = Diagnostic(
            severity=Severity.ERROR,
            message="err",
            code_description=CodeDescription(href="https://docs.example.com/E001"),
        )
        lsp = d.to_lsp()
        assert lsp["codeDescription"] == {"href": "https://docs.example.com/E001"}

    def test_from_validation_error(self) -> None:
        from pydantic import BaseModel, ValidationError

        class TestModel(BaseModel):
            value: int

        try:
            TestModel(value="not an int")
        except ValidationError as exc:
            loc = Location.from_path("/tmp/test.yaml", line=0)
            d = Diagnostic.from_validation_error(exc, loc, code="SCHEMA-001")
            assert d.severity == Severity.ERROR
            assert d.code == "SCHEMA-001"
            assert "value" in d.message


class TestDiagnosticReport:
    """测试 DiagnosticReport。"""

    def test_empty_passes(self) -> None:
        report = DiagnosticReport()
        assert report.passed is True
        assert report.error_count == 0

    def test_with_fatal_fails(self) -> None:
        report = DiagnosticReport()
        report.add(Diagnostic.fatal("boom"))
        assert report.passed is False
        assert report.fatal_count == 1

    def test_with_error_fails(self) -> None:
        report = DiagnosticReport()
        report.add(Diagnostic.error("err"))
        assert report.passed is False
        assert report.error_count == 1

    def test_with_warning_passes(self) -> None:
        report = DiagnosticReport()
        report.add(Diagnostic.warning("warn"))
        assert report.passed is True
        assert report.warning_count == 1

    def test_counts(self) -> None:
        report = DiagnosticReport()
        report.add(Diagnostic.fatal("f"))
        report.add(Diagnostic.error("e"))
        report.add(Diagnostic.warning("w"))
        report.add(Diagnostic.info("i"))
        report.add(Diagnostic.debug("d"))
        assert report.fatal_count == 1
        assert report.error_count == 1
        assert report.warning_count == 1
        assert report.info_count == 1
        assert report.debug_count == 1
        assert report.pass_count == 3  # warning + info + debug

    def test_by_severity(self) -> None:
        report = DiagnosticReport()
        report.add(Diagnostic.error("e1"))
        report.add(Diagnostic.error("e2"))
        report.add(Diagnostic.warning("w"))
        assert len(report.by_severity(Severity.ERROR)) == 2
        assert len(report.by_severity(Severity.WARNING)) == 1

    def test_by_file(self) -> None:
        report = DiagnosticReport()
        report.add(Diagnostic.error("e1", location=Location.from_path("/tmp/a.yaml")))
        report.add(Diagnostic.error("e2", location=Location.from_path("/tmp/b.yaml")))
        assert len(report.by_file("/tmp/a.yaml")) == 1

    def test_by_code(self) -> None:
        report = DiagnosticReport()
        report.add(Diagnostic.error("e1", code="E-001"))
        report.add(Diagnostic.error("e2", code="E-002"))
        assert len(report.by_code("E-001")) == 1

    def test_has_fatal(self) -> None:
        report = DiagnosticReport()
        assert report.has_fatal() is False
        report.add(Diagnostic.fatal("boom"))
        assert report.has_fatal() is True

    def test_to_lsp(self) -> None:
        report = DiagnosticReport()
        report.add(Diagnostic.error("err", location=Location.from_path("/tmp/t.yaml")))
        lsp_list = report.to_lsp()
        assert len(lsp_list) == 1
        assert lsp_list[0]["severity"] == 1

    def test_to_dict(self) -> None:
        report = DiagnosticReport()
        report.add(Diagnostic.error("err"))
        data = report.to_dict()
        assert data["passed"] is False
        assert data["error_count"] == 1
        assert len(data["diagnostics"]) == 1
