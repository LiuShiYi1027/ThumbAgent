"""TaskRun adapter for asynchronous bounded device log collection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mobile_agent.domain.task import TaskRun, TaskStep
from mobile_agent.skills.device_logs import DeviceLogsCollectSkill
from mobile_agent.tasks.diagnostic import DiagnosticTaskRunner


class DeviceLogsTaskRunner:
    """Bind the device log Skill to the shared diagnostic lifecycle."""

    task_type = "device.logs.collect"

    def __init__(self, skill: DeviceLogsCollectSkill) -> None:
        self._skill = skill
        self._diagnostic = DiagnosticTaskRunner()

    async def run(
        self,
        task_id: str,
        device_id: str,
        max_lines: int,
        minimum_level: str,
        confirmed: bool,
        deadline_seconds: float,
        on_step: Callable[[TaskStep], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
        deadline_exceeded: Callable[[], bool] | None = None,
    ) -> TaskRun:
        """Invoke the log Skill once under the shared diagnostic lifecycle."""

        async def invoke() -> dict[str, Any]:
            return (
                await self._skill.invoke(
                    device_id, max_lines, minimum_level, confirmed
                )
            ).to_dict()

        def evidence(payload: dict[str, Any]) -> dict[str, Any]:
            return {
                "skill_call_id": payload["skill_call_id"],
                "artifact_refs": payload["evidence_refs"],
                "captured_bytes": payload["captured_bytes"],
                "truncated": payload["truncated"],
                "redaction_count": payload["redaction_count"],
            }

        return await self._diagnostic.run(
            task_id,
            self.task_type,
            device_id,
            f"采集最近 {max_lines} 行 {minimum_level} 及以上设备日志",
            deadline_seconds,
            invoke,
            evidence,
            on_step,
            cancellation_requested,
            deadline_exceeded,
        )
