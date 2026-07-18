"""Public read-only Runtime and device readiness snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from mobile_agent.domain.device import Device
from mobile_agent.domain.errors import MobileAgentError


class ReadinessStatus(str, Enum):
    READY = "ready"
    ATTENTION = "attention"
    BLOCKED = "blocked"


class GatewayStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class DeviceAvailabilityStatus(str, Enum):
    READY = "ready"
    BUSY = "busy"
    OFFLINE = "offline"
    UNAUTHORIZED = "unauthorized"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ReadinessIssue:
    """A safe user-facing readiness problem and remediation."""

    code: str
    message: str
    suggested_action: str = ""

    @classmethod
    def from_error(cls, error: MobileAgentError) -> ReadinessIssue:
        return cls(error.code, error.message, error.suggested_action)

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "suggested_action": self.suggested_action,
        }


@dataclass(frozen=True, slots=True)
class GatewayReadiness:
    platform: str
    transport: str
    status: GatewayStatus
    issue: ReadinessIssue | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "transport": self.transport,
            "status": self.status.value,
            "issue": self.issue.to_dict() if self.issue is not None else None,
        }


@dataclass(frozen=True, slots=True)
class DeviceAvailability:
    device: Device
    status: DeviceAvailabilityStatus
    lease_owner_id: str | None = None
    lease_session_id: str | None = None
    lease_expired: bool | None = None
    issues: tuple[ReadinessIssue, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "device": self.device.to_dict(),
            "status": self.status.value,
            "lease_owner_id": self.lease_owner_id,
            "lease_session_id": self.lease_session_id,
            "lease_expired": self.lease_expired,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True, slots=True)
class RuntimeReadiness:
    generated_at: str
    status: ReadinessStatus
    gateway: GatewayReadiness
    devices: tuple[DeviceAvailability, ...]
    issues: tuple[ReadinessIssue, ...] = ()
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        ready = sum(
            item.status is DeviceAvailabilityStatus.READY for item in self.devices
        )
        busy = sum(
            item.status is DeviceAvailabilityStatus.BUSY for item in self.devices
        )
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "status": self.status.value,
            "gateway": self.gateway.to_dict(),
            "devices": [device.to_dict() for device in self.devices],
            "summary": {
                "total": len(self.devices),
                "ready": ready,
                "busy": busy,
                "attention": len(self.devices) - ready - busy,
            },
            "issues": [issue.to_dict() for issue in self.issues],
        }
