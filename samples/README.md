# piki Samples

本目录包含精选的示例项目，用于学习和参考。每个示例都是独立的 piki 项目，可直接运行 `piki check`。

## 目录

| 示例 | 插件 | 复杂度 | 说明 |
|------|------|--------|------|
| [01-hello-piki](01-hello-piki/) | telecom | ⭐ 入门 | 最小工作示例：单设备 Schema 校验 |
| [02-telecom-rack](02-telecom-rack/) | telecom | ⭐⭐ 基础 | 电信机架：PDU 功率检查 + U 位冲突检查 |
| [03-data-center](03-data-center/) | telecom | ⭐⭐⭐ 进阶 | 多机柜数据中心：自定义规则 + 报告生成 |
| [04-modular-dc](04-modular-dc/) | datacenter | ⭐⭐⭐⭐ 高级 | 模块化数据中心：集装箱方舱 + 液冷 + 储能 |

## 快速体验

```bash
# 进入任意示例目录
cd samples/02-telecom-rack

# 运行检查
piki check

# 生成报告
piki report --format markdown
```

## 与 templates/ 的区别

- **`src/piki/templates/`** — `piki init` 命令使用的骨架文件，精简到只包含必要结构
- **`samples/`** — 完整可运行的示例项目，包含 README 说明、场景描述和预期输出，用于学习
