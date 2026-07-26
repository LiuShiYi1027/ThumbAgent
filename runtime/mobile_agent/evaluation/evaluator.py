"""Evaluate live Agent outcomes without replaying a fixed action path."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.evaluation.acceptance import AgentGoalAcceptance
from mobile_agent.ui.model import MatchMode, SelectorStrategy, UiSelector


@dataclass(frozen=True, slots=True)
class AgentEvaluationScenario:
    """Versioned goal, constraints, and independent acceptance criteria."""

    scenario_id: str
    goal: str
    foreground_app_id: str | None
    foreground_activity: str | None
    expected_selector: UiSelector | None
    forbidden_tools: tuple[str, ...]
    max_rounds: int
    schema_version: str = "1.0.0"

    @classmethod
    def from_dict(cls, payload: object) -> "AgentEvaluationScenario":
        """Validate an external scenario payload before evaluating a task."""

        if not isinstance(payload, dict):
            raise _invalid("评测场景必须是 JSON object")
        allowed = {
            "schema_version",
            "scenario_id",
            "goal",
            "acceptance",
            "forbidden_tools",
            "max_rounds",
        }
        unknown = sorted(str(key) for key in set(payload) - allowed)
        if unknown:
            raise _invalid("评测场景包含未知字段", {"unknown_fields": unknown})
        if payload.get("schema_version") != "1.0.0":
            raise _invalid("评测场景 schema_version 无效")
        scenario_id = payload.get("scenario_id")
        if not isinstance(scenario_id, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9._-]{2,119}", scenario_id
        ):
            raise _invalid("评测场景 scenario_id 无效")
        goal = payload.get("goal")
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 500:
            raise _invalid("评测场景 goal 无效")
        acceptance = AgentGoalAcceptance.from_dict(payload.get("acceptance"))
        forbidden_tools = payload.get("forbidden_tools")
        if (
            not isinstance(forbidden_tools, list)
            or len(forbidden_tools) > 50
            or any(
                not isinstance(item, str)
                or not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", item)
                for item in forbidden_tools
            )
            or len(set(forbidden_tools)) != len(forbidden_tools)
        ):
            raise _invalid("评测场景 forbidden_tools 无效")
        max_rounds = payload.get("max_rounds")
        if (
            not isinstance(max_rounds, int)
            or isinstance(max_rounds, bool)
            or max_rounds < 1
            or max_rounds > 50
        ):
            raise _invalid("评测场景 max_rounds 无效")
        return cls(
            scenario_id=scenario_id,
            goal=goal.strip(),
            foreground_app_id=acceptance.foreground_app_id,
            foreground_activity=acceptance.foreground_activity,
            expected_selector=acceptance.expected_selector,
            forbidden_tools=tuple(forbidden_tools),
            max_rounds=max_rounds,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the normalized public scenario representation."""

        acceptance = AgentGoalAcceptance(
            self.foreground_app_id,
            self.foreground_activity,
            self.expected_selector,
        )
        return {
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "goal": self.goal,
            "acceptance": acceptance.to_dict(),
            "forbidden_tools": list(self.forbidden_tools),
            "max_rounds": self.max_rounds,
        }


