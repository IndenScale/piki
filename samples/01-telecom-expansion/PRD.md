# Telecom 领域 PRD — 站点工程设计校验与交付

> 版本：0.2.0（草案）
> 最后更新：2026-06-12
> 对应 piki 版本：0.1.0
> 插件：telecom

---

## 1. 领域定义

### 1.1 一句话

**Telecom 领域覆盖电信机房 / 数据中心站点级的设备部署设计**：从拿到扩容需求，到出方案、校验、出交付物（BOM、面板图、端口图），最后交给施工队。

### 1.2 核心对象

```
Rack（机柜）  ← 42U 标准机柜，含配电容量、物理尺寸
  ├── PDU（电源分配单元）  ← 机柜内双路/多路供电，含额定容量、相线
  └── Server（设备）       ← 服务器/交换机/防火墙等，含 TDP、U 位、PSU 冗余
```

### 1.3 用户画像

| 角色                  | 职责                         | 技术背景                  | 使用方式                                  |
| --------------------- | ---------------------------- | ------------------------- | ----------------------------------------- |
| **站点工程师**        | 出扩容方案、画面板图、写 BOM | 熟悉 Excel，部分会 Python | 改 YAML → 跑 check → 出报告/图            |
| **设计审核人**        | 审方案、对照标准规范         | 资深工程经验，不写代码    | 跑 check → 看报告 → Studio 看 3D          |
| **技术骨干 / 团队长** | 定设计规则、沉淀团队经验     | 会 Python + Git           | 写 rules/ → 配置 piki.toml → 维护 models/ |
| **施工队长**          | 按图施工、上架接线           | 看图为主                  | 读面板图 + BOM 表 + 端口图                |

---

## 2. 用户故事

### US-1：扩容方案校验（⭐ 核心故事）

> **作为**站点工程师，
> **我想**在提交扩容方案前，让系统自动检查功率、U 位、外键引用，
> **以便**我不用靠记忆逐项核对，避免上电跳闸、施工返工。

**验收标准：**

- 新增 Instance YAML 后运行 `piki check`，自动检查 PDU 功率预算、U 位冲突、机柜容量、外键完整性
- 错误信息定位到具体文件和字段行号
- 支持 `piki check --skip` 跳过特定规则
- 支持 `piki check --format json` 导出给 CI/CD 消费

**当前状态：** ✅ 已实现（TELECOM-POWER-001/002, TELECOM-RACK-001/002/003, TELECOM-COLLISION-001, TELECOM-FK-001 共 7 条规则）

---

### US-2：多方案并行比选

> **作为**站点工程师，
> **我想**对同一批设备尝试不同的部署方案（放 A 列 vs B 列，接 L1 vs L2），
> **以便**快速找到最优解，不用复制粘贴多份 Excel。

**验收标准：**

- 设备身份（Instance）与部署决策（Layout）分文件管理
- 同一设备可在不同 Git 分支的 layout.yaml 中有不同的 rack_id / pdu_id / position_u
- 分支合并时只冲突 layout.yaml，Instance 文件无冲突
- 切换分支后 `piki check` 自动对应当前分支的部署方案

**当前状态：** ✅ 已实现（ADR-001 Instance/Layout 分离架构）

---

### US-3：型号库复用（避免重复录入）

> **作为**技术骨干，
> **我想**把常用设备型号（Dell R740、HP DL380、华为 CE6800）录入一次型号库，
> **以便**所有项目共享，新项目只需引用型号即可自动获得功耗、尺寸、U 位等参数。

**验收标准：**

- `models/devices/*.yaml` 定义设备型号的默认规格
- Instance 引用 `model: generic-server`，自动继承型号默认值
- Instance 可通过显式声明字段覆盖默认值（如实际功耗低于标称）
- 插件自带型号 + 项目本地型号并存

**当前状态：** ✅ 已实现（Family → Model → Instance 三层模型）

---

### US-4：BOM 清单导出

> **作为**站点工程师，
> **我想**一键导出设备清单（BOM），
> **以便**交给采购和施工队，不用手动从 Excel 里复制粘贴。

**验收标准：**

- `piki generate bom-csv` 导出 CSV 格式 ✅
- CSV 包含：设备 ID、型号、品牌、MPN、机柜、U 位、PDU、功耗、PSU 数量、高度、状态、单价 ✅
- 支持 `--output` 指定输出路径 ✅
- 字段顺序和表头与施工队/采购习惯一致 ✅

