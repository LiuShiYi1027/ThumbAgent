"""OpenAI-compatible Planner provider preview.

This module prepares the provider boundary without enabling real model calls in
the default Runtime. Tests inject a fake transport so the fast test suite never
depends on network access or model credentials.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, replace
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mobile_agent.agent.planner import (
    AgentDecision,
    AgentObservationSummary,
    parse_llm_decision_payload,
)
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.goals.compiler import AgentGoalSpec, model_goal_spec


@dataclass(frozen=True, slots=True)
class OpenAICompatiblePlannerConfig:
    """Configuration for an OpenAI-compatible chat-completions endpoint."""

    base_url: str
    model: str
    api_key: str
    timeout_seconds: float = 30.0

    def endpoint(self) -> str:
        """Return the chat-completions endpoint URL."""

        return f"{self.base_url.rstrip('/')}/chat/completions"


class ModelTransport(Protocol):
    """Transport boundary for model HTTP calls."""

    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        """POST JSON and return a decoded JSON object."""


class HttpModelTransport:
    """Standard-library JSON HTTP transport."""

    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        """POST JSON using urllib and decode the response."""

        data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = Request(url, data=data, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            retryable = error.code == 429 or 500 <= error.code <= 599
            raise _model_unavailable(
                "http_status",
                retryable=retryable,
                details={"http_status": error.code},
                suggested_action=(
                    "稍后重试或检查 Provider 配额"
                    if retryable
                    else "检查 Provider 地址、模型名和密钥"
                ),
            ) from error
        except TimeoutError as error:
            raise _model_unavailable(
                "timeout",
                retryable=True,
                details={"timeout_seconds": timeout_seconds},
                suggested_action="稍后重试或调高模型超时配置",
            ) from error
        except URLError as error:
            failure_kind = "timeout" if isinstance(error.reason, TimeoutError) else "connection"
            raise _model_unavailable(
                failure_kind,
                retryable=True,
                details={"timeout_seconds": timeout_seconds}
                if failure_kind == "timeout"
                else {},
                suggested_action="检查网络和 Provider 可用性后重试",
            ) from error
        except OSError as error:
            raise _model_unavailable(
                "connection",
                retryable=True,
                suggested_action="检查网络和 Provider 可用性后重试",
            ) from error
        except json.JSONDecodeError as error:
            raise _model_unavailable(
                "invalid_json",
                retryable=True,
                suggested_action="稍后重试或检查 Provider 兼容性",
            ) from error
        if not isinstance(payload, dict):
            raise MobileAgentError(
                code="MODEL_OUTPUT_INVALID",
                category=ErrorCategory.VALIDATION,
                message="模型 Provider 响应必须是 JSON object",
            )
        return payload


class OpenAICompatiblePlanner:
    """Planner that consumes a chat-completions style structured response."""

    planner_id = "openai_compatible.preview"
    compiler_id = "openai_compatible.goal_compiler.preview"

    def __init__(
        self,
        config: OpenAICompatiblePlannerConfig,
        transport: ModelTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport or HttpModelTransport()

    def decide(
        self,
        goal: str,
        observation: AgentObservationSummary,
        round_index: int,
    ) -> AgentDecision:
        """Call the configured provider and parse a structured Agent decision."""

        if round_index < 1 or round_index > 6:
            raise MobileAgentError(
                code="NO_PROGRESS",
                category=ErrorCategory.EXECUTION,
                message="OpenAI-compatible Planner Preview 超出多轮决策预算",
                details={"round": round_index},
            )
        repair_error: MobileAgentError | None = None
        for repair_count in range(2):
            payload: object | None = None
            try:
                response, provider_retry_count = self._post_with_retry(
                    self._request_body(goal, observation, round_index, repair_error)
                )
                payload = _extract_decision_payload(response)
                decision = parse_llm_decision_payload(payload, self.planner_id)
                return replace(
                    decision,
                    repair_count=repair_count,
                    provider_retry_count=provider_retry_count,
                )
            except MobileAgentError as error:
                if error.code != "MODEL_OUTPUT_INVALID":
                    raise
                if repair_count == 0:
                    repair_error = error
                    continue
                raise MobileAgentError(
                    code=error.code,
                    category=error.category,
                    message=error.message,
                    retryable=error.retryable,
                    outcome=error.outcome,
                    suggested_action=error.suggested_action,
                    details={
                        **error.details,
                        "response_id": f"modelresp_{uuid.uuid4().hex}",
                        "repair_count": repair_count,
                        "payload_summary": _summarize_payload(payload),
                    },
                ) from error
        raise AssertionError("bounded model repair loop exhausted")

    def compile(self, goal: str) -> AgentGoalSpec:
        """Compile a natural-language goal into an unconfirmed GoalSpec draft."""

        if not isinstance(goal, str) or not goal.strip() or len(goal) > 500:
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="目标必须是 1 到 500 字符的文本",
            )
        response, _ = self._post_with_retry(self._goal_compile_request_body(goal.strip()))
        payload = _extract_decision_payload(response)
        return model_goal_spec(goal.strip(), payload, self.compiler_id)

    def _post_with_retry(self, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        for retry_count in range(2):
            try:
                return (
                    self._transport.post_json(
                        self._config.endpoint(),
                        self._headers(),
                        body,
                        self._config.timeout_seconds,
                    ),
                    retry_count,
                )
            except MobileAgentError as error:
                mapped = error
            except TimeoutError:
                mapped = _model_unavailable(
                    "timeout", retryable=True, suggested_action="稍后重试"
                )
            except OSError:
                mapped = _model_unavailable(
                    "connection", retryable=True, suggested_action="检查网络后重试"
                )
            if (
                mapped.code == "MODEL_UNAVAILABLE"
                and mapped.retryable
                and retry_count == 0
            ):
                continue
            if mapped.code == "MODEL_UNAVAILABLE":
                raise MobileAgentError(
                    code=mapped.code,
                    category=mapped.category,
                    message=mapped.message,
                    retryable=mapped.retryable,
                    outcome=mapped.outcome,
                    suggested_action=mapped.suggested_action,
                    details={**mapped.details, "provider_retry_count": retry_count},
                ) from mapped
            raise mapped
        raise AssertionError("bounded provider retry loop exhausted")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request_body(
        self,
        goal: str,
        observation: AgentObservationSummary,
        round_index: int,
        repair_error: MobileAgentError | None = None,
    ) -> dict[str, Any]:
        messages = [
            {
                "role": "system",
                "content": _system_prompt(),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "goal": goal,
                        "observation": observation.to_dict(),
                        "round": round_index,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]
        if repair_error is not None:
            messages.append(
                {
                    "role": "user",
                    "content": json.dumps(
                        _repair_feedback(repair_error),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                }
            )
        return {
            "model": self._config.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": messages,
        }

    def _goal_compile_request_body(self, goal: str) -> dict[str, Any]:
        return {
            "model": self._config.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _goal_compiler_prompt()},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"goal": goal}, ensure_ascii=False, separators=(",", ":")
                    ),
                },
            ],
        }


def _system_prompt() -> str:
    return (
        "You are the Mobile Agent planner for a bounded local Android preview. "
        "Return only one JSON object, without markdown or prose. "
        "You may only choose these decision types: run_tool, finish. "
        "Allowed tools: app.launch, input.tap_element, input.swipe, navigation.back, navigation.home. "
        "Never output shell commands, adb commands, secrets, coordinates, or unlisted tools. "
        "Use run_tool with {\"decision_type\":\"run_tool\",\"tool_id\":\"app.launch\","
        "\"arguments\":{\"app_id\":\"com.android.settings\"},\"reason\":\"...\",\"confidence\":0.8}. "
        "Use input.tap_element only with a selector object. Its selector must explicitly include "
        "resolve_clickable_ancestor=true. Selector fields are limited to strategy, value, match, "
        "package, clickable, enabled, resolve_clickable_ancestor, and ancestor_path; do not add "
        "coordinate or descriptive fields. strategy is text, resource_id, or content_description; "
        "match is exact or contains. Prefer text contains 亮度 or Display. The observation "
        "ui_summary prioritizes semantic text and may "
        "mark clickable_ancestor=true; when the target text is present, tap it instead of scrolling. "
        "ui_summary_truncated indicates that additional semantic candidates were omitted. "
        "Use input.swipe with direction up/down, distance_percent "
        "between 0.1 and 0.8, duration_ms between 100 and 2000. direction describes the finger "
        "gesture: up reveals content lower in a list, while down reveals earlier content above. "
        "After each tool, the runtime will observe again. If the current observation already verifies "
        "the target page, finish. The observation may include last_action_feedback. If its effect is "
        "unchanged, do not repeat the same tool with identical arguments; change direction, parameters, "
        "or choose another safe tool. "
        "For finish, prefer a unique page-title resource_id when repeated text appears in ui_summary. "
        "Also include expected_foreground_app with app_id and activity when the observation provides "
        "stable values. If finish verification feedback reports TARGET_AMBIGUOUS, refine the selector "
        "instead of repeating it. "
        "Return {\"decision_type\":\"finish\",\"arguments\":{\"expected_foreground_app\":"
        "{\"app_id\":\"com.android.settings\"},\"expected_selector\":"
        "{\"strategy\":\"text\",\"value\":\"亮度\",\"match\":\"contains\",\"package\":\"com.android.settings\"}},"
        "\"reason\":\"...\",\"confidence\":0.8}. "
        "finish must include expected_selector; runtime will verify it and may reject your finish."
    )


def _goal_compiler_prompt() -> str:
    return (
        "You compile one mobile-device goal into a reviewable intent draft. "
        "Return only one JSON object with exactly execution_goal, assumptions, confidence, "
        "and optional acceptance. Do not output actions, coordinates, tool calls, adb, shell, "
        "secrets, or a fixed path. execution_goal must preserve the user's intent while making "
        "the desired application, destination, and final state explicit enough for a dynamic "
        "planner. assumptions is an array of short user-visible assumptions. confidence is 0..1. "
        "acceptance may contain foreground_app_id, foreground_activity, or expected_selector, "
        "but omit acceptance unless the final state can be expressed deterministically. Never "
        "invent an Activity or package id. App id alone is insufficient for a page-level goal. "
        "Selector fields are strategy, value, match, and package; strategy is text, resource_id, "
        "or content_description and match is exact or contains. The user will review this draft "
        "before execution. Example: {\"execution_goal\":\"打开系统设置，找到蓝牙入口，点击进入"
        "蓝牙设置页面，并确认已到达蓝牙页面\",\"assumptions\":[\"蓝牙指系统设置中的蓝牙页面\"],"
        "\"confidence\":0.9}."
    )


def _extract_decision_payload(response: dict[str, Any]) -> object:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise _invalid_model_output("模型响应缺少 choices", _response_diagnostics(response))
    first = choices[0]
    if not isinstance(first, dict):
        raise _invalid_model_output("模型响应 choice 格式无效", _response_diagnostics(response))
    message = first.get("message")
    if not isinstance(message, dict):
        raise _invalid_model_output("模型响应缺少 message", _response_diagnostics(response))
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise _invalid_model_output("模型响应缺少结构化 content", _response_diagnostics(response))
    payload = _parse_content_object(content)
    if isinstance(payload.get("decision"), dict):
        payload = payload["decision"]
    if not isinstance(payload, dict):
        raise _invalid_model_output(
            "模型响应 content 必须是 JSON object",
            _content_diagnostics(content),
        )
    return payload


def _parse_content_object(content: str) -> dict[str, Any]:
    candidate = _strip_json_markdown_fence(content.strip())
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise _invalid_model_output(
            "模型响应 content 不是 JSON object",
            _content_diagnostics(content),
        ) from error
    if not isinstance(payload, dict):
        raise _invalid_model_output(
            "模型响应 content 必须是 JSON object",
            _content_diagnostics(content),
        )
    return payload


def _strip_json_markdown_fence(content: str) -> str:
    if not content.startswith("```"):
        return content
    lines = content.splitlines()
    if len(lines) < 3 or not lines[-1].strip().startswith("```"):
        return content
    first_line = lines[0].strip().lower()
    if first_line not in {"```", "```json", "```javascript", "```js"}:
        return content
    return "\n".join(lines[1:-1]).strip()


def _invalid_model_output(
    message: str, details: dict[str, Any] | None = None
) -> MobileAgentError:
    return MobileAgentError(
        code="MODEL_OUTPUT_INVALID",
        category=ErrorCategory.VALIDATION,
        message=message,
        details={
            "response_id": f"modelresp_{uuid.uuid4().hex}",
            **(details or {}),
        },
    )


def _model_unavailable(
    failure_kind: str,
    *,
    retryable: bool,
    details: dict[str, Any] | None = None,
    suggested_action: str = "",
) -> MobileAgentError:
    """Build a classified provider error without exposing response bodies or secrets."""

    return MobileAgentError(
        code="MODEL_UNAVAILABLE",
        category=ErrorCategory.EXECUTION,
        message="模型 Provider 暂不可用",
        retryable=retryable,
        suggested_action=suggested_action,
        details={"failure_kind": failure_kind, **(details or {})},
    )


def _repair_feedback(error: MobileAgentError) -> dict[str, Any]:
    """Build bounded, secret-free feedback for one model output repair attempt."""

    allowed_detail_keys = (
        "tool_id",
        "argument_keys",
        "missing_argument_keys",
        "unknown_argument_keys",
        "selector_error",
        "selector_error_field",
        "selector_unknown_keys",
        "selector_keys",
    )
    safe_details: dict[str, Any] = {}
    for key in allowed_detail_keys:
        value = error.details.get(key)
        if isinstance(value, str):
            safe_details[key] = _safe_preview(value, limit=120)
        elif isinstance(value, list):
            safe_details[key] = [
                _safe_preview(item, limit=120)
                for item in value[:20]
                if isinstance(item, str)
            ]
    return {
        "type": "planner_output_repair",
        "code": "MODEL_OUTPUT_INVALID",
        "message": _safe_preview(error.message, limit=300),
        "details": safe_details,
        "instruction": (
            "Return one corrected JSON object that satisfies the declared Tool argument contract."
        ),
    }


def _response_diagnostics(response: dict[str, Any]) -> dict[str, Any]:
    details: dict[str, Any] = {
        "response_keys": sorted(str(key) for key in response.keys()),
    }
    choices = response.get("choices")
    if isinstance(choices, list):
        details["choices_count"] = len(choices)
        if choices and isinstance(choices[0], dict):
            details["first_choice_keys"] = sorted(str(key) for key in choices[0].keys())
            message = choices[0].get("message")
            if isinstance(message, dict):
                details["message_keys"] = sorted(str(key) for key in message.keys())
                content = message.get("content")
                if isinstance(content, str):
                    details.update(_content_diagnostics(content))
    return details


def _content_diagnostics(content: str) -> dict[str, Any]:
    return {
        "content_chars": len(content),
        "content_preview": _safe_preview(content),
    }


def _summarize_payload(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"type": type(payload).__name__}
    summary: dict[str, Any] = {
        "keys": sorted(str(key) for key in payload.keys()),
    }
    decision_type = payload.get("decision_type")
    if isinstance(decision_type, str):
        summary["decision_type"] = _safe_preview(decision_type, limit=80)
    skill_id = payload.get("skill_id")
    if isinstance(skill_id, str):
        summary["skill_id"] = _safe_preview(skill_id, limit=120)
    tool_id = payload.get("tool_id")
    if isinstance(tool_id, str):
        summary["tool_id"] = _safe_preview(tool_id, limit=120)
    arguments = payload.get("arguments")
    if isinstance(arguments, dict):
        summary["argument_keys"] = sorted(str(key) for key in arguments.keys())
        target = arguments.get("target_selector")
        if isinstance(target, dict):
            summary["target_selector"] = _selector_summary(target)
        expected = arguments.get("expected_selector")
        if isinstance(expected, dict):
            summary["expected_selector"] = _selector_summary(expected)
    return summary


def _selector_summary(selector: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"keys": sorted(str(key) for key in selector.keys())}
    for key in ("strategy", "match"):
        value = selector.get(key)
        if isinstance(value, str):
            summary[key] = _safe_preview(value, limit=120)
    return summary


def _safe_preview(value: str, limit: int = 500) -> str:
    compact = " ".join(value.split())
    redacted = re.sub(
        r"(?i)(api[_-]?key|authorization|bearer|token|secret|password|passwd|验证码|密码)"
        r"\s*[:=]\s*['\"]?[^,'\"\s}]+",
        r"\1=<redacted>",
        compact,
    )
    if len(redacted) <= limit:
        return redacted
    return redacted[:limit] + "…"
