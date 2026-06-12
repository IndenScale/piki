# Piki Studio — 架构设计文档

> 版本：0.1.0
> 状态：草案
> 最后更新：2026-06-11

---

## 1. 架构概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Presentation Layer                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐ │
│  │   Toolbar   │  │  SceneTree  │  │   Viewport  │  │ PropertiesPanel│ │
│  │   工具栏     │  │  场景树     │  │  3D 视口    │  │   属性面板      │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └───────┬────────┘ │
│         │                │                │                  │          │
│  ┌──────┴────────────────┴────────────────┴──────────────────┘          │
│  │                        App (Shell)                                    │
│  │              布局编排 + 组件生命周期 + 全局事件总线                      │
│  └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Core Layer (Business Logic)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐ │
│  │   Project   │  │   Scene     │  │  Selection  │  │    Check       │ │
│  │   Service   │  │   Service   │  │   Service   │  │   Service      │ │
│  │  项目加载    │  │  场景管理    │  │  选中状态    │  │  检查结果      │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Infrastructure Layer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐ │
│  │   File      │  │   YAML      │  │   USDA      │  │    Three.js    │ │
│  │   System    │  │   Parser    │  │   Parser    │  │   Renderer     │ │
│  │  文件系统    │  │  YAML 解析   │  │ USDA 解析   │  │  3D 渲染引擎   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 模块划分

### 2.1 目录结构

```
viewer/src/
├── main.ts                      # 入口：挂载 App
├── app/
│   └── App.ts                   # Shell：布局编排 + 组件协调
├── presentation/
│   ├── Toolbar.ts               # 顶部工具栏
│   ├── SceneTree.ts             # 左侧场景树
│   ├── Viewport.ts              # 中央 3D 视口
│   ├── PropertiesPanel.ts       # 右侧属性面板
│   └── StatusBar.ts             # 底部状态栏
├── core/
│   ├── project/
│   │   ├── ProjectService.ts    # 项目加载、扫描、解析
│   │   └── types.ts             # 项目相关类型
│   ├── scene/
│   │   ├── SceneService.ts      # 场景对象管理、构建
│   │   └── types.ts             # 场景对象类型
│   ├── selection/
│   │   └── SelectionService.ts  # 选中状态管理、双向同步
│   └── check/
│       └── CheckService.ts      # 检查结果加载、统计（预留）
├── infrastructure/
│   ├── parsers/
│   │   ├── YamlParser.ts        # YAML 文本解析
│   │   └── UsdaParser.ts        # USDA 文本解析
│   ├── fs/
│   │   └── FileSystem.ts        # File System Access API 封装
│   └── renderer/
│       └── ThreeRenderer.ts     # Three.js 渲染器封装
├── types/
│   └── index.ts                 # 全局共享类型
└── utils/
    └── index.ts                 # 通用工具函数
```

### 2.2 模块职责边界

#### Presentation Layer（展示层）

| 模块 | 职责 | 禁止做的事 |
|---|---|---|
| `Toolbar` | 渲染工具按钮，触发打开项目操作 | 不直接操作文件系统 |
| `SceneTree` | 渲染树形结构，响应点击高亮 | 不解析 YAML，不构造 SceneObject |
| `Viewport` | 渲染 3D 场景，处理鼠标交互 | 不解析 USDA，不管理选中状态 |
| `PropertiesPanel` | 渲染属性表格，格式化数值 | 不计算几何属性，不编辑 YAML |
| `StatusBar` | 渲染状态信息，显示统计 | 不加载项目，不执行检查 |

**展示层只负责渲染和转发用户事件，所有业务逻辑委托给 Core Layer。**

#### Core Layer（业务逻辑层）

| 模块 | 职责 | 输入 | 输出 |
|---|---|---|---|
| `ProjectService` | 扫描目录、加载 YAML、构建项目模型 | `FileSystemDirectoryHandle` | `PikiProject` |
| `SceneService` | 解析 USDA、构建场景图、管理场景对象 | USDA 文本 | `SceneObject[]` |
| `SelectionService` | 管理当前选中对象，同步各面板 | 用户点击/选择事件 | 选中对象 + 变更通知 |
| `CheckService` | 加载检查结果、统计、过滤（预留） | CheckReport JSON | 过滤后的结果列表 |

**Core Layer 是纯粹的业务逻辑，不依赖任何 DOM 或 Three.js API。**

#### Infrastructure Layer（基础设施层）

| 模块 | 职责 | 封装的外部依赖 |
|---|---|---|
| `FileSystem` | 封装 File System Access API，提供统一接口 | `window.showDirectoryPicker()` |
| `YamlParser` | 将 YAML 文本解析为 JS 对象 | 自研（未来可替换为 yaml 库） |
| `UsdaParser` | 将 USDA 文本解析为场景对象描述 | 自研（未来可替换为 USD WASM） |
| `ThreeRenderer` | 封装 Three.js，提供场景渲染、相机控制、射线检测 | `three` npm 包 |

**Infrastructure Layer 封装所有外部依赖，Core Layer 通过接口使用，不直接依赖具体实现。**

---

## 3. 数据流

### 3.1 项目加载流程