**当前状态：** ✅ 已实现增强版。telecom 插件内置 10 个生成器：

| 生成器 ID | 命令 | 功能 |
|---|---|---|
| `bom-csv` | `piki generate bom-csv` | 设备清单 CSV（14 列，含品牌/MPN/单价） |
| `rack-face-panel` | `piki generate rack-face-panel` | 机柜 U 位面板图（文本格式） |
| `rack-face-panel-svg` | `piki generate rack-face-panel-svg` | 机柜 U 位面板图（SVG 格式，含状态颜色编码） |
| `power-budget` | `piki generate power-budget` | 功率预算汇总（PDU / 机柜 / 各相明细） |
| `cable-list` | `piki generate cable-list` | 线缆清单（光纤跳线 + 光模块） |
| `port-map` | `piki generate port-map` | 端口分配表 CSV |
| `cable-schedule` | `piki generate cable-schedule` | 线缆排期表 CSV（含机柜平面路由描述） |
| `cable-labels` | `piki generate cable-labels` | 线缆打印标签 SVG |
| `port-diagram` | `piki generate port-diagram` | 端口互连拓扑图 SVG |
| `floor-plan` | `piki generate floor-plan` | 机房平面图 SVG（机柜位置、编号、朝向） |

生成器返回结构化的 `GeneratorResult`（`success`, `content`, `file_path`, `content_type`），
支持 CLI 和 SDK 两种消费方式。

---

### US-5：面板图 / U 位正视图导出

> **作为**站点工程师，
> **我想**生成每个机柜的正面 U 位图，标出每台设备在哪个 U 位、型号、功耗，
> **以便**施工队按图安装，不用手画或用 Visio 重新画一遍。

**验收标准：**

- `piki generate rack-face-panel` 为每个机柜生成 U 位占用文本图 ✅
- 图中标注：设备 ID、型号、U 位范围、TDP、状态 ✅
- 按机柜逐个输出 ✅
- 输出格式：SVG（可嵌入文档）✅ / PNG（可打印）❌
- 按机柜过滤：`piki generate rack-face-panel-svg --rack RACK-A01` ✅
- 颜色编码：installed=绿色 / planned=蓝色 / retired=灰色 ✅

**当前状态：** ✅ 已实现文本版 + SVG 版面板图，支持状态颜色编码与按机柜过滤。
PNG 格式待后续阶段实现。

### US-6：线缆打印标签导出（🆕 施工队刚需）

> **作为**站点工程师，
> **我想**一键导出所有线缆的打印标签（包含起端→终端信息、线缆类型、长度），
> **以便**施工队直接打印贴标，不用手写标签或从 Excel 里逐条复制。

**背景：**
在站点施工中，布线是耗时最长、最容易出错的环节。施工队需要给每根线缆两端贴标签，标注"从哪来、到哪去"。手写标签效率低、字迹潦草易出错，且一旦设计变更，所有手写标签需重写。piki 已有线缆 Connection 数据——自动生成可打印的标签 PDF 是自然的交付物延伸。

**验收标准：**

- `piki generate cable-labels` 导出所有线缆标签为单一 PDF（A4 排版，多行多列）
- 每张标签包含：
  - 线缆 ID（如 `CBL-A01-L1-001`）
  - 起端信息：`{设备ID} / {端口号}`（如 `SW-A01-01 / Gi1/0/1`）
  - 终端信息：`{设备ID} / {端口号}`
  - 线缆类型（如 `OM4-LC-LC`、`Cat6A-RJ45`）
  - 长度（如 `3.0m`）
  - （可选）一维条码或 QR 码，编码线缆 ID，支持扫码枪现场核验
- 标签尺寸可配置：默认 30mm × 15mm（适配 Brother / DYMO 标签打印机卷纸）
- 支持按机柜过滤：`piki generate cable-labels --rack RACK-A01`
- 支持按线缆类型过滤：`piki generate cable-labels --type fiber`
- 输出的 PDF 可直接发送打印店或办公室打印机

**当前状态：** ⚠️ 已实现 SVG 版线缆标签（`piki generate cable-labels`），A4 排版，每张标签含线缆 ID、起端/终端设备与端口、线缆类型、长度。PDF 格式与 QR 码待后续阶段实现。

