"""Asynchronous TaskRun adapters for application lifecycle Skills."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from mobile_agent.domain.app_lifecycle import AppDataClearApproval
from mobile_agent.domain.task import TaskRun, TaskStep
from mobile_agent.skills.app_lifecycle import (
    AppDataClearSkill,
    AppLaunchSkill,
    AppStopSkill,
)
from mobile_agent.tasks.diagnostic import DiagnosticTaskRunner


class AppLifecycleTaskRunner:
    def __init__(
        self,
        launch: AppLaunchSkill,
        stop: AppStopSkill,
        clear_data: AppDataClearSkill,
    ) -> None:
        self._launch = launch
        self._stop = stop
        self._clear_data = clear_data
        self._runner = DiagnosticTaskRunner()

    async def run_launch(
        self,
        task_id: str,
        device_id: str,
        app_id: str,
        deadline_seconds: float,
        on_step: Callable[[TaskStep], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
        deadline_exceeded: Callable[[], bool] | None = None,
    ) -> TaskRun:
        return await self._run(
            task_id,
            "app.launch",
            device_id,
            f"启动应用并验证前台：{app_id}",
            deadline_seconds,
            lambda: self._result(self._launch.invoke(device_id, app_id)),
            on_step,
            cancellation_requested,
            deadline_exceeded,
        )

    async def run_stop(
        self,
        task_id: str,
        device_id: str,
        app_id: str,
        confirmed: bool,
        deadline_seconds: float,
        on_step: Callable[[TaskStep], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
        deadline_exceeded: Callable[[], bool] | None = None,
    ) -> TaskRun:
        return await self._run(
            task_id,
            "app.stop",
            device_id,
            f"停止非系统应用并验证：{app_id}",
            deadline_seconds,
            lambda: self._result(self._stop.invoke(device_id, app_id, confirmed)),
            on_step,
            cancellation_requested,
            deadline_exceeded,
        )

    async def run_clear_data(
        self,
        task_id: str,
        approval: AppDataClearApproval,
        confirmed: bool,
        deadline_seconds: float,
        on_step: Callable[[TaskStep], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
        deadline_exceeded: Callable[[], bool] | None = None,
    ) -> TaskRun:
        return await self._run(
            task_id,
            "app.data.clear",
            approval.device_id,
            f"清除已批准应用的数据：{approval.app.app_id}",
            deadline_seconds,
            lambda: self._result(self._clear_data.invoke(approval, confirmed)),
            on_step,
            cancellation_requested,
            deadline_exceeded,
        )

    async def _run(
        self,
        task_id: str,
        task_type: str,
        device_id: str,
        goal: str,
        deadline_seconds: float,
        invoke: Callable[[], Awaitable[dict[str, Any]]],
        on_step: Callable[[TaskStep], None] | None,
        cancellation_requested: Callable[[], bool] | None,
        deadline_exceeded: Callable[[], bool] | None,
    ) -> TaskRun:
        def evidence(payload: dict[str, Any]) -> dict[str, Any]:
            return {
                "skill_call_id": payload["skill_call_id"],
                "operation": payload["operation"],
                "app": payload["app"],
                "state": payload["state"],
                "data_cleared": payload["data_cleared"],
            }

        return await self._runner.run(
            task_id,
            task_type,
            device_id,
            goal,
            deadline_seconds,
            invoke,
            evidence,
            on_step,
            cancellation_requested,
            deadline_exceeded,
        )

    @staticmethod
    async def _result(
        awaitable: Awaitable[Any],
    ) -> dict[str, Any]:
        return (await awaitable).to_dict()
