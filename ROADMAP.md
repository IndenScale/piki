# piki 路线图

> 当前版本：**0.1.0（Alpha）** — 核心框架可用，CLI 五大命令完整，两个行业插件就绪。

---

## 已实现

| 模块 | 功能 | 版本 |
|------|------|------|
| CLI | `piki init` / `check` / `report` / `generate` / `plugins list` | 0.1.0 |
| 核心 | Family → Model → Instance 三层声明式建模 | 0.1.0 |
| 核心 | Instance/Layout 分离 (ADR-008) | 0.1.0 |
| 核心 | 嵌套项目 + FQID (ADR-009) | 0.1.0 |
| 核心 | Tag 正交过滤（tags__discipline=compute） | 0.1.0 |
| 核心 | Django-style QuerySet（__gt / __in / __contains 等 9 个操作符） | 0.1.0 |
| 核心 | LSP 兼容诊断（severity / range / relatedInformation） | 0.1.0 |
| 核心 | Schema 校验 + 行级错误定位 | 0.1.0 |
| 核心 | 4 种输出格式（human / json / junit / markdown） | 0.1.0 |
| 插件 | telecom（机柜 + PDU + 服务器，7 条规则 + BOM CSV） | 0.1.0 |
| 插件 | datacenter（方舱 + 配电 + 设备 + 连接，5 条规则 + DC BOM CSV） | 0.1.0 |
| 几何 | USD 场景生成（外部引用 / InlineGeometry / CSG / 代理 Box） | 0.1.0 |
| 几何 | AABB 碰撞检测（同一机柜内设备） | 0.1.0 |
| 几何 | CSG 布尔运算（依赖 manifold3d，可选安装） | 0.1.0 |
| Studio | 浏览器端 3D 预览 IDE（Three.js + USDA 解析器 + File System Access API） | 0.1.0 |
| Git | `piki init` 自动安装 pre-commit hook | 0.1.0 |

---

## 规划中

以下特性尚未实现，按优先级排序：

### 高优先级

- **增量检查** (`piki check --incremental`) — 只检查发生变更的文件，大幅提升大项目性能
- **并行检查** (`piki check --parallel N`) — 多核并行运行规则
- **解析缓存** — 缓存 Family/Model/Instance 解析结果，避免重复计算
- **项目级 Family 定义** — 在 `families/` 目录定义项目特有的设备族，不依赖插件

### 中优先级

- **外部数据同步** (`piki sync`) — 从外部 API / 数据库拉取数据并转为 YAML
- **数据库导入** — 从 PostgreSQL / MySQL 导入已有设计数据
- **敏感字段加密** — `enc:` 前缀标记需要加密存储的字段
- **`piki check --watch`** — 文件变更时自动重新检查

### 低优先级

- **Piki Studio 在线编辑** — 在浏览器中直接编辑 YAML 并回写文件系统
- **Piki Studio 集成 check 结果** — 在 StatusBar 显示 `piki check` 输出
- **多语言 SDK** — piki-sdk-js / piki-sdk-rust
- **在线注册中心** — 社区共享的型号库和规则库

---

## 版本策略

- **0.x** — 快速迭代，API 可能变动
- **1.0** — API 稳定，向后兼容承诺

反馈和建议：[GitHub Issues](https://github.com/indenscale/piki/issues)
