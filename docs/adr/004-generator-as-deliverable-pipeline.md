# ADR-004: 生成器——从文本真相源到工程交付物

> 状态：已实现
> 日期：2026-06-12
> 作者：piki 核心团队
> 替代：无（独立决策）

## 背景

piki 的核心价值主张是 Text-Native：工程师用 YAML 声明设计意图，规则引擎校验合理性。但工程设计最终要**交付给施工队、甲方、监理**——他们不读 YAML，他们看图、看表、看标签。

本 ADR 记录 piki 的生成器（Generator）设计决策：为什么需要生成器、如何设计、产物如何管理。

---

## 1. 问题域：从声明到交付的"最后一公里"

### 1.1 Text-Native 的背面

| 角色       | 消费什么                      | 格式                   |
| ---------- | ----------------------------- | ---------------------- |
| 设计工程师 | YAML 设计文件                 | 文本                   |
| 设计审核人 | `piki check` 报告 + Studio 3D | Markdown / 3D          |
| 施工队长   | 面板图、端口图、线缆标签      | SVG / PDF / 可打印制品 |
| 采购       | BOM 设备清单                  | CSV / Excel            |
| 甲方/监理  | 方案交底材料                  | PDF / 打印图纸         |

YAML 是设计的真相源，但不是交付物的合适格式。piki 需要一种机制，让文本设计**自动派生**出各类下游消费者所需的视觉和结构化制品。

### 1.2 为什么不能依赖 Studio 截图或手动操作

- **不可复现**：每次截图结果取决于视口参数、当前分支，无法在 CI 中自动生成
- **格式不统一**：不同工程师截的图尺寸、标注各异
- **版本无法追溯**：截图无 git diff，无法与特定设计版本建立精确对应
- **不是自动化流程的一部分**：无法在 `pre-commit` 或 CI 中自动生成最新版本

---

## 2. 核心决策：生成器是 Text-Native 的派生层

### 2.1 定位

```
Text Truth Source (YAML) ──check──▶ 校验结果 (Diagnostic)
         │
         └── generate ──▶ 交付物 (GeneratorResult)
                              │
                              ├── BOM CSV       (采购)
                              ├── 面板图 SVG    (施工)
                              ├── 功率汇总 CSV  (设计评审)
                              ├── 线缆清单 CSV  (采购/施工)
                              └── 端口图 SVG    (施工 — 规划中)
```

**生成器不修改设计，只消费设计。** 这个管道很像一个工程编译器：输入 YAML 声明，经过解析和校验，输出多种格式的交付物，类似于编译器将源代码编译为不同目标架构的机器码。

这与 Checker 的规则引擎形成对称：

- **Rule（规则）**：声明式约束，返回 Diagnostic（通过/失败/警告）
- **Generator（生成器）**：声明式模板，返回 GeneratorResult（内容 + 文件路径 + MIME 类型）

### 2.2 选择 Generator（而非硬编码命令）

| 维度       | 硬编码命令                          | Generator 插件化                                 |
| ---------- | ----------------------------------- | ------------------------------------------------ |
| 扩展性     | 每个产物 type 需修改 CLI 核心代码   | 插件注册 `@generator` 装饰器即可                 |
| 领域隔离   | 核心代码知道"面板图""BOM"等电信概念 | 电信概念完全在 telecom 插件内                    |
| 多语言绑定 | 每个命令需在多语言 SDK 中重新实现   | Generator 口径统一，SDK 只消费 GeneratorResult   |
| 组合能力   | 不支持                              | 多个生成器可串接（面板图 → 合并 → 加封面 → PDF） |

### 2.3 GeneratorResult 设计

```python
@dataclass
class GeneratorResult:
    generator_id: str       # "rack-face-panel-svg"
    generator_name: str     # "机柜面板图 SVG"
    success: bool           # 是否成功
    content: str            # 文本产物
    file_path: Path | None  # 写入的文件路径
    content_type: str       # MIME 类型提示 ("image/svg+xml" / "text/csv")
    error: str              # 失败信息
```

**关键设计决策**：返回结构化值而非 side-effect（print / write）。这让 SDK 调用者可以：

- 程序化消费生成器输出（如嵌入 CI 报告的 HTML body）
- 自行决定如何呈现（写文件 / 上传 OSS / 发飞书消息）
- 组合多个生成器（面板图 → 合并 → 加标题 → 输出 PDF）

CLI 层面，`cmd_generate` 对 GeneratorResult 做约定渲染：`content` 打印到 stdout，`file_path` 提示输出路径。

---

## 3. 产物管理：`dist/` 目录约定