**数据依赖：**

- `PortFamily`：设备端口号、端口类型（SFP+ / RJ45 / LC / MPO）
- `ConnectionFamily`：起端设备+端口、终端设备+端口、线缆类型、长度
- `CableFamily`（可选）：线缆规格模板（OM3/OM4/Cat6A/DAC），提供默认外径、颜色编码

---

### US-7：端口图 / 互连接线图导出

> **作为**站点工程师，
> **我想**导出设备间的端口互连图（哪个端口接哪根线、另一端在哪），
> **以便**施工队按图接线，不会插错端口。

**验收标准：**

- telecom 插件支持 PortFamily + ConnectionFamily（端口 + 线缆建模）
- `piki generate port-map` 按设备导出端口分配表
- `piki generate cable-schedule` 导出线缆清单（起端设备/端口 → 终端设备/端口 → 线缆类型 → 长度）
- 输入格式：SVG 拓扑图 + CSV 线缆表

**当前状态：** ✅ 已实现增强版。telecom 插件新增 `PortFamily`（设备端口）和 `PortConnectionFamily`（端口到端口连接），支持端口占用检查、连接端点检查、端口类型兼容性检查、线缆类型匹配检查，以及 `port-map`、`cable-schedule`、`port-diagram` 三个生成器。

**已实现能力：**

- `instances/ports/*.yaml`：用 `PortFamily` 定义每个物理端口
- `instances/port_connections/*.yaml`：用 `PortConnectionFamily` 定义 `from_port` / `to_port` 连接
- 连接引用格式：`DEVICE_ID/PORT_NAME`（与 ADR-005 接口引用一致）
- 5 条新规则：TELECOM-PORT-001/002、TELECOM-CONN-001/002/003
- `port-map` 生成器：输出每设备的端口占用与对端连接 CSV
- `cable-schedule` 生成器：输出带机柜平面位置与走线方式的路由描述
- `port-diagram` 生成器：输出设备间端口互连拓扑图 SVG
- `floor-plan` 生成器：输出机房平面布局 SVG

**待增强（阶段 3 后续）：**

- `piki generate cable-labels`：PDF 格式与 QR 码
- `piki generate port-diagram`：PNG 格式与更精细的布局

---

### US-8：3D 布局预览

> **作为**设计审核人，
> **我想**在浏览器中查看机柜和设备的三维布局，
> **以便**直观感知空间关系，不用在脑海里拼凑二维图纸。

**验收标准：**

- `piki generate usd-scene` 导出 USDA 场景文件
- Piki Studio 加载项目后渲染 3D 视口
- 支持旋转、平移、缩放
- 场景树 ↔ 3D 视口双向高亮同步
- 点击设备显示属性面板

**当前状态：** ✅ 已实现（USD 场景生成 + Studio v0.1.0 3D 预览）

---

### US-9：设计经验规则化沉淀

> **作为**技术骨干，
> **我想**把团队积累的设计经验（"GPU 服务器不能全放同一机柜""核心网设备必须双路 PDU"）写成可复用的规则，
> **以便**新人接手项目时自动走查，不依赖老人带。

**验收标准：**

- `rules/` 目录下 Python 文件，`@rule` 装饰器注册
- 规则支持读取 `piki.toml` 中的阈值配置（不硬编码）
- 规则支持 Tag 过滤（按专业、安全分区、所属系统筛选目标设备）
- 规则失败输出精确到文件和行号
- 提交前 pre-commit hook 自动运行所有规则

**当前状态：** ✅ 已实现（`@rule` + `ctx.query` + Tag 过滤 + pre-commit hook）

---

### US-10：命名规范自动检查

> **作为**技术骨干，
> **我想**定义设备 ID 的命名规范并自动检查（如 `SRV-{机柜后缀}-{序号}`），
> **以便**几百台设备不会出现命名混乱。

**验收标准：**

- 规则读取 Instance ID 和 Layout 中的 rack_id，校验命名一致性
- 规则失败输出具体设备 ID 和期望格式
- 支持不同设备类型定义不同命名规则

**当前状态：** ✅ 已实现（sample 03-data-center 中有 NAMING-001 规则作为参考）

---

### US-11：报告生成与分享

