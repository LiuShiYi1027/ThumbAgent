"""Interpreter for declarative composite skills (ITER-0062, ADR-0021).

Executes a validated SkillDslDocument against the ToolRuntime. Execution
semantics are locked by the iteration contract:

- One preflight pass before any device action: input binding validation
  (type/required/minimum/maximum/max_length per the inputs declaration),
  $inputs.<name> reference resolution against declared inputs, registration
  of every referenced tool (via derive_skill_risk), and the derived-risk
  policy gate. LOW passes unconditionally; MEDIUM requires confirmed=True,
  otherwise CONFIRMATION_REQUIRED; HIGH/PROHIBITED is always
  ACTION_REJECTED_BY_POLICY because custom DSL skills do not support the
  High-risk approval flow.
- A failing top-level tool step aborts the whole run; if-steps may only
  reference already-executed top-level steps (enforced by the parser).
- Loop body failures are recorded and the loop continues until
  max_iterations or max_duration_seconds (monotonic clock), whichever is
  hit first; bounds are checked before each iteration.
- If-steps pick then/else by comparing the referenced step's latest status
  against condition_equals; a failing branch step propagates like a failure
  at the if-step's own level.
- Skill steps (ADR-0021 Amendment 1) reference whitelisted built-in skills and
  are dispatched through the caller-provided skill_invoker. A document that
  contains skill steps but no invoker fails preflight with SKILL_DSL_INVALID
  before any device action. At runtime a skill step behaves exactly like a
  tool step at its level: invoker MobileAgentError → failed step record,
  top-level abort, loop-body tolerance.

run_dsl_skill never raises MobileAgentError for expected failures: they are
returned as DslSkillResult(status="failed", error=...). On a preflight
failure caused by an unregistered tool, derived_risk cannot be computed and
stays LOW in the result; the error field carries the real cause.

ITER-0065: settled skill-step records carry an output_summary distilled from
the invoker result through a fixed per-skill key whitelist
(_SKILL_OUTPUT_SUMMARY_KEYS), so stability reporting sees aggregate snapshots
and crash verdicts without raw log content ever entering DslStepRecord.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from typing import Any, Literal

from mobile_agent.domain.action import RiskLevel
from mobile_agent.domain.errors import ErrorCategory, ErrorOutcome, MobileAgentError
from mobile_agent.domain.skill_dsl import (
    IfStep,
    LoopStep,
    SkillDslDocument,
    SkillDslInput,
    SkillStep,
    Step,
    ToolStep,
)
from mobile_agent.skills.dsl_risk import derive_skill_risk, iter_skill_ids
from mobile_agent.tools.runtime import ToolRuntime

_INPUT_REF_RE = re.compile(r"^\$inputs\.([a-z][a-z0-9_]*)$")

StepStatus = Literal["succeeded", "failed"]

# (skill_id, device_id, resolved_arguments) -> 结果 dict。由调用方装配白名单
# 内内置 Skill 的真实执行；解释器只负责解析参数、派发与记录。
SkillInvoker = Callable[[str, str, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class DslStepRecord:
    """One executed step's outcome.

    tool_id 为 None 表示 loop/if 容器或 skill 引用步骤；skill 步骤时
    tool_id=None 且 skill_id 有值，容器记录两者均为 None。
    output_summary（ITER-0065）只出现在成功的白名单 skill 步骤上：按
    _SKILL_OUTPUT_SUMMARY_KEYS 从 invoker 结果透传的聚合摘要键，其余情况
    一律为 None（tool 步骤、容器步骤、失败步骤）。
    """

    step_id: str
    tool_id: str | None
    status: StepStatus
    error_code: str | None = None
    skill_id: str | None = None
    output_summary: dict[str, Any] | None = None


# output_summary 白名单：skill 步骤结果只透传稳定性报告呈现所需的聚合键。
# 性能快照保留 snapshot 原样（聚合 cpu/memory/battery/system，无进程细节）；
# 日志采集保留崩溃判定与 Artifact 元数据，原始日志文本永不进入记录。
_SKILL_OUTPUT_SUMMARY_KEYS: dict[str, tuple[str, ...]] = {
    "device.performance.snapshot": ("snapshot",),
    "device.logs.collect": ("crash_check", "artifact"),
}


def _skill_output_summary(
    skill_id: str, result: dict[str, Any]
) -> dict[str, Any] | None:
    """Distill an invoker result to the whitelisted summary keys; None if none."""

    keys = _SKILL_OUTPUT_SUMMARY_KEYS.get(skill_id)
    if keys is None:
        return None
    summary = {key: result[key] for key in keys if key in result}
    return summary or None


@dataclass(frozen=True, slots=True)
class DslSkillResult:
    """Outcome of one DSL skill execution, including preflight failures."""

    status: StepStatus
    step_records: tuple[DslStepRecord, ...]
    derived_risk: RiskLevel
    error: MobileAgentError | None


def _input_invalid(field: str, message: str) -> MobileAgentError:
    return MobileAgentError(
        code="SKILL_INPUT_INVALID",
        category=ErrorCategory.VALIDATION,
        message=message,
        outcome=ErrorOutcome.REJECTED,
        details={"field": field},
    )


def _bind_inputs(document: SkillDslDocument, inputs: dict[str, Any]) -> dict[str, Any]:
    """Validate provided inputs against the declaration; return usable values."""

    bound: dict[str, Any] = {}
    for declaration in document.inputs:
        value = inputs.get(declaration.name)
        if value is None:
            if declaration.required:
                raise _input_invalid(
                    declaration.name, f"缺少必需的输入 {declaration.name}"
                )
            continue
        _check_input_value(declaration, value)
        bound[declaration.name] = value
    return bound


def _check_input_value(declaration: SkillDslInput, value: Any) -> None:
    expected = declaration.type
    if expected == "string":
        if not isinstance(value, str):
            raise _input_invalid(declaration.name, f"输入 {declaration.name} 必须是字符串")
        if declaration.max_length is not None and len(value) > declaration.max_length:
            raise _input_invalid(
                declaration.name,
                f"输入 {declaration.name} 超过 max_length={declaration.max_length}",
            )
        return
    if expected == "boolean":
        if not isinstance(value, bool):
            raise _input_invalid(declaration.name, f"输入 {declaration.name} 必须是布尔值")
        return
    # integer/number：bool 是 int 的子类，必须显式排除。
    if expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        raise _input_invalid(declaration.name, f"输入 {declaration.name} 必须是整数")
    if expected == "number" and (
        not isinstance(value, int | float) or isinstance(value, bool)
    ):
        raise _input_invalid(declaration.name, f"输入 {declaration.name} 必须是数字")
    if declaration.minimum is not None and value < declaration.minimum:
        raise _input_invalid(
            declaration.name, f"输入 {declaration.name} 小于 minimum={declaration.minimum}"
        )
    if declaration.maximum is not None and value > declaration.maximum:
        raise _input_invalid(
            declaration.name, f"输入 {declaration.name} 大于 maximum={declaration.maximum}"
        )


def _iter_action_steps(document: SkillDslDocument) -> tuple[ToolStep | SkillStep, ...]:
    collected: list[ToolStep | SkillStep] = []

    def _walk(steps: tuple[Step, ...] | tuple[ToolStep | SkillStep, ...]) -> None:
        for step in steps:
            if isinstance(step, ToolStep | SkillStep):
                collected.append(step)
            elif isinstance(step, LoopStep):
                _walk(step.steps)
            elif isinstance(step, IfStep):
                _walk(step.then_steps)
                _walk(step.else_steps)

    _walk(document.steps)
    return tuple(collected)


def _validate_input_references(document: SkillDslDocument) -> None:
    """Every $inputs.<name> reference must name a declared input."""

    declared = document.input_names()
    for step in _iter_action_steps(document):
        for key, value in step.arguments.items():
            if not isinstance(value, str):
                continue
            match = _INPUT_REF_RE.fullmatch(value)
            if match is not None and match.group(1) not in declared:
                raise _input_invalid(
                    f"{step.step_id}.arguments.{key}",
                    f"$inputs.{match.group(1)} 引用了未声明的输入",
                )


def _resolve_arguments(
    arguments: dict[str, Any], bound_inputs: dict[str, Any]
) -> dict[str, Any]:
    """Substitute $inputs references; absent optional inputs drop the key."""

    resolved: dict[str, Any] = {}
    for key, value in arguments.items():
        if isinstance(value, str):
            match = _INPUT_REF_RE.fullmatch(value)
            if match is not None:
                name = match.group(1)
                if name in bound_inputs:
                    resolved[key] = bound_inputs[name]
                continue
        resolved[key] = value
    return resolved


def _enforce_policy_gate(derived_risk: RiskLevel, confirmed: bool) -> None:
    if derived_risk in (RiskLevel.HIGH, RiskLevel.PROHIBITED):
        raise MobileAgentError(
            code="ACTION_REJECTED_BY_POLICY",
            category=ErrorCategory.POLICY,
            message="自定义 DSL 技能不支持 High/Prohibited 风险能力（无授权流）",
            outcome=ErrorOutcome.REJECTED,
            details={"derived_risk": derived_risk.value},
        )
    if derived_risk is RiskLevel.MEDIUM and not confirmed:
        raise MobileAgentError(
            code="CONFIRMATION_REQUIRED",
            category=ErrorCategory.POLICY,
            message="该 DSL 技能派生风险为 Medium，需要用户明确确认",
            outcome=ErrorOutcome.REJECTED,
            details={"derived_risk": derived_risk.value},
        )


async def run_dsl_skill(
    document: SkillDslDocument,
    *,
    device_id: str,
    inputs: dict[str, Any],
    confirmed: bool,
    tools: ToolRuntime,
    step_boundary: Callable[[], bool] | None = None,
    on_step: Callable[[DslStepRecord], None] | None = None,
    skill_invoker: SkillInvoker | None = None,
) -> DslSkillResult:
    """Preflight then execute the document; expected failures return a result.

    step_boundary（可选）在每个步骤边界（含 loop 每次迭代与每个体内步骤之前）
    调用；返回 True 即中止：不再触发任何设备动作，结果 status=failed 且
    error.code=TASK_CANCELLED，由异步任务层映射为 cancelled/timed_out。
    on_step（可选）在每条 DslStepRecord 落定时回调，用于实时进度事件。
    skill_invoker（可选）是 skill 引用步骤的执行入口；文档含 skill 步骤而
    未提供 invoker 时 preflight 以 SKILL_DSL_INVALID 失败（零设备动作）。
    三者默认 None 时行为与原契约完全一致。
    """

    derived_risk = RiskLevel.LOW
    try:
        bound_inputs = _bind_inputs(document, inputs)
        _validate_input_references(document)
        # 顺带完成全部 tool_id 的注册检查与 skill_id 白名单检查：未注册工具在
        # 此抛出 TOOL_NOT_FOUND，非白名单 Skill 抛出 SKILL_REFERENCE_NOT_ALLOWED。
        derived_risk = derive_skill_risk(document)
        _enforce_policy_gate(derived_risk, confirmed)
        if skill_invoker is None and iter_skill_ids(document):
            raise MobileAgentError(
                code="SKILL_DSL_INVALID",
                category=ErrorCategory.VALIDATION,
                message="文档包含 skill 引用步骤，但未提供 skill_invoker",
                outcome=ErrorOutcome.REJECTED,
                details={"field": "skill_invoker"},
            )
    except MobileAgentError as error:
        return DslSkillResult(
            status="failed",
            step_records=(),
            derived_risk=derived_risk,
            error=error,
        )

    records: list[DslStepRecord] = []
    top_level_status: dict[str, StepStatus] = {}

    def emit(record: DslStepRecord) -> None:
        records.append(record)
        if on_step is not None:
            on_step(record)

    def aborted() -> bool:
        return step_boundary is not None and step_boundary()

    async def run_action_step(
        step: ToolStep | SkillStep,
    ) -> tuple[DslStepRecord, MobileAgentError | None]:
        arguments = _resolve_arguments(step.arguments, bound_inputs)
        if isinstance(step, ToolStep):
            try:
                # preflight 已过派生风险策略门；confirmed=True 是文档级授权传递。
                await tools.execute(step.tool_id, device_id, arguments, confirmed=True)
            except MobileAgentError as error:
                return (
                    DslStepRecord(step.step_id, step.tool_id, "failed", error.code),
                    error,
                )
            return DslStepRecord(step.step_id, step.tool_id, "succeeded"), None
        # Skill 引用步骤：preflight 已保证 invoker 存在且 skill_id 在白名单内。
        assert skill_invoker is not None
        try:
            output = await skill_invoker(step.skill_id, device_id, arguments)
        except MobileAgentError as error:
            return (
                DslStepRecord(
                    step.step_id, None, "failed", error.code, skill_id=step.skill_id
                ),
                error,
            )
        return (
            DslStepRecord(
                step.step_id,
                None,
                "succeeded",
                skill_id=step.skill_id,
                output_summary=_skill_output_summary(step.skill_id, output),
            ),
            None,
        )

    def failed_result(error: MobileAgentError) -> DslSkillResult:
        return DslSkillResult(
            status="failed",
            step_records=tuple(records),
            derived_risk=derived_risk,
            error=error,
        )

    for step in document.steps:
        if aborted():
            return failed_result(_boundary_aborted_error())
        if isinstance(step, ToolStep | SkillStep):
            record, error = await run_action_step(step)
            emit(record)
            top_level_status[step.step_id] = record.status
            if error is not None:
                return failed_result(error)
        elif isinstance(step, LoopStep):
            if await _run_loop(step, run_action_step, emit, aborted):
                return failed_result(_boundary_aborted_error())
            # 循环体失败按契约被容忍；循环到达任一上限即视为成功完成。
            emit(DslStepRecord(step.step_id, None, "succeeded"))
            top_level_status[step.step_id] = "succeeded"
        elif isinstance(step, IfStep):
            branch = (
                step.then_steps
                if top_level_status[step.condition_step] == step.condition_equals
                else step.else_steps
            )
            branch_error: MobileAgentError | None = None
            for branch_step in branch:
                if aborted():
                    return failed_result(_boundary_aborted_error())
                record, error = await run_action_step(branch_step)
                emit(record)
                if error is not None:
                    branch_error = error
                    break
            emit(
                DslStepRecord(
                    step.step_id,
                    None,
                    "failed" if branch_error is not None else "succeeded",
                    branch_error.code if branch_error is not None else None,
                )
            )
            top_level_status[step.step_id] = (
                "failed" if branch_error is not None else "succeeded"
            )
            if branch_error is not None:
                return failed_result(branch_error)

    return DslSkillResult(
        status="succeeded",
        step_records=tuple(records),
        derived_risk=derived_risk,
        error=None,
    )


def _boundary_aborted_error() -> MobileAgentError:
    """Stable marker for a step-boundary abort; the task layer maps it to
    cancelled/timed_out based on its own control-probe state."""

    return MobileAgentError(
        code="TASK_CANCELLED",
        category=ErrorCategory.EXECUTION,
        message="任务已在步骤边界按请求中止",
        outcome=ErrorOutcome.KNOWN_FAILURE,
    )


ActionStepRunner = Callable[
    [ToolStep | SkillStep], Awaitable[tuple[DslStepRecord, MobileAgentError | None]]
]


async def _run_loop(
    step: LoopStep,
    run_action_step: ActionStepRunner,
    emit: Callable[[DslStepRecord], None],
    aborted: Callable[[], bool],
) -> bool:
    """Run the bounded loop; returns True when aborted at a step boundary."""

    deadline = monotonic() + step.max_duration_seconds
    iteration = 0
    while iteration < step.max_iterations and monotonic() < deadline:
        if aborted():
            return True
        iteration += 1
        for body_step in step.steps:
            if aborted():
                return True
            record, _ = await run_action_step(body_step)
            emit(record)
    return False
