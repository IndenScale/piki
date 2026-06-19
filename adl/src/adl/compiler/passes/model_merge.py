"""ModelMergePass — 合并 Model 默认值与 Instance 覆盖值。

输入：SymbolResolvePass 生成的 MIR（含指向 Model 的指针）。
输出：每个 ResolvedInstanceIR 的 fields/overrides/resolved_data 已合并，
      non-overridable 字段被保护，Schema 校验已执行。
"""

from __future__ import annotations

from typing import Any

from adl.diagnostics import Diagnostic, Location, Severity
from adl.models.base import get_non_overridable_fields
from adl.project.loader import _flatten

from ..hir import InstanceUnit
from ..mir import MIRValue, ResolvedCompilation, ResolvedInstanceIR, ResolvedModelIR
from ..pass_manager import Pass, PassContext, PassResult, PassStage


class ModelMergePass(Pass):
    """合并 Model + Instance，执行 non-overridable 检查与 Schema 校验。"""

    name = "model-merge"
    stage = PassStage.MIR
    description = "合并 Model 默认值与 Instance 覆盖值并校验"

    def run(self, ctx: PassContext) -> PassResult:
        result = PassResult()
        resolved: ResolvedCompilation | None = ctx.resolved
        if resolved is None:
            ctx.emit(
                Diagnostic(
                    severity=Severity.ERROR,
                    message="model-merge: MIR 为空，需要先运行 symbol-resolve",
                    location=Location(uri=str(ctx.root)),
                    code="MIR-002",
                    source="adl.compiler.model_merge",
                )
            )
            return result

        merger = _ModelMerger(resolved)
        merger.run()
        ctx.diagnostics.extend(merger.diagnostics)
        result.modified = True
        return result


class _ModelMerger:
    def __init__(self, resolved: ResolvedCompilation) -> None:
        self.resolved = resolved
        self.diagnostics: list[Diagnostic] = []

    def run(self) -> None:
        for inst in self.resolved.resolved_instances.values():
            self._merge_instance(inst)

    def _merge_instance(self, inst: ResolvedInstanceIR) -> None:
        hir_inst: InstanceUnit | None = self._find_hir_instance(inst.id)

        # 1. 收集 Model 默认值
        model_defaults: dict[str, Any] = {}
        if inst.model is not None:
            model_defaults = self._mir_fields_to_dict(inst.model.fields)

        # 2. 收集 Instance 覆盖值
        overrides = self._mir_fields_to_dict(inst.fields)
        overrides.pop("model", None)
        overrides.pop("family", None)

        # 3. Non-overridable 检查
        family_cls = inst.family.pydantic_model if inst.family else None
        if family_cls is not None:
            non_overridable = get_non_overridable_fields(family_cls)
            for field_name in sorted(non_overridable):
                if field_name in overrides:
                    self._emit(
                        inst,
                        "SCHEMA-002",
                        f"Instance '{inst.id}' 覆盖了不可覆盖字段 '{field_name}'",
                    )
                    del overrides[field_name]

        # 记录原始覆盖值
        inst.overrides = {k: MIRValue.literal(v) for k, v in overrides.items()}

        # 4. 合并并扁平化
        merged = _flatten(
            {**model_defaults, **overrides},
            preserve_keys={"assets", "tags", "shape", "kinematics", "load_capacity"},
        )
        merged["id"] = inst.id

        # 5. Schema 校验
        if family_cls is not None:
            try:
                from pydantic import ValidationError

                validated = family_cls.model_validate(merged)
                resolved_dict = _flatten(
                    validated.model_dump(),
                    preserve_keys={"assets", "tags", "shape", "kinematics", "load_capacity"},
                )
                inst.resolved_data = resolved_dict
            except ValidationError as exc:
                inst.validation_error = str(exc)
                inst.family = None  # type: ignore[assignment]
                inst.resolved_data = _flatten(overrides)
                inst.resolved_data["id"] = inst.id
                self._emit(
                    inst,
                    "SCHEMA-001",
                    f"Instance '{inst.id}' Schema 校验失败: {exc}",
                )
        else:
            inst.resolved_data = merged

        # 6. 把合并后的字段存回 fields（供后续 pass / BackCompatEmit 使用）
        inst.fields = {k: MIRValue.literal(v) for k, v in inst.resolved_data.items()}

    def _find_hir_instance(self, instance_id: str) -> InstanceUnit | None:
        return self.resolved.hir.instances.get(instance_id)

    def _mir_fields_to_dict(self, fields: dict[str, MIRValue]) -> dict[str, Any]:
        return {k: self._mir_value_to_python(v) for k, v in fields.items()}

    def _mir_value_to_python(self, val: MIRValue) -> Any:
        if val.kind.value == "literal":
            return val.data
        if val.kind.value == "list":
            return [self._mir_value_to_python(item) for item in (val.data or [])]
        if val.kind.value == "mapping":
            return {k: self._mir_value_to_python(v) for k, v in (val.data or {}).items()}
        if val.kind.value.endswith("_ptr"):
            return val.data
        return val.data

    def _emit(self, inst: ResolvedInstanceIR, code: str, message: str) -> None:
        self.diagnostics.append(
            Diagnostic(
                severity=Severity.ERROR,
                message=message,
                location=Location(uri=str(inst.source) if inst.source else ""),
                code=code,
                source="adl.compiler.model_merge",
            )
        )
