"""Deterministic device.performance.snapshot@1 Skill."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from mobile_agent.domain.performance import DevicePerformanceSnapshotResult
from mobile_agent.tools.performance_capture import DevicePerformanceCaptureTool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class DevicePerformanceSnapshotSkill:
    """Capture and verify one aggregate, local-only performance snapshot."""

    skill_id = "device.performance.snapshot"
    version = "1.0.0"

    def __init__(self, tool: DevicePerformanceCaptureTool) -> None:
        self._tool = tool

    async def invoke(self, device_id: str) -> DevicePerformanceSnapshotResult:
        started_at = _now()
        captured = await self._tool.execute(device_id)
        return DevicePerformanceSnapshotResult(
            skill_call_id=f"skillcall_{uuid.uuid4().hex}",
            device_id=device_id,
            snapshot=captured.snapshot,
            artifact=captured.artifact,
            started_at=started_at,
            completed_at=_now(),
        )
