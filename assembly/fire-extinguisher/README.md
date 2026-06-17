# 灭火器地面放置

**配合类型**: 面面配合 (face-on-face mate)

**参数**: 4 个自由度 — 基准面上位置 (u, v) + 绕法向旋转 (θ) + 离地距离 (d)

**求解器**: `solve_face_mate()` — 参见 `adl/src/adl/compiler/constraint_solver.py`

## 运行

```bash
open assembly/fire-extinguisher/index.html
```

## 几何推导

```
y_child = y_ground_top + distance + child_half_height
        = 100 + d + 250

x_child = u (基准面坐标)
z_child = v
rot_y = θ
```
