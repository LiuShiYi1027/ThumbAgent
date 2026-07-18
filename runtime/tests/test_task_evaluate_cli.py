from __future__ import annotations

import unittest

from mobile_agent.cli.task_evaluate import render_evaluation_result


class TaskEvaluateCliTests(unittest.TestCase):
    def test_renders_path_independent_evaluation_metrics(self) -> None:
        report = render_evaluation_result(
            {
                "scenario_id": "settings.display.live.v1",
                "task_id": "task_" + "a" * 32,
                "passed": False,
                "failure_reasons": ["forbidden_tool_used"],
                "metrics": {
                    "round_count": 4,
                    "tool_call_count": 3,
                    "changed_action_count": 2,
                    "unchanged_action_count": 1,
                    "model_repair_count": 1,
                    "duration_ms": 1200,
                    "used_tools": ["app.launch", "input.swipe"],
                },
            }
        )

        self.assertIn("Result:   FAILED", report)
        self.assertIn("Rounds:   4", report)
        self.assertIn("app.launch, input.swipe", report)
        self.assertIn("forbidden_tool_used", report)
