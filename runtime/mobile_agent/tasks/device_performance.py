"""TaskRun adapter for aggregate device performance snapshots."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mobile_agent.domain.task import TaskRun, TaskStep
from mobile_agent.skills.device_performance import DevicePerformanceSnapshotSkill
from mobile_agent.tasks.diagnostic import DiagnosticTaskRunner


class DevicePerformanceTaskRunner:
    """Bind the performance Skill to the shared diagnostic lifecycle."""

    task_type = "device.performance.snapshot"

    def __init__(self, skill: DevicePerformanceSnapshotSkill) -> None:
        self._skill = skill
        self._diagnostic = DiagnosticTaskRunner()

    async def run(
        self,
        task_id: str,
        device_id: str,
        deadline_seconds: float,
        on_step: Callable[[TaskStep], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
        deadline_exceeded: Callable[[], bool] | None = None,
    ) -> TaskRun:
        """Invoke the performance Skill once under the diagnostic lifecycle."""

        async def invoke() -> dict[str, Any]:
            return (await self._skill.invoke(device_id)).to_dict()

        def evidence(payload: dict[str, Any]) -> dict[str, Any]:
            snapshot = payload["snapshot"]
            return {
                "skill_call_id": payload["skill_call_id"],
                "artifact_refs": payload["evidence_refs"],
                "cpu_total_usage_percent": snapshot["cpu"]["total_usage_percent"],
                "memory_used_percent": snapshot["memory"]["used_percent"],
                "battery_level_percent": snapshot["battery"]["level_percent"],
                "battery_temperature_celsius": snapshot["battery"]["temperature_celsius"],
            }

        return await self._diagnostic.run(
            task_id,
            self.task_type,
            device_id,
            "采集设备聚合性能快照",
            deadline_seconds,
            invoke,
            evidence,
            on_step,
            cancellation_requested,
            deadline_exceeded,
        )