### 3.1 问题

当前所有生成器产物通过 `--output` 手动指定路径。这导致三个问题：

1. **无约定路径**：不同工程师把产物放在不同位置，协作混乱
2. **无场景分组**：BOM 和面板图是给不同角色看的，但散落在同一目录
3. **无 Git 策略**：不知道产物应该 version 还是 ignore

### 3.2 决策：引入 `dist/` 目录，按交付场景分类

```text
project/
├── dist/                       # 产物根目录
│   ├── 施工图/                 # 施工队看图施工
│   │   ├── rack-panel-{RACK_ID}.svg
│   │   ├── port-map-{RACK_ID}.svg   (规划中)
│   │   └── cable-labels.pdf         (规划中)
│   ├── 采购清单/               # 采购/供应链
│   │   ├── bom.csv
│   │   └── cable-list.csv
│   └── 设计评审/               # 设计交底/甲方沟通
│       ├── power-budget.csv
│       └── check-report.md
```

### 3.3 约定细节

| 约定              | 规则                                                      | 理由                                      |
| ----------------- | --------------------------------------------------------- | ----------------------------------------- |
| 目录名            | `dist/` 固定根，子目录按交付场景中文命名                  | 施工队、采购读得懂                        |
| Git               | 建议 `gitignore`，但可 `git add` 里程碑快照               | 产物可从 YAML 重新生成，不应进入日常 diff |
| 场景映射          | 每个生成器在元数据中声明 `target_dir`（如 `dist/施工图`） | 生成器知道自己的受众                      |
| 多文件拆分        | 多机柜场景自动按机柜 ID 拆分为独立文件                    | 施工队每个机柜拿一张图                    |
| `--output` 优先级 | `--output` 显式路径 > `dist/` 约定路径                    | 允许临时导出覆盖                          |

### 3.4 为什么用中文子目录名

- **受众是工程人员**，不是开发者。他们不读 API 文档。
- **与 PRD 中的用户故事对齐**：US-5 "面板图"，US-4 "BOM 清单"，US-6 "端口图"
- **降低沟通成本**：说"看 dist/施工图/rack-panel-RACK-A01.svg"不需要解释

### 随时可改回英文

目录名是在生成器元数据中声明的字符串，不是硬编码在核心引擎中。如果团队约定用英文，修改 telecom 插件中一行即可。

---

## 4. `piki generate` 增强

### 4.1 新的 CLI 行为

```bash
# 运行单个生成器，输出到 dist/ 约定路径
piki generate rack-face-panel-svg          # → dist/施工图/rack-panel-*.svg

# 显式指定输出路径（覆盖约定）
piki generate rack-face-panel-svg --output /tmp/panel.svg

# 运行所有启用的生成器（通过 piki.toml 配置）
piki generate                              # → dist/ 下各子目录
```

### 4.2 `piki.toml` 配置

```toml
[generators]
enabled = ["bom-csv", "rack-face-panel-svg", "power-budget", "cable-list"]

[generators.dist]
# 产物根目录（相对于项目根目录），默认 "dist"
root = "dist"

# 按生成器覆盖场景目录（可选）
[generators.dist.targets]
bom-csv = "采购清单"
rack-face-panel-svg = "施工图"
power-budget = "设计评审"
cable-list = "采购清单"
```

### 4.3 生成器侧的责任

每个生成器函数负责：

1. 接收 `config` dict（包含 `dist_dir` 和 `target_dir`）
2. 如果有多个产出文件，按适当的 key 拆分（如 `rack_id`）
3. 返回 `GeneratorResult` 含 `file_path`

生成器**不负责**：

- 创建 `dist/` 目录（CLI 层负责）
- 决定 Git 策略（`.gitignore` 由 `piki init` 生成）
- 文件命名规范（由生成器自行决定，但建议 `{type}-{id}.{ext}`）

---

## 5. 生成器与外部系统联动：从手动分发到自动化开通

### 5.1 为什么 piki 不做内置集成

`GeneratorResult` 返回的是结构化数据（`content` + `file_path` + `content_type`）——它不关心下游是谁。piki 核心**不内置**邮件发送、IM 通知、网盘上传、多维表格写入。原因：

- **边界清晰**：piki 负责"从设计到交付物"，分发是另一个问题域
- **生态多样**：不同团队用不同的 IM（飞书、企微、Slack）、不同的存储（S3、企业网盘、OSS）、不同的流程引擎
- **避免膨胀**：每多一个集成，核心代码多一份维护负担

### 5.2 对接模式：两阶段演进

