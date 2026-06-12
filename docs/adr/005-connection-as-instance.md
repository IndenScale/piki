# ADR-005: 连接关系实例化与接口模型

> 状态：已实现
> 日期：2026-06-12
> 作者：piki 核心团队

## 背景

piki 的核心三层模型（Family → Model → Instance）已覆盖设备、方舱、配电单元等实体对象。
但**连接关系**和**可连接接口**尚未作为一等概念建模：

| 维度 | 现状 | 问题 |
|------|------|------|
| 连接关系 | `LayoutEntry.connections` 字段解析后被丢弃；仅 datacenter 的 `ConnectionFamily` 走 Instance 模型 | 无通用框架支持 |
| 可连接接口 | 不存在 | 端口类型兼容性无法校验 |
| 引用语法 | 无 | 无法表达"SRV-01 的 eth0 端口" |

本 ADR 引入 **Interface（接口）** 和 **Connection（连接）** 作为框架级一等概念，对齐 EDA netlist / MCAD assembly mates 等行业标准。

---

## 1. 核心概念

```
┌─────────────────────────────────────────────────────┐
│                    Instance                         │
│  ┌───────────────────────────────────────────────┐  │
│  │              Interface (可连接点)               │  │
│  │  - 我有什么接口？什么类型？什么规格？             │  │
│  └──────────────────┬────────────────────────────┘  │
│                     │ 引用 SRV-01/eth0               │
│                     ▼                                │
│            ┌───────────────┐                         │
│            │  Connection   │  ← 独立 Instance        │
│            │  两个 Interface│                         │
│            │  之间的连接关系 │                         │
│            └───────────────┘                         │
└─────────────────────────────────────────────────────┘
```

| 概念 | 是什么 | 谁定义 | 存在形式 |
|------|--------|--------|---------|
| **Interface** | Instance 对外暴露的可连接点 | 设备（Family 约束 + Instance 赋值） | 内嵌在 Instance 的 `interfaces` 列表中 |
| **Connection** | 两个 Interface 之间的连接关系 | 连接本身（独立 Instance） | 独立的 YAML 文件，走 Family → Model → Instance |

---

## 2. Interface：可连接接口

### 2.1 设计原则

1. **内嵌，不独立**：Interface 依附于 Instance，不作为独立 Instance。和 ADR-007 "引用而非嵌入" 策略一脉相承——Instance 声明自己有什么接口，但不负责连接逻辑。
2. **离散化**：每个 Interface 都是离散的、可枚举的点。连续接口（面贴面焊接、管道沿线焊缝）不在本 ADR 范围内。
3. **类型化**：每个 Interface 有 `interface_type`，两个 Interface 能否连接取决于类型兼容性。

### 2.2 Schema

```python
class InterfaceSpec(BaseModel):
    """Instance 对外暴露的可连接点。"""
    id: str                             # 在 Instance 内唯一：eth0, power-a, hole-3
    interface_type: str                 # SFP28 / IEC-C14 / M16-bolt-hole / RJ45 / UQD
    direction: str = "bidirectional"    # input | output | bidirectional
    description: str = ""              # 人类可读描述

    # 接口自身的规格参数（自由扩展，由领域插件定义约束）
    specs: dict[str, Any] = Field(default_factory=dict)
```

### 2.3 在 Family 中的使用

```python
class ServerFamily(BaseModel):
    id: str
    interfaces: list[InterfaceSpec] = Field(default_factory=list)
    # 其他字段 ...
```

### 2.4 在 Instance 中的使用

```yaml
# instances/devices/SRV-01.yaml
id: SRV-01
family: ServerFamily
model: generic-server
interfaces:
  - id: eth0
    interface_type: SFP28
    direction: bidirectional
    description: "管理网口，后侧左 1"
  - id: eth1
    interface_type: SFP28
    direction: bidirectional
    description: "业务网口，后侧右 1"
  - id: power-a
    interface_type: IEC-C14
    direction: input
```

---

## 3. Connection：连接关系

### 3.1 设计原则

1. **连接是一等 Instance**：走完整 Family → Model → Instance 生命周期。
2. **引用 Interface 而非 Instance**：`from: SRV-01/eth0` 而不是 `from: SRV-01`。精确到接口级别。
3. **领域自描述**：每个领域插件定义自己的 Connection Family。框架不定义 `ConnectionFamily` 基类。
4. **与 Layout 正交**：Layout 只管物理放置，Connection 只管拓扑。

### 3.2 Schema（示例：光纤连接）

```python
class FiberConnectionFamily(BaseModel):
    id: str
    from_interface: str       # "SRV-01/eth0"
    to_interface: str         # "SW-01/Gi1-0-1"
    cable_type: str           # OM4-LC-LC
    length_m: float
    attenuation_db: float = Field(default=0.3)
    status: str = "planned"
```

### 3.3 Instance 文件

```yaml
# instances/connections/FIBER-S01-SW01.yaml
id: FIBER-S01-SW01
family: FiberConnectionFamily
from_interface: SRV-01/eth0
to_interface: SW-01/Gi1-0-1
cable_type: OM4-LC-LC
length_m: 12.5
status: installed
```

