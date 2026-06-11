# ADR-007: CAD 资产引用与白牌标准型号

> 状态：草案
> 日期：2026-06-11
> 作者：piki 核心团队

## 背景

piki 的核心数据单元是声明式 YAML——Family/Model/Instance 三层结构定义了工程对象的属性和约束。这些是**设计意图**的表示，足够支撑规则检查、BOM 生成、3D 碰撞检测。

但工程设计最终要落地到物理世界。一台设备不只有 `tdp_w: 350` 和 `height_u: 2`——它有外壳、有热源分布、有进风面、有安装孔位。这些**物理几何和物理场属性**不属于 piki 的声明式建模层，但 piki 不能假装它们不存在。

本 ADR 记录我们对 CAD 资产集成的边界决策：piki 应该如何处理供应商提供的高精度 3D 资产和物理仿真数据。

---

## 1. 问题域：多专业系统集成的信息断裂

在真实工程项目中，多个专业看同一台设备，需要不同的数据维度：

| 专业 | 关心 Dell R740 的什么 | 数据来源 |
|------|----------------------|---------|
| 结构 | `weight_kg: 25`，楼板荷载 | YAML（piki 可表达） |
| 暖通 | `tdp_w: 350`，`airflow_cfm: 120`，进风面位置 | YAML + 几何引用 |
| 电气 | `psu_count: 2`，`input_v: 200-240`，ATS 切换 | YAML（piki 可表达） |
| 消防 | 物理尺寸，是否遮挡喷淋 | 几何引用 |
| 弱电 | `nic_count: 4`，`sfp_type: QSFP28` | YAML（piki 可表达） |

当前状态：

- 性能参数散落在 PDF datasheet 中，靠工程师手工转录
- 3D 几何锁在供应商的 CAD 文件里，每个项目重新画、重新简化
- 热仿真模型由仿真工程师手动构建，从 CAD 中提取、简化、赋参

结果是：同一个设备在结构模型、暖通模型、电气模型中是**三个不同的人工制品**，互相之间没有引用关系。改了任何一处，另外两处不知道。

---

## 2. 核心决策：引用而非嵌入

**piki 不加工、不托管、不转换 CAD 资产。piki 只引用路径。**

### 2.1 原则

| 维度 | 声明 |
|------|------|
| 资产所有者 | 供应商 / 业主 / 项目团队 |
| piki 的角色 | 消费引用的下游（阅读端） |
| piki 不做什么 | 不提供 3D 建模能力、不转换格式、不托管资产 |
| 何时解析引用 | 导出 OpenUSD 场景时、运行 L4 几何检查时、对接仿真工具时 |

### 2.2 动机

1. **边界清晰**：piki 的核心价值是声明式建模和规则检查，不是 3D 几何处理。涉足几何加工会分散精力、污染核心抽象。
2. **避免格式战争**：供应商用 SolidWorks、Catia、Creo、Inventor、Revit 等各种工具。piki 如果试图转换格式，会陷入无底洞。
3. **资产可更新**：供应商更新了设备模型，只需要替换文件，不需要 piki 侧做任何事。
4. **保持 piki 数据的轻量**：YAML 文件几十行。嵌入 mesh 数据会让仓库从 KB 级膨胀到 GB 级，破坏 Git 友好性。

### 2.3 什么是"白牌标准型号"

"白牌标准型号"（White-Label Standard Model）是指**一个行业通用、不与任何特定厂商绑定的设备数值模板**。

例如，piki 的 `library/` 中可以有一个 `generic-1u-server`：

```yaml
# library/devices/generic-1u-server.yaml
model: generic-1u-server
family: ServerFamily

physical:
  height_u: 1
  depth_mm: 800
  width_mm: 482

weight_kg: 18

power:
  tdp_w: 300
  psu_count: 2

assets:
  mesh: "models/generic-1u-server.usd"
  enclosure_step: "models/generic-1u-server/v1.step"
  thermal: "models/generic-1u-server-thermal/v1.json"
```

白牌型号的作用：

- **早期设计阶段的占位**：在厂商选型确认之前，工程师可以用白牌型号推进布局和系统设计。
- **设计比选的基准**："我们需要一台 1U 服务器，TFLOPS ≥ 1200，功耗 ≤ 500W"——白牌型号提供了约束边界，实际厂商型号在这个边界内竞争。
- **供应链中立**：白牌型号不属于任何厂商，避免 piki 在选型阶段偏向特定供应商。

