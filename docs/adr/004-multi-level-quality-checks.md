# ADR-004: 多级质量检查体系

> 状态：已接受  
> 日期：2026-06-11  
> 作者：piki 核心团队

## 背景

工程设计的错误发现得越晚，修复成本越高。传统流程中，不同阶段的检查由不同工具、不同角色执行，检查标准不统一、结果难追溯。piki 的目标是将尽可能多的检查**左移**到设计阶段，并以统一的方式呈现结果。本 ADR 记录我们设计多级质量检查体系的思路。

---

## 1. 为什么需要多级检查

### 1.1 单一检查层的局限

假设只有一层检查（如"规则引擎"）：

```
设计 → 规则检查 → 通过/失败
```

问题：

- **风格问题**（如 YAML 缩进不一致）和**结构错误**（如字段类型错误）混在一起
- **快速反馈**和**深度分析**无法区分——用户必须等所有检查跑完才知道结果
- **不同严重级别**无法表达——"缩进不对"和"PDU 过载"都是"失败"

### 1.2 工程设计的检查层次

真实工程中，检查天然分层：

```
Layer 0: 文件格式合法性
    ↓ "这甚至不是合法的 YAML"
Layer 1: 字段类型/范围（Schema 校验）
    ↓ "height_u 必须是 1-48 的整数"
Layer 2: 单记录完整性（外键、必填项）
    ↓ "rack_id 引用的机柜不存在"
Layer 3: 跨记录业务规则（功率预算、空间冲突）
    ↓ "PDU-A 负载率 95%，超过阈值 80%"
Layer 4: 几何检查（3D 碰撞、间距）
    ↓ "SRV-01 与 SRV-02 在 U10 处空间重叠"
Layer 5: 物理仿真验证（未来）
    ↓ "液冷管路压降超过泵的扬程"
Layer 6: 基于 AI 的评估（未来）
    ↓ "该布局与历史最优方案偏差 30%，建议参考项目 X"
```

每一层的：

- **输入依赖**不同（L0 只需要文件内容，L6 需要历史项目数据）
- **执行成本**不同（L0 毫秒级，L6 可能需要 GPU）
- **反馈时效**不同（L0-L3 应该实时，L4+ 可以异步）
- **修复成本**不同（L0 改缩进，L6 可能重排整个方案）

---

## 2. piki 的五级检查体系

### 2.1 当前已实现

| 层级   | 名称           | 实现方式             | 执行时机     | 典型耗时 |
| ------ | -------------- | -------------------- | ------------ | -------- |
| **L0** | 文件格式       | YAML 解析器异常      | 加载时       | < 1ms    |
| **L1** | Schema 校验    | pydantic Family 验证 | 加载时       | < 10ms   |
| **L2** | 单记录完整性   | pydantic validator   | 加载时       | < 10ms   |
| **L3** | 跨记录业务规则 | `@rule` 装饰器函数   | `piki check` | 10-100ms |

### 2.2 规划中

| 层级   | 名称         | 实现方式                     | 执行时机            | 典型耗时 |
| ------ | ------------ | ---------------------------- | ------------------- | -------- |
| **L4** | 几何检查     | Python AABB/OBB 算法         | `piki check`        | 100ms-1s |
| **L5** | 物理仿真验证 | 外部物理引擎（PhysX/Bullet） | `piki check --deep` | 1s-1min  |
| **L6** | AI 评估      | LLM/ML 模型                  | `piki check --ai`   | 1-10s    |

### 2.3 L3 规则清单（当前已实现）

**telecom 插件：**

| 规则 ID | 名称 | 优先级 | Severity | 说明 |
|---------|------|--------|----------|------|
| TELECOM-POWER-001 | PDU 功率预算检查 | 10 | ERROR | 单 PDU 负载率不超过阈值 |
| **TELECOM-POWER-002** | **PDU 相线平衡检查** | 5 | WARNING | 同一机柜多相 PDU 负载均衡 |
| TELECOM-RACK-001 | U 位冲突检查 | 5 | ERROR | 同一机柜内设备 U 位不重叠 |
| TELECOM-RACK-002 | 机柜容量检查 | 5 | ERROR | 设备总高度不超过机柜容量 |
| **TELECOM-RACK-003** | **设备物理尺寸与机柜匹配检查** | 3 | WARNING | 设备 depth/width 不超过机柜 |
| TELECOM-FK-001 | 外键完整性检查 | 10 | WARNING | rack_id / pdu_id 引用有效性 |

