# FC 光纤连接器

**配合类型**: 槽配合 + 阶段锁 (slot mate with staged DOF locking)

**阶段**:
1. **自由阶段** — 插头可轴向移动，旋转锁死
2. **锁紧阶段** — 完全插入后，旋转解锁

**参数**: 2 个自由度
- 插入深度 t (0-15mm) — 始终活跃
- 旋转角度 θ (0-30°) — 仅在 inserted 状态活跃

**签名模型**: `FC-fiber-plug` / `FC-fiber-adapter`

## 运行

```bash
open assembly/fc-fiber-connector/index.html
```
