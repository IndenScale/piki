# 03-mechanical-keyboard — 机械键盘设计校验

> 消费电子产品级机电集成示例：铝坨坨 + 硅胶隔音 + 三模 + 锂电 + PBT 键帽 + 国产轴体。

## 场景

你设计了一把 65% 布局的无线机械键盘：

| 组件 | 选型 |
|------|------|
| 外壳 | 65% 铝合金 gasket 结构（铝坨坨） |
| 定位板 | PC 材质，1.5mm，带 flex cuts |
| PCB | RP2040 控制器，三模，热插拔 MX，per-key RGB |
| 轴体 | Gateron Yellow Pro（国产佳达隆） |
| 键帽 | PBT 热升华 OEM 高度 |
| 卫星轴 | 钢板卫星轴，螺丝固定 |
| 隔音 | 硅胶底壳垫 + Poron gasket 条 |
| 电池 | 4000mAh 锂聚合物 |
| 线材 | USB-C 航插弹簧线 |

piki 帮你：**在下单打样前，自动发现 stem、针脚、开孔、电流、续航、天线等跨组件兼容性问题。**

## 项目结构

```
03-mechanical-keyboard/
├── piki.toml                      # 项目配置
├── models/                        # 型号库
│   ├── cases/aluminum-65.yaml
│   ├── plates/pc-65.yaml
│   ├── pcbs/rp2040-wireless-65.yaml
│   ├── switches/gateron-yellow-pro.yaml
│   ├── keycaps/pbt-dye-sub-oem-65.yaml
│   ├── stabilizers/screw-in-steel.yaml
│   ├── dampeners/silicone-case-bottom.yaml
│   ├── dampeners/poron-gasket-strip.yaml
│   ├── batteries/li-po-4000.yaml
│   └── cables/usb-c-coiled.yaml
├── instances/                     # 实际部署实例
│   ├── assembly/KB-MAIN.yaml      # 整机组装
│   ├── cases/CASE-01.yaml
│   ├── plates/PLATE-01.yaml
│   ├── pcbs/PCB-01.yaml
│   ├── switches/SW-*.yaml         # 代表性轴体（ESC/A/Enter/Space）
│   ├── keycaps/KC-*.yaml          # 代表性键帽
│   ├── stabilizers/STAB-SPC.yaml
│   ├── dampeners/DAMP-*.yaml
│   ├── batteries/BATT-01.yaml
│   ├── cables/CABLE-01.yaml
│   ├── nets/NET-*.yaml            # 电气网络（VBUS/GND/VBAT/矩阵）
│   └── key_clusters/ALPHA-CLUSTER.yaml  # 批量声明的键簇
├── mates/                         # 配合关系（Mating Graph）
│   ├── case-bottom-dampener/      # 底壳隔音垫
│   ├── plate-gasket-mount/        # 定位板 gasket 装配
│   ├── pcb-standoff-mount/        # PCB 固定
│   ├── switch-plate-snap/         # 轴体卡入定位板
│   ├── switch-pcb-solder/         # 轴体焊接/热插拔到 PCB
│   ├── stabilizer-plate-mount/    # 卫星轴卡入定位板
│   ├── stabilizer-pcb-screw/      # 卫星轴螺丝固定到 PCB
│   ├── keycap-stem-mount/         # 键帽装配
│   ├── battery-pcb-cable/         # 电池连接
│   └── usb-cable-mate/            # USB 线连接
├── layouts/layout.yaml            # 3D 空间位置
└── dist/                          # 生成物输出目录
```

> 注：为保持示例可读，本项目只创建了 4 颗代表性轴体/键帽。真实 65% 项目会创建全部 68 颗，或通过 `KeyCluster` 等抽象批量声明。

## 快速体验

```bash
cd samples/03-mechanical-keyboard
piki check
# 预期：全部通过

piki generate keyboard-bom
# 预期：输出 BOM CSV

piki generate keyboard-spec
# 预期：输出 Markdown 规格说明书
```

## 你学到了什么

| 能力 | 对应位置 |
|------|---------|
| **消费电子 Family 体系** | `src/piki/extensions/keyboard/plugin.py` |
| **机电配合关系** | `mates/`：轴体↔定位板、轴体↔PCB、键帽↔轴体、卫星轴↔PCB |
| **接口兼容性检查** | KB-STEM-001（键帽 stem）、KB-SWITCH-001（针脚）、KB-PLATE-001（开孔） |
| **安装方式一致性** | KB-MOUNT-001：case/plate/pcb 的 mounting_style 必须一致 |
| **无线设计约束** | KB-WIRELESS-001：金属外壳需天线开口；KB-POWER-001：续航估算 |
| **电流预算** | KB-CURRENT-001：LED + 控制器 + 轴体不超过 USB/电池限额 |
| **环境适应性** | KB-ENV-001：户外使用 ABS 键帽报警 |
| **BOM/规格生成** | `keyboard-bom`、`keyboard-spec` Generator |
| **电气网络（Net）** | `instances/nets/`：多节点网络表达 VBUS/GND/矩阵行/列 |
| **跨插件协作** | `keyboard` + `consumer-electronics` 插件共用 Net 与接口类型 |
| **model_id 追溯** | BOM 中显示实例引用的型号 ID |
| **功耗预算框架** | `consumer-electronics` 的 `PowerBudget` 被键盘规则复用 |
| **键簇批量声明** | `KeyClusterFamily`：用 1 个 YAML 声明 N 颗相同轴体/键帽 |
| **Footprint 复合接口** | USB-C/JST 等多 pin 连接器建模为 `FootprintSpec`，Net 引用到 pin 级 |

## 故意保留的教学用例

当前示例全部通过。你可以尝试修改以下字段来触发规则：

```yaml
# 把键帽 stem 改成 choc，触发 KB-STEM-001
# instances/keycaps/KC-A.yaml
stem_mount: choc
```

```yaml
# 把外壳改成无天线开口，触发 KB-WIRELESS-001
# models/cases/aluminum-65.yaml
has_antenna_aperture: false
```

```yaml
# 把电池容量改小，触发 KB-POWER-001
# models/batteries/li-po-4000.yaml
capacity_mah: 500
```

## 关联概念

- [ADR-006: Mating Graph](../../docs/adr/006-mating-graph.md)
- [ADR-005: Connection 与 Interface](../../docs/adr/005-connection-as-instance.md)
- [编写检查规则](../../docs/concepts/02-writing-rules.md)
- [piki-keyboard 插件源码](../../src/piki/extensions/keyboard/plugin.py)
- [piki-consumer-electronics 插件源码](../../src/piki/extensions/consumer_electronics/plugin.py)
- [缺口清单：GAPS.md](GAPS.md)