> **作为**设计审核人，
> **我想**生成可分享的设计检查报告（Markdown / PDF），
> **以便**在 PR 评论里引用、在评审会上投影、存档为合规证据。

**验收标准：**

- `piki report --format markdown` 生成 Markdown 报告
- `piki report --format json` 生成机器可解析报告
- `piki report --format junit` 生成 CI/CD 兼容报告
- 报告中列出每条失败规则的详情、建议

**当前状态：** ✅ 已实现（四种输出格式）

---

## 3. 功能矩阵与状态

| 用户故事 | 功能                                   | 状态      | 备注                             |
| -------- | -------------------------------------- | --------- | -------------------------------- |
| US-1     | 扩容方案校验（15 条规则）              | ✅ 已实现 | 含功率/U位/尺寸/碰撞/端口/连接/冗余/承重/散热/线缆/维护空间/机房平面 |
| US-2     | 多方案并行比选（Instance/Layout 分离） | ✅ 已实现 |                                  |
| US-3     | 型号库复用（三层模型 + Catalog）       | ✅ 已实现 | 引入真实厂商型号与 Catalog 权威层 |
| US-4     | BOM CSV 导出                           | ✅ 已实现 | 含品牌/MPN/单价等采购字段        |
| US-5     | 面板图 / U 位正视图                    | ✅ 已实现 | 文本+SVG，支持状态颜色编码与按机柜过滤 |
| US-6     | 线缆打印标签导出                       | ⚠️ 基础版 | SVG 标签已可用，PDF/QRC 码待实现 |
| US-7     | 端口图 / 互连接线图                    | ✅ 已实现 | port-map / cable-schedule / port-diagram |
| US-8     | 3D 布局预览                            | ⚠️ 待恢复 | USD 场景生成当前不可用，Studio 仍支持 |
| US-9     | 设计经验规则化                         | ✅ 已实现 |                                  |
| US-10    | 命名规范检查                           | ✅ 已实现 |                                  |
| US-11    | 报告生成（human/json/junit/md）        | ✅ 已实现 |                                  |

---

## 4. 优先级路线图

### 阶段 1：现在 — 设计校验闭环（piki 0.1.0）

✅ 已交付。站点工程师可以用 YAML 描述设备和部署，用 `piki check` 自动校验，用 `piki check --format json` 接入 CI/CD。

**价值：** 替代 Excel 里的手动核对。覆盖角色：技术骨干、设计审核人。

**局限：** 站点工程师仍需回 Excel 写 BOM、画端口图；面板图已可用（文本/SVG），但 PNG 输出和按机柜过滤尚未支持。

---

### 阶段 2：近期（目标 piki 0.2.0）— 补齐交付物

#### 2.1 BOM CSV 格式对齐（P0）

- 收集真实站点 BOM 模板，补充缺失字段（品牌、序列号、采购备注）
- 支持自定义列：`piki generate bom-csv --columns id,name,model,tdp_w,psu_count`
- 支持按 Tag 过滤：`piki generate bom-csv --filter tags__discipline=compute`

#### 2.2 面板图生成器增强（P0）

- ✅ 已注册 `rack-face-panel-svg` generator，按机柜生成 U 位正视图 SVG
- 颜色编码：绿色（installed）、蓝色（planned）、灰色（retired）
- 每格标注设备 ID + TDP + PDU
- 输出到 `dist/施工图/rack-panel-{rack_id}.svg`
- 支持批量生成：`piki generate rack-face-panel-svg` 生成所有机柜
- 待实现：按机柜过滤（`--rack`）、PNG 导出

#### 2.3 物理尺寸校验增强（P1）

- `TELECOM-RACK-003` 规则已实现设备和机柜的深度/宽度匹配检查
- 补充：设备重量 + 机柜承重检查（需 `RackFamily.max_load_kg` + `ServerFamily.weight_kg`）

---

### 阶段 3：中期（目标 piki 0.3.0）— 端口与线缆

#### 3.1 PortFamily + ConnectionFamily（P0）

- telecom 插件新增 `PortFamily`（设备级端口）和 `ConnectionFamily`（端口间连接）
- 或复用 datacenter 插件的 `ConnectionFamily`，向下兼容端口级粒度

#### 3.2 端口图 / 线缆清单生成器（P1）

