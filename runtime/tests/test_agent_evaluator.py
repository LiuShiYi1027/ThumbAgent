from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evaluation import AgentEvaluator, AgentGoalAcceptance
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService


ROOT = Path(__file__).resolve().parents[2]


class AgentEvaluatorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.runtime = RuntimeService(
            FakeDeviceAdapter(), ArtifactStore(Path(self.directory.name))
        )

    async def test_live_task_passes_independent_goal_acceptance(self) -> None:
        task = await self.runtime.run_agent_task(
            "fake:android-001", "open display settings", confirmed=True
        )

        result = AgentEvaluator().evaluate(
            task,
            scenario(
                foreground_app_id="com.android.settings",
                expected_selector={
                    "strategy": "text",
                    "value": "Display settings",
                    "match": "contains",
                    "package": "com.android.settings",
                },
            ),
        )

        self.assertTrue(result["passed"])
        self.assertEqual([], result["failure_reasons"])
        self.assertEqual(3, result["metrics"]["round_count"])
        self.assertEqual(2, result["metrics"]["tool_call_count"])
        self.assertEqual(["app.launch", "input.tap_element"], result["metrics"]["used_tools"])
        self.assertEqual(0, result["metrics"]["provider_latency_ms"])
        self.assertEqual(0, result["metrics"]["provider_attempt_count"])
        self.assertEqual(0, result["metrics"]["provider_retry_count"])
        self.assertEqual(0, result["metrics"]["no_progress_count"])
        self.assertEqual(0, result["metrics"]["model_unavailable_count"])
        self.assertEqual("", result["metrics"]["terminal_error_code"])

    async def test_evaluation_rejects_wrong_outcome_forbidden_tool_and_budget(self) -> None:
        task = await self.runtime.run_agent_task(
            "fake:android-001", "open display settings", confirmed=True
        )
        payload = scenario(
            foreground_app_id="com.example.jd",
            expected_selector={
                "strategy": "text",
                "value": "商品详情",
                "match": "contains",
            },
        )
        payload["forbidden_tools"] = ["input.tap_element"]
        payload["max_rounds"] = 1

        result = AgentEvaluator().evaluate(task, payload)

        self.assertFalse(result["passed"])
        self.assertEqual(
            [
                "round_budget_exceeded",
                "foreground_app_mismatch",
                "expected_selector_not_met",
                "forbidden_tool_used",
            ],
            result["failure_reasons"],
        )

    async def test_evaluation_checks_foreground_activity(self) -> None:
        task = await self.runtime.run_agent_task(
            "fake:android-001", "open display settings", confirmed=True
        )

        result = AgentEvaluator().evaluate(
            task,
            scenario(
                foreground_app_id="com.android.settings",
                foreground_activity=".WrongActivity",
            ),
        )

        self.assertFalse(result["passed"])
        self.assertIn("foreground_activity_mismatch", result["failure_reasons"])

    async def test_evaluation_matches_final_observation_not_planner_verified_node(self) -> None:
        task = await self.runtime.run_agent_task(
            "fake:android-001", "open display settings", confirmed=True
        )
        task["evidence_summary"]["verified_node"] = {
            "text": "unrelated planner node",
            "resource_id": "other",
            "package": "com.android.settings",
            "clickable": False,
            "enabled": True,
        }

        result = AgentEvaluator().evaluate(
            task,
            scenario(
                foreground_app_id="com.android.settings",
                expected_selector={
                    "strategy": "text",
                    "value": "Display settings",
                    "match": "exact",
                    "package": "com.android.settings",
                },
            ),
        )

        self.assertTrue(result["passed"])

    def test_goal_acceptance_rejects_empty_and_unknown_fields(self) -> None:
        for payload in ({}, {"unexpected": True}):
            with self.subTest(payload=payload):
                with self.assertRaises(MobileAgentError) as raised:
                    AgentGoalAcceptance.from_dict(payload)
                self.assertEqual("INVALID_ARGUMENT", raised.exception.code)

    async def test_runtime_evaluates_stored_live_task(self) -> None:
        task = await self.runtime.run_agent_task(
            "fake:android-001", "open display settings", confirmed=True
        )

        status, payload = self.runtime.evaluate_agent_task_sync(
            task["task_id"], scenario(foreground_app_id="com.android.settings")
        )

        self.assertEqual(200, status.value)
        self.assertTrue(payload["evaluation"]["passed"])

    def test_evaluation_contracts_are_versioned(self) -> None:
        scenario_schema = json.loads(
            (ROOT / "contracts/schemas/agent-evaluation-scenario.schema.json").read_text(
                encoding="utf-8"
            )
        )
        result_schema = json.loads(
            (ROOT / "contracts/schemas/agent-evaluation-result.schema.json").read_text(
                encoding="utf-8"
            )
        )
        suite_schema = json.loads(
            (ROOT / "contracts/schemas/agent-evaluation-suite.schema.json").read_text(
                encoding="utf-8"
            )
        )
        summary_schema = json.loads(
            (ROOT / "contracts/schemas/agent-evaluation-summary.schema.json").read_text(
                encoding="utf-8"
            )
        )
        acceptance_schema = json.loads(
            (ROOT / "contracts/schemas/agent-goal-acceptance.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            "https://mobile-agent.local/schemas/agent-evaluation-scenario/v1.json",
            scenario_schema["$id"],
        )
        self.assertEqual(
            "https://mobile-agent.local/schemas/agent-evaluation-result/v1.json",
            result_schema["$id"],
        )
        self.assertEqual(
            "https://mobile-agent.local/schemas/agent-goal-acceptance/v1.json",
            acceptance_schema["$id"],
        )
        self.assertEqual(
            "https://mobile-agent.local/schemas/agent-evaluation-suite/v1.json",
            suite_schema["$id"],
        )
        self.assertEqual(
            "https://mobile-agent.local/schemas/agent-evaluation-summary/v1.json",
            summary_schema["$id"],
        )
        self.assertEqual(
            "agent-goal-acceptance.schema.json",
            scenario_schema["properties"]["acceptance"]["$ref"],
        )
        self.assertIn("forbidden_tool_used", result_schema["properties"]["failure_reasons"]["items"]["enum"])
        self.assertIn(
            "provider_latency_ms",
            result_schema["properties"]["metrics"]["properties"],
        )


def scenario(
    *,
    foreground_app_id: str | None = None,
    foreground_activity: str | None = None,
    expected_selector: dict[str, object] | None = None,
) -> dict[str, object]:
    acceptance: dict[str, object] = {}
    if foreground_app_id is not None:
        acceptance["foreground_app_id"] = foreground_app_id
    if foreground_activity is not None:
        acceptance["foreground_activity"] = foreground_activity
    if expected_selector is not None:
        acceptance["expected_selector"] = expected_selector
    return {
        "schema_version": "1.0.0",
        "scenario_id": "settings.display.live.v1",
        "goal": "open display settings",
        "acceptance": acceptance,
        "forbidden_tools": [],
        "max_rounds": 6,
    }
