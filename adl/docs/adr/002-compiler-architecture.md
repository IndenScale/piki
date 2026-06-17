# ADL-002：ADL 编译器架构设计

> 状态：设计阶段
> 日期：2026-06-17
> 前置：ADL-001

## 一、目标

将 ADL 从 "YAML loader + dict merger + validator" 重构为完整的工程设计编译器。编译管线：

```
YAML/TOML 源文件
     │
     ▼
┌─────────────────────────────────────────────┐
│                  FRONTEND                   │
│                                             │
│  Lexer → Parser → AST                       │
│  (YAML → 语法树，保留源码位置)               │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│                  MIDDLE-END                 │
│                                             │
│  AST → HIR → SymbolTable → MIR              │
│  (语义分析、符号消解、类型检查、合并消解)     │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│               PASS PIPELINE                 │
│                                             │
│  PassManager: 注册、依赖、并行调度           │
│  Pass 在 HIR/MIR 上运行                     │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│                 BACKEND                     │
│                                             │
│  MIR → Project (当前 API 兼容)              │
│  MIR → diagnostics / report                 │
│  MIR → USD / glTF / BOM / ...               │
└─────────────────────────────────────────────┘
```

## 二、IR 层级设计

### 2.1 AST（抽象语法树）— 源码层

AST 是 YAML 文件的直接结构化表示，一个 YAML 文件 = 一个 `SourceFile` AST 节点。

```python
@dataclass
class Span:
    """源码位置：文件 + 起止行列。"""
    source: Path
    start_line: int
    start_col: int
    end_line: int
    end_col: int

@dataclass
class SourceFile:
    """一个 YAML 源文件的 AST 根节点。"""
    path: Path
    kind: FileKind  # INSTANCE | MODEL | CATALOG | LAYOUT | MATE | CONFIG | CONNECTION | GRID
    declarations: list[Declaration]  # 顶层声明列表
    span: Span

class FileKind(Enum):
    INSTANCE = "instance"
    MODEL = "model"
    CATALOG = "catalog"
    LAYOUT = "layout"
    MATE = "mate"
    CONFIG = "config"      # piki.toml
    CONNECTION = "connection"
    GRID = "grid"

@dataclass
class Declaration:
    """AST 中的一条顶层声明。"""
    name: str                # 标识符
    kind: DeclKind
    fields: list[FieldDecl]  # 键值对列表
    span: Span

class DeclKind(Enum):
    INSTANCE = "instance"
    MODEL = "model"
    CATALOG_ENTRY = "catalog_entry"
    LAYOUT_ENTRY = "layout_entry"
    MATE_SPEC = "mate_spec"
    CONNECTION = "connection"
    GRID_DEF = "grid_def"
    CONTEXT_DEF = "context_def"

@dataclass
class FieldDecl:
    """声明中的一个字段。"""
    key: str
    value: Value
    span: Span

# Value 类型
Value = (
    ScalarValue       # str, int, float, bool, null
    | ListValue       # list[Value]
    | MappingValue    # dict[str, Value]
    | ReferenceValue  # 引用：instance_id, instance_id/interface_id, model_id, catalog_id
)
```

**AST 的特性：**
- 一棵树对应一个 YAML 文件，不做任何语义分析
- 每个节点携带 `Span`，支持精确的源码定位
- YAML 别名/锚点在解析时展开，但保留原始锚点名以便诊断
- YAML 多文档文件每个文档为独立的 `SourceFile`

### 2.2 HIR（高级中间表示）— 语义层

HIR 是语义分析的结果：命名空间已建立、Family 类型已知、引用已记录（但未消解）。

```
SourceFile (AST) × N
       │
       │  Lowering Pass
       ▼
Compilation (HIR 根)
  ├── namespaces: dict[str, Namespace]
  │     ├── ""           (root)
  │     ├── "child-proj" (嵌套项目)
  │     └── "ext/alias"  (外部项目)
  ├── semantic_units: list[SemanticUnit]
  │     ├── InstanceUnit
  │     ├── ModelUnit
  │     ├── CatalogUnit
  │     ├── LayoutUnit
  │     ├── MateUnit
  │     └── GridUnit
  ├── symbol_table: SymbolTable
  └── diagnostics: list[Diagnostic]
```

