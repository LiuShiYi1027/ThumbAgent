"""Asynchronous TaskRun adapter for diagnostic evidence bundle collection."""

from __future__ import annotations

from collections.abc import Callable

from mobile_agent.domain.task import TaskRun, TaskStep
from mobile_agent.skills.diagnostic_bundle import DiagnosticBundleSkill
from mobile_agent.tasks.diagnostic import DiagnosticTaskRunner


class DiagnosticBundleTaskRunner:
    def __init__(self, skill: DiagnosticBundleSkill) -> None:
        self._skill = skill
        self._runner = DiagnosticTaskRunner()

    async def run(
        self,
        task_id: str,
        device_id: str,
        app_id: str | None,
        max_log_lines: int,
        minimum_log_level: str,
        confirmed: bool,
        deadline_seconds: float,
        on_step: Callable[[TaskStep], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
        deadline_exceeded: Callable[[], bool] | None = None,
    ) -> TaskRun:
        async def invoke() -> dict[str, object]:
            return (
                await self._skill.invoke(
                    device_id,
                    app_id,
                    max_log_lines,
                    minimum_log_level,
                    confirmed,
                )
            ).to_dict()

        def evidence(payload: dict[str, object]) -> dict[str, object]:
            return {
                "skill_call_id": payload["skill_call_id"],
                "foreground_app": payload["foreground_app"],
                "app_state": payload["app_state"],
                "log_summary": payload["log_summary"],
                "performance_summary": payload["performance_summary"],
                "source_artifacts": payload["source_artifacts"],
                "bundle_artifact": payload["bundle_artifact"],
                "artifact_refs": payload["evidence_refs"],
            }

        return await self._runner.run(
            task_id,
            "device.diagnostics.bundle",
            device_id,
            "采集本地工程诊断包",
            deadline_seconds,
            invoke,
            evidence,
            on_step,
            cancellation_requested,
            deadline_exceeded,
        )
