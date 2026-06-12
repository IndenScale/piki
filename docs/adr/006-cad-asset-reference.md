# ADR-006: CAD 资产引用与白牌标准型号

> 状态：已接受
> 日期：2026-06-12
> 作者：piki 核心团队
> 替代：ADR-007（CAD 资产引用）

## 背景

piki 的核心价值是声明式建模和规则检查——Family/Model/Instance 三层结构定义了工程对象的属性和约束。但工程设计最终要落地到物理世界：一台设备不只有 `tdp_w: 350` 和 `height_u: 2`——它有外壳、热源分布、进风面、安装孔位。这些物理几何和物理场属性不属于 piki 的声明式建模层，但 piki 不能假装它们不存在。

本 ADR 记录 piki 对 CAD 资产集成的边界决策：引用而非嵌入。

---

## 1. 问题域：多专业系统集成的信息断裂

| 专业 | 关心同一台设备的什么 | 数据来源 |
|------|-------------------|---------|
| 结构 | `weight_kg: 25`，楼板荷载 | YAML |
| 暖通 | `tdp_w: 350`，进风面位置 | YAML + 几何引用 |
| 电气 | `psu_count: 2`，输入电压 | YAML |
| 消防 | 物理尺寸，是否遮挡喷淋 | 几何引用 |

当前状态：性能参数散落在 PDF datasheet 中靠手工转录，3D 几何锁在供应商 CAD 文件里每个项目重新画，热仿真模型手动构建。同一台设备在结构、暖通、电气模型中是三个不同的人工制品，互相没有引用关系。

---

## 2. 核心决策：引用而非嵌入

**piki 不加工、不托管、不转换 CAD 资产。piki 只引用路径。**

| 维度 | 声明 |
|------|------|
| 资产所有者 | 供应商 / 业主 / 项目团队 |
| piki 的角色 | 消费引用的下游 |
| piki 不做什么 | 不提供 3D 建模、不转换格式、不托管资产 |
| 何时解析引用 | 导出 OpenUSD 场景时、运行 L4 几何检查时、对接仿真工具时 |

### 2.1 动机

1. **边界清晰**：piki 的核心价值是声明式建模和规则检查，涉足几何加工会分散精力。
2. **避免格式战争**：供应商用 SolidWorks、Catia、Revit 等各种工具，piki 如果转换格式会陷入无底洞。
3. **资产可更新**：供应商更新设备模型，只需替换文件。
4. **保持 piki 数据轻量**：YAML 文件几十行，嵌入 mesh 数据会让仓库膨胀到 GB 级。

---

## 3. 白牌标准型号

"白牌标准型号"是指行业通用、不与特定厂商绑定的设备数值模板。

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

assets:
  mesh: "models/generic-1u-server.usd"
  enclosure_step: "models/generic-1u-server.step"
  thermal: "models/generic-1u-server-thermal.json"
```

白牌型号作用：早期设计阶段占位、设计比选基准、供应链中立。

白牌型号的 3D 资产可用简化几何（一个 Box），用于空间校验和碰撞检测。厂商特定型号可提供更高精度的替换资产。

---

## 4. 资产完整性校验

Model YAML 中声明 `asset_hash`：

```yaml
assets:
  mesh: "models/dell-r740.usd"
  asset_hash: "sha256:e3b0c44298fc1c149afbf4c8996fb924..."
```

`piki check` 在 L2 阶段校验实际文件哈希与声明的 `asset_hash` 是否一致。不一致时警告，提示确认是否需要审核新版本的供应商模型。

---

## 5. 决策总结

| 决策 | 选择 | 核心理由 |
|------|------|----------|
| 资产归属 | 引用路径，不嵌入 | 边界清晰、避免格式战争、保持数据轻量 |
| 占位策略 | 白牌标准型号 + 简化几何 | 早期设计可用，厂商资产后补充 |
| 完整性 | `asset_hash` 校验 | 消费端检测未审核的资产变更 |
| 热模型 | 最小 schema（heat_sources + airflow） | 下游消费者可靠读取，其余透传 |

---

## 参考

- [空间可视化策略](../adr/004-spatial-visualization-strategy.md)
