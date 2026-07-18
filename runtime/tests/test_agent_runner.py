from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mobile_agent.agent import (
    AgentDecision,
    AgentDecisionType,
    AgentObservationSummary,
    AgentRunner,
    MockLLMPlanner,
    RuleBasedPlanner,
    UnavailablePlanner,
    parse_llm_decision_payload,
)
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.runtime import RuntimeService
from mobile_agent.skills.open_app import OpenAppSkill
from mobile_agent.skills.settings_navigate import SettingsScrollNavigateSkill
from mobile_agent.tools.runtime import ToolRegistry, ToolRuntime


ROOT = Path(__file__).resolve().parents[2]


class AgentRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    async def test_agent_run_records_observe_plan_act_round(self) -> None:
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(Path(self.directory.name)),
        )

        task = await runtime.run_agent_task(
            "fake:android-001",
            "open display settings",
            confirmed=True,
        )

        self.assertEqual("agent.run", task["task_type"])
        self.assertEqual("succeeded", task["status"])
        self.assertEqual(3, len(task["steps"]))
        step = task["steps"][0]
        self.assertEqual("agent_round", step["kind"])
        self.assertEqual("agent.round", step["name"])
        result = step["result"]
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertEqual("1.0.0", result["schema_version"])
        self.assertEqual(1, result["round"])
        self.assertEqual("1.0.0", result["observation"]["schema_version"])
        self.assertEqual("1.0.0", result["decision"]["schema_version"])
        self.assertEqual("rule_based.preview", result["decision"]["planner_id"])
        self.assertEqual("app.launch", result["decision"]["tool_id"])
        self.assertEqual("app.launch", result["action_result"]["tool_id"])
        self.assertIsNone(result["skill_result"])
        self.assertIsNone(result["verified_node"])
        self.assertEqual("finish", task["steps"][2]["result"]["decision"]["decision_type"])
        self.assertEqual("Display settings", task["evidence_summary"]["verified_node"]["text"])

        stored = runtime.get_task(task["task_id"])
        events = runtime.list_task_events(task["task_id"])
        self.assertEqual(task["task_id"], stored["task_id"])
        self.assertEqual("agent.run", events[0]["payload"]["task_type"])

    async def test_agent_run_returns_failed_task_for_unsupported_goal(self) -> None:
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(Path(self.directory.name)),
        )

        task = await runtime.run_agent_task(
            "fake:android-001",
            "打开 Wi-Fi 设置",
            confirmed=True,
        )

        self.assertEqual("failed", task["status"])
        self.assertEqual("INVALID_ARGUMENT", task["error"]["code"])
        self.assertEqual("failed", task["steps"][0]["status"])
        self.assertEqual("INVALID_ARGUMENT", task["steps"][0]["error"]["code"])

    async def test_agent_runner_rejects_planner_decision_outside_allowlist(self) -> None:
        adapter = FakeDeviceAdapter()
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        runner = AgentRunner(
            adapter,
            artifacts,
            UnsafePlanner(),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
        )

        task = await runner.run(
            "fake:android-001",
            "open display settings",
            confirmed=True,
        )

        self.assertEqual("failed", task.status.value)
        assert task.error is not None
        self.assertEqual("ACTION_REJECTED_BY_POLICY", task.error["code"])
        self.assertEqual([], adapter.actions)

    async def test_mock_llm_planner_runs_valid_structured_decision(self) -> None:
        adapter = FakeDeviceAdapter()
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        runner = AgentRunner(
            adapter,
            artifacts,
            MockLLMPlanner(valid_llm_payload()),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
        )

        task = await runner.run(
            "fake:android-001",
            "open display settings",
            confirmed=True,
        )

        self.assertEqual("succeeded", task.status.value)
        step = task.steps[0]
        assert step.result is not None
        decision = step.result["decision"]
        self.assertEqual("mock_llm.preview", decision["planner_id"])
        self.assertEqual("llm", decision["source"])
        self.assertEqual(0.82, decision["confidence"])
        self.assertEqual("mock_llm.preview", task.evidence_summary["planner_id"])

    async def test_mock_llm_planner_rejects_invalid_output_before_device_action(self) -> None:
        adapter = FakeDeviceAdapter()
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        runner = AgentRunner(
            adapter,
            artifacts,
            MockLLMPlanner({"decision_type": "run_skill", "skill_id": "settings.scroll_navigate"}),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
        )

        task = await runner.run(
            "fake:android-001",
            "open display settings",
            confirmed=True,
        )

        self.assertEqual("failed", task.status.value)
        assert task.error is not None
        self.assertEqual("MODEL_OUTPUT_INVALID", task.error["code"])
        self.assertEqual([], adapter.actions)

    async def test_unavailable_planner_fails_task_before_device_action(self) -> None:
        adapter = FakeDeviceAdapter()
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        runner = AgentRunner(
            adapter,
            artifacts,
            UnavailablePlanner(
                MobileAgentError(
                    code="MODEL_UNAVAILABLE",
                    category=ErrorCategory.EXECUTION,
                    message="模型不可用",
                    details={"has_api_key_ref": True},
                )
            ),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
        )

        task = await runner.run(
            "fake:android-001",
            "open display settings",
            confirmed=True,
        )

        self.assertEqual("failed", task.status.value)
        assert task.error is not None
        self.assertEqual("MODEL_UNAVAILABLE", task.error["code"])
        self.assertEqual([], adapter.actions)

    async def test_mock_llm_planner_structured_shell_decision_is_policy_rejected(self) -> None:
        adapter = FakeDeviceAdapter()
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        payload = {
            **valid_llm_payload(),
            "skill_id": "shell.execute",
        }
        runner = AgentRunner(
            adapter,
            artifacts,
            MockLLMPlanner(payload),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
        )

        task = await runner.run(
            "fake:android-001",
            "open display settings",
            confirmed=True,
        )

        self.assertEqual("failed", task.status.value)
        assert task.error is not None
        self.assertEqual("ACTION_REJECTED_BY_POLICY", task.error["code"])
        self.assertEqual([], adapter.actions)

    def test_llm_decision_payload_parser_rejects_invalid_shapes(self) -> None:
        invalid_payloads: list[object] = [
            "not-object",
            {**valid_llm_payload(), "decision_type": "shell"},
            {**valid_llm_payload(), "arguments": {}},
            {**valid_llm_payload(), "confidence": 1.5},
            {**valid_llm_payload(), "reason": {"unexpected": True}},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(MobileAgentError) as raised:
                    parse_llm_decision_payload(payload, "mock_llm.preview")
                self.assertEqual("MODEL_OUTPUT_INVALID", raised.exception.code)

    def test_llm_decision_uses_audit_fallback_when_reason_is_missing(self) -> None:
        payload = valid_llm_payload()
        payload.pop("reason")

        decision = parse_llm_decision_payload(payload, "mock_llm.preview")

        self.assertEqual("模型未提供决策说明。", decision.reason)

    def test_llm_tool_call_requires_explicit_clickable_ancestor_resolution(self) -> None:
        payload = {
            "decision_type": "run_tool",
            "tool_id": "input.tap_element",
            "arguments": {
                "selector": {
                    "strategy": "text",
                    "value": "显示和亮度",
                    "match": "contains",
                    "package": "com.android.settings",
                }
            },
            "reason": "The target is visible.",
        }

        with self.assertRaises(MobileAgentError) as raised:
            parse_llm_decision_payload(payload, "mock_llm.preview")

        self.assertEqual("MODEL_OUTPUT_INVALID", raised.exception.code)
        self.assertEqual("input.tap_element", raised.exception.details["tool_id"])
        self.assertEqual([], raised.exception.details["unknown_argument_keys"])

    def test_llm_tool_call_reports_safe_selector_field_diagnostics(self) -> None:
        payload = {
            "decision_type": "run_tool",
            "tool_id": "input.tap_element",
            "arguments": {
                "selector": {
                    "strategy": "text",
                    "value": "显示和亮度",
                    "match": "contains",
                    "resolve_clickable_ancestor": True,
                    "unexpected": "must-not-be-echoed",
                }
            },
            "reason": "The target is visible.",
        }

        with self.assertRaises(MobileAgentError) as raised:
            parse_llm_decision_payload(payload, "mock_llm.preview")

        self.assertEqual("MODEL_OUTPUT_INVALID", raised.exception.code)
        self.assertEqual("unknown_fields", raised.exception.details["selector_error_field"])
        self.assertEqual(["unexpected"], raised.exception.details["selector_unknown_keys"])
        self.assertNotIn("must-not-be-echoed", str(raised.exception.to_dict()))

    def test_runtime_sync_wraps_agent_run(self) -> None:
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(Path(self.directory.name)),
        )

        status, payload = runtime.run_agent_task_sync(
            "fake:android-001",
            "open display settings",
            confirmed=True,
        )

        self.assertEqual(200, status.value)
        self.assertEqual("succeeded", payload["task"]["status"])
        self.assertEqual("agent.run", payload["task"]["task_type"])

    async def test_mock_llm_planner_runs_multi_round_tool_decisions(self) -> None:
        adapter = FakeDeviceAdapter()
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        runner = AgentRunner(
            adapter,
            artifacts,
            MockLLMPlanner(
                [
                    {
                        "decision_type": "run_tool",
                        "tool_id": "app.launch",
                        "arguments": {"app_id": "com.android.settings"},
                        "reason": "Open settings first.",
                    },
                    {
                        "decision_type": "run_tool",
                        "tool_id": "input.tap_element",
                        "arguments": {
                            "selector": {
                                "strategy": "text",
                                "value": "Display",
                                "match": "contains",
                                "package": "com.android.settings",
                                "resolve_clickable_ancestor": True,
                            }
                        },
                        "reason": "Tap display entry.",
                    },
                    {
                        "decision_type": "finish",
                        "arguments": {
                            "expected_selector": {
                                "strategy": "text",
                                "value": "Display settings",
                                "match": "contains",
                                "package": "com.android.settings",
                            }
                        },
                        "reason": "Display settings is visible.",
                    },
                ]
            ),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
        )

        task = await runner.run("fake:android-001", "open display settings", confirmed=True)

        self.assertEqual("succeeded", task.status.value)
        self.assertEqual(3, len(task.steps))
        self.assertEqual("app.launch", task.steps[0].result["decision"]["tool_id"])
        self.assertEqual("input.tap_element", task.steps[1].result["decision"]["tool_id"])
        self.assertEqual("finish", task.steps[2].result["decision"]["decision_type"])
        self.assertEqual(("app.launch", "fake:android-001", "com.android.settings"), adapter.actions[0])
        self.assertEqual("input.tap", adapter.actions[1][0])

    async def test_agent_stops_repeated_tool_after_unchanged_ui_feedback(self) -> None:
        adapter = FakeDeviceAdapter()
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        swipe = {
            "decision_type": "run_tool",
            "tool_id": "input.swipe",
            "arguments": {"direction": "up", "distance_percent": 0.5, "duration_ms": 500},
            "reason": "Look for the target below.",
        }
        runner = AgentRunner(
            adapter,
            artifacts,
            MockLLMPlanner(
                [
                    {
                        "decision_type": "run_tool",
                        "tool_id": "app.launch",
                        "arguments": {"app_id": "com.android.settings"},
                        "reason": "Open settings.",
                    },
                    swipe,
                    swipe,
                ]
            ),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
        )

        task = await runner.run("fake:android-001", "open display settings", confirmed=True)

        self.assertEqual("failed", task.status.value)
        assert task.error is not None
        self.assertEqual("NO_PROGRESS", task.error["code"])
        self.assertEqual(3, len(task.steps))
        feedback = task.steps[1].result["action_feedback"]
        self.assertEqual("unchanged", feedback["effect"])
        self.assertEqual("input.swipe", feedback["tool_id"])
        self.assertEqual(2, len(adapter.actions))

    async def test_ambiguous_finish_is_recoverable_and_can_be_refined(self) -> None:
        adapter = FakeDeviceAdapter()
        adapter.foreground_app = "com.android.settings"
        adapter.foreground_activity = ".Settings$BluetoothSettingsActivity"
        adapter.custom_ui_xml = (
            b'<?xml version="1.0"?><hierarchy>'
            b'<node text="" resource-id="root" class="android.view.View" '
            b'package="com.android.settings" clickable="false" enabled="true" '
            b'visible-to-user="true" bounds="[0,0][2,3]">'
            b'<node text="Bluetooth" resource-id="android:id/action_bar_title" '
            b'class="android.widget.TextView" package="com.android.settings" '
            b'clickable="false" enabled="true" visible-to-user="true" bounds="[0,0][2,1]"/>'
            b'<node text="Bluetooth" resource-id="switch_text" '
            b'class="android.widget.TextView" package="com.android.settings" '
            b'clickable="false" enabled="true" visible-to-user="true" bounds="[0,1][2,2]"/>'
            b'</node></hierarchy>'
        )
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        runner = AgentRunner(
            adapter,
            artifacts,
            MockLLMPlanner(
                [
                    {
                        "decision_type": "finish",
                        "arguments": {
                            "expected_selector": {
                                "strategy": "text",
                                "value": "Bluetooth",
                                "match": "exact",
                                "package": "com.android.settings",
                            }
                        },
                        "reason": "Bluetooth page is visible.",
                    },
                    {
                        "decision_type": "finish",
                        "arguments": {
                            "expected_foreground_app": {
                                "app_id": "com.android.settings",
                                "activity": ".Settings$BluetoothSettingsActivity",
                            },
                            "expected_selector": {
                                "strategy": "resource_id",
                                "value": "android:id/action_bar_title",
                                "match": "exact",
                                "package": "com.android.settings",
                            },
                        },
                        "reason": "Use the unique page title and foreground activity.",
                    },
                ]
            ),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
        )

        task = await runner.run(
            "fake:android-001", "open Bluetooth settings", confirmed=True, max_rounds=2
        )

        self.assertEqual("succeeded", task.status.value)
        self.assertEqual("failed", task.steps[0].status.value)
        self.assertEqual("TARGET_AMBIGUOUS", task.steps[0].error["code"])
        feedback = task.steps[0].result["action_feedback"]
        self.assertEqual("finish_verification", feedback["basis"])
        self.assertEqual(2, feedback["details"]["match_count"])
        self.assertEqual("succeeded", task.steps[1].status.value)
        self.assertEqual(
            "android:id/action_bar_title",
            task.steps[1].result["verified_node"]["resource_id"],
        )
        self.assertEqual([], adapter.actions)

    async def test_runtime_acceptance_is_authoritative_for_finish(self) -> None:
        adapter = FakeDeviceAdapter()
        planner = MockLLMPlanner(
            [
                {
                    "decision_type": "run_tool",
                    "tool_id": "app.launch",
                    "arguments": {"app_id": "com.android.settings"},
                    "reason": "Open settings.",
                },
                {
                    "decision_type": "run_tool",
                    "tool_id": "input.tap_element",
                    "arguments": {
                        "selector": {
                            "strategy": "text",
                            "value": "Display",
                            "match": "exact",
                            "package": "com.android.settings",
                            "resolve_clickable_ancestor": True,
                        }
                    },
                    "reason": "Open display settings.",
                },
                {
                    "decision_type": "finish",
                    "arguments": {
                        "expected_selector": {
                            "strategy": "text",
                            "value": "model-selected-wrong-target",
                            "match": "exact",
                        }
                    },
                    "reason": "The goal is complete.",
                },
            ]
        )
        runtime = RuntimeService(
            adapter,
            ArtifactStore(Path(self.directory.name)),
            planner=planner,
        )
        acceptance = {
            "foreground_app_id": "com.android.settings",
            "foreground_activity": ".DisplaySettings",
            "expected_selector": {
                "strategy": "resource_id",
                "value": "settings_title",
                "match": "exact",
                "package": "com.android.settings",
            },
        }

        task = await runtime.run_agent_task(
            "fake:android-001",
            "open display settings",
            confirmed=True,
            acceptance=acceptance,
        )

        self.assertEqual("succeeded", task["status"])
        self.assertEqual("runtime_acceptance", task["completion_source"])
        self.assertEqual(
            "com.android.settings", task["goal_acceptance"]["foreground_app_id"]
        )
        self.assertEqual(
            "settings_title",
            task["goal_acceptance"]["expected_selector"]["value"],
        )
        self.assertEqual(
            "settings_title", task["evidence_summary"]["verified_node"]["resource_id"]
        )

    async def test_runtime_acceptance_failure_is_recoverable(self) -> None:
        adapter = FakeDeviceAdapter()
        adapter.foreground_app = "com.android.settings"
        adapter.foreground_activity = ".DisplaySettings"
        runtime = RuntimeService(
            adapter,
            ArtifactStore(Path(self.directory.name)),
            planner=MockLLMPlanner(
                {
                    "decision_type": "finish",
                    "arguments": {
                        "expected_selector": {
                            "strategy": "resource_id",
                            "value": "settings_title",
                            "match": "exact",
                        }
                    },
                    "reason": "The model believes the goal is complete.",
                }
            ),
        )

        task = await runtime.run_agent_task(
            "fake:android-001",
            "open display settings",
            confirmed=True,
            max_rounds=2,
            acceptance={"foreground_app_id": "com.example.not-current"},
        )

        self.assertEqual("failed", task["status"])
        self.assertEqual("failed", task["steps"][0]["status"])
        self.assertEqual("TARGET_NOT_FOUND", task["steps"][0]["error"]["code"])
        self.assertEqual(
            "runtime_acceptance", task["steps"][0]["result"]["action_feedback"]["basis"]
        )

    async def test_failed_tool_step_preserves_observation_and_decision(self) -> None:
        adapter = FakeDeviceAdapter()
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        runner = AgentRunner(
            adapter,
            artifacts,
            MockLLMPlanner(
                {
                    "decision_type": "run_tool",
                    "tool_id": "input.tap_element",
                    "arguments": {
                        "selector": {
                            "strategy": "text",
                            "value": "Missing target",
                            "match": "contains",
                            "resolve_clickable_ancestor": True,
                        }
                    },
                    "reason": "Try the requested target.",
                }
            ),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
        )

        task = await runner.run(
            "fake:android-001", "open display settings", confirmed=True, max_rounds=1
        )

        self.assertEqual("failed", task.status.value)
        self.assertEqual("TARGET_NOT_FOUND", task.error["code"])
        self.assertEqual(1, len(task.steps))
        step = task.steps[0]
        self.assertEqual("failed", step.status.value)
        self.assertEqual("input.tap_element", step.result["decision"]["tool_id"])
        self.assertEqual("obs_", step.result["observation"]["observation_id"][:4])
        self.assertIsNone(step.result["action_result"])
        self.assertEqual("TARGET_NOT_FOUND", step.result["action_feedback"]["error_code"])

    async def test_observation_summary_prioritizes_semantics_and_redacts_identifiers(self) -> None:
        adapter = FakeDeviceAdapter()
        structural_nodes = "".join(
            f'<node text="" resource-id="container_{index}" class="android.view.View" '
            'package="com.android.settings" clickable="false" enabled="true" '
            'visible-to-user="true" bounds="[0,0][2,3]"/>'
            for index in range(35)
        )
        adapter.custom_ui_xml = (
            '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            + structural_nodes
            + '<node text="150******20" resource-id="android:id/title" '
            'class="android.widget.TextView" package="com.android.settings" clickable="false" '
            'enabled="true" visible-to-user="true" bounds="[0,0][2,1]"/>'
            '<node text="" resource-id="dashboard_tile" class="android.widget.LinearLayout" '
            'package="com.android.settings" clickable="true" enabled="true" '
            'visible-to-user="true" bounds="[0,1][2,3]">'
            '<node text="显示和亮度" resource-id="android:id/title" '
            'class="android.widget.TextView" package="com.android.settings" clickable="false" '
            'enabled="true" visible-to-user="true" bounds="[0,1][2,2]"/>'
            "</node></hierarchy>"
        ).encode()
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        runner = AgentRunner(
            adapter,
            artifacts,
            MockLLMPlanner(valid_llm_payload()),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
        )
        observation = await adapter.observe("fake:android-001", artifacts)

        payload = runner._summarize_observation(observation).to_dict()

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertIn("显示和亮度", serialized)
        self.assertNotIn("150******20", serialized)
        self.assertIn("[REDACTED_PHONE]", serialized)
        self.assertFalse(payload["ui_summary_truncated"])
        self.assertEqual(2, payload["ui_summary_total_candidates"])
        target = next(item for item in payload["ui_summary"] if item["text"] == "显示和亮度")
        self.assertTrue(target["clickable_ancestor"])
        self.assertNotIn("container_", serialized)

    def test_agent_contracts_are_versioned_and_task_run_accepts_agent_steps(self) -> None:
        feedback_schema = json.loads(
            (ROOT / "contracts/schemas/agent-action-feedback.schema.json").read_text(
                encoding="utf-8"
            )
        )
        decision_schema = json.loads(
            (ROOT / "contracts/schemas/agent-decision.schema.json").read_text(encoding="utf-8")
        )
        tool_call_schema = json.loads(
            (ROOT / "contracts/schemas/agent-tool-call.schema.json").read_text(encoding="utf-8")
        )
        finish_schema = json.loads(
            (ROOT / "contracts/schemas/agent-finish-criteria.schema.json").read_text(
                encoding="utf-8"
            )
        )
        summary_schema = json.loads(
            (ROOT / "contracts/schemas/agent-observation-summary.schema.json").read_text(
                encoding="utf-8"
            )
        )
        step_schema = json.loads(
            (ROOT / "contracts/schemas/agent-step-result.schema.json").read_text(encoding="utf-8")
        )
        task_schema = json.loads(
            (ROOT / "contracts/schemas/task-run.schema.json").read_text(encoding="utf-8")
        )

        self.assertEqual(
            "https://mobile-agent.local/schemas/agent-decision/v1.json",
            decision_schema["$id"],
        )
        self.assertEqual(
            "https://mobile-agent.local/schemas/agent-action-feedback/v1.json",
            feedback_schema["$id"],
        )
        self.assertEqual(
            ["changed", "unchanged", "unknown"],
            feedback_schema["properties"]["effect"]["enum"],
        )
        self.assertEqual("1.0.0", decision_schema["properties"]["schema_version"]["const"])
        self.assertEqual(
            "https://mobile-agent.local/schemas/agent-tool-call/v1.json",
            tool_call_schema["$id"],
        )
        self.assertIn("repair_count", decision_schema["properties"])
        self.assertIn("provider_retry_count", decision_schema["properties"])
        self.assertEqual(
            "https://mobile-agent.local/schemas/agent-finish-criteria/v1.json",
            finish_schema["$id"],
        )
        self.assertIn("run_tool", decision_schema["properties"]["decision_type"]["enum"])
        self.assertIn("finish", decision_schema["properties"]["decision_type"]["enum"])
        self.assertEqual(
            "https://mobile-agent.local/schemas/agent-observation-summary/v1.json",
            summary_schema["$id"],
        )
        self.assertEqual(30, summary_schema["properties"]["ui_summary"]["maxItems"])
        self.assertIn("last_action_feedback", summary_schema["properties"])
        self.assertIn("ui_summary_total_candidates", summary_schema["properties"])
        self.assertIn("ui_summary_truncated", summary_schema["properties"])
        self.assertIn(
            "clickable_ancestor",
            summary_schema["properties"]["ui_summary"]["items"]["properties"],
        )
        self.assertEqual(
            "https://mobile-agent.local/schemas/agent-step-result/v1.json",
            step_schema["$id"],
        )
        self.assertIn("action_result", step_schema["required"])
        self.assertIn("action_feedback", step_schema["properties"])
        self.assertIn("agent.run", task_schema["properties"]["task_type"]["enum"])
        self.assertIn("timed_out", task_schema["properties"]["status"]["enum"])
        self.assertIn("deadline_seconds", task_schema["properties"])
        self.assertEqual(
            "agent-goal-acceptance.schema.json",
            task_schema["properties"]["goal_acceptance"]["$ref"],
        )
        self.assertEqual(
            "agent-goal-spec.schema.json",
            task_schema["properties"]["goal_spec"]["$ref"],
        )
        self.assertIn(
            "runtime_acceptance",
            task_schema["properties"]["completion_source"]["enum"],
        )
        step_properties = task_schema["properties"]["steps"]["items"]["properties"]
        self.assertIn("agent_round", step_properties["kind"]["enum"])
        self.assertIn("agent.round", step_properties["name"]["enum"])
        self.assertIn(
            {"$ref": "agent-step-result.schema.json"},
            step_properties["result"]["oneOf"],
        )

    def test_rule_planner_reverses_swipe_after_unchanged_feedback(self) -> None:
        planner = RuleBasedPlanner()
        summary = AgentObservationSummary(
            observation_id="obs_test",
            foreground_app={"app_id": "com.android.settings", "activity": ".Main"},
            device_state="interactive",
            last_action_feedback={
                "schema_version": "1.0.0",
                "tool_id": "input.swipe",
                "arguments": {"direction": "up", "distance_percent": 0.35},
                "effect": "unchanged",
                "basis": "ui_tree_and_foreground",
                "message": "unchanged",
            },
        )

        decision = planner.decide("open display settings", summary, 3)

        self.assertEqual("input.swipe", decision.tool_id)
        self.assertEqual("down", decision.arguments["direction"])


class UnsafePlanner:
    planner_id = "unsafe.test"

    def decide(
        self,
        goal: str,
        observation: AgentObservationSummary,
        round_index: int,
    ) -> AgentDecision:
        return AgentDecision(
            decision_id="decision_unsafe",
            decision_type=AgentDecisionType.RUN_TOOL,
            skill_id="",
            tool_id="shell.execute",
            arguments={},
            reason="test unsafe decision",
            planner_id=self.planner_id,
        )


def valid_llm_payload() -> dict[str, object]:
    return {
        "decision_type": "run_skill",
        "skill_id": "settings.scroll_navigate",
        "arguments": {
            "target_selector": {
                "strategy": "text",
                "value": "Display",
                "match": "contains",
                "resolve_clickable_ancestor": True,
            },
            "expected_selector": {
                "strategy": "text",
                "value": "Display",
                "match": "contains",
            },
            "direction": "up",
            "max_scrolls": 1,
            "distance_percent": 0.35,
            "duration_ms": 900,
            "settle_seconds": 0,
        },
        "reason": "The goal asks to open the display settings page.",
        "confidence": 0.82,
    }
