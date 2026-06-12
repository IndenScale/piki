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

### 7. 数组/列表字段的查询过滤

**修复**：核心 `QuerySet` 的 `__in` 操作符现在支持 list 字段：字段中任一元素在期望集合中即匹配；`__contains` 保持"字段值包含期望值"的语义。

**验证**：`ctx.query("assembly", connectivity__contains="bluetooth")` 和 `connectivity__in=["usb", "bluetooth"]` 均可正常工作，并补充了单元测试。

### 8. 运行时类型分支的友好 API

**修复**：核心 `Context` 新增 `instance_family(id)`、`find_model(model_id)` 公开 API，以及 `mate_parent_instance(mate)` / `mate_child_instance(mate)` 便捷访问。键盘插件的 `_get_mated_*_instance` 已迁移到这些 API。

**验证**：`tests/unit/test_context_helpers.py` 覆盖这些新 API。

### 9. 装配层级（Assembly）支持

**修复**：核心新增 `piki.core.models.assembly.AssemblyFamily`，支持 `children` 和 `sub_assemblies`；`Context` 新增 `mated_descendants()` / `mated_ancestors()` 递归层级遍历。`KeyboardAssemblyFamily` 继承自 `AssemblyFamily`。

**验证**：键盘示例新增 `SUB-ALPHA` 子装配体，`KB-MAIN` 通过 `sub_assemblies` 引用，并通过 `KB-ASSEMBLY-001` 规则校验。

### 10. 环境适应性规则库

**修复**：新增 `piki-environments` 插件，提供 `OperatingEnvironmentFamily`（使用环境谱）和 `MaterialFamily`（材料耐候性），并新增 `ENV-*` 规则检查温度、UV、盐雾、IP 等级匹配。

**验证**：键盘示例新增 `INDOOR-USE` 环境、`PBT`/`ABS` 材料实例，键帽声明 `material_id`，`ENV-MAT-001/002/003` 全部通过。

### 11. EDA 工具导入/导出

**修复**：`piki-consumer-electronics` 新增 `importer` 模块，提供 POC 级 `import_kicad_netlist()`、`import_kicad_bom()`、`import_kicad_pnp()`，支持从 KiCad XML netlist / BOM CSV / pick-and-place CSV 提取 piki 可消费的 NetFamily 数据与组件清单。

**验证**：`tests/unit/test_consumer_electronics_importer.py` 覆盖三种导入器。

### 12. 制造约束即服务（DfX）

**修复**：新增 `piki-manufacturing` 插件，提供 `ManufacturingProcessFamily`（工艺约束）和 `BuildJobFamily`（制造工单），并新增 `DFX-*` 规则检查零件尺寸、壁厚、拔模角、表面处理。零件可直接通过 `process_id` 声明工艺，也可通过 BuildJob 建模下游工单。

**验证**：键盘外壳 `CASE-01` 声明 `process_id: CNC-ALU-65` 与 `surface_finish: anodized-black`，通过 `DFX-002/003/005` 规则；注塑拔模角规则 `DFX-004` 在单元/集成测试中覆盖。

## 仍然存在的缺口

### 13. 环境-组件自动关联

**现象**：当前需要零件显式声明 `environment_id` 和 `material_id` 才能触发环境规则。

**影响**：键盘键帽通过 `material_id` 关联，但轴体、PCB 等组件尚未系统化关联环境；`KB-ENV-001` 仍是硬编码规则。

**建议**：提供默认关联策略（如按 Family 或 `material` 字符串字段自动映射到 `MaterialFamily`），并扩展 `KB-ENV-001` 使用 environments 插件数据。

### 14. EDA 导入与 piki 实例的自动对齐

**现象**：importer 目前只返回结构化 dict，还没有 CLI 命令把 netlist/BOM 直接转成 `instances/` YAML。

**影响**：用户仍需手动把 importer 输出写入文件。

**建议**：增加 `piki import kicad-netlist` 等 CLI 命令，自动生成 NetFamily / Instance YAML。

### 15. DfX 与 3D 几何联动

**现象**：当前 DFX 规则依赖手动填写的 `length_mm`、`wall_thickness_mm` 等字段。

**影响**：无法从 CAD 资产（如 STEP/GLB）自动提取几何特征做壁厚/拔模角检查。

**建议**：与 `GeometryAssets` 和 CSG 模块集成，实现真正的几何级 DfX。

## 下一步可推进

1. 为 environments/manufacturing 插件补充更多样本规则（如湿度、盐雾小时数、CNC 孔径）
2. 实现 `piki import kicad-netlist` CLI 命令
3. 把 `GeometryAssets` 与 DFX 规则联动，做真正的几何约束检查
4. 为 keyboard 插件的每个 Family 增加 `environment_id` / `material_id` 字段的默认映射
