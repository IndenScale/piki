# ADL — Assembly Definition Language

ADL（装配体定义语言）是一套声明式工程数据建模与验证运行时。它负责把分散的 YAML 文本加载成结构化的内存模型，并产出自洽性诊断（Diagnostics）。

## 定位

- **ADL**：声明式建模语言 + 加载器 + 验证器
- **piki**：基于 ADL 的工程框架，负责插件发现、规则执行、报告格式化

ADL 可以独立发布为 `adl` PyPI 包；piki 通过依赖使用它，并作为编排器存在。

## 安装

```bash
pip install adl
```

## 核心模块

| 模块 | 职责 |
|------|------|
| `adl.models` | 领域模型：Instance, Model, MateSpec, ResolvedInstance, Catalog 等 |
| `adl.parsing` | YAML 解析与 YAML 树包装 |
| `adl.project` | 项目加载器 `ProjectLoader`，输出 `Project` |
| `adl.types` | 类型注册表 `TypeRegistry`、MateType 等可扩展类型 |
| `adl.validation` | ADL 层验证器 `ADLValidator`，生成诊断 |
| `adl.diagnostics` | 诊断消息基础设施 |

## 快速使用

```python
from pathlib import Path
from adl import TypeRegistry, ProjectLoader, ADLValidator

reg = TypeRegistry()
loader = ProjectLoader(Path("my_project"), reg)
project = loader.load()

diagnostics = ADLValidator(project).validate()
for d in diagnostics:
    print(d)
```

## 与 piki 的关系

```
piki (framework)
  └─ depends on adl
        └─ ProjectLoader / ADLValidator / TypeRegistry
```

piki 插件通过 `register_types()` 向 `TypeRegistry` 注册领域类型；piki 在加载阶段调用 ADL；
验证阶段把 ADL 诊断与插件规则诊断合并为统一报告。
