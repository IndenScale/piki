# ADL-001：ADL 是否应该作为编译器设计？

> 状态：讨论中
> 日期：2026-06-17

## 问题

ADL 目前在概念上被类比为 "工程设计的 SQL"、"编译器的前端"，但实现上是一个 **YAML loader + dict merger + validator**，缺少编译器应有的基础设施。

当前架构：

```
YAML 文件 → SourceTrackedDict → _flatten() → _merge() → ResolvedInstance → dict.get() 查询
```

这不是编译，这是加载和合并。

## 缺失的编译基础设施

### 1. 没有符号表（Symbol Table）

`Project.instances` 是 `dict[str, ResolvedInstance]`，没有：

- **作用域层级** — 嵌套项目通过 `parent` 指针和 `find_instance()` 递归 `dict.get` 实现，没有词法作用域或命名空间栈
- **定义-使用链** — 无法追溯"这个引用解析到了哪个定义，以及谁引用了这个定义"
- **符号消解阶段** — 引用解析和加载混在一起，不是独立的 pass

### 2. 没有中间表示（IR）

YAML 直接合并成 `ResolvedInstance`（扁平字典 + pydantic wrapper），中间没有：

- **AST** — 没有语法树，`SourceTrackedDict` 只是给 dict 的 key 贴了行号，不是树结构
- **语义模型** — 没有独立于 YAML 语法的语义节点。Model、Instance、Layout 合并规则是硬编码的 Python 逻辑，不是 IR 上的变换
- **类型推导** — `TypeRegistry` 只是 Family 名到 pydantic 类的映射，没有泛型约束、子类型关系、类型推断

### 3. 没有 Pass Pipeline

`ProjectLoader.load()` 是单一大函数，硬编码调用顺序：

```python
def load(self):
    load_models_into(...)
    load_catalogs_into(...)
    load_layout_into(...)
    load_grids_into(...)
    load_instances(...)        # 内部调用 _resolve_instances()
    load_mates_into(...)
    load_children(...)
```

没有：

- Pass 注册机制
- 可组合的编译阶段
- 增量编译（改一个 YAML 需要全量 reload）
- Pass 之间的依赖图

### 4. 没有类型系统

当前"类型" = pydantic `BaseModel` 的 schema 校验。缺失：

- 类型兼容性关系（如 InterfaceType 的兼容性矩阵）
- 泛型约束（如 "`MateType<T>` 的两个 participant 必须是兼容类型"）
- 类型推导（Instance 不写 `family` 时，从 `model` 推导是硬编码的 `dict.get`，不是类型推导规则）
- 子类型 / LSP

### 5. 诊断基础设施薄弱

`ADLValidator` 返回扁平的 `list[Diagnostic]`：

- 没有错误恢复 — 一个 YAML 解析失败，整个实例跳过
- Source span 精度不足 — `Location` 是文件级，不是字符级 span
- 没有诊断去重 / 抑制机制
- 没有与编译阶段的绑定（哪个 pass 产生了哪个 diagnostic）

## 后果：表达能力受限

1. **跨文件静态分析不可行** — 引用解析是运行时 `dict.get`，无法做数据流分析
2. **复杂类型约束无法表达** — `SFP28 → QSFP28` 兼容性需要兼容性矩阵，当前靠规则硬编码
3. **增量编译不可行** — 全量加载是唯一路径
4. **IDE 集成受限于文件级诊断** — 无法做到字段级红色波浪线
5. **跨插件类型关系无法表达** — 两个插件的 Family 之间的关系只能靠运行时规则

## 讨论：需要什么样的编译器架构？

### 候选方案

**方案 A：保持现状，渐进增强**

- 在现有 dict 模型上加 pass manager
- 优点：改动小，兼容现有代码
- 缺点：dict 作为 IR 本质上是无结构的，pass 只能做 dict → dict 变换，表达能力天花板低

**方案 B：引入 AST → HIR → MIR 的多层 IR**

- YAML → AST（语法树，保留源码位置）
- AST → HIR（高级 IR：Family/Model/Instance/Layout 语义节点，符号表已建立）
- HIR → MIR（中级 IR：消解后的 resolved 实体，引用已消解为指针）
- Pass 在 HIR 和 MIR 上运行
- 优点：标准的编译器架构，每层有明确的语义级别
- 缺点：工程量大，需要重新设计整个加载管线

**方案 C：以符号表和 Pass Pipeline 为起点，IR 逐步引入**

- 第一阶段：引入 `SymbolTable` + `PassManager`，保留现有 dict 作为初级 IR
- 第二阶段：引入 HIR 层（语义节点），将 `ResolvedInstance` 的构建过程改为 HIR → MIR 变换
- 第三阶段：引入 AST 层（如果需要更精确的源码位置）
- 优点：渐进式，每一步都有可交付价值
- 缺点：中间状态可能不优雅

### 需要回答的设计问题

1. IR 的粒度应该是什么？以 Instance 为单元，还是以字段为单元？
2. 符号消解（name resolution）是否应该是独立的 pass？还是和加载合并？
3. Pass pipeline 是否需要支持并行？
4. 类型系统应该独立于 pydantic，还是建立在 pydantic 之上？
5. 诊断应该绑定到 IR 节点还是独立传输？

## 参考

- LLVM IR 设计：Module → Function → BasicBlock → Instruction 层级
- Roslyn（C# 编译器）：SyntaxTree → Compilation → SemanticModel
- Rust：AST → HIR → THIR → MIR → LLVM IR
- SysML v2：Kernel Modeling Language (KerML) 作为语义内核
