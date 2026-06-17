"""轴网（Grid）数据模型。

Grid 把建筑/机房中的定位轴线系统表达为可解析的资源，
让 ``grid_id`` / ``grid_position`` 能从符号坐标自动换算成绝对坐标。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from adl.geometry import Vec3


def _vec3_from_value(value: Any) -> Any:
    """把 ``[x, y, z]`` 列表简写转换为 Vec3 dict。"""
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return {"x": value[0], "y": value[1], "z": value[2]}
    return value


class GridAxis(BaseModel):
    """轴网中的一组平行轴线。

    例如机房中的所有 "排" 线（A/B/C...）或所有 "列" 线（1/2/3...）。
    """

    direction: Vec3 = Field(default_factory=lambda: Vec3(x=0.0, y=1.0, z=0.0))
    lines: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _accept_list_direction(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if isinstance(data.get("direction"), (list, tuple)):
            data["direction"] = _vec3_from_value(data["direction"])
        return data

    def position_of(self, line_id: str) -> float | None:
        """返回指定轴线的坐标值，不存在返回 None。"""
        return self.lines.get(line_id)


class Grid(BaseModel):
    """轴网资源。

    当前仅支持正交轴网（orthogonal），由两组互相垂直的平行轴线构成。
    未来可扩展为放射网格（radial）或不规则网格（irregular）。
    """

    id: str
    type: Literal["orthogonal"] = "orthogonal"
    origin: Vec3 = Field(default_factory=Vec3)
    axes: list[GridAxis] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_list_origin(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if isinstance(data.get("origin"), (list, tuple)):
            data["origin"] = _vec3_from_value(data["origin"])
        return data

    @model_validator(mode="after")
    def _check_orthogonal_axes(self):
        if self.type != "orthogonal":
            return self
        if len(self.axes) != 2:
            raise ValueError("orthogonal grid requires exactly 2 axes")
        if not self.axes[0].lines or not self.axes[1].lines:
            raise ValueError("each grid axis must have at least one line")
        return self

    def resolve(self, axis_a_id: str, axis_b_id: str) -> Vec3 | None:
        """把两个轴号解析为全局坐标点。

        ``axis_a_id`` 对应第一组轴（axes[0]），``axis_b_id`` 对应第二组轴（axes[1]）。
        返回值 = origin + pos_a * direction_a + pos_b * direction_b。
        任一轴号不存在时返回 None。
        """
        if len(self.axes) != 2:
            return None
        pos_a = self.axes[0].position_of(axis_a_id)
        pos_b = self.axes[1].position_of(axis_b_id)
        if pos_a is None or pos_b is None:
            return None

        dir_a = self.axes[0].direction
        dir_b = self.axes[1].direction

        return Vec3(
            x=self.origin.x + pos_a * dir_a.x + pos_b * dir_b.x,
            y=self.origin.y + pos_a * dir_a.y + pos_b * dir_b.y,
            z=self.origin.z + pos_a * dir_a.z + pos_b * dir_b.z,
        )

    def has_line(self, axis_index: int, line_id: str) -> bool:
        """检查指定轴组中是否存在指定轴线。"""
        if axis_index < 0 or axis_index >= len(self.axes):
            return False
        return line_id in self.axes[axis_index].lines
