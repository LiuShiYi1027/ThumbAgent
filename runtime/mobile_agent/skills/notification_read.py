"""Deterministic device.notifications.read@1 Skill."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from mobile_agent.domain.notification import (
    DeviceNotificationsResult,
    validate_max_notifications,
)
from mobile_agent.tools.notification_capture import DeviceNotificationsCaptureTool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class DeviceNotificationsReadSkill:
    """Read a bounded, privacy-minimized notification snapshot via one Tool."""

    skill_id = "device.notifications.read"
    version = "1.0.0"

    def __init__(self, tool: DeviceNotificationsCaptureTool) -> None:
        self._tool = tool

    async def invoke(
        self,
        device_id: str,
        max_notifications: int = 20,
        confirmed: bool = False,
    ) -> DeviceNotificationsResult:
        max_notifications = validate_max_notifications(max_notifications)
        started_at = _now()
        captured = await self._tool.execute(device_id, max_notifications, confirmed)
        return DeviceNotificationsResult(
            skill_call_id=f"skillcall_{uuid.uuid4().hex}",
            device_id=device_id,
            requested_max_notifications=max_notifications,
            notifications=captured.notifications,
            total_matched=captured.total_matched,
            truncated=captured.truncated,
            artifact=captured.artifact,
            started_at=started_at,
            completed_at=_now(),
        )
