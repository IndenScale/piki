# 02-telecom-rack — 电信机架示例

> 从真实问题出发：新增服务器前，自动检查 PDU 功率和 U 位冲突。

## 场景

你管理一个小型机房，机柜 `RACK-A01` 里已有 2 台服务器：

| 设备 | 功耗 | 位置 |
|------|------|------|
| `SRV-01` | 300W | U10-U11 |
| `SRV-02` | 250W | U8-U9 |

PDU-A 额定容量 2000W，当前负载 550W（27.5%）。

现在你要新增 `SRV-03`（400W，U6-U7），接 PDU-A。你检查了 U 位没有冲突，但**忘了算功率**——新增后 PDU-A 负载变成 950W（47.5%），超过项目设定的阈值 40%。

piki 帮你：**在提交设计前，自动发现这个问题。**

## 项目结构

```
02-telecom-rack/
├── piki.toml                    # 项目配置（阈值设定）
├── library/
│   └── devices/
│       └── generic-server.yaml  # 型号库：generic-server 规格
├── racks/
│   └── RACK-A01.yaml            # 机柜数据
├── pdus/
│   ├── PDU-A.yaml               # 主路 PDU
│   └── PDU-B.yaml               # 备路 PDU
├── devices/
│   ├── SRV-01.yaml              # 已有设备 1
│   └── SRV-02.yaml              # 已有设备 2（覆盖功耗）
└── rules/
    └── power.py                 # 项目自定义规则（预留）
```

## 运行初始检查

```bash
cd samples/02-telecom-rack
piki check
```

预期输出（全部通过）：

```
[PASS] TELECOM-POWER-001: PDU 功率预算检查
[PASS] TELECOM-RACK-001: U 位冲突检查
[PASS] TELECOM-RACK-002: 机柜容量检查
[PASS] TELECOM-FK-001: 外键完整性检查
============================================================
总计: 0 错误, 0 警告, 4 通过
============================================================
```

## 步骤 1：编写新增方案（触发问题）

创建 `devices/SRV-03.yaml`：

```yaml
id: SRV-03
name: 服务器-03
model: generic-server
status: planned
rack_id: RACK-A01
position_u: 6
pdu_id: PDU-A

tdp_w: 400
```

运行检查：

```bash
piki check
```

预期输出（功率检查失败）：

```
[FAIL] TELECOM-POWER-001: PDU 功率预算检查
       PDU-A 负载率 47.5%（950W / 2000W），超过项目阈值 40.0%。已接入设备: SRV-01, SRV-02, SRV-03
============================================================
总计: 1 错误, 0 警告, 3 通过
============================================================
```

## 步骤 2：修正方案

把 `SRV-03` 改接到 PDU-B：

```yaml
# devices/SRV-03.yaml
id: SRV-03
name: 服务器-03
model: generic-server
status: planned
rack_id: RACK-A01
position_u: 6
pdu_id: PDU-B        # 改接 PDU-B

tdp_w: 400
```

重新运行 `piki check`，全部通过。

## 步骤 3：尝试 U 位冲突

把 `position_u` 改成 `10`：

```yaml
# devices/SRV-03.yaml
position_u: 10       # 与 SRV-01（U10-U11）冲突
```

重新运行 `piki check`，U 位冲突检查会失败：

```
[FAIL] TELECOM-RACK-001: U 位冲突检查
       机柜 RACK-A01 U10-U11 冲突: SRV-01（U10-U11）与 SRV-03（U10-U11）
```

## 你学到了什么

| 能力 | 说明 |
|------|------|
| 型号库 | `library/` 定义设备规格，实例可覆盖默认值 |
| 功率检查 | 自动汇总 PDU 下所有设备功耗，与阈值比较 |
| U 位检查 | 自动检测同一机柜内的 U 位重叠 |
| 外键检查 | 自动验证 `rack_id`、`pdu_id` 引用是否存在 |
| 项目阈值 | `piki.toml` 中配置，不同项目可有不同标准 |
