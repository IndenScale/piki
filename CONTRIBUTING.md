# 贡献指南

感谢你对 piki 的兴趣！本文档帮助你快速搭建开发环境并参与贡献。

## 开发环境搭建

### 前置要求

- Python 3.11+
- Git

### 从源码安装

```bash
# 克隆仓库
git clone https://github.com/indenscale/piki.git
cd piki

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装开发依赖（包含 pytest、ruff、mypy）
pip install -e ".[dev]"
```

### 验证安装

```bash
# 检查 piki 是否可运行
piki --version

# 运行 piki 框架测试
pytest

# 运行 ADL 包测试
cd adl && pytest

# 运行测试并生成覆盖率报告
pytest --cov=piki --cov-report=term-missing
```

---

## 项目结构

```
piki/                          # monorepo 根目录
├── adl/                       # 独立的 ADL（Assembly Definition Language）Python 包
│   ├── src/adl/               #   解析、模型、验证、几何运行时
│   ├── tests/                 #   ADL 自身测试
│   ├── docs/                  #   ADL 技术规范与架构决策
│   └── pyproject.toml         #   ADL 包配置
├── src/piki/                  # piki 编排框架
│   ├── cli.py                 # CLI 入口
│   ├── commands/              # CLI 子命令实现
│   ├── core/                  # 框架内核
│   │   ├── engine/            # 规则引擎、查询、注册表
│   │   ├── models/            # 数据模型（Diagnostic 等）
│   │   ├── plugin.py          # 插件基类与发现
│   │   └── project.py         # piki 项目编排入口
│   ├── ext/                   # 扩展能力（如 CSG 几何）
│   └── extensions/            # 内置插件（telecom、datacenter 等）
├── tests/                     # piki 框架测试
├── docs/                      # piki 用户文档与理念文章
├── samples/                   # 示例项目
├── studio/                    # 浏览器端 3D 预览 IDE（可选）
├── pyproject.toml             # piki 包配置
└── README.md
```

piki 依赖 `adl` 包。开发时两者在同一仓库，但发布周期和文档相互独立。

---

## 代码规范

### 格式化与检查

```bash
# 代码格式化
ruff format src/ tests/

# 代码检查
ruff check src/ tests/

# 类型检查
mypy src/piki
```

### 代码风格

- 遵循 PEP 8
- 使用类型注解（Python 3.11+ 特性）
- 模块、类、公共函数必须有 docstring
- 使用 `from __future__ import annotations` 支持延迟类型评估

---

## 测试

### 运行测试

```bash
# piki 框架全部测试（在仓库根目录）
pytest

# ADL 包全部测试
pushd adl && pytest && popd

# 特定测试文件
pytest tests/test_cli.py

# 特定测试函数
pytest tests/test_cli.py::test_check_passes

# 带详细输出
pytest -v

# 失败时进入 pdb
pytest --pdb
```

### 编写测试

- 测试文件放在 `tests/` 目录
- 使用 `pytest` 框架
- E2E 测试使用临时目录和 `subprocess` 调用 CLI
- 单元测试直接导入模块测试

---

## 提交 PR

### 流程

1. **Fork 仓库** 并克隆到本地
2. **创建分支**：`git checkout -b feature/your-feature`
3. **编写代码** 并添加测试
4. **确保测试通过**：`pytest`
5. **确保代码规范**：`ruff check && ruff format --check`
6. **提交更改**：`git commit -m "feat: 描述"`
7. **推送到 Fork**：`git push origin feature/your-feature`
8. **创建 Pull Request**

### Commit 规范

使用 [Conventional Commits](https://www.conventionalcommits.org/)：

| 类型 | 说明 |
|------|------|
| `feat:` | 新功能 |
| `fix:` | 修复 bug |
| `docs:` | 文档更新 |
| `test:` | 测试相关 |
| `refactor:` | 重构（无功能变化） |
| `perf:` | 性能优化 |
| `chore:` | 构建/工具相关 |

**示例：**

```bash
git commit -m "feat: 添加 construction 插件支持"
git commit -m "fix: 修复 PDU 功率计算浮点精度问题"
git commit -m "docs: 补充 CLI 命令参考文档"
```

---

## 开发插件

如果你想为 piki 开发新插件：

1. 创建 `src/piki/extensions/your_plugin/` 目录
2. 继承 `piki.Plugin` 基类
3. 实现 `register_families`、`register_rules`、`register_generators`
4. 添加测试和文档
5. 提交 PR

详细指南：参考现有插件源码（`src/piki/extensions/telecom/plugin.py`、`src/piki/extensions/datacenter/plugin.py`）和 [docs/reference/06-api.md](docs/reference/06-api.md) 中的 API 说明。独立的插件开发指南待补充。

---

## 问题反馈

- **Bug 报告**：[GitHub Issues](https://github.com/indenscale/piki/issues)
- **功能建议**：[GitHub Issues](https://github.com/indenscale/piki/issues)
- **讨论**：[GitHub Discussions](https://github.com/indenscale/piki/discussions)

反馈时请提供：

- piki 版本（`piki --version`）
- Python 版本
- 操作系统
- 最小复现步骤

---

## 许可证

贡献即表示你同意将你的代码在 [MIT 许可证](LICENSE) 下发布。
