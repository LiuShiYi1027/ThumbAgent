"""Planner contracts for the bounded Agent Loop preview."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.ui.model import UiSelector


class AgentDecisionType(str, Enum):
    """Supported preview decision types."""

    RUN_SKILL = "run_skill"
    RUN_TOOL = "run_tool"
    FINISH = "finish"


@dataclass(frozen=True, slots=True)
class AgentObservationSummary:
    """Small observation snapshot safe to include in task reports and model prompts."""

    observation_id: str
    foreground_app: dict[str, Any]
    device_state: str
    ui_summary: tuple[dict[str, Any], ...] = ()
    ui_summary_total_candidates: int = 0
    ui_summary_truncated: bool = False
    last_action_feedback: dict[str, Any] | None = None
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "observation_id": self.observation_id,
            "foreground_app": self.foreground_app,
            "device_state": self.device_state,
            "ui_summary": [dict(item) for item in self.ui_summary],
            "ui_summary_total_candidates": self.ui_summary_total_candidates,
            "ui_summary_truncated": self.ui_summary_truncated,
            "last_action_feedback": dict(self.last_action_feedback)
            if self.last_action_feedback
            else None,
        }


@dataclass(frozen=True, slots=True)
class AgentDecision:
    """A structured decision produced by a planner and validated by the runner."""

    decision_id: str
    decision_type: AgentDecisionType
    skill_id: str
    arguments: dict[str, Any]
    reason: str
    planner_id: str
    tool_id: str = ""
    confidence: float | None = None
    source: str = "planner"
    repair_count: int = 0
    provider_retry_count: int = 0
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "decision_id": self.decision_id,
            "decision_type": self.decision_type.value,
            "skill_id": self.skill_id,
            "tool_id": self.tool_id,
            "arguments": self.arguments,
            "reason": self.reason,
            "planner_id": self.planner_id,
            "confidence": self.confidence,
            "source": self.source,
            "repair_count": self.repair_count,
            "provider_retry_count": self.provider_retry_count,
        }


class Planner(Protocol):
    """Produce the next safe Agent decision from a goal and observation summary."""

    planner_id: str

    def decide(self, goal: str, observation: AgentObservationSummary, round_index: int) -> AgentDecision:
        """Return a structured decision or raise a domain error."""


class RuleBasedPlanner:
    """Preview planner that maps one safe goal family to bounded tool decisions."""

    planner_id = "rule_based.preview"

    def decide(self, goal: str, observation: AgentObservationSummary, round_index: int) -> AgentDecision:
        """Return deterministic tool decisions for the display/brightness demo goal."""

        normalized = goal.strip().lower()
        if round_index < 1 or round_index > 6:
            raise MobileAgentError(
                code="NO_PROGRESS",
                category=ErrorCategory.EXECUTION,
                message="预览 Planner 超出多轮决策预算",
                details={"round": round_index},
            )
        if not _is_display_brightness_goal(normalized):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="当前 Agent Preview 只支持进入系统设置的显示/亮度页面",
                suggested_action="请尝试目标：进入显示和亮度页面",
                details={"planner_id": self.planner_id},
            )
        if round_index == 1:
            return AgentDecision(
                decision_id=f"decision_{uuid.uuid4().hex}",
                decision_type=AgentDecisionType.RUN_TOOL,
                skill_id="",
                tool_id="app.launch",
                arguments={"app_id": "com.android.settings"},
                reason="先打开系统设置，随后根据页面观察决定下一步。",
                planner_id=self.planner_id,
                confidence=1.0,
                source="rule",
            )
        expected_selector = _expected_selector_for_goal(normalized)
        if _summary_contains(observation, "Display settings") or _summary_contains(observation, "显示和亮度"):
            return AgentDecision(
                decision_id=f"decision_{uuid.uuid4().hex}",
                decision_type=AgentDecisionType.FINISH,
                skill_id="",
                tool_id="",
                arguments={"expected_selector": expected_selector},
                reason="当前 Observation 已出现目标页面的可验证文本。",
                planner_id=self.planner_id,
                confidence=1.0,
                source="rule",
            )
        selector_value = "亮度" if _contains_cjk(normalized) else "Display"
        if _summary_contains(observation, selector_value):
            return AgentDecision(
                decision_id=f"decision_{uuid.uuid4().hex}",
                decision_type=AgentDecisionType.RUN_TOOL,
                skill_id="",
                tool_id="input.tap_element",
                arguments={
                    "selector": {
                        "strategy": "text",
                        "value": selector_value,
                        "match": "contains",
                        "resolve_clickable_ancestor": True,
                        "package": "com.android.settings",
                    }
                },
                reason="当前设置页已出现显示/亮度入口，点击对应元素。",
                planner_id=self.planner_id,
                confidence=1.0,
                source="rule",
            )
        direction = "up"
        feedback = observation.last_action_feedback
        if (
            feedback
            and feedback.get("tool_id") == "input.swipe"
            and feedback.get("effect") == "unchanged"
        ):
            previous_arguments = feedback.get("arguments")
            if isinstance(previous_arguments, dict):
                previous_direction = previous_arguments.get("direction")
                if previous_direction == "up":
                    direction = "down"
                elif previous_direction == "down":
                    direction = "up"
        return AgentDecision(
            decision_id=f"decision_{uuid.uuid4().hex}",
            decision_type=AgentDecisionType.RUN_TOOL,
            skill_id="",
            tool_id="input.swipe",
            arguments={"direction": direction, "distance_percent": 0.35, "duration_ms": 900},
            reason="当前页面尚未看到目标入口；若上一方向无进展则切换方向后重新观察。",
            planner_id=self.planner_id,
            confidence=1.0,
            source="rule",
        )


class MockLLMPlanner:
    """Offline planner that validates recorded LLM-like structured output."""

    planner_id = "mock_llm.preview"

    def __init__(self, payload: object) -> None:
        self._payload = payload

    def decide(self, goal: str, observation: AgentObservationSummary, round_index: int) -> AgentDecision:
        """Parse the configured mock payload into a safe Agent decision."""

        payload = self._payload
        if isinstance(payload, list):
            index = round_index - 1
            if index < 0 or index >= len(payload):
                raise MobileAgentError(
                    code="NO_PROGRESS",
                    category=ErrorCategory.EXECUTION,
                    message="Mock LLM Planner 决策序列已耗尽",
                    details={"round": round_index},
                )
            payload = payload[index]
        elif round_index != 1:
            raise MobileAgentError(
                code="NO_PROGRESS",
                category=ErrorCategory.EXECUTION,
                message="Mock LLM Planner 只提供了一轮决策",
                details={"round": round_index},
            )
        return parse_llm_decision_payload(payload, self.planner_id)


class UnavailablePlanner:
    """Planner placeholder that preserves explicit model-unavailable failures."""

    planner_id = "model.unavailable"

    def __init__(self, error: MobileAgentError) -> None:
        self._error = error

    def decide(self, goal: str, observation: AgentObservationSummary, round_index: int) -> AgentDecision:
        """Fail with the configured model availability error before any device action."""

        raise self._error


def parse_llm_decision_payload(payload: object, planner_id: str) -> AgentDecision:
    """Validate an LLM-like structured payload and return an AgentDecision."""

    if not isinstance(payload, dict):
        raise _model_output_invalid("Planner 输出必须是 JSON object", {"payload_type": type(payload).__name__})
    decision_type = payload.get("decision_type")
    allowed_types = {item.value for item in AgentDecisionType}
    if decision_type not in allowed_types:
        raise _model_output_invalid(
            "Planner 输出了不支持的 decision_type",
            {"decision_type": _safe_scalar(decision_type), "payload_keys": _sorted_keys(payload)},
        )
    decision_kind = AgentDecisionType(str(decision_type))
    skill_id = _optional_string(payload.get("skill_id"))
    tool_id = _optional_string(payload.get("tool_id"))
    if decision_kind is AgentDecisionType.RUN_SKILL and not skill_id:
        raise _model_output_invalid("Planner 输出缺少有效 skill_id", {"payload_keys": _sorted_keys(payload)})
    if decision_kind is AgentDecisionType.RUN_TOOL and not tool_id:
        raise _model_output_invalid("Planner 输出缺少有效 tool_id", {"payload_keys": _sorted_keys(payload)})
    arguments = payload.get("arguments")
    if not isinstance(arguments, dict):
        raise _model_output_invalid(
            "Planner 输出缺少有效 arguments",
            {"payload_keys": _sorted_keys(payload), "arguments_type": type(arguments).__name__},
        )
    if decision_kind is AgentDecisionType.RUN_SKILL and (
        not isinstance(arguments.get("target_selector"), dict)
        or not isinstance(arguments.get("expected_selector"), dict)
    ):
        raise _model_output_invalid(
            "Planner 输出缺少有效 Selector 参数",
            {
                "payload_keys": _sorted_keys(payload),
                "argument_keys": _sorted_keys(arguments),
                "target_selector_type": type(arguments.get("target_selector")).__name__,
                "expected_selector_type": type(arguments.get("expected_selector")).__name__,
            },
        )
    if decision_kind is AgentDecisionType.RUN_TOOL:
        validate_agent_tool_arguments(tool_id, arguments)
    if decision_kind is AgentDecisionType.FINISH:
        validate_finish_arguments(arguments)
    raw_reason = payload.get("reason")
    if raw_reason is None or (isinstance(raw_reason, str) and not raw_reason.strip()):
        reason = "模型未提供决策说明。"
    elif isinstance(raw_reason, str) and len(raw_reason) <= 500:
        reason = raw_reason.strip()
    else:
        raise _model_output_invalid(
            "Planner 输出的 reason 格式无效",
            {
                "payload_keys": _sorted_keys(payload),
                "reason_type": type(raw_reason).__name__,
                "reason_chars": len(raw_reason) if isinstance(raw_reason, str) else None,
            },
        )
    confidence = _parse_confidence(payload.get("confidence"))
    return AgentDecision(
        decision_id=f"decision_{uuid.uuid4().hex}",
        decision_type=decision_kind,
        skill_id=skill_id,
        tool_id=tool_id,
        arguments=dict(arguments),
        reason=reason,
        planner_id=planner_id,
        confidence=confidence,
        source="llm",
    )


def validate_agent_tool_arguments(tool_id: str, arguments: dict[str, Any]) -> None:
    """Validate model-facing Tool arguments before any device action is dispatched."""

    if tool_id == "app.launch":
        _require_argument_keys(tool_id, arguments, {"app_id"}, {"app_id"})
        app_id = arguments.get("app_id")
        if not isinstance(app_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", app_id
        ):
            raise _tool_arguments_invalid(tool_id, arguments, "app_id 必须是有效应用标识")
        return
    if tool_id == "input.tap_element":
        _require_argument_keys(tool_id, arguments, {"selector"}, {"selector"})
        selector = arguments.get("selector")
        if not isinstance(selector, dict):
            raise _tool_arguments_invalid(tool_id, arguments, "selector 必须是 object")
        if selector.get("resolve_clickable_ancestor") is not True:
            raise _tool_arguments_invalid(
                tool_id,
                arguments,
                "input.tap_element selector 必须显式设置 resolve_clickable_ancestor=true",
                selector_error="resolve_clickable_ancestor_required",
                selector_error_field="resolve_clickable_ancestor",
                selector_keys=_sorted_keys(selector),
            )
        try:
            UiSelector.from_dict(selector)
        except MobileAgentError as error:
            error_field = error.details.get("field")
            unknown_fields = error.details.get("unknown_fields")
            raise _tool_arguments_invalid(
                tool_id,
                arguments,
                "input.tap_element selector 无效",
                selector_error=error.code,
                selector_error_field=error_field if isinstance(error_field, str) else "",
                selector_unknown_keys=(
                    [item for item in unknown_fields if isinstance(item, str)]
                    if isinstance(unknown_fields, list)
                    else []
                ),
                selector_keys=_sorted_keys(selector),
            ) from error
        return
    if tool_id == "input.swipe":
        required = {"direction", "distance_percent", "duration_ms"}
        _require_argument_keys(tool_id, arguments, required, required)
        direction = arguments.get("direction")
        distance = arguments.get("distance_percent")
        duration = arguments.get("duration_ms")
        if direction not in {"up", "down", "left", "right"}:
            raise _tool_arguments_invalid(tool_id, arguments, "direction 无效")
        if (
            not isinstance(distance, int | float)
            or isinstance(distance, bool)
            or distance < 0.1
            or distance > 0.8
        ):
            raise _tool_arguments_invalid(tool_id, arguments, "distance_percent 无效")
        if (
            not isinstance(duration, int)
            or isinstance(duration, bool)
            or duration < 100
            or duration > 2000
        ):
            raise _tool_arguments_invalid(tool_id, arguments, "duration_ms 无效")
        return
    if tool_id in {"navigation.back", "navigation.home"}:
        _require_argument_keys(tool_id, arguments, set(), set())


def validate_finish_arguments(arguments: dict[str, Any]) -> None:
    """Validate deterministic finish criteria before Runtime verification."""

    allowed = {"expected_selector", "expected_foreground_app"}
    _require_argument_keys("finish", arguments, allowed, {"expected_selector"})
    raw_selector = arguments.get("expected_selector")
    if not isinstance(raw_selector, dict):
        raise _tool_arguments_invalid("finish", arguments, "expected_selector 必须是 object")
    try:
        UiSelector.from_dict(raw_selector)
    except MobileAgentError as error:
        raise _tool_arguments_invalid(
            "finish", arguments, "expected_selector 无效", selector_error=error.code
        ) from error
    foreground = arguments.get("expected_foreground_app")
    if foreground is None:
        return
    if not isinstance(foreground, dict):
        raise _tool_arguments_invalid(
            "finish", arguments, "expected_foreground_app 必须是 object"
        )
    unknown = set(foreground) - {"app_id", "activity"}
    if unknown or not foreground:
        raise _tool_arguments_invalid(
            "finish",
            arguments,
            "expected_foreground_app 字段无效",
            unknown_argument_keys=sorted(str(key) for key in unknown),
        )
    for key, value in foreground.items():
        limit = 255 if key == "app_id" else 500
        if not isinstance(value, str) or not value or len(value) > limit:
            raise _tool_arguments_invalid(
                "finish", arguments, f"expected_foreground_app.{key} 无效"
            )


def _require_argument_keys(
    tool_id: str,
    arguments: dict[str, Any],
    allowed: set[str],
    required: set[str],
) -> None:
    actual = set(arguments)
    missing = sorted(required - actual)
    unknown = sorted(actual - allowed)
    if missing or unknown:
        raise _tool_arguments_invalid(
            tool_id,
            arguments,
            "Tool arguments 字段不符合契约",
            missing_argument_keys=missing,
            unknown_argument_keys=unknown,
        )


def _tool_arguments_invalid(
    tool_id: str,
    arguments: dict[str, Any],
    message: str,
    *,
    missing_argument_keys: list[str] | None = None,
    unknown_argument_keys: list[str] | None = None,
    selector_error: str = "",
    selector_error_field: str = "",
    selector_unknown_keys: list[str] | None = None,
    selector_keys: list[str] | None = None,
) -> MobileAgentError:
    return _model_output_invalid(
        message,
        {
            "tool_id": tool_id,
            "argument_keys": _sorted_keys(arguments),
            "missing_argument_keys": missing_argument_keys or [],
            "unknown_argument_keys": unknown_argument_keys or [],
            "selector_error": selector_error,
            "selector_error_field": selector_error_field,
            "selector_unknown_keys": selector_unknown_keys or [],
            "selector_keys": selector_keys or [],
        },
    )


def _parse_confidence(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool) or value < 0 or value > 1:
        raise _model_output_invalid("Planner 输出 confidence 必须在 0 到 1 之间")
    return float(value)


def _model_output_invalid(message: str, details: dict[str, Any] | None = None) -> MobileAgentError:
    return MobileAgentError(
        code="MODEL_OUTPUT_INVALID",
        category=ErrorCategory.VALIDATION,
        message=message,
        details=details or {},
    )


def _sorted_keys(value: dict[Any, Any]) -> list[str]:
    return sorted(str(key) for key in value.keys())


def _safe_scalar(value: object) -> object:
    if isinstance(value, str):
        return value[:120]
    if isinstance(value, int | float | bool) or value is None:
        return value
    return type(value).__name__


def _optional_string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _summary_contains(observation: AgentObservationSummary, text: str) -> bool:
    needle = text.lower()
    for item in observation.ui_summary:
        for key in ("text", "resource_id", "content_description"):
            value = item.get(key)
            if isinstance(value, str) and needle in value.lower():
                return True
    return False


def _expected_selector_for_goal(goal: str) -> dict[str, Any]:
    selector_value = "亮度" if _contains_cjk(goal) else "Display settings"
    selector: dict[str, Any] = {
        "strategy": "text",
        "value": selector_value,
        "match": "contains",
        "package": "com.android.settings",
    }
    if _contains_cjk(goal):
        selector["ancestor_path"] = [
            {"strategy": "resource_id", "value": "action_bar", "match": "contains"}
        ]
    return selector


def _is_display_brightness_goal(goal: str) -> bool:
    if not goal:
        return False
    cjk_match = ("显示" in goal or "屏幕" in goal) and "亮度" in goal
    english_match = ("display" in goal or "screen" in goal) and "brightness" in goal
    fake_test_match = "display settings" in goal
    return cjk_match or english_match or fake_test_match


def _contains_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)