```
阶段一（手动触发）              阶段二（自动开通）
┌──────────────────┐            ┌──────────────────┐
│ 工程师本地改 YAML │            │ CI/CD 触发       │
│   ↓               │            │   ↓               │
│ piki check        │            │ piki check        │
│   ↓               │            │   ↓               │
│ piki generate     │            │ piki generate     │
│   ↓               │            │   ↓               │
│ 产物写入 dist/    │            │ GeneratorResult   │
│   ↓               │            │   ↓               │
│ 人工审查          │            │ 脚本/SDK 消费     │
│   ↓               │            │   ├── 飞书消息     │
│ 手动发邮件/IM     │            │   ├── 邮件附件     │
│   └── 发施工队     │            │   ├── 多维表格     │
└──────────────────┘            │   ├── 网盘归档     │
                                │   └── 自动审批流转  │
                                └──────────────────┘
```

**阶段一（当前）**：工程师手动运行 `piki generate`，产物写入 `dist/`，人工审查后通过邮件或 IM 发给施工队/采购。

**阶段二（自动化）**：CI/CD 触发 `piki check && piki generate`，外部脚本消费 `GeneratorResult`：

- `content_type == "text/csv"` → 写入飞书多维表格，自动更新 BOM 台账
- `content_type == "image/svg+xml"` → 作为邮件附件或飞书消息卡片发送给施工队长
- `file_path` → 上传至企业网盘或 OSS，生成分享链接
- 检查全通过 → 自动触发审批流程；有失败 → 通知设计工程师修正

### 5.3 典型集成场景

| 场景 | 触发方式 | GeneratorResult 消费 |
|---|---|---|
| 设计变更通知 | `git push` → CI | `content` 嵌入飞书/Slack 消息卡片 |
| BOM 自动入库 | `git tag v1.0` → CI | CSV 写入飞书多维表格或 ERP |
| 施工图分发 | 手动 `piki generate` | SVG 上传网盘，链接发施工群 |
| 审批流转 | CI 全通过 → webhook | `success=True` 触发 OA 审批 |
| 竣工归档 | 项目结项 → 脚本 | 全部 `file_path` 打包上传归档系统 |

### 5.4 piki 提供什么，团队自己做什么

| piki 提供 | 团队/插件自行实现 |
|---|---|
| `GeneratorResult.content` | 飞书消息格式化、邮件正文拼装 |
| `GeneratorResult.file_path` | 上传 OSS/网盘、作为邮件附件 |
| `GeneratorResult.content_type` | 路由到不同的下游系统 |
| `GeneratorResult.success` | 决定触发审批还是打回修正 |
| `--output` 显式路径 | 临时导出到共享目录 |
| `dist/` 约定路径 | 脚本直接扫描 `dist/采购清单/*.csv` |

---

## 6. 与现有 ADR 的关系

| ADR                     | 关系 | 说明                                                  |
| ----------------------- | ---- | ----------------------------------------------------- |
| ADR-002（插件架构）     | 依赖 | Generator 通过 `@generator` 装饰器在插件中注册        |
| ADR-003（多级检查）     | 互补 | Checker 输出诊断 → Generator 输出制品，目标消费者不同 |
| ADR-008（空间可视化）   | 互补 | Studio 是交互式沟通媒介，Generator 是标准化交付物     |
| ADR-007（CAD 资产引用） | 互补 | Generator 可引用 `assets.mesh` 渲染带厂商几何的面板图 |

---

## 7. 决策总结

| 决策       | 选择                             | 核心理由                       |
| ---------- | -------------------------------- | ------------------------------ |
| 生成器定位 | Text-Native 的派生层，不修改设计 | 文本是唯一真相源               |
| 扩展方式   | `@generator` 装饰器 + 插件注册   | 领域隔离，核心不膨胀           |
| 返回值     | 结构化 `GeneratorResult`         | 支持 CLI 和 SDK 两种消费方式   |
| 产物管理   | `dist/` 目录，按交付场景分类     | 降低施工队/采购/甲方的沟通成本 |
| 外部集成   | GeneratorResult 结构化输出 + 外部脚本 | 核心不膨胀，集成团队自行实现 |
| 中文子目录 | 受众优先，可随时改回英文         | 降低工厂人员认知负担           |
| Git 策略   | 默认 `gitignore`，里程碑手动存档 | 产物可重新生成，不应日常 diff  |

---

## 参考

- [ADR-002: 插件架构](002-plugin-architecture.md)
- [Telecom 领域 PRD](../../samples/01-telecom-expansion/PRD.md)
- [GeneratorRegistry 源码](../../src/piki/core/engine/generator_registry.py)
