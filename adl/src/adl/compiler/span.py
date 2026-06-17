"""Span：源码位置追踪。

AST 每个节点携带 Span，支持精确到行列的源码定位。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, order=True)
class Span:
    """源码中的一个连续区域。

    行号从 1 开始，列号从 1 开始。
    单点位置：start == end。
    """

    source: Path
    start_line: int
    start_col: int
    end_line: int
    end_col: int

    @classmethod
    def point(cls, source: Path, line: int, col: int) -> "Span":
        return cls(source, line, col, line, col)

    @classmethod
    def synthetic(cls) -> "Span":
        """合成 Span（编译器内部生成，无对应源码）。"""
        return cls(Path("<synthetic>"), 0, 0, 0, 0)

    def merge(self, other: "Span") -> "Span":
        """合并两个 Span，取覆盖范围。"""
        assert self.source == other.source
        if self.start_line < other.start_line or (
            self.start_line == other.start_line and self.start_col <= other.start_col
        ):
            sl, sc = self.start_line, self.start_col
        else:
            sl, sc = other.start_line, other.start_col
        if self.end_line > other.end_line or (
            self.end_line == other.end_line and self.end_col >= other.end_col
        ):
            el, ec = self.end_line, self.end_col
        else:
            el, ec = other.end_line, other.end_col
        return Span(self.source, sl, sc, el, ec)

    def __repr__(self) -> str:
        return (
            f"{self.source.name}:{self.start_line}:{self.start_col}"
            f"-{self.end_line}:{self.end_col}"
        )
