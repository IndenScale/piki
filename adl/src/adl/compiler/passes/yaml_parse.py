"""YAMLParsePass — YAML 源文件 → AST (SourceFile)。

复用现有 adl.parsing.yaml_source 中的 PyYAML compose 能力，
将 SourceTrackedDict 转换为编译器 AST 节点。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from adl.parsing.yaml_source import SourceMark, SourceTrackedDict, load_yaml_with_source

from ..ast_ import (
    ASTValue,
    Declaration,
    DeclKind,
    Field,
    FileKind,
    SourceFile,
    ValueKind,
)
from ..pass_manager import Pass, PassContext, PassResult, PassStage
from ..span import Span

# ---------------------------------------------------------------------------
# 目录 → 文件类型的映射
# ---------------------------------------------------------------------------

_DIR_KIND: dict[str, FileKind] = {
    "instances": FileKind.INSTANCE,
    "models": FileKind.MODEL,
    "catalogs": FileKind.CATALOG,
    "mates": FileKind.MATE,
    "layouts": FileKind.LAYOUT,
    "grids": FileKind.GRID,
    "connections": FileKind.CONNECTION,
}

# 识别 Instance 文件的字段
_INSTANCE_ID_KEYS = {"id", "instance"}
_MODEL_ID_KEYS = {"model"}
_CATALOG_ID_KEYS = {"id", "catalog_id"}
_MATE_ID_KEYS = {"type"}


def _mark_to_span(mark: SourceMark) -> Span:
    """SourceMark (0-based) → Span (1-based)。"""
    return Span(
        source=mark.path,
        start_line=mark.line + 1,
        start_col=mark.column + 1,
        end_line=mark.line + 1,
        end_col=mark.column + 1,  # 单点位置
    )


def _infer_file_kind(path: Path, data: dict[str, Any]) -> FileKind:
    """推断 YAML 文件类型。"""
    # 先按目录推断
    for part in path.parts:
        if part in _DIR_KIND:
            return _DIR_KIND[part]

    # 按内容推断
    if "type" in data and ("parent" in data or "child" in data or "constrains" in data):
        return FileKind.MATE
    if "entries" in data or "sections" in data:
        return FileKind.LAYOUT
    if "family" in data:
        if "model" in data:
            return FileKind.MODEL
        return FileKind.INSTANCE
    return FileKind.UNKNOWN


def _infer_decl_kind(file_kind: FileKind, data: dict[str, Any]) -> DeclKind:
    """推断声明类型。"""
    _MAP: dict[FileKind, DeclKind] = {
        FileKind.INSTANCE: DeclKind.INSTANCE,
        FileKind.MODEL: DeclKind.MODEL,
        FileKind.CATALOG: DeclKind.CATALOG_ENTRY,
        FileKind.MATE: DeclKind.MATE_SPEC,
        FileKind.CONNECTION: DeclKind.CONNECTION,
        FileKind.GRID: DeclKind.GRID_DEF,
    }
    return _MAP.get(file_kind, DeclKind.INSTANCE)


def _value_to_ast(raw: Any, mark: SourceMark | None, path: Path) -> ASTValue:
    """将 Python 值 + SourceMark 转换为 ASTValue。"""
    span = _mark_to_span(mark) if mark else Span.point(path, 0, 0)

    if raw is None:
        return ASTValue(kind=ValueKind.NULL, data=None, span=span)
    elif isinstance(raw, bool):
        return ASTValue(kind=ValueKind.BOOL, data=raw, span=span)
    elif isinstance(raw, int):
        return ASTValue(kind=ValueKind.INT, data=raw, span=span)
    elif isinstance(raw, float):
        return ASTValue(kind=ValueKind.FLOAT, data=raw, span=span)
    elif isinstance(raw, str):
        return ASTValue(kind=ValueKind.STR, data=raw, span=span)
    elif isinstance(raw, list):
        items = [
            _value_to_ast(item, None, path)  # 列表元素没有单独的 SourceMark
            for item in raw
        ]
        return ASTValue(kind=ValueKind.LIST, data=items, span=span)
    elif isinstance(raw, dict):
        mapping: dict[str, ASTValue] = {}
        if isinstance(raw, SourceTrackedDict):
            for key, val in raw.items():
                m = raw._get_source(key)
                mapping[key] = _value_to_ast(val, m, path)
        else:
            for key, val in raw.items():
                mapping[key] = _value_to_ast(val, None, path)
        return ASTValue(kind=ValueKind.MAPPING, data=mapping, span=span)
    else:
        return ASTValue(kind=ValueKind.STR, data=str(raw), span=span)


def _parse_file(path: Path) -> SourceFile:
    """解析单个 YAML 文件为 SourceFile。"""
    try:
        data = load_yaml_with_source(path)
    except ValueError:
        # YAML sequence (layout files etc.) — load as raw list
        import yaml
        with open(path, 'r', encoding='utf-8') as f:
            raw = yaml.safe_load(f)
        if isinstance(raw, list):
            data = {'entries': raw}
        else:
            raise
    kind = _infer_file_kind(path, data)
    sf = SourceFile(path=path, kind=kind, raw=data)

    if kind == FileKind.LAYOUT:
        # Layout 文件：每个 entry 是一个 Declaration
        entries = data.get("entries", [])
        if isinstance(entries, list):
            for entry_data in entries:
                if not isinstance(entry_data, dict):
                    continue
                inst_id = entry_data.get("instance", "")
                decl = Declaration(
                    kind=DeclKind.LAYOUT_ENTRY,
                    name=str(inst_id),
                    span=Span.point(path, 0, 0),
                )
                if isinstance(entry_data, SourceTrackedDict):
                    for key, val in entry_data.items():
                        m = entry_data._get_source(key)
                        span = _mark_to_span(m) if m else Span.point(path, 0, 0)
                        decl.fields.append(
                            Field(key=key, value=_value_to_ast(val, m, path), span=span)
                        )
                else:
                    for key, val in entry_data.items():
                        decl.fields.append(
                            Field(
                                key=key,
                                value=_value_to_ast(val, None, path),
                                span=Span.point(path, 0, 0),
                            )
                        )
                sf.declarations.append(decl)
    else:
        # 其他文件类型：整个顶层 dict 是一条 Declaration
        decl_kind = _infer_decl_kind(kind, data)

        # 确定声明名
        decl_name = ""
        for cand in ["id", "instance", "model", "catalog_id"]:
            if cand in data:
                decl_name = str(data[cand])
                break
        if not decl_name and kind == FileKind.MATE:
            parent = data.get("parent", "")
            child = data.get("child", "")
            decl_name = f"{parent}→{child}" if parent and child else "unnamed_mate"

        decl = Declaration(kind=decl_kind, name=decl_name, span=Span.point(path, 0, 0))

        if isinstance(data, SourceTrackedDict):
            for key, val in data.items():
                m = data._get_source(key)
                span = _mark_to_span(m) if m else Span.point(path, 0, 0)
                decl.fields.append(
                    Field(key=key, value=_value_to_ast(val, m, path), span=span)
                )
        else:
            for key, val in data.items():
                decl.fields.append(
                    Field(
                        key=key,
                        value=_value_to_ast(val, None, path),
                        span=Span.point(path, 0, 0),
                    )
                )
        sf.declarations.append(decl)

    return sf


# ---------------------------------------------------------------------------
# Pass
# ---------------------------------------------------------------------------


class YAMLParsePass(Pass):
    """YAML 解析 Pass：扫描目录，解析所有 YAML 文件为 AST SourceFile。"""

    name = "yaml-parse"
    stage = PassStage.AST
    description = "解析项目中的 YAML 文件，生成 AST (SourceFile)"

    def run(self, ctx: PassContext) -> PassResult:
        result = PassResult()
        yaml_files: list[tuple[Path, FileKind | None]] = []

        # 项目主目录：按目录名推断类型
        for fpath in ctx.root.rglob("*.yaml"):
            if self._is_excluded(fpath):
                continue
            yaml_files.append((fpath, None))

        # 插件/额外型号库：强制为 MODEL
        for extra_dir in ctx.extra_model_dirs:
            if not extra_dir.exists():
                continue
            for fpath in extra_dir.rglob("*.yaml"):
                if self._is_excluded(fpath):
                    continue
                yaml_files.append((fpath, FileKind.MODEL))

        # 插件/额外 Catalog：强制为 CATALOG
        for extra_dir in ctx.extra_catalog_dirs:
            if not extra_dir.exists():
                continue
            for fpath in extra_dir.rglob("*.yaml"):
                if self._is_excluded(fpath):
                    continue
                yaml_files.append((fpath, FileKind.CATALOG))

        for fpath, forced_kind in sorted(yaml_files, key=lambda t: str(t[0])):
            try:
                sf = _parse_file(fpath)
                if forced_kind is not None:
                    sf.kind = forced_kind
                    # 当 kind 被强制改变时，同步修正第一条 Declaration 的 kind
                    if sf.declarations and sf.kind == FileKind.MODEL:
                        sf.declarations[0].kind = DeclKind.MODEL
                    elif sf.declarations and sf.kind == FileKind.CATALOG:
                        sf.declarations[0].kind = DeclKind.CATALOG_ENTRY
                ctx.source_files[fpath] = sf
            except Exception as exc:
                from adl.diagnostics import Diagnostic, Location, Severity

                ctx.emit(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=f"YAML 解析失败: {exc}",
                        location=Location.from_path(fpath),
                        code="PARSE-001",
                        source="adl.compiler.yaml_parse",
                    )
                )

        result.modified = len(ctx.source_files) > 0
        return result

    @staticmethod
    def _is_excluded(fpath: Path) -> bool:
        s = str(fpath)
        return "dist/" in s or ".git/" in s or "__pycache__" in s or ".piki" in s

