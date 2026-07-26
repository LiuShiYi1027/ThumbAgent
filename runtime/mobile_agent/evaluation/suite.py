"""Versioned live evaluation suites and path-independent aggregate metrics."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.evaluation.evaluator import AgentEvaluationScenario


@dataclass(frozen=True, slots=True)
class AgentEvaluationSuite:
    """A bounded set of versioned scenarios and required repetitions."""

    suite_id: str
    runs_per_scenario: int
    scenarios: tuple[AgentEvaluationScenario, ...]
    schema_version: str = "1.0.0"

    @classmethod
    def from_dict(cls, payload: object) -> "AgentEvaluationSuite":
        """Validate a suite definition without accessing devices or models."""

        if not isinstance(payload, dict):
            raise _invalid("评测 Suite 必须是 JSON object")
        allowed = {"schema_version", "suite_id", "runs_per_scenario", "scenarios"}
        unknown = sorted(str(key) for key in set(payload) - allowed)
        if unknown:
            raise _invalid("评测 Suite 包含未知字段", {"unknown_fields": unknown})
        if payload.get("schema_version") != "1.0.0":
            raise _invalid("评测 Suite schema_version 无效")
        suite_id = payload.get("suite_id")
        if not isinstance(suite_id, str) or re.fullmatch(
            r"[a-z0-9][a-z0-9._-]{2,119}", suite_id
        ) is None:
            raise _invalid("评测 Suite suite_id 无效")
        runs = payload.get("runs_per_scenario")
        if not isinstance(runs, int) or isinstance(runs, bool) or runs < 1 or runs > 5:
            raise _invalid("评测 Suite runs_per_scenario 无效")
        raw_scenarios = payload.get("scenarios")
        if not isinstance(raw_scenarios, list) or not 1 <= len(raw_scenarios) <= 20:
            raise _invalid("评测 Suite scenarios 无效")
        scenarios = tuple(AgentEvaluationScenario.from_dict(item) for item in raw_scenarios)
        scenario_ids = [scenario.scenario_id for scenario in scenarios]
        if len(set(scenario_ids)) != len(scenario_ids):
            raise _invalid("评测 Suite scenario_id 必须唯一")
        return cls(suite_id, runs, scenarios)

    def to_dict(self) -> dict[str, Any]:
        """Return the normalized public Suite representation."""

        return {
            "schema_version": self.schema_version,
            "suite_id": self.suite_id,
            "runs_per_scenario": self.runs_per_scenario,
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
        }


class AgentEvaluationAggregator:
    """Aggregate completed evaluation results without replaying device actions."""

    def aggregate(
        self, suite_payload: object, evaluations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Validate complete Suite coverage and return deterministic aggregate metrics."""

        suite = AgentEvaluationSuite.from_dict(suite_payload)
        expected = len(suite.scenarios) * suite.runs_per_scenario
        if len(evaluations) != expected:
            raise _invalid(
                "评测结果数量与 Suite 不一致",
                {"expected_run_count": expected, "evaluated_run_count": len(evaluations)},
            )
        scenario_ids = {scenario.scenario_id for scenario in suite.scenarios}
        task_ids: set[str] = set()
        grouped: dict[str, list[dict[str, Any]]] = {
            scenario.scenario_id: [] for scenario in suite.scenarios
        }
        for result in evaluations:
            if not isinstance(result, dict):
                raise _invalid("评测结果必须是 JSON object")
            scenario_id = result.get("scenario_id")
            task_id = result.get("task_id")
            if scenario_id not in scenario_ids:
                raise _invalid("评测结果包含未知场景")
            if not isinstance(task_id, str) or re.fullmatch(r"task_[a-f0-9]{32}", task_id) is None:
                raise _invalid("评测结果 task_id 无效")
            if task_id in task_ids:
                raise _invalid("评测结果 task_id 重复")
            if not isinstance(result.get("passed"), bool):
                raise _invalid("评测结果 passed 无效")
            if not isinstance(result.get("metrics"), dict):
                raise _invalid("评测结果 metrics 无效")
            task_ids.add(task_id)
            grouped[str(scenario_id)].append(result)
        if any(len(items) != suite.runs_per_scenario for items in grouped.values()):
            raise _invalid("评测结果未完整覆盖每个场景")

        passed = sum(result["passed"] is True for result in evaluations)
        durations = [_metric(result, "duration_ms") for result in evaluations]
        scenario_results = []
        for scenario in suite.scenarios:
            items = grouped[scenario.scenario_id]
            scenario_passed = sum(item["passed"] is True for item in items)
            scenario_results.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "run_count": len(items),
                    "passed_count": scenario_passed,
                    "pass_rate": _rate(scenario_passed, len(items)),
                }
            )
        return {
            "schema_version": "1.0.0",
            "suite_id": suite.suite_id,
            "expected_run_count": expected,
            "evaluated_run_count": len(evaluations),
            "passed_run_count": passed,
            "pass_rate": _rate(passed, len(evaluations)),
            "scenario_results": scenario_results,
            "metrics": {
                "average_round_count": _average(evaluations, "round_count"),
                "average_tool_call_count": _average(evaluations, "tool_call_count"),
                "average_duration_ms": round(sum(durations) / len(durations)),
                "p50_duration_ms": _percentile(durations, 0.50),
                "p95_duration_ms": _percentile(durations, 0.95),
                "total_provider_latency_ms": _total(evaluations, "provider_latency_ms"),
                "total_provider_attempt_count": _total(evaluations, "provider_attempt_count"),
                "total_provider_retry_count": _total(evaluations, "provider_retry_count"),
                "total_no_progress_count": _total(evaluations, "no_progress_count"),
                "total_model_unavailable_count": _total(evaluations, "model_unavailable_count"),
                "total_policy_violation_count": _total(evaluations, "policy_violation_count"),
            },
            "failure_reasons": _counts(
                reason
                for result in evaluations
                for reason in _string_list(result.get("failure_reasons"))
            ),
            "terminal_errors": _counts(
                code
                for result in evaluations
                for code in [_terminal_error(result)]
                if code
            ),
        }


def _metric(result: dict[str, Any], key: str) -> int:
    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        return 0
    value = metrics.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _total(evaluations: list[dict[str, Any]], key: str) -> int:
    return sum(_metric(result, key) for result in evaluations)


def _average(evaluations: list[dict[str, Any]], key: str) -> float:
    return round(_total(evaluations, key) / len(evaluations), 2)


def _rate(count: int, total: int) -> float:
    return round(count / total, 4)


def _percentile(values: list[int], quantile: float) -> int:
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _terminal_error(result: dict[str, Any]) -> str:
    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        return ""
    value = metrics.get("terminal_error_code")
    return value if isinstance(value, str) else ""


def _counts(values: Any) -> list[dict[str, Any]]:
    counts = Counter(values)
    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _invalid(message: str, details: dict[str, Any] | None = None) -> MobileAgentError:
    return MobileAgentError(
        code="INVALID_ARGUMENT",
        category=ErrorCategory.VALIDATION,
        message=message,
        details=details or {},
    )
