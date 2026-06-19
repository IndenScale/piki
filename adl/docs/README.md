# ADL 设计文档

此处讨论 ADL 运行时本身的设计问题：IR 架构、编译 pass pipeline、符号表设计、类型系统等。

与 `piki/docs/`（piki 框架、概念、ADL 语言规范）不同，本目录专用于 ADL 包的内核设计决策。

## 核心概念

1. [ADL 核心概念索引](concepts/README.md)
2. [ADL 分层概念模型](concepts/01-layered-model.md) — PDL / PML / PLL 三子语言、每层概念与全局位姿计算链
3. [接口与坐标系](concepts/02-interface-and-coordinate-system.md) — Interface、local_transform、坐标系约定、Footprint
4. [配合类型与自由度](concepts/03-mating-kinds-and-dof.md) — MatingKind、InterfaceSignature、DOF、签名耦合
5. [布局与参数化定位链](concepts/04-layout-and-placement-chain.md) — Layout、坐标优先级、Mate 与 Layout 关系、全局坐标

## 内核设计文档

| 编号 | 标题 | 状态 |
|------|------|------|
| [001](adr/001-adl-as-compiler.md) | ADL 是否应该作为编译器设计？ | 已完成 |
| [002](adr/002-compiler-architecture.md) | ADL 编译器架构设计 | 设计阶段 |
| [003](adr/003-interface-first-mating.md) | 接口优先的配合建模 | 已完成 |
| [004](adr/004-interface-signature.md) | 接口运动自由度签名系统 | 已完成 |

## 用户指南

- [装配体建模指南](guides/modeling-assemblies.md) — Instance + Layout + Mate：从两零件到多层装配
