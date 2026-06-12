"""piki-consumer-electronics 内置插件：消费电子通用抽象。

提供跨产品域共享的 Family、Rule 和工具函数：
- NetFamily：电气网络（多节点连接）
- OperatingEnvironmentFamily：使用环境谱
- 功耗/电流预算辅助函数
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from piki.core.engine.checker import Checker
from piki.core.engine.context import Context
from piki.core.engine.registry import Registry
from piki.core.models.diagnostic import Severity
from piki.core.models.interface import (
    InterfaceSpec,
    get_interfaces_from_resolved,
    register_interface_types,
)
from piki.core.models.tags import Tags
from piki.core.plugin import Plugin

# ---------------------------------------------------------------------------
# 消费电子通用接口类型
# ---------------------------------------------------------------------------

CONSUMER_ELECTRONICS_INTERFACE_TYPES = [
    # 电源
    "vbus",
    "gnd",
    "vcc-3v3",
    "vcc-5v",
    "vbat",
    "battery-positive",
    "battery-negative",
    # 数据
    "usb2-dp",
    "usb2-dn",
    "usb3-sstx-p",
    "usb3-sstx-n",
    "usb3-ssrx-p",
    "usb3-ssrx-n",
    "usb-cc",
    "usb-sbu",
    "i2c-sda",
    "i2c-scl",
    "spi-mosi",
    "spi-miso",
    "spi-sclk",
    "spi-cs",
    "uart-tx",
    "uart-rx",
    "swd-io",
    "swd-clk",
    # 无线
    "antenna-2g4",
    "antenna-5g",
    "antenna-gnss",
    # 通用
    "gpio",
    "adc",
    "pwm",
    "interrupt",
]


# ---------------------------------------------------------------------------
# Family 定义
# ---------------------------------------------------------------------------


class NetFamily(BaseModel):
    """电气网络：连接多个接口的多节点网络。

    替代 piki 核心的 point-to-point Connection，用于表达：
    - 电源/地网络
    - 键盘矩阵行/列
    - USB 数据/电源
    - I2C/SPI/UART 总线
    """

    id: str = Field(...)
    name: str = Field(default="")
    net_type: str = Field(...)  # power, ground, matrix_row, matrix_col, data, differential_pair
    nodes: list[str] = Field(default_factory=list)  # ["PCB-01/VBUS", "CABLE-01/VBUS"]
    protocol: str = Field(default="")  # usb2, usb3, i2c, spi, uart
    voltage_v: float = Field(default=0, ge=0)
    current_limit_ma: float = Field(default=0, ge=0)
    description: str = Field(default="")
    tags: Tags = Field(default_factory=Tags)

    @model_validator(mode="after")
    def check_node_format(self):
        """节点必须是 instance_id/interface_id 格式。"""
        for node in self.nodes:
            if "/" not in node:
                raise ValueError(f"Net node '{node}' 格式无效，应为 'instance_id/interface_id'")
        return self


class OperatingEnvironmentFamily(BaseModel):
    """使用环境谱：描述产品预期运行的环境条件。"""

    id: str = Field(...)
    name: str = Field(default="")
    temperature_min_c: float = Field(default=-20)
    temperature_max_c: float = Field(default=60)
    humidity_min_pct: float = Field(default=0, ge=0, le=100)
    humidity_max_pct: float = Field(default=95, ge=0, le=100)
    uv_exposure_hours_per_year: float = Field(default=0, ge=0)
    salt_spray: bool = Field(default=False)
    ip_rating_required: str = Field(default="")  # IP65, IP67
    fire_rating_required: str = Field(default="")  # UL94-V0
    description: str = Field(default="")
    tags: Tags = Field(default_factory=Tags)


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class ConsumerElectronicsPlugin(Plugin):
    name = "consumer-electronics"
    version = "0.1.0"

    @property
    def model_dir(self) -> Path:
        return Path(__file__).parent / "models"

    def register_families(self, registry: Registry) -> None:
        register_interface_types(CONSUMER_ELECTRONICS_INTERFACE_TYPES)
        registry.add_family("NetFamily", NetFamily)
        registry.add_family("OperatingEnvironmentFamily", OperatingEnvironmentFamily)

    def register_mate_types(self, registry: Registry) -> None:
        # Net 不是 Mate，不需要注册 Mate type
        pass

    def register_rules(self, checker: Checker) -> None:
        checker.add_rule(
            "CE-NET-001",
            "Net 节点格式与存在性检查",
            check_net_nodes,
            priority=10,
            severity=Severity.ERROR,
        )
        checker.add_rule(
            "CE-NET-002",
            "Net 节点接口类型兼容",
            check_net_interface_compatibility,
            priority=5,
            severity=Severity.ERROR,
        )

    def register_generators(self, checker: Checker) -> None:
        pass


# ---------------------------------------------------------------------------
# 规则实现
# ---------------------------------------------------------------------------


def _parse_node_ref(node: str) -> tuple[str, str]:
    """解析 Net node 引用。"""
    if "/" not in node:
        raise ValueError(f"Invalid net node: {node}")
    inst_id, iface_id = node.split("/", 1)
    return inst_id.strip(), iface_id.strip()


def _find_interface(ctx: Context, instance_id: str, interface_id: str) -> InterfaceSpec | None:
    """查找指定实例的接口定义。"""
    inst = ctx.find_instance(instance_id)
    if inst is None:
        return None
    for iface in get_interfaces_from_resolved(inst):
        if iface.id == interface_id:
            return iface
    return None


def check_net_nodes(ctx):
    """检查 Net 的所有节点指向真实存在的实例和接口。"""
    for net in ctx.query("nets"):
        for node in net.resolved.nodes:
            inst_id, iface_id = _parse_node_ref(node)
            inst = ctx.find_instance(inst_id)
            assert inst is not None, f"Net {net.id} 节点 {node} 引用的实例 {inst_id} 不存在"
            iface = _find_interface(ctx, inst_id, iface_id)
            assert iface is not None, (
                f"Net {net.id} 节点 {node} 引用的接口 {iface_id} 在实例 {inst_id} 上不存在"
            )


def check_net_interface_compatibility(ctx):
    """检查同一 Net 的所有节点接口类型是否兼容。

    按 net_type 使用不同的兼容性策略：
    - power/ground: 必须是同类电源/地接口
    - matrix_row/matrix_col: 允许 gpio 与 switch-pin 混接
    - data/differential_pair: 允许协议定义的差异对
    """
    # net_type -> 允许的 interface_type 集合
    allowed_by_net_type: dict[str, set[str]] = {
        "power": {"vbus", "vcc-3v3", "vcc-5v", "vbat", "battery-positive"},
        "ground": {"gnd", "battery-negative"},
        "matrix_row": {"gpio", "switch-pin"},
        "matrix_col": {"gpio", "switch-pin"},
        "data": {"usb2-dp", "usb2-dn", "usb-cc", "i2c-sda", "i2c-scl"},
        "differential_pair": {"usb2-dp", "usb2-dn", "usb3-sstx-p", "usb3-sstx-n"},
    }

    for net in ctx.query("nets"):
        net_type = net.resolved.net_type
        allowed = allowed_by_net_type.get(net_type)
        if allowed is None:
            # 未定义策略的 net_type：退化为所有节点类型相同
            types = []
            for node in net.resolved.nodes:
                inst_id, iface_id = _parse_node_ref(node)
                iface = _find_interface(ctx, inst_id, iface_id)
                if iface is None:
                    continue
                types.append(iface.interface_type)
            if len(types) >= 2:
                first = types[0]
                for t in types[1:]:
                    assert t == first, f"Net {net.id} 节点接口类型不一致: {first} vs {t}"
            continue

        for node in net.resolved.nodes:
            inst_id, iface_id = _parse_node_ref(node)
            iface = _find_interface(ctx, inst_id, iface_id)
            if iface is None:
                continue
            assert iface.interface_type in allowed, (
                f"Net {net.id} (type={net_type}) 节点 {node} "
                f"接口类型 {iface.interface_type} 不在允许列表 {allowed} 中"
            )


# ---------------------------------------------------------------------------
# 功耗/电流预算工具
# ---------------------------------------------------------------------------


class PowerBudget:
    """消费电子产品功耗/电流预算计算器。

    从项目配置读取参数，提供统一的电流估算和续航估算方法。
    配置项（均可在 piki.toml [plugins.consumer-electronics] 中覆盖）：
      - switch_active_ma: 单颗开关/轴体工作电流
      - led_full_brightness_ma: 单颗 LED 满亮度电流
      - led_brightness_pct: LED 平均亮度百分比
      - controller_active_ma: 控制器工作时基础电流
      - controller_sleep_ma: 控制器休眠电流
      - wireless_extra_ma: 无线模块额外电流
      - active_duty_cycle_pct: 设备工作时间占比
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self.switch_active_ma: float = cfg.get("switch_active_ma", 0.1)
        self.led_full_brightness_ma: float = cfg.get("led_full_brightness_ma", 20.0)
        self.led_brightness_pct: float = cfg.get("led_brightness_pct", 50.0)
        self.controller_active_ma: float = cfg.get("controller_active_ma", 15.0)
        self.controller_sleep_ma: float = cfg.get("controller_sleep_ma", 0.05)
        self.wireless_extra_ma: float = cfg.get("wireless_extra_ma", 5.0)
        self.active_duty_cycle_pct: float = cfg.get("active_duty_cycle_pct", 10.0)

    def led_current_ma(self, led_count: int) -> float:
        """估算 LED 总电流。"""
        return led_count * self.led_full_brightness_ma * (self.led_brightness_pct / 100.0)

    def active_current_ma(
        self,
        switch_count: int,
        led_count: int = 0,
        wireless: bool = False,
    ) -> float:
        """估算设备工作时的总电流。"""
        total = self.controller_active_ma
        total += switch_count * self.switch_active_ma
        total += self.led_current_ma(led_count)
        if wireless:
            total += self.wireless_extra_ma
        return total

    def average_current_ma(
        self,
        switch_count: int,
        led_count: int = 0,
        wireless: bool = False,
    ) -> float:
        """考虑占空比的平均电流。"""
        active = self.active_current_ma(switch_count, led_count, wireless)
        duty = self.active_duty_cycle_pct / 100.0
        return active * duty + self.controller_sleep_ma * (1 - duty)

    def estimate_runtime_hours(
        self,
        capacity_mah: float,
        switch_count: int,
        led_count: int = 0,
        wireless: bool = False,
    ) -> float:
        """估算电池续航时间（小时）。"""
        avg = self.average_current_ma(switch_count, led_count, wireless)
        if avg <= 0:
            return float("inf")
        return capacity_mah / avg


def make_power_budget(ctx: Context) -> PowerBudget:
    """从当前 Context 配置创建 PowerBudget 实例。"""
    return PowerBudget(ctx.config)
