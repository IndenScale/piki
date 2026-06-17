"""TOMLParsePass — piki.toml → config dict。"""

from __future__ import annotations

from adl.parsing.loaders import load_toml

from ..pass_manager import Pass, PassContext, PassResult, PassStage


class TOMLParsePass(Pass):
    """TOML 配置解析 Pass：加载 piki.toml 到 ctx.config。"""

    name = "toml-parse"
    stage = PassStage.AST
    description = "解析 piki.toml 配置"

    def run(self, ctx: PassContext) -> PassResult:
        result = PassResult()
        toml_path = ctx.root / "piki.toml"
        if toml_path.exists():
            try:
                config = load_toml(toml_path)
                ctx.config.update(config)
                result.modified = True
            except Exception as exc:
                from adl.diagnostics import Diagnostic, Location, Severity

                ctx.emit(
                    Diagnostic(
                        severity=Severity.ERROR,
                        message=f"piki.toml 解析失败: {exc}",
                        location=Location.from_path(toml_path),
                        code="PARSE-002",
                        source="adl.compiler.toml_parse",
                    )
                )
        return result
