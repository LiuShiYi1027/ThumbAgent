"""Asynchronous TaskRun adapter for scoped APK installation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mobile_agent.domain.apk import ApkInstallApproval
from mobile_agent.domain.task import TaskRun, TaskStep
from mobile_agent.skills.apk_install import ApkInstallSkill
from mobile_agent.tasks.diagnostic import DiagnosticTaskRunner


class ApkInstallTaskRunner:
    task_type = "app.install"

    def __init__(self, skill: ApkInstallSkill) -> None:
        self._skill = skill
        self._runner = DiagnosticTaskRunner()

    async def run(
        self,
        task_id: str,
        approval: ApkInstallApproval,
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
                "app": payload["app"],
                "apk_sha256": payload["apk_sha256"],
                "apk_size_bytes": payload["apk_size_bytes"],
                "replaced_existing": payload["replaced_existing"],
            }

        return await self._runner.run(
            task_id, self.task_type, approval.device_id,
            f"安装已批准的本地 APK：{approval.package.app_id}", deadline_seconds,
            invoke, evidence, on_step, cancellation_requested, deadline_exceeded,
        )
