"""项目自定义规则：命名规范检查。

本示例展示如何编写项目级规则，检查设备命名是否符合
数据中心统一命名规范。
"""

import re

from piki.core.engine.checker import rule
from piki.core.engine.context import Context


@rule("DC-NAMING-001", "设备命名规范检查")
def check_device_naming(ctx: Context) -> None:
    """检查设备 ID 是否符合命名规范：SRV-<机柜>-<序号>。

    规范格式：
    - SRV-A01-01  ✓ 正确
    - SRV-A01-1   ✗ 序号必须两位
    - server-01   ✗ 前缀必须是 SRV
    """
    pattern = re.compile(r"^SRV-[A-Z]\d{2}-\d{2}$")

    for device in ctx.query("devices"):
        ctx.set_current_file(str(device.source))
        assert pattern.match(device.id), (
            f"设备 {device.id} 命名不符合规范。"
            f"期望格式: SRV-<机柜>-<两位序号>，例如 SRV-A01-01"
        )
    ctx.clear_current_file()
