"""Declarative composite skill DSL (ITER-0062, ADR-0021).

A DSL document is pure data: no code, no expression evaluation, no external
references. The interpreter (application layer) may only reference registered
tools; this module validates document shape against the same bounds declared in
contracts/schemas/skill-dsl.schema.json. Keep both in lockstep — the contract
tests assert the pairing.

Control flow is deliberately minimal: sequential tool steps, a time-boxed loop
with dual bounds, and an if-step that branches on a previous step's outcome
status. Loop/if bodies contain tool steps only — no nested control flow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from mobile_agent.domain.errors import ErrorCategory, ErrorOutcome, MobileAgentError

SCHEMA_VERSION = "1.0.0"

_SKILL_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*)+$")
_STEP_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_INPUT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_INPUT_REF_RE = re.compile(r"^\$inputs\.([a-z][a-z0-9_]*)$")

MAX_INPUTS = 8
MAX_STEPS = 32
MAX_BODY_STEPS = 16
MAX_LOOP_DURATION_SECONDS = 600
MAX_LOOP_ITERATIONS = 200
MAX_TIMEOUT_SECONDS = 1800

StepType = Literal["tool", "loop", "if"]


def _invalid(field: str, message: str) -> MobileAgentError:    return MobileAgentError(
        code="SKILL_DSL_INVALID",
        category=ErrorCategory.VALIDATION,
        message=message,
        outcome=ErrorOutcome.REJECTED,
        details={"field": field},
    )


def _require_str(payload: dict[str, Any], field: str, max_length: int) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise _invalid(field, f"{field} 必须是 1..{max_length} 字符的字符串")
    return value


@dataclass(frozen=True, slots=True)
class SkillDslInput:
    """One declared input parameter of a composite skill."""

    name: str
    type: Literal["string", "integer", "number", "boolean"]
    required: bool
    description: str
    max_length: int | None
    minimum: float | None
    maximum: float | None


@dataclass(frozen=True, slots=True)
class ToolStep:
    """Invoke one registered tool with literal or $inputs-referenced arguments."""

    step_id: str
    tool_id: str
    arguments: dict[str, Any]

    @property
    def type(self) -> StepType:
        return "tool"


@dataclass(frozen=True, slots=True)
class LoopStep:
    """Time-boxed bounded repetition over tool steps (dual bounds required)."""

    step_id: str
    max_duration_seconds: int
    max_iterations: int
    steps: tuple[ToolStep, ...]

    @property
    def type(self) -> StepType:
        return "loop"


@dataclass(frozen=True, slots=True)
class IfStep:
    """Branch on a previous step's outcome status; bodies are tool steps only."""

    step_id: str
    condition_step: str
    condition_equals: Literal["succeeded", "failed"]
    then_steps: tuple[ToolStep, ...]
    else_steps: tuple[ToolStep, ...]

    @property
    def type(self) -> StepType:
        return "if"


Step = ToolStep | LoopStep | IfStep


@dataclass(frozen=True, slots=True)
class SkillDslDocument:
    """Validated declarative composite skill definition."""

    skill_id: str
    skill_version: str
    name: str
    description: str
    timeout_seconds: int | None
    inputs: tuple[SkillDslInput, ...]
    steps: tuple[Step, ...]

    def input_names(self) -> frozenset[str]:
        return frozenset(item.name for item in self.inputs)


