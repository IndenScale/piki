# ADR-009: 嵌套项目结构与共享数据环境

> 状态：草案  
> 日期：2026-06-11  
> 作者：piki 核心团队

## 背景

ADR-008 将 Instance 与 Layout 分离，Layout 文件是给定范围内唯一的部署真相源。但"范围"的粒度是什么？

真实工程中，一个厂区可能跨越多个物理区域（安全壳内/外、不同建筑、不同楼层），同时跨越多个管理维度（专业、标段、安全等级）。传统 BIM 和 PLM 工具通常强制选择单一维度作为项目划分依据，导致交叉维度的信息断裂。

本 ADR 记录 piki 对项目层级、嵌套结构、以及共享数据环境的组织决策。

---

## 1. 核心决策一：支持嵌套项目

### 1.1 定义

piki 项目可以嵌套。一个项目可以包含子项目，子项目继承父项目的配置、型号库和 Instance，并可覆盖参数。

```text
厂区/                          ← 根项目
├── piki.toml
├── library/                   ← 全厂共享型号
├── instances/                 ← 全厂共享设备
│
├── 安全壳内/                  ← 子项目
│   ├── piki.toml              ← 覆盖：抗震等级 9，屏蔽要求
│   ├── layouts/
│   │   └── building-a/
│   │       └── floor-2/
│   │           └── layout.yaml
│   │
│   └── 1号楼/                 ← 孙项目
│       ├── piki.toml          ← 覆盖：层高、荷载
│       ├── instances/         ← 1号楼特有设备
│       └── layouts/
│           └── floor-1/
│               └── layout.yaml
│
├── 安全壳外/
│   ├── piki.toml              ← 覆盖：抗震等级 7，无不屏蔽
│   └── ...
│
└── 七通一平/
    ├── piki.toml              ← 覆盖：土建参数
    └── ...
```

### 1.2 继承规则

| 资源 | 继承行为 |
|------|---------|
| `piki.toml` 参数 | 子项目合并父项目参数，同名字段覆盖 |
| `library/` 型号 | 子项目可见父项目所有型号；子项目可追加自己的型号 |
| `instances/` | 子项目可见父项目所有 Instance；子项目可追加自己的 Instance |
| Layout | 不继承（每个子项目的 Layout 是独立的） |
| 规则 | 父项目启用的插件和规则自动应用于子项目 |

### 1.3 嵌套 vs 扁平

| 场景 | 推荐结构 |
|------|---------|
| 小型机房（< 100 设备） | 单层项目，不嵌套 |
| 中型数据中心（按楼层分） | 根项目 + 楼层子项目 |
| 大型厂区（按建筑/安全边界分） | 根项目 + 建筑子项目 + 楼层孙项目 |

嵌套不是强制要求。项目可以从单层开始，需要时再拆分子项目。

---

## 2. 核心决策二：物理空间作为主划分维度

### 2.1 共享数据环境设计

本 ADR 借鉴 BIM 标准（ISO 19650）中 **CDE**（Common Data Environment）的概念——项目中所有工程信息的单一访问环境——但不做完整实现。piki 的共享数据环境就是项目的文件树，借助 Git 仓库承载。**piki 不实现 CDE 状态机**（WIP → Shared → Published）、审批流或版本锁定——这些由工程团队的现有 CDE 平台负责。

piki 只负责：确保自身数据模型能够清晰映射到任何 CDE 的文件夹结构中，并被 CDE 的版本管理机制覆盖。

### 2.2 为什么物理空间是主维度

工程设计中，四个维度同时存在且互相交叉：

```
专业        ← 一个设备属于结构/暖通/电气
物理空间     ← 一个设备在 1号楼 2层 B区
安全边界     ← 安全壳内还是壳外
行政管辖     ← 合同包 1、标段 A、EPC 总包
```

其中，**物理空间是唯一不以人的意志为转移的维度**：

