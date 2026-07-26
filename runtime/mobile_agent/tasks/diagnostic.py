"""Shared TaskRun lifecycle for explicitly registered deterministic diagnostics."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from mobile_agent.domain.errors import ErrorCategory, ErrorOutcome, MobileAgentError
from mobile_agent.domain.task import TaskRun, TaskStatus, TaskStep


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class DiagnosticTaskRunner:
    """Apply one common lifecycle to a trusted diagnostic Skill invocation."""

    async def run(
        self,
        task_id: str,
        task_type: str,
        device_id: str,
        goal: str,
        deadline_seconds: float,
        invoke: Callable[[], Awaitable[dict[str, Any]]],
        evidence_from_result: Callable[[dict[str, Any]], dict[str, Any]],
        on_step: Callable[[TaskStep], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
        deadline_exceeded: Callable[[], bool] | None = None,
    ) -> TaskRun:
        """Run a trusted Skill once and preserve evidence at every safe boundary."""

        started_at = _now()
        terminal = self._preflight_terminal(
            task_id,
            task_type,
            device_id,
            goal,
            started_at,
            deadline_seconds,
            cancellation_requested,
            deadline_exceeded,
        )
        if terminal is not None:
            return terminal

        step_started_at = _now()
        try:
            payload = await invoke()
        except MobileAgentError as error:
            completed_at = _now()
            step = TaskStep(
                step_id=f"step_{uuid.uuid4().hex}",
                sequence=1,
                kind="diagnostic",
                name=task_type,
                status=TaskStatus.FAILED,
                started_at=step_started_at,
                completed_at=completed_at,
                error=error.to_dict(),
            )
            if on_step is not None:
                on_step(step)
            return TaskRun(
                task_id=task_id,
                task_type=task_type,
                device_id=device_id,
                goal=goal,
                status=TaskStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
                steps=(step,),
                evidence_summary=_failure_evidence(error),
                error=error.to_dict(),
                deadline_seconds=deadline_seconds,
            )

        completed_at = _now()
        step = TaskStep(
            step_id=f"step_{uuid.uuid4().hex}",
            sequence=1,
            kind="diagnostic",
            name=task_type,
            status=TaskStatus.SUCCEEDED,
            started_at=step_started_at,
            completed_at=completed_at,
            result=payload,
        )
        if on_step is not None:
            on_step(step)
        if cancellation_requested is not None and cancellation_requested():
            status = TaskStatus.CANCELLED
            error = _cancelled_error()
        elif deadline_exceeded is not None and deadline_exceeded():
            status = TaskStatus.TIMED_OUT
            error = _deadline_error()
        else:
            status = TaskStatus.SUCCEEDED
            error = None
        return TaskRun(
            task_id=task_id,
            task_type=task_type,
            device_id=device_id,
            goal=goal,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            steps=(step,),
            evidence_summary=evidence_from_result(payload),
            error=error,
            completion_source="skill_result" if status is TaskStatus.SUCCEEDED else None,
            deadline_seconds=deadline_seconds,
        )

    @staticmethod
    def _preflight_terminal(
        task_id: str,
        task_type: str,
        device_id: str,
        goal: str,
        started_at: str,
        deadline_seconds: float,
        cancellation_requested: Callable[[], bool] | None,
        deadline_exceeded: Callable[[], bool] | None,
    ) -> TaskRun | None:
        if cancellation_requested is not None and cancellation_requested():
            status = TaskStatus.CANCELLED
            error = _cancelled_error()
        elif deadline_exceeded is not None and deadline_exceeded():
            status = TaskStatus.TIMED_OUT
            error = _deadline_error()
        else:
            return None
        return TaskRun(
            task_id=task_id,
            task_type=task_type,
            device_id=device_id,
            goal=goal,
            status=status,
            started_at=started_at,
            completed_at=_now(),
            steps=(),
            evidence_summary={},
            error=error,
            deadline_seconds=deadline_seconds,
        )


def _cancelled_error() -> dict[str, Any]:
    return MobileAgentError(
        code="TASK_CANCELLED",
        category=ErrorCategory.EXECUTION,
        message="诊断任务已按用户请求取消",
        outcome=ErrorOutcome.KNOWN_FAILURE,
    ).to_dict()


def _deadline_error() -> dict[str, Any]:
    return MobileAgentError(
        code="TASK_DEADLINE_EXCEEDED",
        category=ErrorCategory.EXECUTION,
        message="诊断任务超过总执行时间预算",
        outcome=ErrorOutcome.KNOWN_FAILURE,
    ).to_dict()


def _failure_evidence(error: MobileAgentError) -> dict[str, Any]:
    refs = error.details.get("artifact_refs")
    if isinstance(refs, list) and all(isinstance(item, str) for item in refs):
        return {"artifact_refs": list(refs)}
    return {}
