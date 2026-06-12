# 03-data-center — 多机柜数据中心

> 三个机柜、五台服务器、双路 PDU，演示自定义规则、报告生成和 Tag 机制。
> 演示 ADR-008 Instance/Layout 分离 + ADR-009 Tag 过滤。

## 场景

小型数据中心有 3 个机柜（RACK-A01、RACK-A02、RACK-B01），每个机柜双路 PDU（L1/L2）。你负责确保：

1. 每台服务器至少接入 2 路 PDU（冗余）
2. 同一功能组的服务器不在同一机柜（防单点故障）
3. 命名规范：`SRV-{机柜}-{序号}`

## 项目结构

```
03-data-center/
├── piki.toml                    # 项目配置 + Tag 声明
├── models/
│   └── devices/
│       ├── generic-server.yaml
│       └── high-density-server.yaml
├── racks/                       # 机柜数据
│   ├── RACK-A01.yaml
│   ├── RACK-A02.yaml
│   └── RACK-B01.yaml
├── pdus/                        # PDU 数据（双路）
│   ├── PDU-A01-L1.yaml
│   ├── PDU-A01-L2.yaml
│   ├── PDU-A02-L1.yaml
│   ├── PDU-A02-L2.yaml
│   ├── PDU-B01-L1.yaml
│   └── PDU-B01-L2.yaml
├── instances/                   # 设备身份
│   ├── SRV-A01-01.yaml
│   ├── SRV-A01-02.yaml
│   ├── SRV-A01-03.yaml
│   ├── SRV-A02-01.yaml
│   └── SRV-B01-01.yaml
├── layouts/
│   └── layout.yaml              # 部署决策
└── rules/                       # 项目自定义规则
    ├── cross_rack.py            # 跨机柜分布检查（Tag 过滤）
    ├── naming.py                # 命名规范检查（Layout 查询）
    └── redundancy.py            # 多 PDU 冗余检查
```

## 运行

```bash
cd samples/03-data-center
piki check
```

预期输出（可能存在相不平衡和 3D 碰撞警告）：

```
============================================================
总计: 0 错误, 10 通过
============================================================
```

## Tag 机制示例

本项目在 `piki.toml` 中声明了允许的 Tag 键：

```toml
[tags]
allowed = ["discipline", "security_zone", "system"]
```

实例文件中使用 Tags：

```yaml
# instances/SRV-A01-01.yaml
id: SRV-A01-01
name: 计算节点-A01-01
model: generic-server
status: installed
tags:
  discipline: compute
  security_zone: standard
  system: web-tier
```

自定义规则可按 Tag 过滤查询：

```python
# rules/cross_rack.py
# 查询所有 system=web-tier 的设备
web_servers = ctx.query("devices", tags__system="web-tier")
```

## 生成报告

```bash
piki report --format markdown
piki report --format json
```

## 你学到了什么

| 能力 | 说明 |
|------|------|
| Tag 机制 | 正交维度标签（专业/安全分区/系统），支持按 Tag 过滤 |
| 自定义规则 | Python 函数表达业务规则，`@rule` 装饰器注册 |
| 命名规范 | 利用正则和 Layout 查询验证命名约定 |
| 报告生成 | markdown / json / junit / human 四种格式 |
| 多 PDU 冗余 | 跨机柜双路配电检查 |
