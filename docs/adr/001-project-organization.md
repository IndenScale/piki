# ADR-001: 项目组织模型——嵌套结构、物理空间与正交标签

> 状态：已实现（基础完成）
> 日期：2026-06-12
> 作者：piki 核心团队
> 替代：ADR-008（Instance/Layout 分离）、ADR-009（嵌套项目与 CDE）

## 背景

piki 的核心数据单元是声明式 YAML。但数据如何组织成项目、项目之间如何嵌套、多维度信息如何不互相污染——这些结构决策影响每一条规则、每一个文件、每一次 Git 操作。

本 ADR 记录三个关联决策：Instance 与 Layout 分离、嵌套项目结构、Tag 正交维度。

---

## 1. Instance 与 Layout 分离

### 1.1 问题

设计数据天然包含两类信息：

| 信息类型 | 内容 | 变更频率 | 变更原因 |
|----------|------|---------|---------|
| **Instance 自身属性** | 型号、功耗、固资编号 | 低 | 更换型号、改配置 |
| **Layout 部署决策** | 放哪个机柜、哪个 U 位、接哪个 PDU | 高 | 方案比选、布局优化 |

两类信息缝在同一文件里导致：方案比选需要复制 Instance 文件、协作冲突发生在不相关维度、Instance 无法跨项目复用。

### 1.2 决策：分离为两个独立概念层

```yaml
# instances/SRV-01.yaml  ← 只声明"这台设备是什么"
id: SRV-01
model: generic-server
tdp_w: 250
```

```yaml
# layouts/room-1/layout.yaml  ← 只声明"放哪、接哪"
- instance: SRV-01
  rack_id: RACK-A01
  position_u: 10
  pdu_id: PDU-A
```

每个子项目只有一个 Layout 文件。方案比选不维护多份 Layout 文件，而是通过 Git 分支承载：`git diff main..design-v2` 精确显示布局层的变化，不被 Instance 自身属性的不变字段污染。

### 1.3 为什么不在项目内维护多 Layout 文件

物理空间是天然的 sharding key。同一空间内的物理耦合（振动、热量、电磁）必须在一个 Layout 文件中检查，拆散会丢失空间上下文。Layout 文件内允许按 discipline 分 section 以支持不同专业，但文件级别仍是一个。

---

## 2. 嵌套项目结构

### 2.1 为什么需要嵌套

真实工程中，一个厂区跨越多个物理区域（建筑、楼层、安全边界），同时跨越多个管理维度（专业、标段）。传统 BIM 工具强制选单一维度作项目划分，导致交叉维度信息断裂。

piki 选择**支持嵌套项目**，物理空间作为文件组织的主维度：

```text
厂区/                          ← 根项目
├── piki.toml
├── models/                    ← 全厂共享型号
├── instances/                 ← 全厂共享设备
│
├── 安全壳内/                  ← 子项目
│   ├── piki.toml              ← 覆盖：抗震等级 9
│   ├── layouts/
│   └── 1号楼/                 ← 孙项目
│       ├── piki.toml
│       └── layouts/
│
├── 安全壳外/
│   └── ...
```

**继承规则**：子项目合并父项目的 piki.toml 参数、型号库、实例（同名覆盖）。Layout 不继承——每个子项目的布局独立。插件和规则自动应用于子项目。

### 2.2 为什么物理空间是主维度

四个管理维度同时存在：专业、物理空间、安全边界、行政管辖。

其中，**物理空间是唯一不以人的意志为转移的维度**。重力方向、电磁传播路径、振动耦合不以管理决策改变。物理临近意味着必然的物理干涉。

Layout 文件的物理空间组织不是偏好选择，是对物理现实的忠实映射。

---

## 3. Tag：正交维度标签

### 3.1 问题

物理空间做了文件组织。那专业、标段、安全分区这些正交维度如何表达？

### 3.2 决策：键值对标签，与物理空间独立

```yaml
# instances/SRV-01.yaml
tags:
  discipline: "compute"
  security_zone: "dmz"
  contract_package: "pkg-1"
  system: "web-cluster-a"
```

| 维度 | 表达方式 | 原因 |
|------|---------|------|
| 物理空间 | 文件路径 | 主键，决定 Layout 归属 |
| 专业/标段/系统 | `tags.*` | 正交标签，不与物理空间耦合 |

规则按 Tag 触发而非按目录：

```python
@rule("NUCLEAR-SAFETY-001")
def check_containment_hvac(ctx: Context):
    instances = ctx.query(
        tags__security_zone="containment",
        tags__discipline="hvac"
    )
```

### 3.3 为什么不用目录表达正交维度

如果用目录表达专业归属（`instances/compute/SRV-01.yaml`），一台设备的物理空间归属（文件路径）和专业归属就被捆绑了。当同一台设备同时属于"计算专业"和"安全壳内"，只能二选一，或者制造冗余目录。Tag 允许任意多个正交维度同时存在而不互相污染。

---

## 4. 跨仓库 Instance 引用

EPC 项目中，不同分包商有自己的 Git 仓库。piki 支持通过 `$PROJECT_ROOT` 变量 + Git Submodule 实现跨仓库引用：

```yaml
# 主项目 layout.yaml 引用分包商设备
- instance: $PROJECT_ROOT/vendor/power-systems/instances/UPS-01
  rack_id: RACK-A01
  position_u: 1
```

对于非 Submodule 的外部项目，可在 `piki.toml` 中注册：

```toml
[external]
power-systems = "/network/epc-project/power-systems"
```

---

## 5. 决策总结

| 决策 | 选择 | 核心理由 |
|------|------|----------|
| Instance/Layout 关系 | 分离为两个独立层 | 方案比选 = Git 分支；协作解耦 |
| 项目结构 | 支持嵌套，物理空间作主维度 | 物理现实不可变，映射忠实 |
| 正交维度 | Tag 键值对 | 不与物理空间耦合，支持任意多维度 |
| 跨仓库协作 | `$PROJECT_ROOT` + Submodule | Git 原生支持，不引入新协议 |

---

## 参考

- [Layout 格式规范](../reference/05-layout.md)
- [Instance 格式规范](../reference/04-instance.md)
- [项目目录结构](../reference/00-project-layout.md)
