from __future__ import annotations

import unittest
from urllib.error import URLError

from mobile_agent.cli.evaluation_suite_report import (
    _friendly_error,
    _parse_assignments,
    _validate_coverage,
    render_evaluation_summary,
)
from mobile_agent.evaluation import AgentEvaluationSuite


class EvaluationSuiteCliTests(unittest.TestCase):
    def test_renders_success_rate_latency_and_reliability(self) -> None:
        report = render_evaluation_summary(
            {
                "suite_id": "android.settings.smoke.v1",
                "expected_run_count": 2,
                "evaluated_run_count": 2,
                "passed_run_count": 1,
                "pass_rate": 0.5,
                "scenario_results": [
                    {
                        "scenario_id": "settings.bluetooth.v1",
                        "run_count": 1,
                        "passed_count": 1,
                        "pass_rate": 1.0,
                    }
                ],
                "metrics": {
                    "average_round_count": 2.5,
                    "average_tool_call_count": 1.5,
                    "average_duration_ms": 500,
                    "p50_duration_ms": 100,
                    "p95_duration_ms": 900,
                    "total_provider_latency_ms": 600,
                    "total_provider_attempt_count": 3,
                    "total_provider_retry_count": 1,
                    "total_no_progress_count": 1,
                    "total_model_unavailable_count": 1,
                    "total_policy_violation_count": 0,
                },
                "failure_reasons": [{"name": "task_failed", "count": 1}],
                "terminal_errors": [{"name": "MODEL_UNAVAILABLE", "count": 1}],
            }
        )

        self.assertIn("Pass rate:   50.0%", report)
        self.assertIn("p95=900 ms", report)
        self.assertIn("retries=1", report)
        self.assertIn("no_progress=1", report)
        self.assertIn("MODEL_UNAVAILABLE: 1", report)

    def test_assignment_coverage_is_exact_and_unique(self) -> None:
        suite = AgentEvaluationSuite.from_dict(suite_payload())
        assignments = _parse_assignments(
            [
                "settings.bluetooth.v1=task_" + "a" * 32,
                "settings.display.v1=task_" + "b" * 32,
            ]
        )

        _validate_coverage(suite, assignments)

        with self.assertRaises(ValueError):
            _validate_coverage(suite, assignments[:1])

        invalid = list(assignments)
        invalid[0] = (invalid[0][0], "task_1234")
        with self.assertRaisesRegex(ValueError, "invalid task_id"):
            _validate_coverage(suite, invalid)

    def test_connection_failure_has_actionable_runtime_message(self) -> None:
        message = _friendly_error(URLError(ConnectionRefusedError(61, "refused")))

        self.assertIn("Runtime is not reachable", message)
        self.assertIn("run-mcp-preview.zsh", message)


def suite_payload() -> dict[str, object]:
    def scenario(scenario_id: str, title: str) -> dict[str, object]:
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
                },
            },
            "forbidden_tools": [],
            "max_rounds": 6,
        }

    return {
        "schema_version": "1.0.0",
        "suite_id": "android.settings.smoke.v1",
        "runs_per_scenario": 1,
        "scenarios": [
            scenario("settings.bluetooth.v1", "蓝牙"),
            scenario("settings.display.v1", "显示和亮度"),
        ],
    }
