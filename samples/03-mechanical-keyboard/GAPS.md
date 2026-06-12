# 03-mechanical-keyboard 暴露的 piki 核心与扩展需求

本示例在搭建过程中，用实际需求反推了 piki 核心与消费电子扩展需要补强的能力。以下按优先级列出。

## 已修复 ✅

### 1. ResolvedInstance 暴露 `model_id`

**修复**：`ResolvedInstance` 新增 `model_id` 字段，`_resolve` 在合并 Model/Instance 时保留型号 ID。

**验证**：`piki generate keyboard-bom` 现在"型号"列可显示 `aluminum-65`、`pc-65` 等 model ID。

### 2. Interface 类型校验解耦 telecom 插件

**修复**：核心 `piki.core.models.interface` 新增全局接口类型注册表（`register_interface_type(s)` / `is_known_interface_type` / `get_known_interface_types`）。

- `telecom/types.py` 在模块导入时自动注册所有电信接口类型
- `keyboard` 插件注册键盘领域接口类型
- `consumer-electronics` 插件注册通用消费电子接口类型

**验证**：键盘示例中的 `vbus`、`gnd`、`switch-pin` 等类型不再触发 `UserWarning`。

### 3. Net（电气网络）抽象

**修复**：新增 `piki-consumer-electronics` 插件，定义 `NetFamily`，支持多节点网络：`nodes: list[instance_id/interface_id]`。

**验证**：键盘示例创建了 `NET-VBUS`、`NET-GND`、`NET-VBAT`、`NET-ROW0`、`NET-COL1` 等网络，并通过 `CE-NET-001/002` 规则检查节点存在性与接口类型兼容。

### 4. Footprint/Symbol 复合接口抽象

**修复**：核心 `piki.core.models.interface` 新增 `FootprintSpec`，支持 `pins: list[InterfaceSpec]`；`get_interfaces_from_resolved` 自动把 footprint pin 的 id 展开为 `footprint_id/pin_id`。

**验证**：键盘示例的 PCB、电池、线材模型改用 `footprints` 声明 USB-C、JST 等多 pin 连接器，Net 节点使用 3 级引用（如 `PCB-01/usb-c/VBUS`）。

### 5. KeyCluster 批量键声明

**修复**：`keyboard` 插件新增 `KeyClusterFamily`，支持用单个 YAML 声明 N 颗相同型号的轴体+键帽及其矩阵位置。

**验证**：键盘示例用 `ALPHA-CLUSTER` 声明 4 颗键，BOM 中轴体/键帽总数自动累加，电流预算也包含 cluster 键数。

### 6. 通用功耗/电流预算框架

**修复**：`consumer-electronics` 插件新增 `PowerBudget` 类，提供 `active_current_ma`、`average_current_ma`、`estimate_runtime_hours` 等方法；键盘插件的 `KB-CURRENT-001`、`KB-POWER-001` 已改用该框架。

**验证**：修改 `piki.toml` 中 `[plugins.consumer-electronics]` 的参数（如 `led_brightness_pct`）会直接影响续航估算。

## 仍然存在的缺口

### 7. 数组/列表字段的查询过滤

**现象**：`connectivity: [usb, bluetooth, 2.4g]` 这类 list 字段，QuerySet 当前只能做精确匹配。

**影响**：规则写 `connectivity__contains="bluetooth"` 可能不工作。

**建议**：QuerySet 支持 `__contains`、`__in` 对 list 字段的过滤。

### 8. 运行时类型分支的友好 API

**现象**：规则中经常需要判断 mate 的 parent 是 Switch 还是 Stabilizer，写法较冗长。

**影响**：规则代码可读性差。

**建议**：Context 提供 `instance_family(id)` 或 Mate 提供 `parent_instance`、`child_instance` 便捷访问。

### 9. 装配层级（Assembly）支持

**现象**：键盘总成是一个 Assembly，但当前只是普通 Instance 加引用字段。

**影响**：无法表达"子装配体可独立复用"（如把 PCB+轴体+键帽作为一个独立子装配）。

**建议**：核心支持 `AssemblyFamily` 和 `mated_children()` / `mated_parents()` 的层级遍历。

### 10. 环境适应性规则库

**现象**：KB-ENV-001 只检查了 ABS 键帽户外使用。

**影响**：温度、湿度、IP 等级、UV、盐雾等环境约束无法系统化表达。

**建议**：`piki-environments` 插件提供 `OperatingEnvironmentFamily` 和 `Material`/`Component` 耐候性匹配规则。

### 11. EDA 工具导入/导出

**现象**：当前没有从 KiCad/Altium 导入 netlist/footprint/BOM 的能力。

**影响**：piki 只能用于"人写 YAML"的设计阶段，无法 consuming 现有 EDA 数据。

**建议**：`piki-consumer-electronics` 提供 KiCad netlist + pick-and-place + BOM 的 importer，以及 design-rule 约束 exporter。

### 12. 制造约束即服务（DfX）

**现象**：3D 打印、CNC、注塑等工艺约束无法在本示例中体现。

**影响**：键盘外壳的 CNC 最小壁厚、阳极氧化颜色、注塑拔模角等无法检查。

**建议**：`piki-manufacturing` 插件提供 `ManufacturingProcessFamily` 和 `BuildJobFamily`，与 keyboard 插件集成。

## 下一步可推进

1. QuerySet 支持 list 字段的 `__contains` / `__in`
2. Context 增加 `find_model()` 公开 API（替代当前 `ctx._registry.find_model`）
3. KiCad netlist importer POC
4. `piki-manufacturing` 插件骨架 + 键盘外壳 CNC 约束示例