- `piki generate port-map` → 每设备端口分配 SVG/CSV
- `piki generate cable-schedule` → 线缆清单 CSV
- 线缆长度自动检查规则：`TELECOM-CABLE-001`

---

### 阶段 4：远期（目标 piki 0.4.0+）— 协作与智能化

#### 4.1 Studio 在线编辑（P2）

- 浏览器端直接编辑 YAML 并回写文件系统
- Studio StatusBar 集成 `piki check` 结果

#### 4.2 外部数据同步（P2）

- `piki sync` 从 CMDB / 网管系统 / Excel 导入已有设备数据

#### 4.3 AI 辅助设计（P3）

- 自然语言描述需求 → 生成 Instance/Layout YAML → 自动跑 check → 通过后提交 PR

---

## 5. 非功能需求

### 5.1 性能

| 指标              | 目标        | 说明           |
| ----------------- | ----------- | -------------- |
| 单项目 check      | < 5s        | 200 台设备规模 |
| BOM CSV 生成      | < 1s        | 500 行         |
| 面板图生成        | < 2s / 机柜 | 42U 满配       |
| 线缆标签 PDF 生成 | < 3s        | 200 根线缆     |

### 5.2 数据安全

- 所有数据存储在本地文件系统
- 不上传任何数据到云端
- Git 控制访问权限

### 5.3 可迁移性

- 项目目录即完整设计：拷贝文件夹即可迁移
- 不依赖数据库、不依赖 SaaS 平台
- 依赖声明：`piki.toml` 中的插件列表

---

## 6. 与 datacenter 领域的关系

telecom 覆盖**站点级**（机柜内设备部署），datacenter 覆盖**方舱/园区级**（方舱间配电与连接）。两者互补：

|             | telecom             | datacenter                                     |
| ----------- | ------------------- | ---------------------------------------------- |
| 粒度        | 设备-U位-PDU        | 方舱-配电-连接                                 |
| 核心 Family | Rack / PDU / Server | Container / PowerUnit / Equipment / Connection |
| 典型用户    | 站点工程师          | 数据中心架构师                                 |
| 面板图需求  | ✅ 关键             | 不需要                                         |
| 端口图需求  | ✅ 关键             | 不需要                                         |
| PUE 计算    | —                   | ✅                                             |
| 方舱级连接  | —                   | ✅                                             |

---

## 7. 竞争对比：piki telecom vs Excel vs 专业网管软件

| 维度             | Excel               | 专业网管（NetBox / DCIM） | piki telecom          |
| ---------------- | ------------------- | ------------------------- | --------------------- |
| **方案校验**     | 手动                | 内置规则                  | ✅ Python 可定制规则  |
| **版本控制**     | ❌ 文件名缀日期     | ⚠️ 平台内置               | ✅ Git 精确 diff      |
| **面板图**       | 手动 Visio          | ✅ 自动生成               | ⚠️ 文本+SVG，PNG/过滤待实现 |
| **BOM 导出**     | 手动                | ✅                        | ⚠️ 基础版             |
| **线缆标签**     | 手写                | ⚠️ 需额外工具             | ✅ SVG 标签已可用     |
| **端口图**       | 手动                | ✅ 自动生成               | ✅ 已实现             |
| **机房平面图**   | 手动 Visio          | ✅ 自动生成               | ✅ 已实现             |
| **学习成本**     | 低                  | 高（需培训）              | 中（需 Python + Git） |
| **许可费用**     | 免费（Office 已购） | 昂贵                      | ✅ 开源免费           |
| **自定义规则**   | VBA / 公式          | ⚠️ 有限                   | ✅ Python 无限扩展    |
| **AI Readiness** | ❌                  | ❌ 闭源                   | ✅ Text-Native + 开源 |
| **离线可用**     | ✅                  | ❌ 需服务器               | ✅ 纯本地             |
| **3D 预览**      | ❌                  | ⚠️ 部分                   | ✅ Studio             |

---

## 8. 风险与缓解

| 风险                  | 影响                      | 缓解                                          |
| --------------------- | ------------------------- | --------------------------------------------- |
| 站点工程师不会 Python | 规则无法自维护            | 技术骨干先写好规则，站点工程师只需改 YAML     |
| Excel 习惯惯性大      | 推广阻力                  | 从"Excel + piki 并行"开始，不要求一步切换     |
| 面板图缺少 PNG/按机柜过滤 | 打印和单柜输出不便 | 阶段 2 补齐 PNG 与 `--rack` 过滤              |
| PortFamily 建模复杂度 | 端口图延期                | 先做面板图（数据已就绪），端口图在阶段 3 再做 |

