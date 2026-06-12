# Layout 格式规范

> Layout 是 piki 的**部署决策层**——描述"这台设备部署在哪、怎么接"。
>
> 每个子项目只有一个 `layout.yaml` 文件。Instance 与 Layout 分离（ADR-008），使方案比选通过 Git 分支实现。

## 基本结构

```yaml
# layout.yaml
- instance: SRV-01
  rack_id: RACK-A01
  position_u: 10
  pdu_id: PDU-A

- instance: SRV-02
  rack_id: RACK-A01
  position_u: 8
  pdu_id: PDU-A

- instance: RACK-A01
  room_id: ROOM-101
  grid_id: A-3
```

## 格式说明

Layout 是一个 YAML 列表，每个元素是一个部署条目。

### 必填字段

| 字段       | 类型  | 说明               |
| ---------- | ----- | ------------------ |
| `instance` | `str` | 引用的 Instance ID |

### 常用部署字段

| 字段            | 类型    | 说明                        | 适用场景     |
| --------------- | ------- | --------------------------- | ------------ |
| `rack_id`       | `str`   | 机柜 ID                     | 机柜式部署   |
| `position_u`    | `int`   | U 位起始位置（从下往上数）  | 机柜式部署   |
| `pdu_id`        | `str`   | 接入的 PDU ID               | 机柜式部署   |
| `grid_id`       | `str`   | 网格坐标（如 `A-3`、`B-5`） | 自由空间部署 |
| `position_x_mm` | `float` | X 坐标（mm）                | 自由空间部署 |
| `position_y_mm` | `float` | Y 坐标（mm）                | 自由空间部署 |
| `position_z_mm` | `float` | Z 坐标（mm）                | 自由空间部署 |

### 连接关系

```yaml
- instance: SW-01
  rack_id: RACK-A01
  position_u: 42
  connections:
    - port: Gi1/0/1
      to_instance: SRV-01
      to_port: eth0
      cable_type: OM4-LC-LC
      length_m: 3.0

    - port: Gi1/0/2
      to_instance: SRV-02
      to_port: eth0
      cable_type: OM4-LC-LC
      length_m: 2.5
```

| 连接字段      | 类型    | 说明                                             |
| ------------- | ------- | ------------------------------------------------ |
| `port`        | `str`   | 本设备端口号                                     |
| `to_instance` | `str`   | 对端设备 Instance ID                             |
| `to_port`     | `str`   | 对端端口号                                       |
| `cable_type`  | `str`   | 线缆类型：如 `OM4-LC-LC`、`Cat6A-RJ45`、`DAC-3m` |
| `length_m`    | `float` | 线缆长度（米）                                   |

## 按专业分 Section

大型项目可以按专业分 section：

```yaml
# layout.yaml
electrical:
  - instance: PDU-A
    rack_id: RACK-A01
    phase: L1

  - instance: PDU-B
    rack_id: RACK-A01
    phase: L2

compute:
  - instance: SRV-01
    rack_id: RACK-A01
    position_u: 10
    pdu_id: PDU-A

  - instance: SRV-02
    rack_id: RACK-A01
    position_u: 8
    pdu_id: PDU-A

network:
  - instance: SW-01
    rack_id: RACK-A01
    position_u: 42
    pdu_id: PDU-A
```

Section 名是任意的，由项目自定义。分 section 不影响解析，只是便于人类阅读和组织。

## 模块引用

Layout 支持引用可复用模块，类似 Terraform module 或硬件 IP 核。

### 模块定义

```yaml
# modules/standard-rack.yaml
- instance: "{{prefix}}-SW-01"
  rack_id: "{{rack_id}}"
  position_u: 42
  pdu_id: "{{pdu_id}}"

- instance: "{{prefix}}-SW-02"
  rack_id: "{{rack_id}}"
  position_u: 40
  pdu_id: "{{pdu_id}}"

- instance: "{{prefix}}-SRV-01"
  rack_id: "{{rack_id}}"
  position_u: 38
  pdu_id: "{{pdu_id}}"

- instance: "{{prefix}}-SRV-02"
  rack_id: "{{rack_id}}"
  position_u: 36
  pdu_id: "{{pdu_id}}"
```

### 模块引用

```yaml
# layout.yaml
modules:
  rack-a01:
    source: ./modules/standard-rack.yaml
    params:
      prefix: A01
      rack_id: RACK-A01
      pdu_id: PDU-A

  rack-a02:
    source: ./modules/standard-rack.yaml
    params:
      prefix: A02
      rack_id: RACK-A02
      pdu_id: PDU-B

# 内联条目（非模块化的特殊设备）
- instance: STORAGE-01
  rack_id: RACK-A01
  position_u: 20
  pdu_id: PDU-A
```

### 模块参数

| 参数语法                 | 说明                         |
| ------------------------ | ---------------------------- |
| `{{param_name}}`         | 模板变量，展开时替换为传入值 |
| `{{param_name:default}}` | 带默认值的模板变量           |

模块展开后，所有条目合并到 Layout 中统一处理。

## 嵌套项目中的 Layout

每个子项目有独立的 `layout.yaml`：

```text
parent-project/
├── piki.toml
├── instances/               # 父项目共享实例
├── layout.yaml              # 父项目 Layout（可为空或只引用子项目）
│
└── floor-1/                 # 子项目
    ├── piki.toml
    ├── instances/           # 楼层特有实例
    └── layout.yaml          # 楼层 Layout
```

子项目的 Layout 可以引用父项目的 Instance：

```yaml
# floor-1/layout.yaml
- instance: SRV-01 # 在父项目 instances/ 中定义
  rack_id: RACK-A01
  position_u: 10

- instance: FLOOR-1-PUMP-01 # 在 floor-1/instances/ 中定义
  grid_id: B-3
```

Instance 解析顺序：**当前项目 → 父项目 → 根项目**。找到即停。

## Layout 与 Instance 的关系

```text
Instance（设备身份）          Layout（部署决策）
    ↓                              ↓
    └──────── 合并 ────────────────┘
              ↓
        ResolvedInstance
        （完整对象，含所有字段）
```

合并顺序：

1. **Model 默认值** → 基础规格
2. **Instance 覆盖值** → 实际参数
3. **Layout 部署值** → 位置信息（不参与 Schema 校验）

```python
# 伪代码
resolved = {**model.defaults, **instance.overrides, **layout_entry}
validated = pydantic.validate(resolved, family)
```

## 检查规则

piki 自动检查 Layout 的完整性：

| 规则             | 说明                                   |
| ---------------- | -------------------------------------- |
| `LAYOUT-FK-001`  | Layout 引用的 Instance 必须存在        |
| `LAYOUT-FK-002`  | Layout 引用的 rack_id 必须存在         |
| `LAYOUT-FK-003`  | Layout 引用的 pdu_id 必须存在          |
| `LAYOUT-DUP-001` | 同一 Instance 不能在 Layout 中出现两次 |

## 最佳实践

1. **每个子项目只有一个 Layout 文件**：不拆多文件，方案比选用 Git 分支
2. **Instance ID 与 Layout 条目一一对应**：不要遗漏、不要重复
3. **用模块复用标准配置**：10 个相同机柜？写一次模块，引用 10 次
4. **按专业分 section（可选）**：大型项目便于阅读，不影响功能
5. **连接关系写完整**：端口、对端、线缆类型、长度，施工队需要
6. **状态变化只改 Layout**：设备退役？从 Layout 中移除条目，Instance 文件保留（历史记录）