```python
@dataclass
class Compilation:
    """一次编译的 HIR 根节点。"""
    root: Path
    namespaces: dict[str, Namespace]
    units: dict[str, SemanticUnit]        # unit_id → SemanticUnit
    symbol_table: SymbolTable
    config: dict[str, Any]
    diagnostics: list[Diagnostic]
    type_system: TypeSystem

@dataclass
class Namespace:
    """命名空间：对应一个项目（根/子/外部）。"""
    id: str                              # "" (root), "child-proj", "ext:alias"
    root: Path
    parent: str | None                    # 父命名空间 id
    children: list[str]
    is_external: bool

# --- Semantic Units ---

@dataclass
class InstanceUnit:
    """Instance 声明的语义节点（HIR）。"""
    id: str
    namespace: str
    family_ref: SymbolRef               # 指向 Family 的未消解引用
    model_ref: SymbolRef | None         # 指向 Model 的未消解引用
    fields: dict[str, HIRValue]         # 扁平化字段
    interfaces: list[InterfaceUnit]
    footprints: list[FootprintUnit]
    tags: dict[str, str]
    span: Span
    ast_node: Declaration               # 反向引用 AST

@dataclass
class ModelUnit:
    """Model 声明的语义节点（HIR）。"""
    id: str
    namespace: str
    family_ref: SymbolRef
    fields: dict[str, HIRValue]
    span: Span

@dataclass
class LayoutUnit:
    """Layout 声明的语义节点（HIR）。"""
    namespace: str
    entries: list[LayoutEntryUnit]
    span: Span

@dataclass
class LayoutEntryUnit:
    instance_ref: SymbolRef
    rack_ref: SymbolRef | None
    position_u: int | None
    pdu_ref: SymbolRef | None
    parent_ref: SymbolRef | None
    grid_ref: SymbolRef | None
    grid_position: tuple[str, str] | None
    absolute_position: Vec3 | None
    transform: Transform | None
    span: Span

@dataclass
class MateUnit:
    """Mate 声明的语义节点（HIR）。"""
    id: str
    namespace: str
    mate_type: str
    parent_ref: SymbolRef
    child_ref: SymbolRef
    constraints: list[MateConstraintUnit]
    interface_pairings: list[InterfacePairingUnit]
    span: Span

@dataclass
class CatalogUnit:
    id: str
    namespace: str
    family: str
    model_ref: SymbolRef | None
    source: str                        # project | parent | enterprise | public
    fields: dict[str, HIRValue]
    span: Span

@dataclass
class InterfaceUnit:
    id: str
    interface_type: str
    active_type: str | None
    direction: str
    specs: dict[str, Any]
    span: Span

@dataclass
class FootprintUnit:
    id: str
    footprint_type: str
    pins: list[InterfaceUnit]
    span: Span

# --- 符号引用 ---

@dataclass
class SymbolRef:
    """HIR 中的符号引用（未消解）。"""
    text: str                           # 原始引用文本，如 "SRV-01/eth0"
    kind: SymbolRefKind
    span: Span

class SymbolRefKind(Enum):
    INSTANCE = "instance"
    INSTANCE_INTERFACE = "instance_interface"    # "SRV-01/eth0"
    MODEL = "model"
    FAMILY = "family"
    CATALOG = "catalog"
    MATE_TYPE = "mate_type"
    GRID = "grid"
    RACK = "rack"
    PDU = "pdu"

# --- HIR 值 ---

@dataclass
class HIRValue:
    """HIR 中的值：可以是字面量、引用、或嵌套结构。"""
    data: Any
    kind: HIRValueKind
    span: Span

class HIRValueKind(Enum):
    LITERAL = "literal"
    REFERENCE = "reference"             # SymbolRef
    LIST = "list"
    MAPPING = "mapping"
```

### 2.3 MIR（中级中间表示）— 消解层

MIR 是所有引用已消解、Model 已合并、类型已检查的结果。

