from __future__ import annotations

import unittest

from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evaluation import AgentEvaluationAggregator, AgentEvaluationSuite


class AgentEvaluationSuiteTests(unittest.TestCase):
    def test_suite_validates_unique_scenarios_and_round_trips(self) -> None:
        payload = suite_payload()

        suite = AgentEvaluationSuite.from_dict(payload)

        self.assertEqual("android.settings.smoke.v1", suite.suite_id)
        normalized = suite.to_dict()
        self.assertEqual("android.settings.smoke.v1", normalized["suite_id"])
        self.assertEqual(2, len(normalized["scenarios"]))
        self.assertEqual(suite, AgentEvaluationSuite.from_dict(normalized))

        duplicate = suite_payload()
        duplicate["scenarios"] = [scenario("settings.bluetooth.v1"), scenario("settings.bluetooth.v1")]
        with self.assertRaises(MobileAgentError) as raised:
            AgentEvaluationSuite.from_dict(duplicate)
        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)

    def test_aggregates_complete_path_independent_results(self) -> None:
        results = [
            evaluation(
                "settings.bluetooth.v1",
                "a",
                passed=True,
                duration_ms=100,
                provider_latency_ms=60,
                provider_attempt_count=1,
            ),
            evaluation(
                "settings.display.v1",
                "b",
                passed=False,
                duration_ms=900,
                provider_latency_ms=700,
                provider_attempt_count=2,
                provider_retry_count=1,
                no_progress_count=1,
                model_unavailable_count=1,
                terminal_error_code="MODEL_UNAVAILABLE",
                failure_reasons=["task_failed"],
            ),
        ]

        summary = AgentEvaluationAggregator().aggregate(suite_payload(), results)

        self.assertEqual(0.5, summary["pass_rate"])
        self.assertEqual(100, summary["metrics"]["p50_duration_ms"])
        self.assertEqual(900, summary["metrics"]["p95_duration_ms"])
        self.assertEqual(760, summary["metrics"]["total_provider_latency_ms"])
        self.assertEqual(1, summary["metrics"]["total_provider_retry_count"])
        self.assertEqual([{"name": "task_failed", "count": 1}], summary["failure_reasons"])
        self.assertEqual(
            [{"name": "MODEL_UNAVAILABLE", "count": 1}], summary["terminal_errors"]
        )

    def test_aggregator_rejects_missing_unknown_and_duplicate_tasks(self) -> None:
        aggregator = AgentEvaluationAggregator()
        first = evaluation("settings.bluetooth.v1", "a")
        second = evaluation("settings.display.v1", "b")

        invalid_sets = (
            [first],
            [first, {**second, "scenario_id": "unknown.scenario"}],
            [first, {**second, "task_id": first["task_id"]}],
        )
        for results in invalid_sets:
            with self.subTest(results=results):
                with self.assertRaises(MobileAgentError) as raised:
                    aggregator.aggregate(suite_payload(), results)
                self.assertEqual("INVALID_ARGUMENT", raised.exception.code)


def suite_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "suite_id": "android.settings.smoke.v1",
        "runs_per_scenario": 1,
        "scenarios": [scenario("settings.bluetooth.v1"), scenario("settings.display.v1")],
    }


def scenario(scenario_id: str) -> dict[str, object]:
    title = "蓝牙" if "bluetooth" in scenario_id else "显示和亮度"
    return {
        "schema_version": "1.0.0",
        "scenario_id": scenario_id,
        "goal": f"进入{title}设置页面",
        "acceptance": {
            "foreground_app_id": "com.android.settings",
            "expected_selector": {
                "strategy": "text",
                "value": title,
                "match": "exact",
                "package": "com.android.settings",
            },
        },
        "forbidden_tools": [],
        "max_rounds": 6,
    }


def evaluation(
    scenario_id: str,
    task_suffix: str,
    *,
    passed: bool = True,
    duration_ms: int = 100,
    provider_latency_ms: int = 0,
    provider_attempt_count: int = 0,
    provider_retry_count: int = 0,
    no_progress_count: int = 0,
    model_unavailable_count: int = 0,
    terminal_error_code: str = "",
    failure_reasons: list[str] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "evaluation_id": "evaluation_" + task_suffix * 32,
        "scenario_id": scenario_id,
        "task_id": "task_" + task_suffix * 32,
        "passed": passed,
        "failure_reasons": failure_reasons or [],
        "metrics": {
            "round_count": 2,
            "tool_call_count": 1,
            "duration_ms": duration_ms,
            "provider_latency_ms": provider_latency_ms,
            "provider_attempt_count": provider_attempt_count,
            "provider_retry_count": provider_retry_count,
            "no_progress_count": no_progress_count,
            "model_unavailable_count": model_unavailable_count,
            "policy_violation_count": 0,
            "terminal_error_code": terminal_error_code,
        },
    }
