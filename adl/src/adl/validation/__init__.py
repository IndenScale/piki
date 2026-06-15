"""ADL 声明层验证。

提供 ``ADLValidator`` 对已经加载的 ``Project`` 执行引用完整性、Mate 约束、
Catalog 引用、FQID 冲突等验证。
"""

from .validator import ADLValidator

__all__ = ["ADLValidator"]