```python
@dataclass
class ResolvedCompilation:
    """MIR 根节点。"""
    hir: Compilation                    # 反向引用 HIR
    resolved_instances: dict[str, ResolvedInstanceIR]
    resolved_layouts: dict[str, ResolvedLayoutIR]
    resolved_mates: dict[str, ResolvedMateIR]
    resolved_catalogs: dict[str, ResolvedCatalogIR]
    resolved_grids: dict[str, ResolvedGridIR]
    diagnostics: list[Diagnostic]

@dataclass
class ResolvedInstanceIR:
    """消解后的 Instance（MIR）。"""
    id: str
    fqid: str                          # 全限定 ID
    namespace: str
    family: FamilyDef                  # 已消解到 Family 对象
    model: ModelUnit | None            # 已消解到 Model 对象
    fields: dict[str, MIRValue]        # Instance + Model 合并后的完整字段集
    overrides: dict[str, MIRValue]     # 仅 Instance 覆盖的字段
    non_overridable_violations: list[Diagnostic]
    interfaces: list[ResolvedInterfaceIR]
    catalog: ResolvedCatalogIR | None
    tags: dict[str, str]
    bbox: BBox | None
    source_span: Span

@dataclass
class MIRValue:
    """MIR 中的值：所有引用已消解为指针或字面量。"""
    data: Any
    kind: MIRValueKind
    span: Span

class MIRValueKind(Enum):
    LITERAL = "literal"
    INSTANCE_PTR = "instance_ptr"       # → ResolvedInstanceIR
    INTERFACE_PTR = "interface_ptr"     # → ResolvedInterfaceIR
    MODEL_PTR = "model_ptr"
    CATALOG_PTR = "catalog_ptr"
    LIST = "list"
    MAPPING = "mapping"
```

### 2.4 符号表（SymbolTable）

```python
@dataclass
class SymbolTable:
    """多层符号表：命名空间 → 符号名 → 符号条目。"""
    scopes: dict[str, Scope]           # namespace_id → Scope
    resolution_cache: dict[tuple[str, str, str], Any]  # (from_ns, name, kind) → resolved

@dataclass
class Scope:
    """一个命名空间的作用域。"""
    namespace: str
    symbols: dict[str, Symbol]         # name → Symbol
    parent_scope: str | None           # 父命名空间 id
    children: list[str]

@dataclass
class Symbol:
    name: str
    kind: SymbolKind
    namespace: str
    definition: SemanticUnit           # 指向 HIR 中的定义单元
    is_public: bool                    # 是否对子命名空间可见
    span: Span

class SymbolKind(Enum):
    INSTANCE = "instance"
    MODEL = "model"
    FAMILY = "family"
    CATALOG = "catalog"
    LAYOUT = "layout"
    MATE = "mate"
    GRID = "grid"
    INTERFACE = "interface"
    NAMESPACE = "namespace"
```

## 三、编译 Pass Pipeline

### 3.1 Pass 框架

```python
class Pass(ABC):
    """单个编译 Pass 的抽象基类。"""

    name: str                          # Pass 标识
    description: str
    runs_on: PassStage                 # AST | HIR | MIR

    @abstractmethod
    def run(self, ctx: PassContext) -> PassResult:
        ...

class PassStage(Enum):
    AST = "ast"
    HIR = "hir"
    MIR = "mir"

@dataclass
class PassContext:
    compilation: Compilation | None    # HIR 阶段可用
    resolved: ResolvedCompilation | None  # MIR 阶段可用
    source_files: dict[Path, SourceFile]  # AST 阶段可用
    diagnostics: list[Diagnostic]
    config: dict[str, Any]

@dataclass
class PassResult:
    success: bool
    diagnostics: list[Diagnostic]
    modified: bool                     # 是否修改了 IR
    artifacts: dict[str, Any]          # pass 产出的工件

class PassManager:
    """Pass 管理器：注册、依赖排序、调度执行。"""

    def __init__(self):
        self._passes: list[Pass] = []
        self._deps: dict[str, set[str]] = {}    # pass_name → {dependencies}
        self._stage_order = [PassStage.AST, PassStage.HIR, PassStage.MIR]

    def register(self, p: Pass, *, after: list[str] | None = None) -> None:
        """注册一个 Pass，可选指定依赖。"""
        ...

    def run(self, ctx: PassContext, *, up_to: PassStage | None = None) -> PassContext:
        """按依赖顺序运行所有 Pass，可选停在某个 stage。"""
        ...
```

