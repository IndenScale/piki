# 10 分钟上手

> 从一个真实问题出发，用 piki 在 10 分钟内建立你的第一个声明式建模项目。
>
> 你将用 YAML **声明**设计意图，让规则引擎自动检查合理性。

## 场景

你管理一个小型机房，机柜 `RACK-A01` 里已有 2 台服务器：

| 设备 | 功耗 | 位置 |
|------|------|------|
| `SRV-01` | 300W | U10-U11 |
| `SRV-02` | 250W | U8-U9 |

PDU-A 额定容量 2000W，当前负载 550W（27.5%），看起来安全。

现在你要新增一台 `SRV-03`（400W，放在 U6-U7），接 PDU-A。你检查了 U 位，没有冲突。但**你忘了算功率**——新增后 PDU-A 负载变成 950W，虽然没到 2000W，但如果未来还要扩容，余量已经不足。

piki 要帮你：**在提交设计前，自动发现这个问题。**

## 步骤 1：安装 piki

```bash
pip install piki
```

`piki` 包含核心框架和内置的 `telecom` 等行业插件，提供机柜、设备、PDU 等模型。

## 步骤 2：初始化项目

```bash
mkdir my-datacenter
cd my-datacenter
piki init --plugin telecom
```

这会创建目录结构：

```
my-datacenter/
├── piki.toml           # 项目元数据：根目录声明、插件启用、型号引用
├── library/            # 型号库（厂商规格）
│   └── devices/
│       └── generic-server.yaml
├── racks/              # 机柜数据
│   └── RACK-A01.yaml
├── pdus/               # PDU 数据
│   ├── PDU-A.yaml
│   └── PDU-B.yaml
├── devices/            # 设备数据
│   ├── SRV-01.yaml
│   └── SRV-02.yaml
└── rules/              # 检查规则
    └── power.py
```

`piki.toml` 是项目元数据文件，**声明**三件事：

1. **项目根目录**：piki 从该文件所在目录开始扫描所有数据
2. **启用哪些行业插件**：如 `telecom`、`construction`
3. **引用哪些型号库**：插件自带的 + 项目本地 `library/` 的

```toml
# piki.toml
[project]
name = "my-datacenter"
version = "1.0.0"

[plugins]
enabled = ["telecom"]

[plugins.telecom]
power_threshold = 0.4
rack_usage_threshold = 0.8
```

## 步骤 3：录入现有设施（Brown Field）

先记录机柜：

```yaml
# racks/RACK-A01.yaml
id: RACK-A01
family: RackFamily
name: 主列头柜-A01
location: 机房A-A列
total_u: 42
power_capacity_w: 2000
```

再记录已有设备：

```yaml
# devices/SRV-01.yaml
id: SRV-01
name: 服务器-01
model: generic-server
status: installed
rack_id: RACK-A01
position_u: 10
pdu_id: PDU-A
```

```yaml
# devices/SRV-02.yaml
id: SRV-02
name: 服务器-02
model: generic-server
status: installed
rack_id: RACK-A01
position_u: 8
pdu_id: PDU-A
```

型号库定义了 `generic-server` 的规格：

```yaml
# library/devices/generic-server.yaml
model: generic-server
family: ServerFamily

physical:
  height_u: 2

power:
  tdp_w: 300        # 默认值，实例可覆盖
  psu_count: 1
  psu_redundancy: false
```

注意：`SRV-02` 实际功耗是 250W，不是型号库的 300W。我们可以在实例中覆盖：

```yaml
# devices/SRV-02.yaml（覆盖功耗）
id: SRV-02
name: 服务器-02
model: generic-server
status: installed
rack_id: RACK-A01
position_u: 8
pdu_id: PDU-A

# 覆盖型号库的默认值
tdp_w: 250
```

## 步骤 4：编写新增方案

```yaml
# devices/SRV-03.yaml
id: SRV-03
name: 服务器-03
model: generic-server
status: planned        # 状态：planned（计划中）
rack_id: RACK-A01
position_u: 6
pdu_id: PDU-A

tdp_w: 400            # 这台功耗更高
```

## 步骤 5：运行检查

```bash
piki check
```

输出：

```
[PASS] TELECOM-POWER-001: PDU 功率预算检查
[PASS] TELECOM-RACK-001: U 位冲突检查
[PASS] TELECOM-RACK-002: 机柜容量检查
[FAIL] TELECOM-FK-001: 外键完整性检查
       PDU-A 负载率 47.5%（950W / 2000W），超过项目阈值 40.0%。已接入设备: SRV-01, SRV-02, SRV-03

============================================================
总计: 1 错误, 1 警告, 3 通过
============================================================
```

**piki 发现了问题**：PDU-A 负载率 47.5%，虽然没超过物理上限 80%，但超过了项目设定的阈值 40%。

## 步骤 6：修正并重新检查

把 `SRV-03` 改接到 PDU-B：

```yaml
# devices/SRV-03.yaml（修正后）
id: SRV-03
name: 服务器-03
model: generic-server
status: planned
rack_id: RACK-A01
position_u: 6
pdu_id: PDU-B        # 改接 PDU-B

tdp_w: 400
```

```bash
piki check
```

输出：

```
[PASS] TELECOM-POWER-001: PDU 功率预算检查
[PASS] TELECOM-RACK-001: U 位冲突检查
[PASS] TELECOM-RACK-002: 机柜容量检查
[WARN] TELECOM-FK-001: 外键完整性检查

============================================================
总计: 0 错误, 1 警告, 3 通过
============================================================
```

## 步骤 7：提交到 Git

```bash
git add .
git commit -m "feat: 新增 SRV-03 服务器

- 型号: generic-server
- 位置: RACK-A01 U6-U7
- 功耗: 400W
- 接入: PDU-B（避免 PDU-A 过载）

piki check: 全部通过"
```

然后推送到 review 分支，等待同事审核：

```bash
git push origin HEAD:review/srv-03-addition
```

同事在 Pull Request 中看到：

- 变更的 YAML 文件
- piki 检查报告（全部通过）
- 设计意图（commit message 中的完整说明）

审核通过后，合并到 `main` 分支，再推送到交底分支：

```bash
git checkout main
git merge review/srv-03-addition
git push origin main:handover/2024-Q2-expansion
```

## 你做了什么

| 步骤 | 动作 | piki 的作用 |
|------|------|------------|
| 1 | 安装 | 提供声明式建模框架 + 行业插件 |
| 2 | 初始化 | 创建标准目录结构 |
| 3 | 录入现有设施 | 声明基准状态（brown field） |
| 4 | 编写方案 | 声明设计意图，规格自动补齐 |
| 5 | 运行检查 | **自动发现 PDU 过载风险** |
| 6 | 修正 | 根据反馈调整声明 |
| 7 | 提交 | Git 记录完整设计演进 |

> **💡 不想一步步手动创建？** 完整的示例项目已准备好，直接体验：
>
> ```bash
> cd samples/02-telecom-rack
> piki check
> ```
>
> 或从最小示例开始：
> ```bash
> cd samples/01-hello-piki
> piki check
> ```

## 下一步

- [了解核心概念 →](02-core-concepts.md)
- [学习写规则 →](03-writing-rules.md)
- [查看更多示例 →](../../samples/)
