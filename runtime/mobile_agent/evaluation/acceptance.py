"""Shared independent success criteria for Agent execution and evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.ui.model import UiSelector


@dataclass(frozen=True, slots=True)
class AgentGoalAcceptance:
    """Validated all-of criteria owned by the Agent caller, not the model."""

    foreground_app_id: str | None = None
    foreground_activity: str | None = None
    expected_selector: UiSelector | None = None

    @classmethod
    def from_dict(cls, payload: object) -> "AgentGoalAcceptance":
        """Validate one external acceptance payload."""

        if not isinstance(payload, dict):
            raise _invalid("Agent 成功条件必须是 JSON object")
        allowed = {"foreground_app_id", "foreground_activity", "expected_selector"}
        unknown = sorted(str(key) for key in set(payload) - allowed)
        if unknown:
            raise _invalid("Agent 成功条件包含未知字段", {"unknown_fields": unknown})
        foreground_app_id = _optional_text(
            payload.get("foreground_app_id"), "foreground_app_id", 255
        )
        foreground_activity = _optional_text(
            payload.get("foreground_activity"), "foreground_activity", 500
        )
        raw_selector = payload.get("expected_selector")
        expected_selector = None
        if raw_selector is not None:
            if not isinstance(raw_selector, dict):
                raise _invalid("Agent 成功条件 expected_selector 无效")
            expected_selector = UiSelector.from_dict(raw_selector)
            if expected_selector.resolve_clickable_ancestor or expected_selector.ancestor_path:
                raise _invalid("Agent 成功条件 Selector 不支持可点击祖先或 ancestor_path")
        if (
            foreground_app_id is None
            and foreground_activity is None
            and expected_selector is None
        ):
            raise _invalid("Agent 成功条件至少需要一个判定字段")
        return cls(foreground_app_id, foreground_activity, expected_selector)

    def to_dict(self) -> dict[str, Any]:
        """Return the normalized public Contract representation."""

        payload: dict[str, Any] = {}
        if self.foreground_app_id is not None:
            payload["foreground_app_id"] = self.foreground_app_id
        if self.foreground_activity is not None:
            payload["foreground_activity"] = self.foreground_activity
        if self.expected_selector is not None:
            payload["expected_selector"] = self.expected_selector.to_dict()
        return payload


def _optional_text(value: object, field: str, limit: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > limit:
        raise _invalid(f"Agent 成功条件 {field} 无效")
    return value


def _invalid(message: str, details: dict[str, Any] | None = None) -> MobileAgentError:
    return MobileAgentError(
        code="INVALID_ARGUMENT",
        category=ErrorCategory.VALIDATION,
        message=message,
        details=details or {},
    )