### 3.2 标准 Pass 列表

#### AST 阶段（解析）

| Pass | 描述 |
|------|------|
| `YAMLParsePass` | 解析所有 YAML 文件为 AST |
| `TOMLParsePass` | 解析 piki.toml |
| `ASTValidatePass` | AST 结构合法性（必填字段、ID 格式） |

#### HIR 阶段（Lowering + 语义分析）

| Pass | 描述 |
|------|------|
| `LoweringPass` | AST → HIR：构建 SemanticUnit，填充 SymbolTable（定义端） |
| `NamespaceBuildPass` | 构建命名空间层级（根/子项目/外部） |
| `FamilyResolvePass` | 解析所有 Family 引用（TypeSystem 查找） |
| `FieldFlattenPass` | 扁平化嵌套字段（physical.height_u → physical.height_u） |
| `NonOverridableMarkPass` | 标记 non_overridable 字段 |
| `InterfaceCollectPass` | 收集并规范化 Interface/Footprint 声明 |
| `TagSchemaPass` | Tag 键白名单校验 |

#### MIR 阶段（消解 + 合并 + 类型检查）

| Pass | 描述 |
|------|------|
| `SymbolResolvePass` | 消解所有 SymbolRef → 具体符号（跨命名空间） |
| `ModelMergePass` | Model.defaults + Instance.overrides → ResolvedInstance |
| `NonOverridableCheckPass` | 检查 Instance 是否覆盖了 non_overridable 字段 |
| `LayoutResolvePass` | 消解 Layout 中的 Instance/Rack/PDU/Grid 引用 |
| `LayoutCycleCheckPass` | 检测 Layout parent 链中的环 |
| `LayoutTransformPass` | 计算每个 Instance 的全局 Transform（含 Mate 约束） |
| `MateResolvePass` | 消解 Mate 中的 parent/child 引用 |
| `MateConstraintPass` | 验证 Mate 约束 |
| `InterfaceCompatPass` | 接口兼容性检查（类型兼容性矩阵） |
| `CatalogResolvePass` | 消解 Catalog 引用 |
| `CatalogServiceMethodPass` | 验证 ComponentCatalog 引用的 service_method |
| `FQIDDedupPass` | 检查全限定 ID 冲突 |
| `BBoxComputePass` | 为每个 Instance 计算包围盒 |
| `SpatialCollisionPass` | AABB 碰撞检测（L4） |
| `BackCompatEmitPass` | 从 MIR 生成 Project 对象（向后兼容当前 API） |

## 四、类型系统（TypeSystem）

类型系统从 `TypeRegistry`（Family 名 → pydantic 类的简单映射）升级为完整的类型基础设施。

```python
@dataclass
class TypeSystem:
    """ADL 类型系统。"""

    families: dict[str, FamilyDef]
    mate_types: dict[str, MateTypeDef]
    interface_types: dict[str, InterfaceTypeDef]
    subtype_relations: list[SubtypeRelation]
    compatibility_matrix: dict[tuple[str, str], CompatibilityResult]

@dataclass
class FamilyDef:
    """Family 类型定义。"""
    name: str
    fields: dict[str, FieldDef]
    non_overridable: set[str]
    base_families: list[str]              # 继承的 Family
    pydantic_model: type[BaseModel] | None

@dataclass
class FieldDef:
    name: str
    type: TypeExpr                       # 类型表达式
    required: bool
    default: Any
    non_overridable: bool

# 类型表达式：支持基本类型、联合、泛型
TypeExpr = (
    PrimitiveType                       # str, int, float, bool
    | EnumType                          # 枚举
    | UnionType                         # 联合类型
    | ListType                          # list[T]
    | OptionalType                      # T | None
    | RefType                           # 引用其他 Family
    | ConstrainedType                   # 带约束的类型（如 int >= 0）
)

@dataclass
class InterfaceTypeDef:
    name: str
    compatible_with: set[str]            # 兼容的接口类型
    cable_types: list[str]               # 可用的线缆类型

@dataclass
class MateTypeDef:
    name: str
    default_constraints: list[MateConstraint]
    applicable_parents: set[str]         # 可作为 parent 的 Family 集合
    applicable_children: set[str]        # 可作为 child 的 Family 集合
```

