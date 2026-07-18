"""Minimal deterministic Task Runner for V1 evidence reports."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.domain.task import TaskRun, TaskStatus, TaskStep
from mobile_agent.skills.settings_navigate import SettingsScrollNavigateSkill


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class TaskRunner:
    """Run deterministic tasks and return a structured evidence report."""

    def __init__(self, settings_scroll_navigate: SettingsScrollNavigateSkill) -> None:
        self._settings_scroll_navigate = settings_scroll_navigate

    async def run_settings_scroll_navigation(
        self,
        device_id: str,
        target_selector: dict[str, Any],
        expected_selector: dict[str, Any],
        direction: str = "up",
        max_scrolls: int = 3,
        confirmed: bool = False,
        distance_percent: float = 0.8,
        duration_ms: int = 800,
        settle_seconds: float = 0.8,
        goal: str | None = None,
    ) -> TaskRun:
        """Run the settings scroll navigation skill as a one-step task."""

        task_started_at = _now()
        step_started_at = task_started_at
        step_id = f"step_{uuid.uuid4().hex}"
        task_id = f"task_{uuid.uuid4().hex}"
        task_goal = goal or "Navigate Android Settings to the expected page"
        try:
            result = await self._settings_scroll_navigate.invoke(
                device_id,
                target_selector,
                expected_selector,
                direction,
                max_scrolls,
                confirmed,
                distance_percent,
                duration_ms,
                settle_seconds,
            )
            completed_at = _now()
            result_dict = result.to_dict()
            step = TaskStep(
                step_id=step_id,
                sequence=1,
                kind="skill",
                name=result.skill_id,
                status=TaskStatus.SUCCEEDED,
                started_at=step_started_at,
                completed_at=completed_at,
                result=result_dict,
            )
            return TaskRun(
                task_id=task_id,
                task_type="settings.scroll_navigate",
                device_id=device_id,
                goal=task_goal,
                status=TaskStatus.SUCCEEDED,
                started_at=task_started_at,
                completed_at=completed_at,
                steps=(step,),
                evidence_summary={
                    "final_foreground_app": result.verified_observation.foreground_app.to_dict(),
                    "verified_node": result.verified_node.to_dict(),
                    "skill_call_id": result.skill_call_id,
                    "tap_action_id": result.tap_action.action_id,
                },
            )
        except MobileAgentError as error:
            completed_at = _now()
            error_dict = error.to_dict()
            step = TaskStep(
                step_id=step_id,
                sequence=1,
                kind="skill",
                name="settings.scroll_navigate",
                status=TaskStatus.FAILED,
                started_at=step_started_at,
                completed_at=completed_at,
                error=error_dict,
            )
            return TaskRun(
                task_id=task_id,
                task_type="settings.scroll_navigate",
                device_id=device_id,
                goal=task_goal,
                status=TaskStatus.FAILED,
                started_at=task_started_at,
                completed_at=completed_at,
                steps=(step,),
                evidence_summary={},
                error=error_dict,
            )
