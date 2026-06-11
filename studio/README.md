# Piki Studio

> **Piki Studio** 是面向工程设计工程师的浏览器端可视化 IDE。
>
> 用文本定义工程对象，用规则检查设计合理性，用 Studio 直观预览三维布局。

---

## 快速开始

```bash
# 安装依赖
npm install

# 开发模式
npm run dev

# 构建生产包
npm run build

# 预览生产构建
npm run preview
```

打开浏览器访问 `http://localhost:3000`，点击"打开项目"按钮选择本地 piki 项目目录。

---

## 产品文档

- **[PRD.md](PRD.md)** — 产品需求文档：定位、功能矩阵、里程碑
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — 架构设计：模块划分、数据流、接口契约

---

## 项目结构

```
viewer/
├── src/
│   ├── main.ts                    # 入口：挂载 App
│   ├── app/
│   │   └── App.ts                 # Shell：依赖注入 + 布局编排 + 事件协调
│   ├── presentation/              # 展示层（UI 组件）
│   │   ├── Toolbar.ts             # 顶部工具栏
│   │   ├── SceneTree.ts           # 左侧场景树
│   │   ├── Viewport.ts            # 中央 3D 视口
│   │   ├── PropertiesPanel.ts     # 右侧属性面板
│   │   └── StatusBar.ts           # 底部状态栏
│   ├── core/                      # 业务逻辑层（纯 JS，无 DOM 依赖）
│   │   ├── project/
│   │   │   └── ProjectService.ts  # 项目加载、扫描、解析
│   │   ├── scene/
│   │   │   └── SceneService.ts    # 场景对象管理、构建
│   │   ├── selection/
│   │   │   └── SelectionService.ts # 选中状态管理、双向同步
│   │   └── check/
│   │       └── CheckService.ts    # 检查结果加载、统计（预留）
│   ├── infrastructure/            # 基础设施层（封装外部依赖）
│   │   ├── fs/
│   │   │   └── FileSystem.ts      # File System Access API 封装
│   │   ├── parsers/
│   │   │   ├── YamlParser.ts      # YAML 文本解析
│   │   │   └── UsdaParser.ts      # USDA 文本解析
│   │   └── renderer/
│   │       └── ThreeRenderer.ts   # Three.js 渲染器封装
│   ├── types/
│   │   └── index.ts               # 全局共享类型
│   └── utils/
│       └── index.ts               # 通用工具函数
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── PRD.md
└── ARCHITECTURE.md
```

---

## 架构原则

```
Presentation ──depends on──▶ Core
      │                          │
      └──────────────────────────┘
              (App 协调两者)

Core ──depends on──▶ Infrastructure (via interfaces)

Infrastructure ──depends on──▶ External APIs (Three.js, File System Access)
```

**禁止的依赖方向：**

- ❌ Core Layer 不能依赖 Presentation Layer
- ❌ Infrastructure Layer 不能依赖 Core Layer
- ❌ Presentation Layer 不能直接调用 Infrastructure Layer

---

## 技术栈

| 层面 | 技术 | 说明 |
|---|---|---|
| 语言 | TypeScript | 类型安全 |
| 构建 | Vite | 快速，原生 ESM |
| 3D 渲染 | Three.js | 成熟，社区大 |
| USDA 解析 | 自研文本解析器 | 轻量，无需 WASM |
| 文件系统 | File System Access API | 浏览器原生 |

---

## 浏览器兼容性

| 浏览器 | 支持级别 |
|---|---|
| Chrome / Edge | ✅ 完全支持 |
| Firefox | ✅ 完全支持 |
| Safari | ⚠️ 有限支持（File System Access API） |

---

## 与 piki CLI 的关系

| 场景 | CLI | Studio |
|---|---|---|
| 运行检查 | `piki check` | 未来集成 |
| 生成 USD | `piki generate usd-scene` | 读取 scene.usda |
| 查看 3D | ❌ | ✅ 打开项目即看 |
| 编辑 YAML | VS Code / Vim | 未来支持 |

Studio 是 CLI 的**可视化补充**，不是替代。设计的源头仍然是文本。
