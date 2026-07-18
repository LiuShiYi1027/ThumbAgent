"""Capability metadata and public device inspection descriptors."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from mobile_agent.domain.action import Idempotency, RiskLevel
from mobile_agent.domain.readiness import DeviceAvailability


class CapabilityAvailability(str, Enum):
    AVAILABLE = "available"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class CapabilityVerification(str, Enum):
    REQUIRED = "required"
    SUPPORTED = "supported"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    capability: str
    risk: RiskLevel
    idempotency: Idempotency
    verification: CapabilityVerification
    requirements: tuple[str, ...]
    limitations: tuple[str, ...] = ()


class CapabilityCatalog:
    """Single Runtime metadata source for V1 device capabilities."""

    def __init__(self) -> None:
        definitions = (
            CapabilityDefinition(
                "device.inspect@1",
                RiskLevel.LOW,
                Idempotency.SAFE,
                CapabilityVerification.SUPPORTED,
                ("设备连接可被平台工具发现",),
                ("只返回 Runtime 公开的设备与能力元数据",),
            ),
            CapabilityDefinition(
                "screen.observe@1",
                RiskLevel.LOW,
                Idempotency.SAFE,
                CapabilityVerification.SUPPORTED,
                ("设备在线且已授权调试",),
                ("截图与 UI tree 作为本地 Artifact 保存",),
            ),
            CapabilityDefinition(
                "app.launch@1",
                RiskLevel.LOW,
                Idempotency.CONDITIONAL,
                CapabilityVerification.REQUIRED,
                ("设备在线", "应用标识符已知"),
            ),
            CapabilityDefinition(
                "navigation.back@1",
                RiskLevel.LOW,
                Idempotency.UNSAFE,
                CapabilityVerification.REQUIRED,
                ("设备在线",),
            ),
            CapabilityDefinition(
                "navigation.home@1",
                RiskLevel.LOW,
                Idempotency.SAFE,
                CapabilityVerification.REQUIRED,
                ("设备在线",),
            ),
            CapabilityDefinition(
                "input.tap@1",
                RiskLevel.MEDIUM,
                Idempotency.UNSAFE,
                CapabilityVerification.REQUIRED,
                ("设备在线", "用户明确确认"),
                ("系统安全区和不可交互目标会在派发前拒绝",),
            ),
            CapabilityDefinition(
                "input.swipe@1",
                RiskLevel.MEDIUM,
                Idempotency.UNSAFE,
                CapabilityVerification.REQUIRED,
                ("设备在线", "用户明确确认"),
                ("滑动距离、方向与持续时间均受边界约束",),
            ),
            CapabilityDefinition(
                "input.text@1",
                RiskLevel.MEDIUM,
                Idempotency.UNSAFE,
                CapabilityVerification.REQUIRED,
                ("设备在线", "目标可编辑", "用户明确确认"),
                ("密码、验证码、支付与账号安全输入不支持",),
            ),
            CapabilityDefinition(
                "logs.collect@1",
                RiskLevel.MEDIUM,
                Idempotency.SAFE,
                CapabilityVerification.SUPPORTED,
                ("设备在线且已授权调试", "用户明确确认"),
                (
                    "仅采集最近 1 到 2000 行日志快照",
                    "日志脱敏后作为本地 Artifact 保存，不在公共响应内联原文",
                ),
            ),
            CapabilityDefinition(
                "performance.snapshot@1",
                RiskLevel.LOW,
                Idempotency.SAFE,
                CapabilityVerification.SUPPORTED,
                ("设备在线且已授权调试",),
                (
                    "只保留聚合 CPU、内存、电池与系统负载指标",
                    "不保存进程、应用或 dumpsys 原始输出",
                ),
            ),
        )
        self._definitions = {
            definition.capability: definition for definition in definitions
        }

    def list(self) -> tuple[CapabilityDefinition, ...]:
        return tuple(self._definitions.values())

    def get(self, capability: str) -> CapabilityDefinition:
        return self._definitions[capability]


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    definition: CapabilityDefinition
    availability: CapabilityAvailability
    tools: tuple[str, ...]
    platform: str
    transport: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.definition.capability,
            "availability": self.availability.value,
            "risk": self.definition.risk.value,
            "idempotency": self.definition.idempotency.value,
            "verification": self.definition.verification.value,
            "confirmation_required": self.definition.risk is RiskLevel.MEDIUM,
            "tools": list(self.tools),
            "requirements": list(self.definition.requirements),
            "limitations": list(self.definition.limitations),
            "provider": {"platform": self.platform, "transport": self.transport},
        }


@dataclass(frozen=True, slots=True)
class DeviceInspection:
    generated_at: str
    availability: DeviceAvailability
    capabilities: tuple[CapabilityDescriptor, ...]
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "availability": self.availability.to_dict(),
            "capabilities": [item.to_dict() for item in self.capabilities],
        }
