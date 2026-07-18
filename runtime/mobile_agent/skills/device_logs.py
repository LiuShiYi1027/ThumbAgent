"""Deterministic device.logs.collect@1 Skill."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from mobile_agent.domain.device_log import DeviceLogCaptureResult, DeviceLogLevel
from mobile_agent.tools.log_capture import DeviceLogCaptureTool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class DeviceLogsCollectSkill:
    """Collect a bounded, redacted log snapshot through one registered Tool."""

    skill_id = "device.logs.collect"
    version = "1.0.0"

    def __init__(self, tool: DeviceLogCaptureTool) -> None:
        self._tool = tool

    async def invoke(
        self,
        device_id: str,
        max_lines: int = 500,
        minimum_level: DeviceLogLevel | str = DeviceLogLevel.INFO,
        confirmed: bool = False,
    ) -> DeviceLogCaptureResult:
        started_at = _now()
        captured = await self._tool.execute(
            device_id, max_lines, minimum_level, confirmed
        )
        level = (
            minimum_level
            if isinstance(minimum_level, DeviceLogLevel)
            else DeviceLogLevel(minimum_level)
        )
        return DeviceLogCaptureResult(
            skill_call_id=f"skillcall_{uuid.uuid4().hex}",
            device_id=device_id,
            minimum_level=level,
            requested_max_lines=max_lines,
            captured_bytes=captured.captured_bytes,
            truncated=captured.truncated,
            redaction_count=captured.redaction_count,
            artifact=captured.artifact,
            started_at=started_at,
            completed_at=_now(),
        )