**datacenter 插件：**

| 规则 ID | 名称 | 优先级 | Severity | 说明 |
|---------|------|--------|----------|------|
| DC-POWER-001 | 方舱功率预算检查 | 10 | ERROR | 方舱内设备总功耗不超过配电容量 |
| DC-COOLING-001 | 液冷方舱制冷容量检查 | 10 | ERROR | 液冷设备热负荷不超过制冷容量 |
| DC-WEIGHT-001 | 方舱总重检查 | 5 | ERROR | 设备总重不超过方舱最大承重 |
| **DC-SPACE-001** | **方舱内设备空间边界检查** | 5 | WARNING | 设备尺寸不超过方舱物理边界 |
| DC-CONN-001 | 连接完整性检查 | 10 | ERROR | 连接两端方舱存在且不相同 |
| DC-CONN-002 | 连接容量检查 | 5 | WARNING | 连接容量满足双向传输需求 |
| DC-FK-001 | 外键完整性检查 | 10 | WARNING | container_id / power_unit_id 引用有效性 |
| DC-REDUNDANCY-001 | 配电冗余检查 | 5 | WARNING | 配电单元冗余配置满足项目要求 |

> **新增规则**（本次迭代）：TELECOM-POWER-002、TELECOM-RACK-003、DC-SPACE-001，以及 DC-CONN-002 的双向校验增强。

### 2.3 分层执行策略

```python
# piki check 的默认行为：只跑 L0-L4（快速反馈）
piki check
# → L0: YAML 解析
# → L1-L2: pydantic 校验
# → L3: 业务规则
# → L4: 几何碰撞（如果启用）

# 深度检查：包含 L5
piki check --deep
# → 额外运行物理仿真验证

# AI 评估：包含 L6
piki check --ai
# → 额外运行 LLM 评估
```

**设计原则**：

- 默认只跑低成本检查，保证快速反馈
- 高成本检查需要显式启用
- CI/CD 中可以配置不同流水线跑不同层级

---

## 3. 各层详细设计

### 3.1 L0: 文件格式合法性

```python
# loaders.py —— YAML 解析阶段
try:
    data = yaml.safe_load(content)
except yaml.YAMLError as exc:
    # L0 错误：文件甚至不是合法的 YAML
    diagnostic = Diagnostic.fatal(
        message=f"YAML 解析错误: {exc}",
        location=Location.from_path(path, line=exc.problem_mark.line),
        code="FORMAT-001",
    )
```

**特点**：

- 不依赖任何领域知识
- 不依赖 piki.toml 配置
- 错误位置精确到行/列

### 3.2 L1: Schema 校验（字段类型/范围）

```python
# registry.py —— Family 验证阶段
try:
    family.validate(resolved_data)
except ValidationError as exc:
    # L1 错误：height_u = "abc"（应为整数）
    for error in exc.errors():
        diagnostic = Diagnostic.error(
            message=error["msg"],
            location=Location.from_path(path, line=field_line),
            code="SCHEMA-001",
        )
```

**特点**：

- 依赖 Family 定义（插件提供）
- 利用 pydantic 的丰富错误信息
- 支持嵌套字段定位（`physical.height_u`）

### 3.3 L2: 单记录完整性（外键、必填项）

```python
# 在 Family 中定义 validator
class ServerFamily(BaseModel):
    rack_id: str = Field(...)
    position_u: int = Field(..., ge=1, le=48)

    @field_validator("position_u")
    @classmethod
    def check_position(cls, v):
        if v > 42:  # 特定机柜的最大 U 位
            raise ValueError("position_u 超过该机柜容量")
        return v
```

**特点**：

