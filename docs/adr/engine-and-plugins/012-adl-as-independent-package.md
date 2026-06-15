# ADR-012：ADL 作为独立 Python 包

**状态**：✅ 已实现  
**日期**：2026-06-15  
**范围**：代码库结构、PyPI 包拆分、piki 与 ADL 的架构边界

---

## 背景

piki 最初把「声明式建模语言」与「规则/生成器编排框架」放在同一个 Python 包里。随着模型层（Instance、Model、Mate、Layout、Catalog）越来越厚，两个关注点开始互相拉扯：

- 模型层需要稳定的解析、验证、诊断语义，适合独立演进；
- piki 需要频繁试验插件发现、规则执行、报告格式，不应被 YAML 合并细节拖累。

同时，ADL 本身具有通用性：任何需要声明式工程建模的场景都可以直接使用它，而不一定需要 piki 的插件框架。

## 决策

1. **ADL 拆分为独立的 `adl` PyPI 包**，拥有自己的 `pyproject.toml` 和发布周期。
2. **仓库暂时不分离**：`adl/` 子目录与 `src/piki/` 共存于同一仓库，便于同步修改；未来可随时迁出。
3. **piki 退化为纯编排器**：
   - 不再保留 `piki.core.models` / `piki.core.parsing` 兼容存根；
   - 所有模型与解析能力直接来自 `adl`；
   - piki 的核心职责是：插件发现 → 类型注册 → ADL 加载 → ADL 验证 → 规则/生成器执行 → 报告格式化。

## 架构边界

```text
┌─────────────────────────────────────────────┐
│                   piki                        │
│  插件发现 → ADL 加载 → 规则/生成器 → 报告     │
└─────────────────┬───────────────────────────┘
                  │ depends on
                  ▼
┌─────────────────────────────────────────────┐
│                    adl                        │
│  parsing → project → validation → diagnostics │
└─────────────────────────────────────────────┘
```

| 职责 | 归属 | 说明 |
|------|------|------|
| YAML / TOML 解析、源码位置追踪 | `adl.parsing` | 所有解析工具 |
| Instance / Model / Mate / Layout 等模型 | `adl.models` | 内存模型与基本操作 |
| 类型注册表、MateType 扩展 | `adl.types` | 插件可扩展类型 |
| 项目加载、子项目合并 | `adl.project.ProjectLoader` | 输出 `adl.project.Project` |
| L2 通用验证（引用、FK、Mate、Catalog、FQID、Tag Schema） | `adl.validation.ADLValidator` | 生成 `Diagnostic` |
| Diagnostic 基础设施 | `adl.diagnostics` | LSP-compatible 诊断格式 |
| 插件发现、规则执行、生成器编排 | `piki.core` | 框架层 |
| 报告格式化（human/json/junit/markdown） | `piki.core.reporting` | 消费 ADL 与规则输出 |

## 影响

- **包依赖**：`piki` 依赖 `adl`；`adl` 不依赖 `piki`。
- **导入路径**：内部代码与测试统一使用 `from adl import ...` / `from adl.models import ...` / `from adl.diagnostics import ...`。
- **向后兼容**：删除 `piki.core.models` 与 `piki.core.parsing` 兼容层。任何外部代码若依赖这些路径，需迁移到 `adl`。
- **测试基线**：`440 passed, 6 skipped` 保持通过。

## 相关文件

- `adl/pyproject.toml`
- `adl/src/adl/`
- `src/piki/core/project.py`
- `src/piki/core/engine/registry.py`
- `src/piki/core/engine/context.py`
- `docs/pitch/03-adl.md`
- `docs/reference/06-api.md`