- 专业可以重组（合并团队）
- 安全边界可以重划（退役后壳内变壳外）
- 标段可以重签（合同变更）
- **物理空间不可变**：重力方向、电磁传播路径、振动耦合不以管理决策改变

物理临近意味着**必然的物理干涉**——两台设备在同一层，不管属于哪个专业、哪个标段，它们的振动、热量、电磁干扰就会互相影响。因此：

> **Layout 文件的物理空间组织不是偏好选择，是对物理现实的忠实映射。**

### 2.3 目录组织

```
项目根/                          ← 数据环境根
├── piki.toml
├── library/                     ← 共享型号库
├── instances/                   ← 全局共享 Instance
│
├── containment/                 ← 按安全边界分（物理空间内的第一级）
│   └── building-a/              ← 按建筑分
│       └── floor-2/             ← 按楼层分
│           ├── piki.toml
│           ├── layouts/
│           │   └── layout.yaml  ← 该层唯一 layout（每个子项目一个 Layout 文件）
│           └── instances/       ← 该层特有设备
│
├── non-containment/
│   └── building-a/              ← 同一建筑可能在壳内和壳外都有区域
│       └── floor-6/             ← 6-8 层是壳外
│           └── ...
│
└── site-prep/                   ← 七通一平
    ├── roads/
    └── utilities/
```

物理空间层级：**安全边界（如有） > 建筑 > 楼层 > 房间**。安全边界只在核/化工厂等场景存在第一级意义，普通建筑直接从建筑开始。

嵌套深度不做硬性上限。真实项目的物理层级可能超过 4 层（例如核电站的 containment > building > level > room > sub-room）。当嵌套深度导致目录结构难以管理时，建议将更深层级用 Tag 而非目录表达。

---

## 3. 核心决策三：其他维度使用自定义 Tag 管理

### 3.1 Tag 机制

Instance 通过 `tags` 字段声明其在非空间维度上的归属：

```yaml
# instances/SRV-01.yaml
id: SRV-01
model: pump-model-x

tags:
  discipline: "hvac"              # 专业
  security_zone: "containment"    # 安全边界（与文件路径冗余但语义独立）
  contract_package: "pkg-1"       # 标段
  system: "chilled-water-loop-a"  # 系统/回路
  phase: "phase-2"                # 建设阶段
```

Tag 是键值对，键和值都由项目自定义。piki 不预定义 Tag 语义，只提供查询接口。

### 3.2 Tag vs 物理空间

| 维度 | 表达方式 | 原因 |
|------|---------|------|
| 物理空间 | 文件路径 | 主键，决定 Layout 归属和文件组织 |
| 专业 | `tags.discipline` | 正交标签 |
| 安全边界 | `tags.security_zone` | 正交标签（可与物理空间冗余，语义独立） |
| 标段 | `tags.contract_package` | 正交标签 |
| 系统/回路 | `tags.system` | 正交标签 |

物理空间决定"这个 Instance 放在哪个 layout 文件里"。标签决定"这个 Instance 被哪些规则检查、被哪些视图筛选"。

### 3.3 规则按 Tag 触发

```python
# 安全壳内的暖通设备：抗震等级 ≥ 9 度
@rule("NUCLEAR-SAFETY-001")
def check_containment_hvac(ctx: Context):
    instances = ctx.query(
        tags__security_zone="containment",
        tags__discipline="hvac"
    )
    for i in instances:
        assert i.resolved.seismic_rating >= 9, \
            f"{i.id} 安全壳内暖通设备抗震等级不足"

# 标段交叉电源引用检查
@rule("CONTRACT-001")
def check_cross_package_power(ctx: Context):
    pkg1 = ctx.query(tags__contract_package="pkg-1")
    pkg3 = ctx.query(tags__contract_package="pkg-3")
    # 检查 pkg3 的设备是否错误引用了 pkg1 的电源
```

规则的触发条件不是"在这个目录下"，而是"匹配这个 Tag 组合"。规则不关心文件在哪。

---

