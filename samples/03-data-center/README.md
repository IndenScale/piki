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
├── library/
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
├── instances/                   # 设备身份（ADR-008）
│   ├── SRV-A01-01.yaml
│   ├── SRV-A01-02.yaml
│   ├── SRV-A01-03.yaml
│   ├── SRV-A02-01.yaml
│   └── SRV-B01-01.yaml
├── layouts/
│   └── layout.yaml              # 部署决策（ADR-008）
└── rules/                       # 自定义规则
    ├── redundancy.py            # 冗余检查
    ├── cross_rack.py            # 跨机柜分布
    └── naming.py                # 命名规范
```

### ADR-009 Tag 机制

Instance 文件使用 Tag 标记设备和专业属性：

```yaml
# instances/SRV-A01-01.yaml
id: SRV-A01-01
name: 计算节点-A01-01
model: generic-server
status: installed
tags:
  discipline: compute           # 专业：计算
  security_zone: standard       # 安全分区
  system: web-tier              # 所属系统
```

Tag 在 `piki.toml` 中声明允许的键：

```toml
[tags]
allowed = ["discipline", "security_zone", "system", "contract_package", "phase"]
```

规则通过 Tag 过滤目标设备：

```python
# rules/redundancy.py
@rule("DC-REDUNDANCY-001", "双路 PDU 冗余检查")
def check_dual_pdu(ctx: Context):
    compute_servers = ctx.query(
        "instances", tags__discipline="compute"
    )
    for srv in compute_servers:
        entry = ctx.layout_entry(srv.id)
        ...
```

## 运行

```bash
cd samples/03-data-center
piki check
```

## 你学到了什么

| 能力 | 说明 |
|------|------|
| Instance/Layout 分离 | 设备在 `instances/`，部署在 `layouts/` |
| Tag 机制 | `tags.discipline`、`tags.security_zone` 等正交维度标签 |
| Tag 过滤查询 | `ctx.query("instances", tags__discipline="compute")` |
| 自定义规则 | `rules/` 目录下 Python 规则，`@rule` 装饰器注册 |
| 冗余检查 | 验证每个设备至少接入 N 路 PDU |
| 跨机柜分布 | 确保同功能组设备不在同一机柜 |
| 报告生成 | `piki report` 输出多格式报告 |
