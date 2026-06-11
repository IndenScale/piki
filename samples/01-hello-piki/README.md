# 01-hello-piki — 最小工作示例

> 最简单的 piki 项目：一台服务器，验证 Schema 合规性和外键完整性。

## 场景

你有一台服务器 `SRV-01`，放在机柜 `RACK-DEMO` 的 U10 位置，接入 PDU `PDU-DEMO`。想验证数据格式是否正确、外键引用是否有效。

## 项目结构

```
01-hello-piki/
├── piki.toml           # 项目配置
├── racks/
│   └── RACK-DEMO.yaml  # 机柜
├── pdus/
│   └── PDU-DEMO.yaml   # PDU
└── devices/
    └── SRV-01.yaml     # 服务器
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

## 故意制造一个 Schema 错误

把 `position_u` 改成 `51`（超过机柜最大 48U）：

```yaml
# devices/SRV-01.yaml
position_u: 51   # 错误：超出范围 1-48
```

重新运行 `piki check`，你会看到 Schema 校验失败。

## 故意制造一个外键错误

把 `rack_id` 改成不存在的机柜：

```yaml
# devices/SRV-01.yaml
rack_id: RACK-NOT-EXIST   # 错误：引用的机柜不存在
```

重新运行 `piki check`，外键完整性检查会失败。

## 你学到了什么

- piki 项目只需要 `piki.toml` + 数据文件
- Schema 自动校验字段类型、范围、必填项
- 外键引用自动检查（rack_id → racks/xxx, pdu_id → pdus/xxx）
- 无需编写任何自定义规则，基础校验已内置