白牌型号的 3D 资产可以用**简化几何**（一个 Box 或 LOD 最低的 mesh），用于空间校验和碰撞检测。厂商特定型号可以提供更高精度的替换资产。

### 2.4 白牌型号的治理

白牌型号库的维护责任分层：

| 层级 | 维护者 | 内容 | 示例 |
|------|--------|------|------|
| **piki 内置** | piki 核心团队 | 最通用的设备类模板（1U 服务器、2U 服务器、机柜式 UPS） | `generic-1u-server`、`generic-rack-ups` |
| **行业共享** | 行业组织 / 开源社区 | 细分领域的标准设备（数据中心水冷精密空调、核级泵） | `crac-100kw`（ASHRAE 参考）、`nuclear-grade-pump-a` |
| **项目级** | 项目团队 | 项目特有的设备白牌版本 | `campus-chiller-500ton` |

piki 内置白牌型号随 piki 发行版发布，存放在 `piki-core/library/` 中，不可被用户修改。行业共享型号可通过 piki-registry 获取。项目级白牌型号存放在项目的 `library/` 目录中，优先于内置白牌。

查找顺序：项目 `library/` → piki-registry → piki-core 内置。

---

## 3. 引用机制：Model 层的资产引用字段

### 3.1 Schema 设计

在 Model 的 pydantic 定义中增加可选的 `assets` 字段：

```python
class AssetReference(BaseModel):
    """对外部 CAD 资产的引用"""
    mesh: Optional[str] = None            # OpenUSD mesh 路径
    enclosure_step: Optional[str] = None   # 外壳 STEP 路径
    thermal: Optional[str] = None          # 热模型 JSON 路径
    structural: Optional[str] = None       # 结构模型路径
    mount_points: Optional[str] = None     # 安装孔位定义
    asset_hash: Optional[str] = None       # 资产包的整体哈希（SHA-256），用于版本校验

class DeviceFamily(BaseModel):
    # ... 现有字段 ...
    assets: Optional[AssetReference] = None
```

### 3.2 路径语义

引用路径遵循以下约定：

| 路径类型 | 解析规则 | 示例 |
|---------|---------|------|
| 相对路径 | 相对于 Model YAML 文件所在目录 | `models/dell-r740.usd` |
| 绝对路径 | 文件系统绝对路径 | `/assets/dell/r740.usd` |
| URI | 可解析的远程资源 | `https://registry.piki.dev/models/dell/r740/v2.usd` |

未来 piki-registry 可以作为资产分发层：

```bash
piki assets pull dell-r740    # 拉取型号的所有关联资产到本地缓存
piki assets ls                # 列出已缓存的资产
```

### 3.3 资产版本校验

供应商更新设备模型后，引用路径可能不变但文件内容已变。为防止 L4 几何检查跑在旧新不一的资产上，引入 `asset_hash` 字段：

```yaml
assets:
  mesh: "models/dell-r740.usd"
  enclosure_step: "models/dell-r740.step"
  thermal: "thermal/thermal-model.json"
  asset_hash: "sha256:a1b2c3d4e5f6..."  # 所有资产文件的聚合哈希
```

`piki check` 在运行时校验实际文件哈希与声明的 `asset_hash` 是否一致。不一致时报告警告，提示工程师确认是否需要审核新版本的供应商模型。

### 3.4 热模型最小 Schema

Thermal 模型 JSON 不限制完整格式，但下游消费者（仿真工具对接、L4 热检查）需要可靠读取最小信息集。piki 定义最小 schema，供应商的 thermal JSON 必须包含以下字段：

```json
{
  "$schema": "https://piki.dev/schemas/thermal/v1",
  "version": 1,
  "heat_sources": [
    {
      "id": "main-heat",
      "power_w": 350,
      "position": { "x": 0, "y": 0, "z": 0 },
      "dimensions": { "x": 0.4, "y": 0.1, "z": 0.7 }
    }
  ],
  "airflow": {
    "direction": "front-to-back",
    "intake_faces": ["front"],
    "exhaust_faces": ["back"],
    "max_cfm": 120
  },
  "enclosure": {
    "material": "steel",
    "thickness_mm": 1.2
  }
}
```