## 五、诊断系统升级

### 5.1 诊断绑定到 IR 节点

```python
@dataclass
class Diagnostic:
    severity: Severity
    message: str
    code: str
    source: str                          # pass 名或 "adl.validation"
    span: Span                           # 精确源码位置（不再只是文件级）
    related: list[Span]                  # 相关位置（如"定义处"）
    hint: str | None                     # 修复建议
```

### 5.2 错误恢复

- AST 解析错误：跳过当前声明，继续解析后续声明
- HIR Lowering 错误：标记单元为 `_invalid`，继续编译
- MIR 消解错误：引用消解失败时生成 `UnresolvedRef` 占位符，继续后续 Pass

### 5.3 诊断抑制

```python
# piki.toml
[diagnostics]
# 全局抑制
suppress = ["MATE-001"]

# 按文件/行抑制（YAML 注释）
# instance.yaml:
# id: SRV-01  # adl:suppress=TAGS-001
```

## 六、迁移路径

### Phase 1：基础设施（不影响现有 API）

1. 实现 `Span`、`SymbolTable`、`PassManager` 基础类
2. 实现 AST 层：`YAMLParsePass` → `SourceFile`
3. 实现 `TypeSystem`（从现有 `TypeRegistry` 构建，提供相同语义）
4. 现有 `ProjectLoader` 和 `Project` API 保持不变

### Phase 2：HIR 引入

1. 实现 Lowering：AST → HIR
2. 实现 HIR Pass：Family 解析、字段扁平化、Interface 收集
3. 添加 `Compilation.compile()` 作为新入口点
4. `ProjectLoader` 内部切换到 Pass 管线，`Project` 通过 `BackCompatEmitPass` 输出

### Phase 3：MIR 引入

1. 实现 MIR 消解 Pass：符号消解、Model 合并、Layout 消解
2. 将 `ADLValidator` 的检查逻辑迁移到 MIR Pass
3. `ResolvedCompilation` 成为新的内部 IR

### Phase 4：清理

1. 移除旧的 `ProjectLoader` 单体逻辑
2. piki 直接消费 `ResolvedCompilation`（或通过 `BackCompatEmitPass`）
3. 增量编译支持

## 七、增量编译

```python
class IncrementalCache:
    """增量编译缓存：记录文件→产出的映射。"""

    def __init__(self):
        self.file_hashes: dict[Path, str] = {}
        self.file_outputs: dict[Path, set[str]] = {}     # file → 受影响的 unit_ids
        self.unit_deps: dict[str, set[str]] = {}           # unit_id → 依赖的 unit_ids

    def invalidate(self, changed_files: set[Path]) -> set[str]:
        """返回所有需要重新编译的 unit_ids。"""
        ...

    def update(self, file: Path, hash: str, outputs: set[str]) -> None:
        ...
```

## 八、与 piki 的集成

```python
# 新入口（与旧 API 并行）
compilation = Compilation.compile(
    root=Path("my_project"),
    type_system=type_system,
    extra_model_dirs=[...],
    extra_catalog_dirs=[...],
    stage=PassStage.MIR,     # 编译到 MIR
)

# 向后兼容：从 MIR 生成 Project
project = BackCompatEmitPass().run(compilation.resolved).project

# 直接消费 MIR（未来）
for inst in compilation.resolved.resolved_instances.values():
    print(inst.fqid, inst.family.name, inst.bbox)
```

## 九、开放设计问题

1. **Family 定义是否应独立于 pydantic？** 当前 Family 是 pydantic `BaseModel` 子类。编译器可以继续用 pydantic 做运行时校验，但 FamilyDef 应该在 TypeSystem 中有独立表示，使得类型检查可以在不实例化 pydantic 对象的情况下进行。

2. **Connection 是否应进入 MIR？** ADR-005 将 Connection 建模为独立 Instance。在 MIR 中，Connection 是否应作为一等概念（类似 Mate 的消解链路），还是保持为普通 Instance？

3. **Pass 并行度？** Namespace 级的 Pass（如 Lowering、符号消解）天然可并行。PassManager 应支持命名空间级并行。

4. **IR 序列化？** MIR 是否应支持序列化（如 msgpack）以支持增量编译的缓存持久化？
