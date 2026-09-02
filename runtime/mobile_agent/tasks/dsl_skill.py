"""TaskRun adapter for asynchronous custom DSL skill execution (ITER-0062, ADR-0013/0021).

Binds one registered SkillDslDocument to the shared asynchronous lifecycle:
the interpreter executes step by step while the executor's control probe is
consulted at every step boundary (cancel/pause/deadline), and each settled
DslStepRecord is mirrored to a TaskStep so progress events stream in real time.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Literal

from mobile_agent.domain.errors import ErrorCategory, ErrorOutcome, MobileAgentError
from mobile_agent.domain.skill_dsl import SkillDslDocument
from mobile_agent.domain.task import TaskRun, TaskStatus, TaskStep
from mobile_agent.skills.dsl_interpreter import (
    DslSkillResult,
    DslStepRecord,
    run_dsl_skill,
)
from mobile_agent.tools.runtime import ToolRuntime


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _cancelled_error() -> dict[str, Any]:
    return MobileAgentError(
        code="TASK_CANCELLED",
        category=ErrorCategory.EXECUTION,
        message="任务已按用户请求取消",
        outcome=ErrorOutcome.KNOWN_FAILURE,
    ).to_dict()


def _deadline_error() -> dict[str, Any]:
    return MobileAgentError(
        code="TASK_DEADLINE_EXCEEDED",
        category=ErrorCategory.EXECUTION,
        message="任务超过 deadline，已在步骤边界停止",
        outcome=ErrorOutcome.KNOWN_FAILURE,
    ).to_dict()


class DslSkillTaskRunner:
    """Run one custom DSL skill document under the async task lifecycle."""

    task_type = "skill.dsl.run"

    def __init__(self, tools: ToolRuntime) -> None:
        self._tools = tools

    async def run(
        self,
        task_id: str,
        device_id: str,
        document: SkillDslDocument,
        *,
        document_sha256: str,
        inputs: dict[str, Any],
        confirmed: bool,
        deadline_seconds: float,
        on_step: Callable[[TaskStep], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
        deadline_exceeded: Callable[[], bool] | None = None,
    ) -> TaskRun:
        """Execute the document; cancellation/deadline take effect at step boundaries."""

        goal = f"{document.skill_id}@{document.skill_version}"
        started_at = _now()
        terminal = self._preflight_terminal(
            task_id,
            device_id,
            goal,
            started_at,
            deadline_seconds,
            cancellation_requested,
            deadline_exceeded,
        )
        if terminal is not None:
            return terminal

        steps: list[TaskStep] = []
        abort_reason: Literal["cancelled", "timed_out"] | None = None

        def boundary() -> bool:
            nonlocal abort_reason
            if cancellation_requested is not None and cancellation_requested():
                abort_reason = "cancelled"
                return True
            if deadline_exceeded is not None and deadline_exceeded():
                abort_reason = "timed_out"
                return True
            return False

        def emit(record: DslStepRecord) -> None:
            timestamp = _now()
            step = TaskStep(
                step_id=f"step_{uuid.uuid4().hex}",
                sequence=len(steps) + 1,
                kind="skill",
                name=self.task_type,
                status=(
                    TaskStatus.SUCCEEDED
                    if record.status == "succeeded"
                    else TaskStatus.FAILED
                ),
                started_at=timestamp,
                completed_at=timestamp,
                error=(
                    {"code": record.error_code} if record.error_code is not None else None
                ),
            )
            steps.append(step)
            if on_step is not None:
                on_step(step)

        result = await run_dsl_skill(
            document,
            device_id=device_id,
            inputs=inputs,
            confirmed=confirmed,
            tools=self._tools,
            step_boundary=boundary,
            on_step=emit,
        )

        completed_at = _now()
        if abort_reason == "cancelled":
            status = TaskStatus.CANCELLED
            error = _cancelled_error()
        elif abort_reason == "timed_out":
            status = TaskStatus.TIMED_OUT
            error = _deadline_error()
        elif result.status == "succeeded":
            status = TaskStatus.SUCCEEDED
            error = None
        else:
            status = TaskStatus.FAILED
            error = (
                result.error.to_dict()
                if result.error is not None
                else _cancelled_error()
            )
        return TaskRun(
            task_id=task_id,
            task_type=self.task_type,
            device_id=device_id,
            goal=goal,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            steps=tuple(steps),
            evidence_summary=self._evidence(document_sha256, result.step_records, result),
            error=error,
            completion_source=(
                "skill_result" if status is TaskStatus.SUCCEEDED else None
            ),
            deadline_seconds=deadline_seconds,
        )

    def _preflight_terminal(
        self,
        task_id: str,
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
        now = _now()
        return TaskRun(
            task_id=task_id,
            task_type=self.task_type,
            device_id=device_id,
            goal=goal,
            status=status,
            started_at=started_at,
            completed_at=now,
            steps=(),
            evidence_summary={},
            error=error,
            deadline_seconds=deadline_seconds,
        )

    @staticmethod
    def _evidence(
        document_sha256: str,
        step_records: tuple[DslStepRecord, ...],
        result: DslSkillResult,
    ) -> dict[str, Any]:
        """DslSkillResult 摘要：步骤计数、派生风险与失败步骤（不含设备内容）。"""

        records = [
            {
                "step_id": record.step_id,
                "tool_id": record.tool_id,
                "status": record.status,
                "error_code": record.error_code,
            }
            for record in step_records
        ]
        failed = [record["step_id"] for record in records if record["status"] == "failed"]
        return {
            "document_sha256": document_sha256,
            "derived_risk": result.derived_risk.value,
            "step_count": len(records),
            "failed_step_ids": failed,
            "step_records": records,
        }
