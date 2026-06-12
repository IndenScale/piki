# Model 格式规范

> Model 是 piki 的**默认值层**——提供 Family 的具体数值，即"这个型号的默认规格是什么"。
>
> Model 文件位于 `models/` 目录（项目本地）或插件自带型号库中。

## 基本结构

```yaml
# models/devices/generic-server.yaml
model: generic-server
family: ServerFamily

height_u: 2
tdp_w: 300
psu_count: 1
psu_redundancy: false

# 物理尺寸（毫米）
depth_mm: 715
width_mm: 445
height_mm: 89
weight_kg: 18.5
```

## 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `model` | `str` | 型号唯一标识，如 `generic-server`、`dell-r740` |
| `family` | `str` | 所属 Family 名称，如 `ServerFamily`、`RackFamily` |

## 字段覆盖规则

Model 中的字段是 Family 定义的**默认值**。Instance 可以覆盖这些默认值，但受以下约束：

| 约束 | 说明 |
|------|------|
| Family 类型校验 | 覆盖值必须符合 Family 定义的字段类型和范围 |
| `non_overridable` | 标记为不可覆盖的字段，Instance 覆盖会报错 |
| 嵌套字段 | 支持嵌套命名空间，如 `physical.height_u` |

## 嵌套命名空间

Model 支持嵌套结构，便于组织相关字段：

```yaml
# models/devices/dell-r740.yaml
model: dell-r740
family: ServerFamily

# 物理规格
physical:
  height_u: 2
  depth_mm: 715
  width_mm: 445
  height_mm: 89
  weight_kg: 29.0

# 电源规格
power:
  tdp_w: 350
  psu_count: 2
  psu_redundancy: true

# 网络规格
network:
  nic_count: 4
  nic_speed_gbps: 10
```

解析时，嵌套字段会被**扁平化**合并：

```python
# 扁平化后
{
    "physical.height_u": 2,
    "physical.depth_mm": 715,
    "power.tdp_w": 350,
    "power.psu_count": 2,
    "network.nic_count": 4,
}
```

Instance 覆盖时可以直接写扁平字段：

```yaml
# instances/SRV-01.yaml
id: SRV-01
model: dell-r740
# 覆盖嵌套字段
tdp_w: 320          # 等价于覆盖 power.tdp_w
```

## 保留字段

以下字段名被 piki 保留，Model 中不应使用：

| 保留字段 | 说明 |
|----------|------|
| `id` | Instance 唯一标识，由 Instance 文件提供 |
| `model` | 型号引用（Model 文件自身用，Instance 也用它引用 Model） |
| `family` | Family 名称 |

## 型号继承（未来特性）

规划中支持型号继承：

```yaml
# models/devices/dell-r740-xd.yaml
model: dell-r740-xd
family: ServerFamily
extends: dell-r740          # 继承 dell-r740 的所有默认值

# 只覆盖差异字段
physical:
  depth_mm: 777             # XD 型号更深
power:
  tdp_w: 400                # XD 型号功耗更高
```

## 来源优先级

当多个来源定义了同一个 Model 时：

```
项目本地 models/          ← 最高优先级
插件自带型号库            ← 次之
```

项目可以覆盖插件的默认型号，也可以新增项目特有的型号。

## 最佳实践

1. **一型号一文件**：每个 Model 一个 YAML 文件，文件名与 `model` 字段一致
2. **文件名即 model ID**：`generic-server.yaml` → `model: generic-server`
3. **完整填写默认值**：Model 应包含该型号的所有规格参数，Instance 只写覆盖值
4. **使用嵌套命名空间**：按 `physical`、`power`、`network` 等维度组织字段
5. **注释说明来源**：标明规格数据来源（厂商 datasheet 链接、测量日期等）

```yaml
# models/devices/hp-dl380-g10.yaml
model: hp-dl380-g10
family: ServerFamily

# 来源: HPE ProLiant DL380 Gen10 规格书 (P19720-B21)
# 日期: 2024-03-15
# 链接: https://www.hpe.com/psnow/doc/a50001784enw

physical:
  height_u: 2
  depth_mm: 679
  width_mm: 445
  height_mm: 87
  weight_kg: 14.8

power:
  tdp_w: 500
  psu_count: 2
  psu_redundancy: true
```
