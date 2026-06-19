# 接口与坐标系

> Interface 是 Part/Assembly 对外暴露的可连接点。ADL 中所有物理配合都发生在接口之间，而不是两个 Part 整体之间。

---

## 一、Interface 是什么

工程中的配合总是发生在具体的接触面、安装孔、连接器或卡扣上。Interface 就是把这些"接触点"显式建模为 Part 的一部分：

- 服务器上的 `eth0`、`power-a`；
- 抽屉上的 `slide-rail-left`；
- 法兰盘上的 `face-a`、`bolt-hole-1`；
- USB-C 连接器上的 `usb-c-receptacle`。

**设计原则（ADL-003）**：

> 接口是配合的唯一入口。部件级配合是语法糖，在编译时消解为接口配合。

---

## 二、Interface 的字段

`InterfaceSpec` 定义在 `adl/models/interface.py`：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | `str` | ✅ | Part 内唯一标识，如 `eth0`、`hole-3` |
| `interface_type` | `str` | ✅ | 接口类型，如 `SFP28-cage`、`IEC-C14`、`M16-bolt-hole` |
| `active_type` | `str` | ❌ | 多形态接口当前激活类型（如 Combo 口） |
| `direction` | `str` | ❌ | `input` / `output` / `bidirectional`，默认 `bidirectional` |
| `description` | `str` | ❌ | 人类可读描述 |
| `specs` | `dict` | ❌ | 接口自身规格键值对，由领域插件解释 |
| `local_transform` | `Transform` | ❌ | 接口在 Part 局部坐标系中的位姿 |
| `mating_kind` | `MatingKind` | ❌ | 配合类型：`face / axis / point / slot / rail / none` |
| `mating_params` | `dict` | ❌ | 配合参数，如 `normal`、`tolerance_mm` |
| `signature` | `InterfaceSignature` | ❌ | 运动自由度签名（ADL-004） |

### 2.1 示例

```yaml
# instances/parts/SFP28-MOD-A.yaml
id: SFP28-MOD-A
family: AssemblyPartFamily
interfaces:
  - id: cage-interface
    interface_type: SFP28-module
    direction: bidirectional
    local_transform:
      translation: [0, 6, 28]
      rotation: [0, 0, 0]
    mating_kind: slot
    mating_params:
      normal: [0, 0, 1]
```

---

## 三、坐标系约定

### 3.1 Part 局部坐标系

每个 Part 都有自己的局部坐标系：

- 原点：通常取 Part 几何中心或设计基准点。
- 轴方向：默认右手法则，X 向右，Y 向上，Z 向前（或按领域约定）。
- 单位：毫米（mm），角度为度（°）。

> 具体轴方向由模型/资产约定决定，ADL 不强制。但同一项目内应保持一致。

### 3.2 `local_transform` 的语义

`local_transform` 把接口的局部坐标系变换到 Part 的局部坐标系：

```yaml
local_transform:
  translation: [x, y, z]    # 接口原点相对 Part 原点的平移，mm
  rotation: [rx, ry, rz]    # Z-Y-X 欧拉角，度
  scale: [sx, sy, sz]       # 通常保持 [1, 1, 1]
```

变换顺序：先缩放，再按 Z→Y→X 旋转，最后平移。

### 3.3 旋转表示

ADL 使用 **Z-Y-X（Yaw-Pitch-Roll）欧拉角**，单位度：

- `rx`：绕 X 轴旋转（Roll）
- `ry`：绕 Y 轴旋转（Pitch）
- `rz`：绕 Z 轴旋转（Yaw）

执行顺序：先绕 Z 轴转 `rz`，再绕新 Y 轴转 `ry`，最后绕新 X 轴转 `rx`。

```yaml
# 接口坐标系绕 Z 轴旋转 180°，用于 USB-C 反插状态
rotation: [0, 0, 180]
```

> 完整实现见 `adl/geometry/models.py` 中的 `Transform` 和 `_rotation_matrix_zyx`。

### 3.4 接口坐标轴方向

每个 Interface 隐含一个局部坐标系：