```
用户点击"打开项目"
    │
    ▼
┌─────────────┐
│   Toolbar   │ ──onOpenProject()──▶
└─────────────┘                      │
                                     ▼
┌─────────────────────────────────────────┐
│              App (Shell)                │
│  1. 调用 ProjectService.loadProject()   │
│  2. 获得 PikiProject                    │
│  3. 通知 SceneTree.setProject()         │
│  4. 调用 SceneService.loadFromUsda()    │
│  5. 通知 Viewport.loadScene()           │
│  6. 更新 StatusBar                      │
└─────────────────────────────────────────┘
```

### 3.2 对象选择流程（双向同步）

```
场景树点击                    3D 视口点击
    │                            │
    ▼                            ▼
┌─────────────┐            ┌─────────────┐
│  SceneTree  │            │   Viewport  │
│ onItemClick │            │ onCanvasClick│
└──────┬──────┘            └──────┬──────┘
       │                          │
       └──────────┬───────────────┘
                  ▼
       ┌─────────────────────┐
       │  SelectionService   │
       │  setSelected(obj)   │
       └──────────┬──────────┘
                  │
       ┌──────────┼──────────┐
       ▼          ▼          ▼
  ┌────────┐ ┌────────┐ ┌────────────┐
  │SceneTree│ │Viewport│ │Properties  │
  │highlight│ │highlight│ │   Panel    │
  └────────┘ └────────┘ └────────────┘
```

**SelectionService 是唯一的选中状态源（Single Source of Truth），所有面板通过它同步。**

---

## 4. 接口契约

### 4.1 Core Layer 接口

```typescript
// core/project/ProjectService.ts
interface IProjectService {
  loadProject(dirHandle: FileSystemDirectoryHandle): Promise<PikiProject>;
}

// core/scene/SceneService.ts
interface ISceneService {
  loadFromUsda(content: string): SceneObject[];
  getObjectByName(name: string): SceneObject | null;
}

// core/selection/SelectionService.ts
interface ISelectionService {
  getSelected(): SceneObject | null;
  setSelected(obj: SceneObject | null): void;
  onChange(callback: (obj: SceneObject | null) => void): () => void;
}

// core/check/CheckService.ts
interface ICheckService {
  loadReport(report: CheckReport): void;
  getStats(): { passed: number; failed: number; warnings: number };
  getResultsBySeverity(severity: 'error' | 'warning' | 'info'): CheckResult[];
}
```

### 4.2 Infrastructure Layer 接口

```typescript
// infrastructure/fs/FileSystem.ts
interface IFileSystem {
  pickDirectory(): Promise<FileSystemDirectoryHandle | null>;
  scanDirectory(handle: FileSystemDirectoryHandle, pattern: string): Promise<FileEntry[]>;
  readFile(handle: FileSystemFileHandle): Promise<string>;
}

// infrastructure/parsers/UsdaParser.ts
interface IUsdaParser {
  parse(content: string): SceneObject[];
}

// infrastructure/renderer/ThreeRenderer.ts
interface IThreeRenderer {
  mount(container: HTMLElement): void;
  loadScene(objects: SceneObject[]): void;
  highlightObject(name: string): void;
  onSelect(callback: (name: string | null) => void): void;
  setCameraMode(mode: 'orbit' | 'pan' | 'zoom'): void;
  fitView(): void;
  setWireframe(enabled: boolean): void;
  destroy(): void;
}
```

---

## 5. 依赖规则

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
- ❌ Presentation Layer 不能直接调用 Infrastructure Layer（必须通过 Core）

---

## 6. 演进路线

### 阶段 1：当前（v0.1.0）— 扁平架构

- App 直接持有所有组件实例
- 业务逻辑内联在 App 和组件中
- **目标**：完成 MVP，验证产品价值

### 阶段 2：服务化（v0.2.0）— 引入 Core Layer

- 提取 ProjectService、SceneService、SelectionService
- App 仅负责布局编排和事件转发
- **目标**：解耦业务逻辑与 UI，支持单元测试

### 阶段 3：状态管理（v0.3.0）— 引入 Store

- 当组件超过 15 个或出现跨层级状态共享时
- 评估 Pinia / Zustand / 自研 EventEmitter
- **触发条件**：属性编辑、多项目对比、面板动态增删

### 阶段 4：插件化（v0.4.0+）— 面板扩展

- 领域插件可注册自定义面板和渲染器
- 面板通过标准接口与 Core Layer 通信
- **触发条件**：AI Agent 集成、领域定制面板

---

## 7. 关键决策记录

| 决策 | 选择 | 理由 | 可逆性 |
|---|---|---|---|
| 状态管理 | 当前：直接回调 | 组件少，无需引入库 | 高：v0.3.0 可替换 |
| 样式方案 | 当前：内联 style | 避免构建工具链膨胀 | 高：v0.2.0 可迁移到 CSS Modules |
| USDA 解析 | 自研文本解析器 | 无需 WASM，启动快 | 中：可并行集成 USD WASM |
| 文件系统 | File System Access API | 浏览器原生，无后端 | 低：需 ZIP 上传作为降级 |
