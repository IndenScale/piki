# ADR-005: Piki Studio——浏览器端工程设计 IDE

> 状态：已实现
> 日期：2026-06-12
> 作者：piki 核心团队
> 替代：ADR-006（Piki Studio Web 查看器）

## 背景

piki 提供 `piki generate usd-scene` 导出 3D 场景，但工程师需要一个直观的方式在提交设计前快速预览三维布局。此前 piki 有一个基于 Autodesk USD WASM fork 的轻量查看器，但存在根本性问题。

本 ADR 记录重新设计预览体验的决策：从独立查看器到项目级 IDE。

---

## 1. 旧方案的问题

### 1.1 功能割裂

旧预览器是一个独立的 USDA 文件查看器，与 piki 项目结构无关：无文件树、无属性面板、无规则结果集成、无编辑闭环（改 YAML → 刷新预览）。

### 1.2 技术债务

依赖 `needle-tools/usd-viewer` 完整仓库（30MB+），含 16MB WASM 二进制、Fastify 服务器、示例文件。这些资源与 piki 核心功能无关，却随 Python 包分发。

### 1.3 维护困难

旧预览器是第三方 fork，JavaScript 代码与 piki Python 代码无直接交互。任何功能扩展都需要在两个独立技术栈之间做桥接。

---

## 2. 新方案：Piki Studio

### 2.1 定位

Piki Studio 是一个**基于浏览器的工程设计 IDE**。它不是独立的查看器，而是与 piki 项目深度集成：直接读取本地项目目录（File System Access API）、解析 YAML 构建场景树、渲染 3D 预览、选中对象时同步显示属性。

### 2.2 技术选型

| 层面 | 选型 | 理由 |
|------|------|------|
| 语言 | TypeScript | 类型安全，IDE 开发体验好 |
| 构建工具 | Vite | 快速，原生 ESM |
| 3D 渲染 | Three.js | 成熟，社区大 |
| USDA 解析 | 自研文本解析器 | 不依赖 WASM，启动快，当前阶段只渲染代理几何足够 |
| 项目读取 | File System Access API | 浏览器原生，无需后端 |

### 2.3 为什么不用 USD WASM

当前阶段，Piki Studio 只需要渲染代理几何（Box）和显示属性。自研 USDA 文本解析器（约 200 行）已足够满足需求，且无需下载 16MB WASM 二进制、无需 COOP/COEP headers、解析速度快。

未来如需渲染复杂 USD 场景（引用外部资产、材质、动画），可再集成 USD WASM。

### 2.4 与 piki CLI 的关系

Piki Studio 是 CLI 的**可视化补充**，不是替代。设计的源头仍然是文本，Studio 只是让"看效果"这件事更直观。

---

## 3. 决策

**已执行**以下变更：

1. 新增 `studio/` 目录，包含 TypeScript 源码
2. 删除 `src/piki/ext/usd/web-viewer/` 及所有旧预览器代码
3. 删除 `piki preview` CLI 命令
4. Studio 通过 `studio/` 独立维护，与 Python 核心解耦

---

## 4. 决策总结

| 决策 | 选择 | 核心理由 |
|------|------|----------|
| 预览方案 | 自研 TypeScript IDE | 与项目深度集成，功能演进可控 |
| USDA 解析 | 自研文本解析器 | 无需 WASM，启动快，当前阶段足够 |
| 旧预览器 | 删除 | 功能重叠且更弱，减少 30MB+ 维护负担 |
| 与 CLI 关系 | 可视化补充，非替代 | 设计的源头仍然是文本 |

---

## 参考

- [Studio 源码](../../studio/)
- [空间可视化策略](../adr/004-spatial-visualization-strategy.md)
