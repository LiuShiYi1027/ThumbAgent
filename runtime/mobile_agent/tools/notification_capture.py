"""Registered, policy-gated Tool for bounded device notification snapshots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.domain.artifact import Artifact, ArtifactKind
from mobile_agent.domain.device import ConnectionState
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.notification import (
    MAX_TITLE_LENGTH,
    DeviceNotification,
    validate_max_notifications,
)
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.tools.runtime import ToolRegistry


@dataclass(frozen=True, slots=True)
class CapturedNotifications:
    """Internal output from the registered Tool to its owning Skill."""

    notifications: tuple[DeviceNotification, ...]
    total_matched: int
    truncated: bool
    artifact: Artifact


def _posted_iso(epoch_ms: int) -> str:
    return (
        datetime.fromtimestamp(epoch_ms / 1000, timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


class DeviceNotificationsCaptureTool:
    """Validate, authorize, read, minimize and persist a notification snapshot."""

    tool_id = "device.notifications.capture"

    def __init__(
        self,
        adapter: DeviceAdapter,
        artifacts: ArtifactStore,
        registry: ToolRegistry,
        policy: PolicyEngine,
    ) -> None:
        self._adapter = adapter
        self._artifacts = artifacts
        self._registry = registry
        self._policy = policy

    async def execute(
        self,
        device_id: str,
        max_notifications: int,
        confirmed: bool,
    ) -> CapturedNotifications:
        max_notifications = validate_max_notifications(max_notifications)
        definition = self._registry.get(self.tool_id)
        device = next(
            (
                item
                for item in await self._adapter.list_devices()
                if item.device_id == device_id
            ),
            None,
        )
        if device is None:
            raise MobileAgentError(
                code="DEVICE_NOT_FOUND",
                category=ErrorCategory.DEVICE,
                message="设备不存在",
            )
        if device.connection is not ConnectionState.ONLINE:
            raise MobileAgentError(
                code="DEVICE_OFFLINE",
                category=ErrorCategory.DEVICE,
                message="设备当前不可交互",
                retryable=True,
            )
        if definition.capability not in device.capabilities:
            raise MobileAgentError(
                code="CAPABILITY_UNAVAILABLE",
                category=ErrorCategory.CAPABILITY,
                message="设备不支持通知读取",
                details={"capability": definition.capability},
            )
        self._policy.authorize(definition.risk, confirmed)

        records = await self._adapter.read_notifications(device_id)
        total_matched = len(records)
        truncated = total_matched > max_notifications
        notifications = tuple(
            DeviceNotification(
                package=package,
                title=(
                    title[:MAX_TITLE_LENGTH]
                    if title is not None
                    else None
                ),
                posted_at=_posted_iso(posted_ms) if posted_ms is not None else None,
            )
            for package, title, posted_ms in records[:max_notifications]
        )
        payload = json.dumps(
            {
                "notifications": [item.to_dict() for item in notifications],
                "total_matched": total_matched,
                "truncated": truncated,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        artifact = self._artifacts.write(
            ArtifactKind.DEVICE_NOTIFICATIONS,
            "application/json",
            payload,
            ".json",
        )
        return CapturedNotifications(
            notifications=notifications,
            total_matched=total_matched,
            truncated=truncated,
            artifact=artifact,
        )
