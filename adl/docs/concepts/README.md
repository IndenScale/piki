# ADL 核心概念

本目录展开解释 ADL（Assembly Definition Language）中的关键概念与运行机制。

阅读顺序建议：

1. [ADL 分层概念模型](01-layered-model.md) — 先建立 PDL / PML / PLL 三层全景
2. [接口与坐标系](02-interface-and-coordinate-system.md) — 理解 Interface、local_transform、坐标系约定
3. [配合类型与自由度](03-mating-kinds-and-dof.md) — 理解 mating_kind、InterfaceSignature、DOF、签名耦合
4. [布局与参数化定位链](04-layout-and-placement-chain.md) — 理解 Layout、坐标优先级、全局位姿计算

---

## 索引

| 序号 | 文档 | 主题 |
|:----:|------|------|
| 1 | [01-layered-model.md](01-layered-model.md) | ADL 三子语言：PDL / PML / PLL，每层概念与全局位姿链 |
| 2 | [02-interface-and-coordinate-system.md](02-interface-and-coordinate-system.md) | Interface 定义、坐标系、local_transform、Footprint、接口引用语法 |
| 3 | [03-mating-kinds-and-dof.md](03-mating-kinds-and-dof.md) | MatingKind、几何约束、InterfaceSignature、DOF、签名耦合 |
| 4 | [04-layout-and-placement-chain.md](04-layout-and-placement-chain.md) | LayoutEntry、坐标优先级、parent/transform 链、Mate 与 Layout 关系 |
