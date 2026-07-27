"""Asynchronous TaskRun adapter for local Artifact cleanup."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mobile_agent.domain.local_data import LocalDataCleanupApproval
from mobile_agent.domain.task import TaskRun, TaskStep
from mobile_agent.skills.local_data import LocalDataCleanupSkill
from mobile_agent.tasks.diagnostic import DiagnosticTaskRunner


class LocalDataCleanupTaskRunner:
    """Run local cleanup without acquiring a device Session or Lease."""

    task_type = "local.data.cleanup"
    target_id = "local:runtime"

    def __init__(self, skill: LocalDataCleanupSkill) -> None:
        self._skill = skill
        self._runner = DiagnosticTaskRunner()

    async def run(
        self,
        task_id: str,
        approval: LocalDataCleanupApproval,
        confirmed: bool,
        deadline_seconds: float,
        on_step: Callable[[TaskStep], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
        deadline_exceeded: Callable[[], bool] | None = None,
    ) -> TaskRun:
        async def invoke() -> dict[str, Any]:
            return (
                await self._skill.invoke(
                    approval,
                    confirmed,
                    cancellation_requested,
                    deadline_exceeded,
                )
            ).to_dict()

        def evidence(payload: dict[str, Any]) -> dict[str, Any]:
            return {
                "skill_call_id": payload["skill_call_id"],
                "retention_days": payload["retention_days"],
                "cutoff_at": payload["cutoff_at"],
                "deleted_count": payload["deleted_count"],
                "deleted_bytes": payload["deleted_bytes"],
                "deleted_artifact_ids": payload["deleted_artifact_ids"],
                "verification": payload["verification"],
            }

        return await self._runner.run(
            task_id,
            self.task_type,
            self.target_id,
            "清理已批准的过期本地 Artifact",
            deadline_seconds,
            invoke,
            evidence,
            on_step,
            cancellation_requested,
            deadline_exceeded,
        )