def _parse_arguments(raw: Any, field: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or len(raw) > 8:
        raise _invalid(field, f"{field} 必须是至多 8 个键的对象")
    for key, value in raw.items():
        if not isinstance(key, str) or not key:
            raise _invalid(field, f"{field} 的键必须是非空字符串")
        if isinstance(value, str):
            if len(value) > 2000:
                raise _invalid(field, f"{field}.{key} 超过 2000 字符")
        elif isinstance(value, bool) or value is None:
            if value is None:
                raise _invalid(field, f"{field}.{key} 不允许 null")
        elif not isinstance(value, int | float):
            raise _invalid(field, f"{field}.{key} 只支持字符串/数字/布尔字面量或 $inputs 引用")
    return dict(raw)


def _step_id(payload: dict[str, Any]) -> str:
    step_id = payload.get("step_id")
    if not isinstance(step_id, str) or not _STEP_ID_RE.fullmatch(step_id):
        raise _invalid("step_id", "step_id 必须匹配 ^[a-z][a-z0-9_]*$")
    return step_id


def _parse_tool_step(payload: dict[str, Any]) -> ToolStep:
    step_id = _step_id(payload)
    tool_id = payload.get("tool_id")
    if not isinstance(tool_id, str) or not _SKILL_ID_RE.fullmatch(tool_id):
        raise _invalid("tool_id", f"步骤 {step_id} 的 tool_id 必须是 domain.verb 形式")
    arguments = _parse_arguments(payload.get("arguments"), f"{step_id}.arguments")
    return ToolStep(step_id=step_id, tool_id=tool_id, arguments=arguments)


def _parse_body_steps(raw: Any, field: str) -> tuple[ToolStep, ...]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_BODY_STEPS:
        raise _invalid(field, f"{field} 必须是 1..{MAX_BODY_STEPS} 个工具步骤")
    steps: list[ToolStep] = []
    for item in raw:
        if not isinstance(item, dict) or item.get("type") != "tool":
            raise _invalid(field, f"{field} 只允许工具步骤（不允许嵌套控制流）")
        steps.append(_parse_tool_step(item))
    return tuple(steps)


def _parse_step(payload: Any) -> Step:
    if not isinstance(payload, dict):
        raise _invalid("steps", "每个步骤必须是对象")
    step_type = payload.get("type")
    if step_type == "tool":
        return _parse_tool_step(payload)
    if step_type == "loop":
        step_id = _step_id(payload)
        duration = payload.get("max_duration_seconds")
        iterations = payload.get("max_iterations")
        if (
            not isinstance(duration, int)
            or isinstance(duration, bool)
            or not 1 <= duration <= MAX_LOOP_DURATION_SECONDS
        ):
            raise _invalid(
                "max_duration_seconds",
                f"步骤 {step_id} 的 max_duration_seconds 必须在 1..{MAX_LOOP_DURATION_SECONDS}",
            )
        if (
            not isinstance(iterations, int)
            or isinstance(iterations, bool)
            or not 1 <= iterations <= MAX_LOOP_ITERATIONS
        ):
            raise _invalid(
                "max_iterations",
                f"步骤 {step_id} 的 max_iterations 必须在 1..{MAX_LOOP_ITERATIONS}",
            )
        return LoopStep(
            step_id=step_id,
            max_duration_seconds=duration,
            max_iterations=iterations,
            steps=_parse_body_steps(payload.get("steps"), f"{step_id}.steps"),
        )
    if step_type == "if":
        step_id = _step_id(payload)
        condition = payload.get("condition")
        if not isinstance(condition, dict):
            raise _invalid("condition", f"步骤 {step_id} 缺少 condition")
        ref_step = condition.get("step")
        if not isinstance(ref_step, str) or not _STEP_ID_RE.fullmatch(ref_step):
            raise _invalid("condition.step", f"步骤 {step_id} 的 condition.step 非法")
        if condition.get("field") != "status":
            raise _invalid(
                "condition.field",
                f"步骤 {step_id} 的条件只支持引用前序步骤的 status（ADR-0021）",
            )
        equals = condition.get("equals")
        if equals not in {"succeeded", "failed"}:
            raise _invalid("condition.equals", f"步骤 {step_id} 的 equals 只能是 succeeded/failed")
        raw_else = payload.get("else")
        else_steps = (
            _parse_body_steps(raw_else, f"{step_id}.else")
            if raw_else is not None
            else ()
        )
        return IfStep(
            step_id=step_id,
            condition_step=ref_step,
            condition_equals=equals,
            then_steps=_parse_body_steps(payload.get("then"), f"{step_id}.then"),
            else_steps=else_steps,
        )
    raise _invalid("type", "步骤 type 只能是 tool / loop / if")


def parse_skill_dsl_document(payload: Any) -> SkillDslDocument:
    """Parse and validate a DSL document against the contract bounds.

    Raises MobileAgentError SKILL_DSL_INVALID on any shape violation.
    Reference resolution ($inputs.*), tool registration and risk derivation
    are the interpreter's job, not this parser's.
    """

    if not isinstance(payload, dict):
        raise _invalid("document", "DSL 文档必须是 JSON 对象")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise _invalid("schema_version", f"schema_version 必须是 {SCHEMA_VERSION}")

    skill_id = _require_str(payload, "skill_id", 64)
    if not _SKILL_ID_RE.fullmatch(skill_id):
        raise _invalid("skill_id", "skill_id 必须是 domain.verb 形式")
    skill_version = _require_str(payload, "skill_version", 16)
    if not _VERSION_RE.fullmatch(skill_version):
        raise _invalid("skill_version", "skill_version 必须是 semver（如 1.0.0）")
    name = _require_str(payload, "name", 80)
    description = _require_str(payload, "description", 500)

    timeout = payload.get("timeout_seconds")
    if timeout is not None and (
        not isinstance(timeout, int)
        or isinstance(timeout, bool)
        or not 1 <= timeout <= MAX_TIMEOUT_SECONDS
    ):
        raise _invalid("timeout_seconds", f"timeout_seconds 必须在 1..{MAX_TIMEOUT_SECONDS}")

    raw_inputs = payload.get("inputs")
    if not isinstance(raw_inputs, list) or len(raw_inputs) > MAX_INPUTS:
        raise _invalid("inputs", f"inputs 必须是至多 {MAX_INPUTS} 项的数组")
    inputs: list[SkillDslInput] = []
    for item in raw_inputs:
        if not isinstance(item, dict):
            raise _invalid("inputs", "每个 input 必须是对象")
        input_name = item.get("name")
        if not isinstance(input_name, str) or not _INPUT_NAME_RE.fullmatch(input_name):
            raise _invalid("inputs.name", "input name 必须匹配 ^[a-z][a-z0-9_]*$")
        input_type = item.get("type")
        if input_type not in {"string", "integer", "number", "boolean"}:
            raise _invalid("inputs.type", f"input {input_name} 的 type 非法")
        max_length = item.get("max_length")
        if max_length is not None and (
            not isinstance(max_length, int)
            or isinstance(max_length, bool)
            or not 1 <= max_length <= 2000
        ):
            raise _invalid("inputs.max_length", f"input {input_name} 的 max_length 非法")
        minimum = item.get("minimum")
        maximum = item.get("maximum")
        for bound_field, bound in (("minimum", minimum), ("maximum", maximum)):
            if bound is not None and (
                not isinstance(bound, int | float) or isinstance(bound, bool)
            ):
                raise _invalid(f"inputs.{bound_field}", f"input {input_name} 的 {bound_field} 非法")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise _invalid("inputs.minimum", f"input {input_name} 的 minimum 大于 maximum")
        inputs.append(
            SkillDslInput(
                name=input_name,
                type=input_type,
                required=item.get("required") is True,
                description=item.get("description") if isinstance(item.get("description"), str) else "",
                max_length=max_length,
                minimum=minimum,
                maximum=maximum,
            )
        )
    if len({item.name for item in inputs}) != len(inputs):
        raise _invalid("inputs", "input name 重复")

    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= MAX_STEPS:
        raise _invalid("steps", f"steps 必须是 1..{MAX_STEPS} 项的数组")
    steps = tuple(_parse_step(item) for item in raw_steps)

    all_step_ids: list[str] = []

    def _collect(step_list: tuple[Step, ...] | tuple[ToolStep, ...]) -> None:
        for step in step_list:
            all_step_ids.append(step.step_id)
            if isinstance(step, LoopStep):
                _collect(step.steps)
            elif isinstance(step, IfStep):
                _collect(step.then_steps)
                _collect(step.else_steps)

    _collect(steps)
    if len(set(all_step_ids)) != len(all_step_ids):
        raise _invalid("steps", "step_id 重复")

    seen: set[str] = set()
    for step in steps:
        # 条件只能引用顶层先执行步骤：循环/分支体内的步骤会执行零到多次，
        # 其结果状态对顶层步骤不具确定语义。
        if isinstance(step, IfStep) and step.condition_step not in seen:
            raise _invalid(
                "condition.step",
                f"步骤 {step.step_id} 引用的 {step.condition_step} 不是先执行的顶层步骤",
            )
        seen.add(step.step_id)

    return SkillDslDocument(
        skill_id=skill_id,
        skill_version=skill_version,
        name=name,
        description=description,
        timeout_seconds=timeout,
        inputs=tuple(inputs),
        steps=steps,
    )