`heat_sources` 和 `airflow` 为必填字段，其余由供应商自由扩展。piki 的 L4 热检查只消费 `heat_sources` 和 `airflow`，其余字段透传给外部仿真工具。

### 3.5 解析时机

piki 在以下场景中解析资产引用：

| 场景 | 需要的资产类型 | 处理方式 |
|------|-------------|---------|
| OpenUSD 场景导出 | `mesh` | 组装 USD 场景，引用外部 mesh |
| L4 几何碰撞检查 | `mesh` 或 `enclosure_step` | 加载 Bounding Box 或简化 mesh 做碰撞 |
| L5 物理仿真 | `thermal`, `structural` | 将参数传入仿真工具链 |
| Studio 可视化 | `mesh` | 3D 视口中渲染设备 |

未提供资产引用时，piki 使用 Family 层定义的**回退几何**（默认 Box，按 `height_u`、`depth_mm`、`width_mm` 生成）。

---

## 4. 影响与权衡

### 4.1 有利影响

- **供应链协议化**：对供应商提出明确的数据交付要求。"提供符合 SDE 规范的设备数据包"成为一个可被 EPC / 业主引用的合同条款。
- **多专业单一真相源**：结构、暖通、电气、消防看同一份设备数据，不再各自手工建模。
- **piki 保持轻量**：不加几何内核、不加格式转换器，核心代码库不受污染。
- **渐进采纳**：白牌型号 + 简化几何可以先用起来。厂商高精度资产可以后补充。
- **版本可审计**：`asset_hash` 确保消费端能检测到未审核的资产变更。

### 4.2 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 供应商不提供资产 | 白牌型号 + 简化几何兜底；提供资产模板和文档降低供应商门槛 |
| 格式碎片化（STEP, glTF, FBX…） | piki 只要求一种可用的 mesh 格式（推荐 USD），其他格式由供应商自行转换 |
| 资产文件过大 | 引用路径而非嵌入；资产存储在独立仓库或 Registry |
| 引用断开（路径失效） | `piki check` 增加资产完整性检查规则（ADR-004 L2） |
| 资产未审核即更新 | `asset_hash` + L2 校验，变更需显式更新哈希确认 |
| 热模型格式不一致 | piki 定义最小 schema，其余字段透传；不全的模型降级为仅几何 |

---

## 5. 与其他 ADR 的关系

| ADR | 关系 |
|-----|------|
| ADR-001（几何引擎与物理引擎） | 资产引用是 ADR-001 中 OpenUSD 聚合的**上游数据源** |
| ADR-002（一实例一文件） | 资产引用在 Model 层，Instance 不重复声明资产路径 |
| ADR-004（多级质量检查） | 资产完整性检查属于 L2（引用完整性），资产导致的碰撞属于 L4 |
| ADR-006（Piki Studio） | Studio 3D 视口是资产引用的主要消费者 |

---

## 6. 示例：完整设备数据包

供应商交付一台 Dell R740 时，理想情况下需要提供：

```text
dell-r740/
├── model.yaml              # piki Model 定义
├── models/
│   ├── dell-r740.usd       # 主 mesh（OpenUSD）
│   ├── dell-r740-lod1.usd  # 简化 mesh（碰撞检测用）
│   └── dell-r740.step      # 原始 CAD（可选）
├── thermal/
│   └── thermal-model.json  # 热源分布、进/出风面定义
├── structural/
│   └── mount-points.json   # 安装孔位和承重信息
└── README.md               # 版本、变更记录
```

`model.yaml` 中：

```yaml
model: dell-r740
family: ServerFamily

physical:
  height_u: 2
  depth_mm: 715
  width_mm: 482

power:
  tdp_w: 350
  psu_count: 2

assets:
  mesh: "models/dell-r740.usd"
  enclosure_step: "models/dell-r740.step"
  thermal: "thermal/thermal-model.json"
  structural: "structural/mount-points.json"
  asset_hash: "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
```

piki 的 Instance 只声明部署决策（放哪、接哪个 PDU），不重复声明资产路径。资产路径从 Model 层自动继承。
