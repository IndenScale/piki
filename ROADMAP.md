# piki 路线图

> 当前版本：**0.1.0（Alpha）**
>
> piki 已从“框架 + ADL 一体化”拆分为：
> - **`adl/`**：独立的装配体定义语言运行时（由 adl 包自己维护）
> - **`src/piki/`**：纯编排框架（插件发现 → ADL 加载 → 规则/生成器 → 报告）
>
> 因此，**piki 本仓库进入场景驱动开发阶段**：优先用真实工程场景验证框架，ADL 只修 bug、不扩功能。

---

## 当前阶段：场景驱动（进行中）

### 1. 电信场景规模化（配合 SD-HWE-Bench）

目标：让 telecom 插件覆盖足够多的真实设计任务，为 SD-HWE-Bench 提供可评测场景。

- [ ] 补充 telecom 示例项目到 3–5 个（覆盖扩容、新建、改造）
- [ ] 配合 sd-hwe-bench 把电信任务集扩展到 30+ tasks
- [ ] 补齐 6 种任务类型的难度梯度（L1 直接 / L2 推理 / L3 规划）
- [ ] 跑通 B0/B1/B2 baseline，收集人类基线 B3/B4
- [ ] 验证并稳定 L3/L4 规则输出（功率预算、U 位冲突、接口兼容、三维碰撞）

### 2. ADL 稳定化（维护模式）

ADL 功能已足够支撑当前场景，本阶段只做收敛性工作：

- [ ] 收敛公共 API（`ProjectLoader` / `compile_project`）并更新文档
- [ ] 修复场景运行中暴露的 ADL bug
- [ ] 把 `SpatialCollisionPass` 明确接入或文档化其调用方式
- [ ] 不新增 ADL 通用能力（不统一几何求解器、不实现任意轴旋转、不做增量编译）

### 3. 文档与开发者体验

- [ ] 刷新本仓库文档，明确 piki 与 ADL 的边界（README / docs / AGENTS）
- [ ] 清理 piki 与 adl 之间的重复几何逻辑
- [ ] 补充 datacenter / keyboard 的 minimal 示例
- [ ] 整理插件开发指南

---

## 下一阶段：跨域扩展（待启动）

当电信场景在 SD-HWE-Bench 上证明可用后，按 [docs/METHODOLOGY.md](docs/METHODOLOGY.md) 的域扩展协议进入新域：

1. **datacenter** — 方舱、配电、冷热通道
2. **keyboard** — PCB、键轴、外壳装配
3. **hvac** — 管道路由、坡度、净高
4. **building** — 房间拓扑、疏散、面积

每个域的扩展工作：

- 编写该域 piki 插件（Family、Model、Mate type、Rules、Generators）
- 提供 ≥10 个 Model 和 ≥10 个 tasks，覆盖 ≥3 种任务类型
- 实现该域 L3 规则集（每种任务类型 ≥3 条）
- 收集 B0 + B1 baseline 和至少 1 名人类工程师基线

---

## 明确不做的方向

为避免 ADL 过度工程化，以下特性在当前阶段明确不做：

- 统一几何求解器（当前按 mate type 分支足够）
- 完整任意轴旋转 Rodrigues 变换
- 增量编译 / IR 序列化 / 并行 Pass
- 外部数据同步（`piki sync`）
- 数据库导入
- 敏感字段加密
- 多语言 SDK
- Studio 在线编辑
- 在线注册中心

这些特性可能在未来由场景需求拉动，但不会 preemptively 投入。

---

## 版本策略

- **0.x** — 场景驱动快速迭代，piki 公共 API 尽量稳定，breaking change 会记录
- **1.0** — 当 SD-HWE-Bench 电信域达到 30+ tasks 且基线稳定后，承诺向后兼容

---

## ADL 自身路线图

ADL 的独立路线现在由 `adl/` 目录维护。本文件不再追踪 ADL 内部特性（如编译器优化、几何求解器升级）。如需了解 ADL 计划，请阅读 [adl/docs/adr/](adl/docs/adr/) 与相关 RFC。

---

反馈和建议：[GitHub Issues](https://github.com/indenscale/piki/issues)