- 单记录内交叉字段校验
- 可以访问 Model 默认值
- 无法访问其他实例（这是 L3 的职责）

### 3.4 L3: 跨记录业务规则

```python
# rules/power.py —— pytest 风格
@rule("TELECOM-POWER-001", "PDU 功率预算检查", priority=10)
def check_pdu_budget(ctx: Context):
    for pdu in ctx.query("pdus"):
        devices = ctx.query("devices", pdu_id=pdu.id)
        total_power = sum(d.resolved.tdp_w for d in devices)
        load_ratio = total_power / pdu.resolved.capacity_w
        threshold = ctx.config.get("power_threshold", 0.8)
        assert load_ratio <= threshold, (
            f"{pdu.id} 负载率 {load_ratio:.1%}，超过阈值 {threshold:.1%}"
        )
```

**特点**：

- 跨实例关联检查
- 可访问项目配置（阈值等）
- 优先级排序（`priority` 参数）
- severity 分级（ERROR/WARNING）

### 3.5 L4: 几何检查（依赖条件已就绪）

L4 几何检查的**前置条件**已在本次迭代中完成：

1. **物理尺寸字段已添加到 Family**：
   - `ServerFamily`：`depth_mm`、`width_mm`、`weight_kg`
   - `RackFamily`：`depth_mm`、`width_mm`
   - `EquipmentFamily`：`length_mm`、`width_mm`、`height_mm`、`depth_mm`

2. **L3 规则已覆盖物理尺寸校验**：
   - `TELECOM-RACK-003`：设备深度/宽度 ≤ 机柜深度/宽度
   - `DC-SPACE-001`：设备长/宽/高 ≤ 方舱长/宽/高

这些 L3 规则确保了几何引擎集成时，输入数据具有有效的物理尺寸。

```python
# rules/geometry.py —— 纯 Python 几何算法（规划中）
@rule("TELECOM-COLLISION-001", "3D 空间碰撞检查")
def check_3d_collision(ctx: Context):
    from piki.ext.geometry import AABB, intersect

    boxes = []
    for device in ctx.query("devices"):
        rack = ctx.query("racks", id=device.rack_id).first()
        # 构建设备在全局坐标系中的 AABB
        box = AABB.from_device(device, rack)
        boxes.append((device.id, box))

    # O(n²) 碰撞检测
    for i, (id1, b1) in enumerate(boxes):
        for id2, b2 in boxes[i+1:]:
            if intersect(b1, b2):
                assert False, f"设备 {id1} 与 {id2} 空间冲突"
```

**特点**：

- 不依赖外部物理引擎
- 结果可嵌入 USD 元数据供可视化
- 可扩展为 OBB（定向包围盒）提高精度
- **前置条件已满足**：物理尺寸字段已就绪，L3 规则已验证数据有效性

### 3.6 L5: 物理仿真验证（未来）

```python
# 规划中：调用外部物理引擎
@rule("DC-PHYSICS-001", "液冷管路压降验证")
def check_coolant_pressure(ctx: Context):
    # 导出 USD 场景到临时文件
    usd_path = ctx.generate_temp_usd()

    # 调用 Omniverse/Isaac Sim 进行 CFD 仿真
    result = run_physics_simulation(usd_path, simulation_type="fluid")

    assert result.max_pressure_drop <= ctx.config.get("max_pressure_drop_pa"), (
        f"液冷管路压降 {result.max_pressure_drop}Pa 超过允许值"
    )
```

**特点**：

- 需要外部工具（Omniverse、OpenFOAM 等）
- 执行成本高，不适合默认启用
- 结果可作为 L3 规则的"深度验证"

### 3.7 L6: AI 评估（未来）

```python
# 规划中：LLM 辅助评估
@rule("AI-EVAL-001", "布局优化建议")
def ai_layout_evaluation(ctx: Context):
    # 将设计数据序列化为结构化提示
    prompt = ctx.to_evaluation_prompt()

    # 调用 LLM
    response = llm.evaluate(prompt, context=ctx.project.history)

    if response.confidence > 0.8 and response.concern_level == "high":
        assert False, (
            f"AI 评估发现潜在问题: {response.summary}\n"
            f"参考案例: {response.reference_projects}"
        )
```

