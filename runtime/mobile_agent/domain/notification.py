"""Public value objects for the bounded device notifications snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mobile_agent.domain.artifact import Artifact
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError

MAX_NOTIFICATIONS = 50
MAX_TITLE_LENGTH = 32


@dataclass(frozen=True, slots=True)
class DeviceNotification:
    """One privacy-minimized notification entry.

    The body/content text is never captured; the title is only present when the
    platform already exposes it and is truncated to MAX_TITLE_LENGTH.
    """

    package: str
    title: str | None
    posted_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "package": self.package,
            "title": self.title,
            "posted_at": self.posted_at,
        }


@dataclass(frozen=True, slots=True)
class DeviceNotificationsResult:
    """Verified public result; the normalized snapshot is persisted as an Artifact."""

    skill_call_id: str
    device_id: str
    requested_max_notifications: int
    notifications: tuple[DeviceNotification, ...]
    total_matched: int
    truncated: bool
    artifact: Artifact
    started_at: str
    completed_at: str
    schema_version: str = "1.0.0"
    skill_id: str = "device.notifications.read"
    skill_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "skill_call_id": self.skill_call_id,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "device_id": self.device_id,
            "success": True,
            "status": "succeeded",
            "verification": "verified",
            "source": "android_notification_service",
            "requested_max_notifications": self.requested_max_notifications,
            "notifications": [item.to_dict() for item in self.notifications],
            "total_matched": self.total_matched,
            "truncated": self.truncated,
            "evidence_refs": [self.artifact.artifact_id],
            "artifact": self.artifact.to_dict(),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


def validate_max_notifications(raw: object) -> int:
    """Validate the public bound before any device discovery or lease."""

    if not isinstance(raw, int) or isinstance(raw, bool) or not 1 <= raw <= MAX_NOTIFICATIONS:
        raise MobileAgentError(
            code="INVALID_ARGUMENT",
            category=ErrorCategory.VALIDATION,
            message=f"通知数量上限必须在 1 到 {MAX_NOTIFICATIONS} 之间",
        )
    return raw
