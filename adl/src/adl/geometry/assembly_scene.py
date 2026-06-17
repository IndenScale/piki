"""AssemblyScene —— ADL 装配体场景中间表示。

把 ``Project`` 解析成一个轻量、可序列化的场景描述，供浏览器 viewer、
USD 生成器或其他渲染后端消费。

坐标单位统一为毫米（mm），与 ADL 内部一致；渲染器按需转换。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from adl.diagnostics import Diagnostic
from adl.geometry.models import AssetReference, InlineGeometry, Transform


@dataclass
class InterfacePose:
    """实例上某个接口在全局坐标系中的位姿。"""

    id: str
    interface_type: str
    transform: Transform
    local_transform: Transform = field(default_factory=Transform)
    active_type: str | None = None
    direction: str = "bidirectional"
    description: str = ""
    specs: dict[str, Any] = field(default_factory=dict)
    mating_kind: str = "none"
    mating_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssemblyMaterial:
    """简化材质描述，足以在 Three.js/USD 中建立基础外观。"""

    color: str = "#888888"
    wireframe: bool = False
    opacity: float = 1.0
    roughness: float = 0.5
    metalness: float = 0.0


@dataclass
class AssemblyEntity:
    """场景中的一个装配体实例。"""

    id: str
    label: str
    family: str
    transform: Transform
    geometry: InlineGeometry | AssetReference
    material: AssemblyMaterial = field(default_factory=AssemblyMaterial)
    interfaces: list[InterfacePose] = field(default_factory=list)
    resolved: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssemblyControl:
    """前端交互控件定义。"""

    id: str
    type: Literal["slider", "button"]
    target: str
    param: str
    label: str
    min: float = 0.0
    max: float = 0.0
    default: float = 0.0
    step: float = 1.0
    # button 专用：可选的状态列表
    states: list[str] = field(default_factory=list)
    # 当前激活状态（用于 button）
    current_state: str = ""


@dataclass
class AssemblyScene:
    """装配体场景完整描述。"""

    name: str = ""
    description: str = ""
    entities: list[AssemblyEntity] = field(default_factory=list)
    controls: list[AssemblyControl] = field(default_factory=list)
    collisions: list[tuple[str, str]] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def entity_by_id(self, entity_id: str) -> AssemblyEntity | None:
        for e in self.entities:
            if e.id == entity_id:
                return e
        return None
