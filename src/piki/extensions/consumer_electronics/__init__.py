"""piki-consumer-electronics 内置扩展：消费电子通用抽象。

提供跨具体产品域（键盘、耳机、手环、IoT 等）共享的抽象：
- Net：电气网络（多节点）
- OperatingEnvironment：使用环境谱
- PowerBudget：功耗/电流预算工具函数
"""

from .plugin import ConsumerElectronicsPlugin

__all__ = ["ConsumerElectronicsPlugin"]
