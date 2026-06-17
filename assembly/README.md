# Assembly — 典型装配体演示

本目录包含若干**正式的 piki 子项目**，用于演示 ADL 的装配体建模、几何引擎求解与浏览器可视化。

## 设计哲学

- **文本是真相源**：每个 demo 都是独立的 piki 项目，`piki.toml`、`models/`、`instances/`、`mates/`、`layouts/` 共同定义装配体。
- **ADL 几何引擎驱动**：位姿由 `adl.geometry.AssemblyBuilder` 根据 `Mate` 约束自动求解。
- **双输出**：`piki generate assembly-viewer` 同时产出：
  - `dist/scene.json` — 浏览器 viewer 加载的轻量场景
  - `dist/scene.usda` — OpenUSD 场景，可供 Omniverse / Blender 消费
- **通用浏览器查看器**：所有 demo 共享 `assembly/viewer/` 中的 Three.js 渲染器。

## 目录结构

```
assembly/
├── README.md
├── viewer/                    # 通用 Three.js 查看器
│   ├── index.html
│   ├── viewer.js
│   └── viewer.css
├── sfp28-module/              # piki 子项目：光模块插入交换机
│   ├── piki.toml
│   ├── models/
│   ├── instances/
│   ├── mates/
│   ├── layouts/
│   ├── dist/                  # 生成产物
│   ├── assembly.yaml          # 高阶说明（可选，供人阅读）
│   ├── index.legacy.html      # 旧手搓 demo（保留参考）
│   └── README.md
├── fire-extinguisher/         # 面面配合演示
├── fc-fiber-connector/        # 两阶段装配演示
└── ...
```

## 运行演示

```bash
cd assembly/sfp28-module
piki generate assembly-viewer

# 方式 1：本地 HTTP 服务（推荐，避免 file:// 跨域）
python -m http.server 8000 --directory dist
open http://localhost:8000

# 方式 2：直接打开（部分浏览器限制 JSON 加载）
open dist/index.html
```

## 添加新的装配体演示

1. 在本目录下新建子目录，例如 `assembly/my-assembly/`。
2. 创建 `piki.toml`：
   ```toml
   [project]
   name = "my-assembly"

   [plugins]
   enabled = ["assembly"]

   [generators]
   enabled = ["assembly-viewer"]
   ```
3. 创建 `models/` 定义部件型号，`instances/` 创建实例，`layouts/` 放置实例，`mates/` 定义配合。
4. 运行 `piki generate assembly-viewer`。

## 支持的几何原语

`AssemblyPartFamily` 的 `assets.usd.inline` 支持：

- `box`
- `cylinder`
- `sphere`
- `capsule`

未指定 `assets` 时，自动从 `width_mm/height_mm/depth_mm` 生成 Box 代理几何。

## 支持的 Mate 类型

| Mate 类型 | 说明 | 控件参数 |
|-----------|------|----------|
| `slot` | 槽配合，child 沿槽方向推入 | `t` |
| `face-on-face` / `face` | 面面贴合 | `u`, `v`, `theta_deg`, `distance` |

## 测试

```bash
# 单元测试
pytest tests/unit/test_assembly_builder.py -v

# 集成测试：验证所有 demo 能生成且通过 check
pytest tests/integration/test_assembly_demos.py -v
```