- 原点：配合时的接触/插入参考点。
- Z 轴：通常指向配合方向（如插头插入方向、螺栓拧紧方向、面法向）。
- X/Y 轴：配合平面内的方向。

```yaml
# 一个面朝 +Z 方向的平面接口
local_transform:
  translation: [0, 0, 50]
  rotation: [0, 0, 0]
mating_kind: face
mating_params:
  normal: [0, 0, 1]
```

---

## 四、配合类型与参数

### 4.1 `mating_kind`

`mating_kind` 描述两个接口接触时的几何约束关系，见 `adl/compiler/mating_kinds.py`：

| 取值 | 描述 | 典型场景 |
|------|------|----------|
| `face` | 面贴合，法向对齐 | 法兰密封、PCB 贴合 |
| `axis` | 同轴约束 | 轴与孔、螺栓与孔 |
| `point` | 点重合 | 球窝关节 |
| `slot` | 沿一个方向平移 | SFP 插槽、抽屉导轨 |
| `rail` | 沿导轨方向平移 | 机柜滑轨 |
| `none` | 无几何约束 | 电气信号、数据协议配对 |

### 4.2 `mating_params`

`mating_params` 提供配合求解器所需的额外参数：

```yaml
mating_params:
  normal: [0, 0, 1]        # 配合面法向（在接口局部坐标系中）
  tolerance_mm: 0.5        # 配合容差
  slot_dir: [0, 0, 1]      # 槽/导轨方向
```

> 如果用户不写 `mating_kind` 或 `mating_params`，ADL 会从 `interface_type` 注册表自动填充默认值。

---

## 五、Footprint：多 pin 连接器

某些接口不是单一连接点，而是一组 pin，如 USB-C 母座、JST 电池座。ADL 用 `FootprintSpec` 建模：

```yaml
footprints:
  - id: usb-c
    footprint_type: usb-c-16p
    pins:
      - id: VBUS
        interface_type: power-vbus
        direction: output
      - id: D+
        interface_type: usb-data
        direction: bidirectional
```

Footprint 中的每个 pin 会被展开为完整接口名：`usb-c/VBUS`。

---

## 六、接口引用语法

在 Mate、Connection 中，使用 `instance_id/interface_id` 引用接口：

```yaml
parent: ACCESS-SW/sfp28-port-25
child: SFP28-MOD-A/cage-interface
```

对于 Footprint pin，使用三级引用：

```yaml
from: PCB-01/usb-c/VBUS
to: CABLE-01/usb-c/VBUS
```

解析函数：`adl/models/interface.py:resolve_interface_ref()`。

---

## 七、接口类型注册表

ADL 核心不硬编码领域接口类型。插件通过 `register_interface_type()` 注册已知类型，并通过 `register_mating_defaults()`、`register_signature()` 注册默认配合参数和自由度签名。

```python
# 伪代码：插件注册接口类型及其默认行为
register_interface_type("SFP28-cage")
register_mating_defaults("SFP28-cage", mating_kind="slot")
register_signature("SFP28-cage", InterfaceSignature.pluggable())
```

---

## 八、常见错误

| 错误 | 说明 | 处理/诊断 |
|------|------|-----------|
| 接口 ID 冲突 | 同一 Part 内两个 Interface 使用相同 `id` | 加载/校验时报错 |
| 未知接口类型 | `interface_type` 未注册 | 发出 `UserWarning`（非致命） |
| 接口引用不含 `/` | `resolve_interface_ref()` 要求格式 `inst/iface` | 抛出 `ValueError` |
| Mate 引用无法消解 | 裸 Instance ID 找不到唯一兼容接口对 | `MATE-003` / `MATE-004` |

---

## 九、与相关机制的衔接

- 配合类型与几何约束 → [配合类型与自由度](03-mating-kinds-and-dof.md)
- 布局与全局位姿 → [布局与参数化定位链](04-layout-and-placement-chain.md)
- 接口优先配合 → [ADL-003：接口优先的配合建模](../adr/003-interface-first-mating.md)
- 接口运动自由度签名 → [ADL-004：接口签名系统](../adr/004-interface-signature.md)
