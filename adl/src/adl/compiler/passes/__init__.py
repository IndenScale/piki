"""内置编译 Pass 集合。

AST 阶段:
  - YAMLParsePass: 解析 YAML 文件为 AST
  - TOMLParsePass: 解析 piki.toml

HIR 阶段:
  - LoweringPass: AST → HIR
  - NamespaceBuildPass: 构建命名空间层级
  - FamilyResolvePass: 消解 Family 引用

MIR 阶段:
  - SymbolResolvePass: 消解所有引用
  - ModelMergePass: Model + Instance 合并
  - BackCompatEmitPass: MIR → Project (向后兼容)
"""

