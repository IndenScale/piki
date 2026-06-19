# ADL Assembly Examples

> 真实工程设计装配体示例，每个示例是一个可独立运行的 piki 项目。

## 示例

| # | 示例 | 实体 | 配合类型 |
|---|------|------|----------|
| 01 | [face-gasket](01-face-gasket/) | 泵出口法兰 + PTFE 垫片 + 管道法兰 + 4×M16 螺栓 | face-on-face 面密封 |
| 02 | [shaft-bushing](02-shaft-bushing/) | 传动轴 Ø25h7 + 铜套 Ø25H7 + 轴承座 | axis 轴孔间隙配合 |
| 03 | [dovetail-slide](03-dovetail-slide/) | 60° 燕尾槽底座 + 滑块，行程 120mm | slot 槽配合 |
| 04 | [spur-gears](04-spur-gears/) | 20 齿驱动轮 + 40 齿从动轮，m=2，速比 2:1 | face-on-face 齿轮啮合 |
| 05 | [worm-drive](05-worm-drive/) | 单头蜗杆 + Z30 蜗轮，速比 30:1 | face-on-face 蜗杆蜗轮 |
| 06 | [fiber-connectors](06-fiber-connectors/) | 交换机 SFP28 笼子 + 光模块 + LC/SC 双工跳线 + ODF | slot SFP 插入 + face-on-face LC/SC 对接 |
| 07 | [usb-interfaces](07-usb-interfaces/) | PCB USB-C 母座 + USB-A 母座 + 插头三态 | slot 推入 + discrete_states 正/反/拔 |

## 运行

每个示例可独立运行：

```bash
cd adl/examples/01-face-gasket
piki check
```

## 设计原则

- **配合先行**：先写 `mates/`，再写 `layouts/`
- **Layout 只写根节点坐标**：child 位姿由 Mate 约束求解器推导
- **接口是配合的唯一入口**：Mate 引用 `INSTANCE_ID/interface_id`
- **所有尺寸规格化**：真实孔径、公差、行程、模数、速比

## 对应 ADR

| ADR | 相关示例 |
|-----|---------|
| ADL-003 接口优先配合 | 01-07 全部 |
| ADL-004 接口签名系统 | 07 USB 三态 |
| ADR-005 Connection | 06 LC/SC 跳线 |
| ADR-006 Mating Graph | 01 螺栓贯穿链、02 轴套座链 |
