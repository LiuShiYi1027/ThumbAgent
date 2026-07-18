"""Validated GoalSpec and replaceable goal compiler boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.evaluation import AgentGoalAcceptance


@dataclass(frozen=True, slots=True)
class AgentGoalSpec:
    """A reviewable goal-compilation draft; model output is never implicitly confirmed."""

    source_goal: str
    execution_goal: str
    assumptions: tuple[str, ...]
    confidence: float
    compiler_id: str
    source: str
    confirmation_required: bool
    acceptance: AgentGoalAcceptance | None = None
    schema_version: str = "1.0.0"

    @classmethod
    def from_dict(cls, payload: object) -> "AgentGoalSpec":
        """Validate one public GoalSpec payload."""

        if not isinstance(payload, dict):
            raise _invalid("GoalSpec 必须是 JSON object")
        allowed = {"schema_version", "source_goal", "execution_goal", "acceptance", "assumptions", "confidence", "compiler_id", "source", "confirmation_required"}
        unknown = sorted(str(key) for key in set(payload) - allowed)
        if unknown:
            raise _invalid("GoalSpec 包含未知字段", {"unknown_fields": unknown})
        if payload.get("schema_version") != "1.0.0":
            raise _invalid("GoalSpec schema_version 无效")
        source_goal = _text(payload.get("source_goal"), "source_goal", 500)
        execution_goal = _text(payload.get("execution_goal"), "execution_goal", 1000)
        compiler_id = _text(payload.get("compiler_id"), "compiler_id", 120)
        source = payload.get("source")
        if source not in {"rule", "llm"}:
            raise _invalid("GoalSpec source 无效")
        confirmation_required = payload.get("confirmation_required")
        if not isinstance(confirmation_required, bool):
            raise _invalid("GoalSpec confirmation_required 无效")
        if source == "llm" and not confirmation_required:
            raise _invalid("模型 GoalSpec 必须要求显式确认")
        confidence = payload.get("confidence")
        if not isinstance(confidence, int | float) or isinstance(confidence, bool) or confidence < 0 or confidence > 1:
            raise _invalid("GoalSpec confidence 无效")
        raw_assumptions = payload.get("assumptions")
        if not isinstance(raw_assumptions, list) or len(raw_assumptions) > 8:
            raise _invalid("GoalSpec assumptions 无效")
        assumptions = tuple(_text(item, f"assumptions[{index}]", 300) for index, item in enumerate(raw_assumptions))
        raw_acceptance = payload.get("acceptance")
        acceptance = AgentGoalAcceptance.from_dict(raw_acceptance) if raw_acceptance is not None else None
        return cls(source_goal, execution_goal, assumptions, float(confidence), compiler_id, source, confirmation_required, acceptance)

    def to_dict(self) -> dict[str, Any]:
        """Return the normalized public Contract representation."""

        payload: dict[str, Any] = {"schema_version": self.schema_version, "source_goal": self.source_goal, "execution_goal": self.execution_goal, "assumptions": list(self.assumptions), "confidence": self.confidence, "compiler_id": self.compiler_id, "source": self.source, "confirmation_required": self.confirmation_required}
        if self.acceptance is not None:
            payload["acceptance"] = self.acceptance.to_dict()
        return payload


class GoalCompiler(Protocol):
    """Compile a source goal without observing or mutating a device."""

    compiler_id: str

    def compile(self, goal: str) -> AgentGoalSpec:
        """Return a validated, reviewable GoalSpec draft."""


class PassThroughGoalCompiler:
    """No-model compiler preserving the exact source goal."""

    compiler_id = "rule_based.passthrough"

    def compile(self, goal: str) -> AgentGoalSpec:
        normalized = _text(goal.strip(), "goal", 500)
        return AgentGoalSpec(normalized, normalized, (), 1.0, self.compiler_id, "rule", False)


class UnavailableGoalCompiler:
    """Compiler preserving an explicit model-unavailable configuration failure."""

    compiler_id = "model.unavailable"

    def __init__(self, error: MobileAgentError) -> None:
        self._error = error

    def compile(self, goal: str) -> AgentGoalSpec:
        raise self._error


def model_goal_spec(source_goal: str, payload: object, compiler_id: str) -> AgentGoalSpec:
    """Wrap untrusted model fields with Runtime-owned provenance and confirmation policy."""

    if not isinstance(payload, dict):
        raise _model_invalid("目标编译输出必须是 JSON object")
    allowed = {"execution_goal", "acceptance", "assumptions", "confidence"}
    unknown = sorted(str(key) for key in set(payload) - allowed)
    if unknown:
        raise _model_invalid("目标编译输出包含未知字段", {"unknown_fields": unknown})
    public_payload: dict[str, Any] = {"schema_version": "1.0.0", "source_goal": source_goal, "execution_goal": payload.get("execution_goal"), "assumptions": payload.get("assumptions"), "confidence": payload.get("confidence"), "compiler_id": compiler_id, "source": "llm", "confirmation_required": True}
    if payload.get("acceptance") is not None:
        public_payload["acceptance"] = payload["acceptance"]
    try:
        return AgentGoalSpec.from_dict(public_payload)
    except MobileAgentError as error:
        raise _model_invalid("目标编译输出不符合 GoalSpec Contract", {"payload_keys": sorted(str(key) for key in payload)}) from error


def _text(value: object, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise _invalid(f"GoalSpec {field} 无效")
    return value.strip()


def _invalid(message: str, details: dict[str, Any] | None = None) -> MobileAgentError:
    return MobileAgentError(code="INVALID_ARGUMENT", category=ErrorCategory.VALIDATION, message=message, details=details or {})


def _model_invalid(message: str, details: dict[str, Any] | None = None) -> MobileAgentError:
    return MobileAgentError(code="MODEL_OUTPUT_INVALID", category=ErrorCategory.VALIDATION, message=message, details=details or {})
