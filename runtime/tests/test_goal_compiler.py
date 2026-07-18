from __future__ import annotations

import json
import tempfile
import unittest
import uuid
from pathlib import Path

from mobile_agent.agent import AgentDecision, AgentDecisionType, AgentObservationSummary
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.goals import AgentGoalSpec, PassThroughGoalCompiler
from mobile_agent.runtime import RuntimeService


class GoalCompilerTests(unittest.TestCase):
    def test_goal_spec_contract_is_versioned_and_task_run_references_it(self) -> None:
        root = Path(__file__).parents[2] / "contracts" / "schemas"
        goal_schema = json.loads((root / "agent-goal-spec.schema.json").read_text())
        task_schema = json.loads((root / "task-run.schema.json").read_text())

        self.assertEqual(
            "https://mobile-agent.local/schemas/agent-goal-spec/v1.json",
            goal_schema["$id"],
        )
        self.assertEqual(
            "agent-goal-spec.schema.json",
            task_schema["properties"]["goal_spec"]["$ref"],
        )

    def test_goal_spec_rejects_unknown_invalid_confidence_and_empty_acceptance(self) -> None:
        base = goal_spec_payload()
        invalid_payloads = [
            {**base, "unknown": True},
            {**base, "confidence": 1.1},
            {**base, "acceptance": {}},
            {**base, "confirmation_required": False},
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(MobileAgentError) as raised:
                    AgentGoalSpec.from_dict(payload)
                self.assertEqual("INVALID_ARGUMENT", raised.exception.code)

    def test_passthrough_compiler_preserves_goal_without_confirmation(self) -> None:
        spec = PassThroughGoalCompiler().compile("  进入蓝牙设置页面  ")

        self.assertEqual("进入蓝牙设置页面", spec.source_goal)
        self.assertEqual(spec.source_goal, spec.execution_goal)
        self.assertFalse(spec.confirmation_required)

    def test_unconfirmed_model_goal_spec_is_rejected_before_device_action(self) -> None:
        adapter = FakeDeviceAdapter()
        with tempfile.TemporaryDirectory() as directory:
            runtime = RuntimeService(adapter, ArtifactStore(Path(directory)))
            status, payload = runtime.run_agent_task_sync(
                "fake:android-001",
                "进入蓝牙设置页面",
                confirmed=True,
                goal_spec=goal_spec_payload(),
                goal_spec_confirmed=False,
            )

        self.assertEqual(403, status.value)
        self.assertEqual("CONFIRMATION_REQUIRED", payload["error"]["code"])
        self.assertEqual([], adapter.actions)

    def test_confirmed_goal_spec_drives_planner_and_preserves_source_goal(self) -> None:
        adapter = FakeDeviceAdapter()
        adapter.foreground_app = "com.android.settings"
        adapter.foreground_activity = ".DisplaySettings"
        planner = CapturingFinishPlanner()
        with tempfile.TemporaryDirectory() as directory:
            runtime = RuntimeService(
                adapter, ArtifactStore(Path(directory)), planner=planner
            )
            status, payload = runtime.run_agent_task_sync(
                "fake:android-001",
                "进入显示页面",
                confirmed=True,
                goal_spec=goal_spec_payload(
                    source_goal="进入显示页面",
                    execution_goal="打开系统设置，找到显示入口并进入显示设置页面",
                ),
                goal_spec_confirmed=True,
            )

        self.assertEqual(200, status.value)
        task = payload["task"]
        self.assertEqual("succeeded", task["status"])
        self.assertEqual("进入显示页面", task["goal"])
        self.assertEqual(
            "打开系统设置，找到显示入口并进入显示设置页面", planner.last_goal
        )
        self.assertEqual("llm", task["goal_spec"]["source"])


class CapturingFinishPlanner:
    planner_id = "test.goal-spec"

    def __init__(self) -> None:
        self.last_goal = ""

    def decide(
        self, goal: str, observation: AgentObservationSummary, round_index: int
    ) -> AgentDecision:
        self.last_goal = goal
        return AgentDecision(
            decision_id=f"decision_{uuid.uuid4().hex}",
            decision_type=AgentDecisionType.FINISH,
            skill_id="",
            tool_id="",
            arguments={
                "expected_selector": {
                    "strategy": "resource_id",
                    "value": "settings_title",
                    "match": "exact",
                }
            },
            reason="test finish",
            planner_id=self.planner_id,
        )


def goal_spec_payload(
    source_goal: str = "进入蓝牙设置页面",
    execution_goal: str = "打开系统设置，找到蓝牙入口并进入蓝牙设置页面",
) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "source_goal": source_goal,
        "execution_goal": execution_goal,
        "assumptions": ["蓝牙指系统设置中的蓝牙页面"],
        "confidence": 0.9,
        "compiler_id": "test.llm",
        "source": "llm",
        "confirmation_required": True,
    }