## 4. Layout 文件在嵌套项目中的行为

### 4.1 Layout 不跨项目继承

每个子项目有独立的 Layout 文件。Layout 只描述该项目物理空间内的部署决策。每个子项目只有一个 Layout 文件（详见 ADR-008）。

### 4.2 Layout 可以引用父项目的 Instance

```yaml
# 安全壳内/building-a/floor-2/layouts/layout.yaml
- instance: SRV-01          # SRV-01 在父项目 instances/ 中定义
  rack_id: RACK-A01
  position_u: 10
  pdu_id: PDU-A

- instance: FLOOR-2-PUMP-01 # 在 floor-2/instances/ 中定义
  grid_id: B-3
```

Instance 解析顺序：当前项目 → 父项目 → 根项目。找到即停。

---

## 5. 跨仓库 Instance 引用

### 5.1 问题

EPC 项目中，不同分包商通常有自己的 Git 仓库。若分包商 A 的设备需要被分包商 B 的 Layout 引用，仅靠相对路径无法完成跨仓库引用。

### 5.2 方案：`$PROJECT_ROOT` 变量 + Git Submodule

piki 支持在 Instance 引用路径中使用 `$PROJECT_ROOT` 变量，指向当前项目的根目录。结合 Git Submodule，可以引用其他仓库中的 Instance：

```bash
# 主项目引用分包商仓库
git submodule add git@gitlab.com:epc/power-systems.git vendor/power-systems
```

```yaml
# layouts/layout.yaml 中引用分包商设备
- instance: $PROJECT_ROOT/vendor/power-systems/instances/UPS-01
  rack_id: RACK-A01
  position_u: 1
```

`PathResolver` 解析顺序：
1. 优先解析相对路径和 `$PROJECT_ROOT` 变量
2. 若路径指向 Submodule，自动进入子仓库解析
3. 若找不到，fallback 到当前项目的 `instances/` 目录

### 5.3 piki.toml 中的外部项目注册

对于非 Submodule 的外部项目（例如网络共享路径或工件仓库），可以在 `piki.toml` 中注册：

```toml
[external]
power-systems = "/network/epc-project/power-systems"
vendor-models = "https://artifacts.epc.com/models/v2/"
```

---

## 6. 影响与权衡

### 6.1 有利影响

- **多维度正交表达**：物理空间做文件组织，其他维度做 Tag，不互相污染
- **物理现实映射**：Layout 按空间组织，物理耦合在同一个 Layout 文件中可检查
- **渐进式复杂度**：小型项目不嵌套；需要时再拆分
- **Git 天然适合嵌套**：Monorepo 或 Submodule 都可以承载嵌套项目
- **跨仓库协作**：`$PROJECT_ROOT` 和 Submodule 支持多分包商场景

### 6.2 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 嵌套过深导致复杂度爆炸 | 不设硬上限，但建议超过物理合理层级时用 Tag 补充 |
| Tag 命名不一致 | `piki check` 增加 Tag schema 检查（L2）；提供 `piki.toml` 中定义允许的 Tag 键 |
| Instance 跨项目引用歧义 | Instance ID 在项目树内唯一；全限定 ID = `父项目/子项目/id` |
| 子项目依赖父项目 Instance 被删 | L2 引用完整性检查覆盖跨项目引用 |
| 跨仓库引用路径失效 | `$PROJECT_ROOT` 变量解析 + L2 检查 + `piki check` 报告断链 |

---

## 7. 与其他 ADR 的关系

| ADR | 关系 |
|-----|------|
| ADR-002（一实例一文件） | 嵌套不改变"每个 Instance 一个文件"的原则 |
| ADR-003（插件架构） | 插件在根项目启用，子项目自动继承 |
| ADR-004（多级质量检查） | L2 检查覆盖跨项目引用完整性 |
| ADR-008（Instance/Layout 分离） | 分离后的 Layout 在子项目级别独立，每个子项目一个 Layout 文件；Instance 可跨项目引用 |