---

## 4. 引用语法：`instance_id/interface_id`

### 4.1 路径解析

| 引用 | 解析结果 |
|------|---------|
| `SRV-01/eth0` | Instance `SRV-01` 的 Interface `eth0` |
| `ODF-A01/P24` | Instance `ODF-A01` 的 Interface `P24` |

### 4.2 FK-001 增强

通用外键检查规则 FK-001 感知 `/` 语法：

1. 检查 `SRV-01` 是否存在
2. 检查 `SRV-01` 是否声明了名为 `eth0` 的 Interface
3. 任意一步失败 → 报告外键错误

```python
def check_foreign_keys(ctx):
    for inst in ctx.instances():
        for field_name, field_value in inst._resolved.items():
            if field_name.endswith("_interface") and "/" in field_value:
                instance_id, interface_id = field_value.split("/", 1)
                target = ctx.find_instance(instance_id)
                assert target is not None, f"引用的 Instance '{instance_id}' 不存在"
                interfaces = {i.id for i in safe_get_interfaces(target)}
                assert interface_id in interfaces, \
                    f"Instance '{instance_id}' 无 Interface '{interface_id}'"
```

---

## 5. 接口兼容性检查

新增内置规则 `INTERFACE-COMPAT-001`：

> 对于每条 Connection，检查 `from_interface` 和 `to_interface` 的 `interface_type` 是否一致。

```python
def check_interface_compatibility(ctx):
    for conn in ctx.query("connections"):
        from_iface = resolve_interface(ctx, conn.from_interface)
        to_iface = resolve_interface(ctx, conn.to_interface)
        assert from_iface.interface_type == to_iface.interface_type, \
            f"接口类型不兼容: {conn.from_interface} ({from_iface.interface_type}) "
            f"vs {conn.to_interface} ({to_iface.interface_type})"
```

注意：某些领域可能有"适配器"概念（SFP28 → RJ45 光电转换模块），适配器本身是一个 Instance，它有两个不同类型的 Interface，分别连接两侧。这不是规则违规，而是设计意图。

---

## 6. 框架层改造

### 6.1 废弃 `LayoutEntry.connections`

- 保留字段以兼容旧数据，标记 `DeprecationWarning`
- `to_flat()` 不再合并连接信息

### 6.2 Registry 加载不变

`instances/connections/` 与 `instances/devices/` 无差别加载——任何合法 Family 的 YAML 均按相同流程解析。

### 6.3 新增内置规则

| 规则 ID | 说明 | 自动运行 |
|---------|------|---------|
| `FK-001` | 通用外键引用完整性（含 `instance_id/interface_id` 路径解析） | L2 |
| `INTERFACE-COMPAT-001` | 接口类型兼容性 | L2 |

---

## 7. 搜索路径与接口枚举

**不在本 ADR 范围内。** 搜索路径的定义（如接口的物理位置、枚举值的含义等）留给后续 ADR 或领域插件自行处理。

---

## 8. 范围边界

### 本 ADR 覆盖

- ✅ 离散 Interface 的定义与内嵌
- ✅ Connection 的一等 Instance 建模
- ✅ `instance_id/interface_id` 引用语法
- ✅ FK-001 接口级外键检查
- ✅ INTERFACE-COMPAT-001 类型兼容检查

### 本 ADR 明确不覆盖

- ❌ 连续接口（焊缝、管道沿线、粘接面）
- ❌ 接口的位置/朝向/空间坐标
- ❌ 连接的操作时序（先螺栓再焊接）
- ❌ `InterfaceSpec.specs` 的类型化约束（留给领域插件）
- ❌ 搜索路径定义

---

## 9. 向后兼容

| 数据 | 处理 |
|------|------|
| 旧 `LayoutEntry.connections` | 保留加载，标记 deprecated，不影响现有功能 |
| 无 Interface 的旧 Instance | FK-001 对非 `_interface` 结尾字段无影响 |
| datacenter 的 `ConnectionFamily` | 不受影响，`instances/connections/` 继续加载 |

---

## 10. 决策总结

| 决策 | 选择 | 核心理由 |
|------|------|----------|
| Interface 建模 | 内嵌在 Instance，pydantic 嵌套模型 | 接口依附于设备，不是独立实体 |
| Connection 建模 | 一等 Instance，走 Family → Model → Instance | 对齐 EDA netlist / MCAD assembly mates |
| 引用语法 | `instance_id/interface_id` | 精确、可解析、兼容 Kubernetes 惯例 |
| 连接基类 | 不定义，领域自描述 | 螺栓和光纤无共同 Schema |
| Layout 中的连接 | 废弃 | Layout 管位置，Connection 管拓扑 |
| 接口类型校验 | 内置 INTERFACE-COMPAT-001 | 防止物理上不可能的连接 |

---

## 参考

- [ADR-007: CAD 资产引用](007-cad-asset-reference.md)
- [ADR-001: 项目组织](001-project-organization.md)
- [ADR-002: 插件架构](002-plugin-architecture.md)
- EDA netlist 标准 / IFC: `IfcRelConnectsElements`