class AgentEvaluator:
    """Score a completed live task by outcome and constraints, never by path equality."""

    def evaluate(
        self,
        task: dict[str, Any],
        scenario_payload: object,
    ) -> dict[str, Any]:
        """Return a versioned evaluation result for a persisted Agent task."""

        scenario = AgentEvaluationScenario.from_dict(scenario_payload)
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not re.fullmatch(r"task_[a-f0-9]{32}", task_id):
            raise _invalid("评测输入缺少有效 task_id")
        if task.get("task_type") != "agent.run":
            raise _invalid("只支持评测 agent.run 任务")

        steps = task.get("steps")
        if not isinstance(steps, list):
            raise _invalid("评测输入 steps 无效")
        metrics = _metrics(task, steps)
        failures: list[str] = []
        if task.get("goal") != scenario.goal:
            failures.append("goal_mismatch")
        if task.get("status") != "succeeded":
            failures.append("task_failed")
        if metrics["round_count"] > scenario.max_rounds:
            failures.append("round_budget_exceeded")
        if scenario.foreground_app_id is not None and (
            _final_foreground_app_id(task) != scenario.foreground_app_id
        ):
            failures.append("foreground_app_mismatch")
        if scenario.foreground_activity is not None and (
            _final_foreground_activity(task) != scenario.foreground_activity
        ):
            failures.append("foreground_activity_mismatch")
        if scenario.expected_selector is not None and not _task_selector_met(
            task, scenario.expected_selector
        ):
            failures.append("expected_selector_not_met")
        if set(metrics["used_tools"]) & set(scenario.forbidden_tools):
            failures.append("forbidden_tool_used")
        if metrics["policy_violation_count"] > 0:
            failures.append("policy_violation")

        return {
            "schema_version": "1.0.0",
            "evaluation_id": f"evaluation_{uuid.uuid4().hex}",
            "scenario_id": scenario.scenario_id,
            "task_id": task_id,
            "passed": not failures,
            "failure_reasons": failures,
            "metrics": metrics,
        }


def _metrics(task: dict[str, Any], steps: list[object]) -> dict[str, Any]:
    round_count = 0
    tool_call_count = 0
    changed_action_count = 0
    unchanged_action_count = 0
    model_repair_count = 0
    policy_violation_count = 0
    provider_latency_ms = 0
    provider_attempt_count = 0
    provider_retry_count = 0
    no_progress_count = 0
    model_unavailable_count = 0
    used_tools: list[str] = []
    for raw_step in steps:
        if not isinstance(raw_step, dict):
            continue
        if raw_step.get("kind") == "agent_round":
            round_count += 1
        error = raw_step.get("error")
        if isinstance(error, dict):
            error_code = error.get("code")
            if error_code == "ACTION_REJECTED_BY_POLICY":
                policy_violation_count += 1
            elif error_code == "NO_PROGRESS":
                no_progress_count += 1
            elif error_code == "MODEL_UNAVAILABLE":
                model_unavailable_count += 1
        result = raw_step.get("result")
        if not isinstance(result, dict):
            continue
        decision = result.get("decision")
        if isinstance(decision, dict):
            repair_count = decision.get("repair_count")
            if isinstance(repair_count, int) and not isinstance(repair_count, bool):
                model_repair_count += max(repair_count, 0)
            provider_latency = decision.get("provider_latency_ms")
            if isinstance(provider_latency, int) and not isinstance(provider_latency, bool):
                provider_latency_ms += max(provider_latency, 0)
            attempt_count = decision.get("provider_attempt_count")
            if isinstance(attempt_count, int) and not isinstance(attempt_count, bool):
                provider_attempt_count += max(attempt_count, 0)
            retry_count = decision.get("provider_retry_count")
            if isinstance(retry_count, int) and not isinstance(retry_count, bool):
                provider_retry_count += max(retry_count, 0)
            if decision.get("decision_type") == "run_tool":
                tool_call_count += 1
                tool_id = decision.get("tool_id")
                if isinstance(tool_id, str) and tool_id and tool_id not in used_tools:
                    used_tools.append(tool_id)
        feedback = result.get("action_feedback")
        if isinstance(feedback, dict):
            if feedback.get("effect") == "changed":
                changed_action_count += 1
            elif feedback.get("effect") == "unchanged":
                unchanged_action_count += 1
    terminal_error_code = _terminal_error_code(task)
    if terminal_error_code == "NO_PROGRESS" and no_progress_count == 0:
        no_progress_count = 1
    if terminal_error_code == "MODEL_UNAVAILABLE" and model_unavailable_count == 0:
        model_unavailable_count = 1
    return {
        "round_count": round_count,
        "tool_call_count": tool_call_count,
        "changed_action_count": changed_action_count,
        "unchanged_action_count": unchanged_action_count,
        "model_repair_count": model_repair_count,
        "policy_violation_count": policy_violation_count,
        "provider_latency_ms": provider_latency_ms,
        "provider_attempt_count": provider_attempt_count,
        "provider_retry_count": provider_retry_count,
        "no_progress_count": no_progress_count,
        "model_unavailable_count": model_unavailable_count,
        "terminal_error_code": terminal_error_code,
        "duration_ms": _duration_ms(task),
        "used_tools": used_tools,
    }