---

## 9. 成功指标

### 阶段 1 成功指标（当前）

- [ ] Sample `02-telecom-rack` 可无错误运行 `piki check`
- [ ] Sample `03-data-center` 演示多机柜、Tag 过滤、自定义规则
- [ ] 至少 1 个外部团队跑通 POC（3 小时上手）

### 阶段 2 成功指标（面板图上线后）

- [x] 站点工程师从"打开 Excel 画面板图"改为"跑 `piki generate rack-face-panel-svg`"
- [x] BOM CSV 格式与现有采购流程兼容 ⚠️ 需对照实际 BOM 模板验证
- [ ] `piki check` 替代人工校审，错误拦截率 ≥ 人工水平

### 阶段 3 成功指标（端口图上线上后）

- [ ] telecom 插件覆盖站点工程师完整交付物：方案校验 + BOM + 面板图 + 端口图 + 线缆表
- [ ] Excel 只作为"查看"和"交接"用途，不作为设计源头

---

## 10. 附录：telecom 插件已注册的规则一览

| 规则 ID               | 名称                 | 严重度  | 说明                                     |
| --------------------- | -------------------- | ------- | ---------------------------------------- |
| TELECOM-POWER-001     | PDU 功率预算检查     | ERROR   | PDU 负载率不超过 `power_threshold`       |
| TELECOM-POWER-002     | PDU 相线平衡检查     | WARNING | 同机柜多相 PDU 负载不平衡度              |
| TELECOM-RACK-001      | U 位冲突检查         | ERROR   | 同机柜内设备 U 位不能重叠                |
| TELECOM-RACK-002      | 机柜容量检查         | ERROR   | 设备总 U 位不超过 `rack_usage_threshold` |
| TELECOM-RACK-003      | 物理尺寸匹配检查     | WARNING | 设备深度/宽度不超过机柜尺寸              |
| TELECOM-COLLISION-001 | 3D 碰撞检测          | WARNING | 同机柜内设备 AABB 空间冲突               |
| TELECOM-FK-001        | 外键完整性检查       | WARNING | rack_id、pdu_id 引用有效性               |
| TELECOM-PORT-001      | 端口占用冲突检查     | ERROR   | 同一设备内端口名不能重复                 |
| TELECOM-PORT-002      | 端口所属设备存在性检查 | ERROR   | PortFamily 的 device_id 必须存在         |
| TELECOM-CONN-001      | 连接端点存在性检查   | ERROR   | from_port / to_port 引用必须存在         |
| TELECOM-CONN-002      | 连接端口类型兼容性检查 | ERROR   | 两端 port_type 必须兼容                  |
| TELECOM-CONN-003      | 连接线缆类型匹配检查 | ERROR   | cable_type 必须与端口类型匹配            |
| TELECOM-WEIGHT-001    | 机柜承重检查         | ERROR   | 设备总重量不超过 `rack.max_load_kg`      |
| TELECOM-COOL-001      | 机柜散热能力检查     | ERROR   | 设备总 TDP 不超过 `rack.cooling_capacity_w` |
| TELECOM-CABLE-001     | 线缆长度规格检查     | ERROR   | 光纤跳线长度不超过型号 `max_distance_m`  |
| TELECOM-REDUNDANCY-001| 核心设备双路 PDU 冗余检查 | ERROR | 核心/汇聚设备必须双路 PDU 供电           |
| TELECOM-MAINTENANCE-001| 设备维护空间检查    | WARNING | 机柜前后维护空间满足规范值               |
| TELECOM-FLOOR-001     | 机柜平面布局碰撞检查 | ERROR   | 机房内机柜投影矩形不能重叠               |
| TELECOM-FLOOR-002     | 机柜维护通道宽度检查 | WARNING | 同列机柜间距、列间通道满足规范值         |
| TELECOM-FLOOR-003     | 机柜编号规范检查     | WARNING | 机柜编号与所在列/行一致                  |
| CATALOG-LIFECYCLE-001 | 禁止非既有工程使用 EOL 器件 | ERROR | 仅 `context=existing` 允许使用 EOL 器件 |
