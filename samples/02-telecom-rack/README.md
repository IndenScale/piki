# 02-telecom-rack — 电信机架示例

> 从真实问题出发：新增服务器前，自动检查 PDU 功率和 U 位冲突。
> 演示 ADR-008 Instance/Layout 分离 + Instance 覆盖 Model 默认值。

## 场景

你管理一个小型机房，机柜 `RACK-A01` 里已有 2 台服务器：

| 设备 | 功耗 | 位置 |
|------|------|------|
| `SRV-01` | 300W | U10-U11 |
| `SRV-02` | 250W | U12-U13 |

PDU-A 额定容量 2000W，当前负载 550W（27.5%）。

现在你要新增 `SRV-03`（400W，U6-U7），接 PDU-A。你检查了 U 位没有冲突，但**忘了算功率**——新增后 PDU-A 负载变成 950W（47.5%），超过项目设定的阈值 40%。

piki 帮你：**在提交设计前，自动发现这个问题。**

## 项目结构

```
02-telecom-rack/
├── piki.toml                    # 项目配置（阈值设定）
├── models/
│   └── devices/
│       └── generic-server.yaml  # 型号库：generic-server 规格
├── racks/
│   └── RACK-A01.yaml            # 机柜数据
├── pdus/
│   ├── PDU-A.yaml               # 主路 PDU
│   └── PDU-B.yaml               # 备路 PDU
├── instances/                   # 设备身份（ADR-008 分离）
│   ├── SRV-01.yaml              # 已有设备 1
│   └── SRV-02.yaml              # 已有设备 2（覆盖功耗）
├── layouts/
│   └── layout.yaml              # 部署决策
└── rules/
    └── power.py                 # 项目自定义规则（预留）
```

### ADR-008 分离

Instance 文件只管"设备是什么"：

```yaml
# instances/SRV-01.yaml
id: SRV-01
name: 服务器-01
model: generic-server
status: installed
```

```yaml
# instances/SRV-02.yaml — 覆盖型号默认功耗
id: SRV-02
name: 服务器-02
model: generic-server
status: installed
tdp_w: 250                         # Instance 覆盖：实际功耗低于型号默认 300W
```

Layout 文件管"设备部署在哪"：

```yaml
# layouts/layout.yaml
- instance: SRV-01
  position_u: 10
  pdu_id: PDU-A
  rack_id: RACK-A01
- instance: SRV-02
  position_u: 12
  pdu_id: PDU-A
  rack_id: RACK-A01
- instance: PDU-A
  rack_id: RACK-A01
  phase: L1
- instance: PDU-B
  rack_id: RACK-A01
  phase: L1
```

## 运行初始检查

```bash
cd samples/02-telecom-rack
piki check
```

预期输出（全部通过，可能有 3D 碰撞警告可用性）：

```
============================================================
总计: 0 错误, 7 通过
============================================================
```

## 步骤 1：编写新增方案（触发问题）

创建 `instances/SRV-03.yaml`：

```yaml
id: SRV-03
name: 服务器-03
model: generic-server
status: planned
tdp_w: 400
```

在 `layouts/layout.yaml` 末尾追加部署信息：

```yaml
- instance: SRV-03
  position_u: 6
  pdu_id: PDU-A
  rack_id: RACK-A01
```

运行检查：

```bash
piki check
```

预期输出（功率检查失败）：

```
[FAIL] TELECOM-POWER-001: PDU 功率预算检查
       PDU-A 负载率 47.5%（950W / 2000W），超过项目阈值 40.0%
============================================================
总计: 1 错误, 6 通过
============================================================
```

## 步骤 2：修正方案

把 `SRV-03` 改接到 PDU-B（修改 `layouts/layout.yaml` 中对应条目的 `pdu_id`）：

```yaml
- instance: SRV-03
  position_u: 6
  pdu_id: PDU-B        # 改接 PDU-B
  rack_id: RACK-A01
```

重新运行 `piki check`，全部通过。

## 步骤 3：尝试 U 位冲突

把 `position_u` 改成 `10`（修改 `layouts/layout.yaml`）：

```yaml
- instance: SRV-03
  position_u: 10       # 与 SRV-01（U10-U11）冲突
  pdu_id: PDU-B
  rack_id: RACK-A01
```

重新运行 `piki check`，U 位冲突检查会失败。

## 你学到了什么

| 能力 | 说明 |
|------|------|
| Instance/Layout 分离 | 设备属性在 `instances/`，部署位置在 `layouts/` |
| 型号库 | `models/` 定义设备规格，实例可覆盖默认值（如 tdp_w） |
| 方案比选 | 修改 `layouts/layout.yaml` 即可尝试不同部署方案 |
| PDU 功率检查 | 累加 PDU 下所有设备功耗，与额定容量对比 |
| U 位冲突检查 | 检测同一机柜内位置重叠的设备 |
| 外键完整性 | 自动检查 rack_id、pdu_id 引用是否有效 |
