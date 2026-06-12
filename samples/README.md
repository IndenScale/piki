# piki Samples

精选示例项目，每个都是独立的 piki 项目，可直接运行 `piki check`。

## 目录

| 示例 | 插件 | 故事 |
|------|------|------|
| [01-telecom-expansion](01-telecom-expansion/) | telecom | **设备扩容** — 新增服务器前，自动检查功率、U 位、接口兼容性 |
| [02-modular-datacenter](02-modular-datacenter/) | datacenter | **数据中心建设** — 通信+电力+暖通+建筑跨领域耦合 |
| [03-mechanical-keyboard](03-mechanical-keyboard/) | keyboard | **机械键盘设计** — 消费电子机电集成：铝坨坨、三模、锂电、PBT、国产轴体 |

## 快速体验

```bash
# 通信工程师最日常的场景
cd samples/01-telecom-expansion
piki check
# 预期：2 个错误（接口不兼容 + 线缆不匹配，是故意保留的教学用例）

# 跨领域耦合场景
cd samples/02-modular-datacenter
piki check
# 预期：全部通过

# 消费电子机电集成场景
cd samples/03-mechanical-keyboard
piki check
# 预期：全部通过
```

## 三个示例的关系

```
01-telecom-expansion              02-modular-datacenter              03-mechanical-keyboard
─────────────────────             ────────────────────────           ───────────────────────
粒度：设备级（U 位）               粒度：方舱级（集装箱）              粒度：产品级（键盘组件）
领域：通信（服务器+交换机+光纤）     领域：通信+电力+暖通+建筑           领域：消费电子（轴/帽/PCB/壳）
核心概念：Interface 类型体系        核心概念：多 Family + 跨域连接      核心概念：Mate 多级配合、电流预算
演示：兼容性矩阵、线缆校验           演示：PUE、液冷匹配、配电冗余        演示：stem/针脚/开孔兼容、续航
```

## 相关文档

- [核心概念](../docs/concepts/01-core-concepts.md) — Family → Model → Instance → Interface
- [编写检查规则](../docs/concepts/02-writing-rules.md) — `@rule` + QuerySet
- [RFC-001: Telecom 接口类型体系](../docs/rfcs/001-telecom-interface-types.md) — 接口枚举与兼容性矩阵
- [ADR-005: Connection 与 Interface](../docs/adr/005-connection-as-instance.md) — 连接建模
