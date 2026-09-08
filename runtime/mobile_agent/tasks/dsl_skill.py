"""TaskRun adapter for asynchronous custom DSL skill execution (ITER-0062, ADR-0013/0021).

Binds one registered SkillDslDocument to the shared asynchronous lifecycle:
the interpreter executes step by step while the executor's control probe is
consulted at every step boundary (cancel/pause/deadline), and each settled
DslStepRecord is mirrored to a TaskStep so progress events stream in real time.

ITER-0063 (ADR-0021 Amendment 1): documents may reference whitelisted built-in
observation skills (skill steps). build_dsl_skill_invoker assembles the
execution closures for exactly those two ids; the task runner forwards the
invoker to the interpreter.

ITER-0065: evidence_summary gains stability-reporting fields distilled from
step-record output_summary values — sampling_series (one entry per succeeded
device.performance.snapshot step) and crash_check (from the last
device.logs.collect step carrying one); both keys are absent when the
document produced no such outputs, keeping legacy report shapes untouched.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from mobile_agent.domain.errors import ErrorCategory, ErrorOutcome, MobileAgentError
from mobile_agent.domain.skill_dsl import SkillDslDocument
from mobile_agent.domain.task import TaskRun, TaskStatus, TaskStep
from mobile_agent.skills.dsl_interpreter import (
    DslSkillResult,
    DslStepRecord,
    SkillInvoker,
    run_dsl_skill,
)
from mobile_agent.skills.dsl_risk import skill_reference_not_allowed
from mobile_agent.tools.log_capture import DeviceLogCaptureTool
from mobile_agent.tools.runtime import ToolRuntime

if TYPE_CHECKING:
    from mobile_agent.runtime import RuntimeService


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


def _skill_input_invalid(skill_id: str, message: str) -> MobileAgentError:
    return MobileAgentError(
        code="SKILL_INPUT_INVALID",
        category=ErrorCategory.VALIDATION,
        message=message,
        outcome=ErrorOutcome.REJECTED,
        details={"skill_id": skill_id},
    )


def build_dsl_skill_invoker(runtime: RuntimeService) -> SkillInvoker:
    """装配白名单内置观察 Skill 的执行闭包（ADR-0021 修订一）。

    只映射 DSL_SKILL_REFERENCE_WHITELIST 中的两个 id；arguments 在触碰
    设备前严格校验（不合法即 SKILL_INPUT_INVALID/INVALID_ARGUMENT，零
    设备动作）。闭包复用 RuntimeService 的 *_under_task_lease 薄封装：
    DSL 任务的 run_factory 已持有不可重入的设备租约与 Session 绑定，
    嵌套的内置 Skill 必须复用该上下文而不是再次申请租约。
    """

    async def invoke(
        skill_id: str, device_id: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if skill_id == "device.performance.snapshot":
            if arguments:
                raise _skill_input_invalid(
                    skill_id, "device.performance.snapshot 不接受 arguments"
                )
            return await runtime.capture_device_performance_under_task_lease(
                device_id
            )
        if skill_id == "device.logs.collect":
            unknown = sorted(set(arguments) - {"max_lines", "minimum_level"})
            if unknown:
                raise _skill_input_invalid(
                    skill_id,
                    f"device.logs.collect 只接受 max_lines/minimum_level，收到 {unknown}",
                )
            max_lines = arguments.get("max_lines", 500)
            minimum_level = arguments.get("minimum_level", "info")
            # 边界校验与直连入口一致（不合法抛 INVALID_ARGUMENT）。
            DeviceLogCaptureTool.validate_request(max_lines, minimum_level)
            return await runtime.collect_device_logs_under_task_lease(
                device_id,
                max_lines=max_lines,
                minimum_level=minimum_level,
                confirmed=True,
            )
        # preflight 已强制白名单；此行是防御性兜底。
        raise skill_reference_not_allowed(skill_id)

    return invoke


def _sampling_series(
    step_records: tuple[DslStepRecord, ...]
) -> list[dict[str, Any]]:
    """每个成功的性能采样步骤一条趋势记录，按执行顺序排列（ITER-0065）。"""

    series: list[dict[str, Any]] = []
    for record in step_records:
        if record.skill_id != "device.performance.snapshot":
            continue
        summary = record.output_summary
        if not isinstance(summary, dict):
            continue
        snapshot = summary.get("snapshot")
        if not isinstance(snapshot, dict):
            continue
        series.append(
            {
                "step_id": record.step_id,
                "captured_at": snapshot.get("captured_at"),
                "cpu": snapshot.get("cpu"),
                "memory": snapshot.get("memory"),
                "battery": snapshot.get("battery"),
                "system": snapshot.get("system"),
            }
        )
    return series


def _crash_check(step_records: tuple[DslStepRecord, ...]) -> dict[str, Any] | None:
    """取最后一个携带 crash_check 的日志采集步骤结果；无则缺省（ITER-0065）。"""

    verdict: dict[str, Any] | None = None
    for record in step_records:
        if record.skill_id != "device.logs.collect":
            continue
        summary = record.output_summary
        if not isinstance(summary, dict):
            continue
        candidate = summary.get("crash_check")
        if isinstance(candidate, dict):
            verdict = candidate
    return verdict


class DslSkillTaskRunner:
    """Run one custom DSL skill document under the async task lifecycle."""

    task_type = "skill.dsl.run"

    def __init__(
        self, tools: ToolRuntime, skill_invoker: SkillInvoker | None = None
    ) -> None:
        self._tools = tools
        self._skill_invoker = skill_invoker

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
            skill_invoker=self._skill_invoker,
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
                "skill_id": record.skill_id,
                "status": record.status,
                "error_code": record.error_code,
            }
            for record in step_records
        ]
        failed = [record["step_id"] for record in records if record["status"] == "failed"]
        evidence: dict[str, Any] = {
            "document_sha256": document_sha256,
            "derived_risk": result.derived_risk.value,
            "step_count": len(records),
            "failed_step_ids": failed,
            "step_records": records,
        }
        # ITER-0065：稳定性报告字段。无对应产出时键缺省，旧形状报告不受影响。
        sampling_series = _sampling_series(step_records)
        if sampling_series:
            evidence["sampling_series"] = sampling_series
        crash_check = _crash_check(step_records)
        if crash_check is not None:
            evidence["crash_check"] = crash_check
        return evidence