def _terminal_error_code(task: dict[str, Any]) -> str:
    error = task.get("error")
    if not isinstance(error, dict):
        return ""
    code = error.get("code")
    return code if isinstance(code, str) and len(code) <= 120 else ""


def _duration_ms(task: dict[str, Any]) -> int:
    started_at = task.get("started_at")
    completed_at = task.get("completed_at")
    if not isinstance(started_at, str) or not isinstance(completed_at, str):
        return 0
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, int((completed - started).total_seconds() * 1000))


def _final_foreground_app_id(task: dict[str, Any]) -> str:
    summary = task.get("evidence_summary")
    if not isinstance(summary, dict):
        return ""
    foreground = summary.get("final_foreground_app")
    if not isinstance(foreground, dict):
        return ""
    app_id = foreground.get("app_id")
    return app_id if isinstance(app_id, str) else ""


def _final_foreground_activity(task: dict[str, Any]) -> str:
    summary = task.get("evidence_summary")
    if not isinstance(summary, dict):
        return ""
    foreground = summary.get("final_foreground_app")
    if not isinstance(foreground, dict):
        return ""
    activity = foreground.get("activity")
    return activity if isinstance(activity, str) else ""


def _verified_node(task: dict[str, Any]) -> dict[str, Any] | None:
    summary = task.get("evidence_summary")
    if isinstance(summary, dict) and isinstance(summary.get("verified_node"), dict):
        return summary["verified_node"]
    return None


def _task_selector_met(task: dict[str, Any], selector: UiSelector) -> bool:
    observation = _final_observation(task)
    foreground_app_id = _final_foreground_app_id(task)
    if observation is not None:
        foreground = observation.get("foreground_app")
        if isinstance(foreground, dict) and isinstance(foreground.get("app_id"), str):
            foreground_app_id = foreground["app_id"]
        ui_summary = observation.get("ui_summary")
        if isinstance(ui_summary, list) and any(
            _selector_met(item, selector, foreground_app_id)
            for item in ui_summary
            if isinstance(item, dict)
        ):
            return True
    return _selector_met(_verified_node(task), selector, foreground_app_id)


def _final_observation(task: dict[str, Any]) -> dict[str, Any] | None:
    steps = task.get("steps")
    if not isinstance(steps, list):
        return None
    for step in reversed(steps):
        if not isinstance(step, dict):
            continue
        result = step.get("result")
        if not isinstance(result, dict):
            continue
        observation = result.get("observation")
        if isinstance(observation, dict):
            return observation
    return None


def _selector_met(
    node: dict[str, Any] | None, selector: UiSelector, foreground_app_id: str = ""
) -> bool:
    if node is None:
        return False
    field_name = {
        SelectorStrategy.TEXT: "text",
        SelectorStrategy.RESOURCE_ID: "resource_id",
        SelectorStrategy.CONTENT_DESCRIPTION: "content_description",
    }[selector.strategy]
    actual = node.get(field_name)
    if not isinstance(actual, str):
        return False
    if selector.match is MatchMode.EXACT and actual != selector.value:
        return False
    if selector.match is MatchMode.CONTAINS and selector.value not in actual:
        return False
    if selector.package is not None:
        node_package = node.get("package")
        if isinstance(node_package, str):
            if node_package != selector.package:
                return False
        elif foreground_app_id != selector.package:
            return False
    if selector.clickable is not None and node.get("clickable") is not selector.clickable:
        return False
    if selector.enabled and node.get("enabled") is not True:
        return False
    return True


def _invalid(message: str, details: dict[str, Any] | None = None) -> MobileAgentError:
    return MobileAgentError(
        code="INVALID_ARGUMENT",
        category=ErrorCategory.VALIDATION,
        message=message,
        details=details or {},
    )
