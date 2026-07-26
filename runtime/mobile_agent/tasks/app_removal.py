"""Asynchronous TaskRun adapter for scoped application removal."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mobile_agent.domain.app_removal import AppRemovalApproval
from mobile_agent.domain.task import TaskRun, TaskStep
from mobile_agent.skills.app_removal import AppRemovalSkill
from mobile_agent.tasks.diagnostic import DiagnosticTaskRunner


class AppRemovalTaskRunner:
    task_type = "app.uninstall"

    def __init__(self, skill: AppRemovalSkill) -> None:
        self._skill = skill
        self._runner = DiagnosticTaskRunner()

    async def run(
        self,
        task_id: str,
        approval: AppRemovalApproval,
        confirmed: bool,
        deadline_seconds: float,
        on_step: Callable[[TaskStep], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
        deadline_exceeded: Callable[[], bool] | None = None,
    ) -> TaskRun:
        async def invoke() -> dict[str, Any]:
            return (await self._skill.invoke(approval, confirmed)).to_dict()

        def evidence(payload: dict[str, Any]) -> dict[str, Any]:
            return {
                "skill_call_id": payload["skill_call_id"],
                "removed_app": payload["removed_app"],
                "data_retained": payload["data_retained"],
                "post_removal_state": "absent",
            }

        return await self._runner.run(
            task_id,
            self.task_type,
            approval.device_id,
            f"卸载已批准的应用：{approval.app.app_id}",
            deadline_seconds,
            invoke,
            evidence,
            on_step,
            cancellation_requested,
            deadline_exceeded,
        )