**特点**：

- 非确定性检查（同一输入可能不同输出）
- 适合作为 WARNING 而非 ERROR
- 需要历史项目数据作为上下文

---

## 4. 统一诊断格式

### 4.1 为什么所有层级使用同一诊断格式

无论哪一层发现问题，输出格式统一：

```json
{
  "severity": "ERROR",
  "code": "TELECOM-POWER-001",
  "message": "PDU-A 负载率 95%，超过阈值 80%",
  "location": {
    "uri": "devices/SRV-03.yaml",
    "range": {"start": {"line": 5, "character": 0}, "end": {"line": 5, "character": 10}}
  },
  "source": "piki.telecom",
  "related_information": [
    {
      "location": {"uri": "pdus/PDU-A.yaml", "range": ...},
      "message": "PDU-A 额定容量 2000W"
    }
  ]
}
```

**好处**：

- 用户看到统一的错误列表，不区分"这是哪一层的错误"
- IDE/LSP 客户端可以统一处理所有诊断
- 报告生成器（human/json/junit/markdown）只需实现一次

### 4.2 Severity 映射

| 层级 | 典型 Severity   | 说明                           |
| ---- | --------------- | ------------------------------ |
| L0   | FATAL           | 文件无法解析，后续检查无法继续 |
| L1   | ERROR           | Schema 不合规，数据不可用      |
| L2   | ERROR / WARNING | 完整性问题，视情况而定         |
| L3   | ERROR / WARNING | 业务规则违反，ERROR = 必须修复 |
| L4   | ERROR / WARNING | 几何冲突，ERROR = 物理不可行   |
| L5   | WARNING / INFO  | 仿真结果偏离预期，建议优化     |
| L6   | INFO / WARNING  | AI 建议，非强制                |

---

## 5. 与 CI/CD 的集成

```yaml
# .github/workflows/piki.yml
name: Piki Quality Gate

on: [push, pull_request]

jobs:
  fast-check:
    # L0-L4：快速反馈，阻塞合并
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install piki
      - run: piki check --format junit -o report.xml
      - uses: actions/upload-artifact@v4
        with:
          name: piki-report
          path: report.xml

  deep-check:
    # L5：物理仿真，非阻塞，仅报告
    runs-on: ubuntu-latest
    needs: fast-check
    steps:
      - uses: actions/checkout@v4
      - run: pip install piki[physics]
      - run: piki check --deep --format markdown -o deep-report.md
      - uses: actions/upload-artifact@v4
        with:
          name: piki-deep-report
          path: deep-report.md

  ai-eval:
    # L6：AI 评估，非阻塞
    runs-on: ubuntu-latest
    needs: fast-check
    steps:
      - uses: actions/checkout@v4
      - run: pip install piki[ai]
      - run: piki check --ai --format markdown -o ai-report.md
```

---

## 6. 决策总结

| 决策         | 选择                         | 核心理由                         |
| ------------ | ---------------------------- | -------------------------------- |
| **检查分层** | L0-L6 七层                   | 不同成本、不同时效、不同修复代价 |
| **默认范围** | L0-L4                        | 快速反馈，设计阶段可承受         |
| **深度检查** | `--deep` 显式启用            | 高成本检查不阻塞日常流程         |
| **统一格式** | LSP-compatible Diagnostic    | IDE 集成、统一报告、一次实现     |
| **左移策略** | 尽可能多的检查前置到设计阶段 | 修复成本最低                     |

---

## 参考

- [piki 核心概念：Rule](https://github.com/indenscale/piki/blob/main/docs/concepts/02-core-concepts.md#4-rule%E8%A7%84%E5%88%99)
- [piki 诊断系统](https://github.com/indenscale/piki/blob/main/src/piki/core/models/diagnostic.py)
- [ADR-001: 几何引擎与物理引擎](001-geometry-and-physics-engine.md) — L4-L5 的技术实现
- [ADR-003: 插件架构](003-plugin-architecture.md) — 不同领域的规则如何组织
