# 01-hello-piki — 最小工作示例

> 最简单的 piki 项目：一台服务器，验证 Schema 合规性和外键完整性。
> 演示 ADR-008 Instance/Layout 分离架构。

## 场景

你有一台服务器 `SRV-01`，放在机柜 `RACK-DEMO` 的 U10 位置，接入 PDU `PDU-DEMO`。想验证数据格式是否正确、外键引用是否有效。

## 项目结构

```
01-hello-piki/
├── piki.toml              # 项目配置
├── racks/
│   └── RACK-DEMO.yaml     # 机柜
├── pdus/
│   └── PDU-DEMO.yaml      # PDU
├── instances/             # 设备身份声明（不含位置信息）
│   └── SRV-01.yaml        # 服务器
└── layouts/
    └── layout.yaml        # 部署决策（rack_id, position_u, pdu_id）
```

### ADR-008 分离架构

Instance 文件只声明**设备是什么**，不包含部署位置：

```yaml
# instances/SRV-01.yaml
id: SRV-01
name: 服务器-01
model: generic-server
status: installed
```

Layout 文件描述**部署在哪**：

```yaml
# layouts/layout.yaml
- instance: SRV-01
  position_u: 10
  pdu_id: PDU-DEMO
  rack_id: RACK-DEMO
```

## 运行

```bash
cd samples/01-hello-piki
piki check
```

预期输出：

```
[PASS] TELECOM-POWER-001: PDU 功率预算检查
[PASS] TELECOM-RACK-001: U 位冲突检查
[PASS] TELECOM-RACK-002: 机柜容量检查
[PASS] TELECOM-FK-001: 外键完整性检查
============================================================
总计: 0 错误, 0 警告, 4 通过
============================================================
```

## 你学到了什么

- Instance / Layout 分离：设备身份和部署决策在两个独立文件中
- Schema 自动校验字段类型、范围、必填项
- 外键引用自动检查（rack_id → racks/xxx, pdu_id → pdus/xxx）
- 无需编写任何自定义规则，基础校验已内置
