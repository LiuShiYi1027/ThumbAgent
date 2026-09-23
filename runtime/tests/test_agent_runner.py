from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any

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
from mobile_agent.agent.planner import MAX_AGENT_ROUNDS
from mobile_agent.agent.shortcuts import match_navigation_shortcut
from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.unicode_input import HELPER_PACKAGE
from mobile_agent.domain.app import InstalledApp
from mobile_agent.domain.app_lifecycle import AppRuntimeState
from mobile_agent.domain.artifact import ArtifactWriter
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.device_log import DeviceLogLevel
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.navigation import NavigationTarget
from mobile_agent.domain.observation import Observation
from mobile_agent.domain.performance import DevicePerformanceSnapshot
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.evaluation import AgentGoalAcceptance
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.runtime import RuntimeService
from mobile_agent.skills.open_app import OpenAppSkill
from mobile_agent.skills.settings_navigate import SettingsScrollNavigateSkill
from mobile_agent.skills.unicode_input import UnicodeTextInputSkill
from mobile_agent.tools.runtime import ToolRegistry, ToolRuntime
from mobile_agent.tools.unicode_input import UnicodeTextInputTool


ROOT = Path(__file__).resolve().parents[2]


class AgentRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    async def test_agent_run_records_observe_plan_act_round(self) -> None:
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(Path(self.directory.name)),
            navigation_shortcuts_enabled=False,
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

    async def test_navigation_shortcut_completes_settings_goal_without_planner(self) -> None:
        """导航类目标默认走 Runtime 捷径：一次 app.navigate 完成，不经 Planner。"""
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(Path(self.directory.name)),
        )

        task = await runtime.run_agent_task(
            "fake:android-001",
            "open display settings",
            confirmed=True,
        )

        self.assertEqual("succeeded", task["status"])
        self.assertEqual("runtime_shortcut", task["completion_source"])
        self.assertEqual(1, len(task["steps"]))
        step = task["steps"][0]
        self.assertEqual("agent_round", step["kind"])
        self.assertEqual("agent.shortcut", step["name"])
        self.assertEqual("app.navigate", step["result"]["skill_id"])
        self.assertEqual("runtime_shortcut", task["evidence_summary"]["planner_id"])
        self.assertEqual("settings.display", task["evidence_summary"]["shortcut"])
        self.assertEqual(
            "com.android.settings",
            task["evidence_summary"]["final_foreground_app"]["app_id"],
        )

    async def test_navigation_shortcut_falls_back_when_capability_missing(self) -> None:
        """设备缺少 app.navigate 能力时降级回 Planner 循环，而不是直接失败。"""
        adapter = FakeDeviceAdapter(
            devices=[
                Device(
                    device_id="fake:android-001",
                    platform=Platform.ANDROID,
                    name="Fake Android Device",
                    model="fake_android",
                    os_version="15",
                    connection=ConnectionState.ONLINE,
                    capabilities=(
                        "device.inspect@1",
                        "screen.observe@1",
                        "app.launch@1",
                        "navigation.back@1",
                        "navigation.home@1",
                        "input.tap@1",
                        "input.swipe@1",
                    ),
                )
            ]
        )
        runtime = RuntimeService(
            adapter,
            ArtifactStore(Path(self.directory.name)),
        )

        task = await runtime.run_agent_task(
            "fake:android-001",
            "open display settings",
            confirmed=True,
        )

        self.assertEqual("succeeded", task["status"])
        self.assertEqual("rule_based.preview", task["evidence_summary"]["planner_id"])
        self.assertEqual(3, len(task["steps"]))
        self.assertFalse(
            any(action[0] == "app.navigate" for action in adapter.actions)
        )

    async def test_agent_run_returns_failed_task_for_unsupported_goal(self) -> None:
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(Path(self.directory.name)),
        )

        task = await runtime.run_agent_task(
            "fake:android-001",
            "帮我点一杯咖啡",
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
            # 这些用例验证 Planner 决策循环本身，关闭导航捷径避免目标被接管。
            navigation_shortcuts_enabled=False,
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
            # 这些用例验证 Planner 决策循环本身，关闭导航捷径避免目标被接管。
            navigation_shortcuts_enabled=False,
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
            # 这些用例验证 Planner 决策循环本身，关闭导航捷径避免目标被接管。
            navigation_shortcuts_enabled=False,
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
            # 这些用例验证 Planner 决策循环本身，关闭导航捷径避免目标被接管。
            navigation_shortcuts_enabled=False,
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
            # 这些用例验证 Planner 决策循环本身，关闭导航捷径避免目标被接管。
            navigation_shortcuts_enabled=False,
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

    async def test_agent_executes_unicode_input_skill_via_planner(self) -> None:
        """中文输入目标经模型循环调用 input.unicode_text 完成并恢复原 IME。"""
        adapter = FakeDeviceAdapter()
        # 动态 fake 路径：读回文本随 input.text 追加更新（追加语义验证）。
        adapter.foreground_app = "com.example.form"
        adapter.foreground_activity = ".MainActivity"
        adapter.field_text = ""
        adapter.installed_imes = (
            "com.example.ime/.DefaultIme",
            f"{HELPER_PACKAGE}/{HELPER_PACKAGE}.UnicodeImeService",
        )
        adapter.enabled_imes = ["com.example.ime/.DefaultIme"]
        adapter.current_ime = "com.example.ime/.DefaultIme"
        artifacts = ArtifactStore(Path(self.directory.name))
        registry = ToolRegistry()
        policy = PolicyEngine()
        tools = ToolRuntime(adapter, artifacts, registry, policy)
        unicode_skill = UnicodeTextInputSkill(
            UnicodeTextInputTool(adapter, artifacts, registry, policy)
        )
        payloads = [
            {
                "decision_type": "run_skill",
                "skill_id": "input.unicode_text",
                "arguments": {
                    "selector": {
                        "strategy": "resource_id",
                        "value": "search_box",
                        "match": "exact",
                    },
                    "text": "你好世界",
                },
                "reason": "The goal asks to type Chinese text into the search box.",
                "confidence": 0.85,
            },
            {
                "decision_type": "finish",
                "arguments": {
                    "expected_selector": {
                        "strategy": "text",
                        "value": "你好世界",
                        "match": "exact",
                    }
                },
                "reason": "The field now shows the requested text.",
                "confidence": 0.9,
            },
        ]
        runner = AgentRunner(
            adapter,
            artifacts,
            MockLLMPlanner(payloads),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
            # 这些用例验证 Planner 决策循环本身，关闭导航捷径避免目标被接管。
            navigation_shortcuts_enabled=False,
            unicode_text_input=unicode_skill,
        )

        task = await runner.run(
            "fake:android-001",
            "在搜索框输入你好世界",
            confirmed=True,
        )

        self.assertEqual("succeeded", task.status.value)
        skill_result = task.steps[0].result["skill_result"]
        self.assertEqual("input.unicode_text", skill_result["skill_id"])
        self.assertTrue(skill_result["ime"]["restored"])
        self.assertEqual(
            "com.example.ime/.DefaultIme", skill_result["ime"]["previous_id"]
        )
        self.assertNotIn("你好世界", str(skill_result))
        set_actions = [a for a in adapter.actions if a[0] == "input.ime.set"]
        self.assertEqual(
            ("input.ime.set", "fake:android-001", "com.example.ime/.DefaultIme"),
            set_actions[-1],
        )

    def test_llm_unicode_skill_payload_requires_selector_and_text(self) -> None:
        valid = {
            "decision_type": "run_skill",
            "skill_id": "input.unicode_text",
            "arguments": {
                "selector": {"strategy": "resource_id", "value": "search_box"},
                "text": "你好",
            },
            "reason": "type unicode text",
            "confidence": 0.8,
        }

        decision = parse_llm_decision_payload(valid, "mock_llm.preview")
        self.assertEqual("input.unicode_text", decision.skill_id)

        for bad_arguments in (
            {"selector": {"strategy": "resource_id", "value": "search_box"}},
            {"text": "你好"},
            {"target_selector": {}, "expected_selector": {}},
        ):
            with self.subTest(arguments=bad_arguments):
                with self.assertRaises(MobileAgentError) as raised:
                    parse_llm_decision_payload(
                        {**valid, "arguments": bad_arguments}, "mock_llm.preview"
                    )
                self.assertEqual("MODEL_OUTPUT_INVALID", raised.exception.code)

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
            # 这些用例验证 Planner 决策循环本身，关闭导航捷径避免目标被接管。
            navigation_shortcuts_enabled=False,
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
            # 这些用例验证 Planner 决策循环本身，关闭导航捷径避免目标被接管。
            navigation_shortcuts_enabled=False,
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
            # 这些用例验证 Planner 决策循环本身，关闭导航捷径避免目标被接管。
            navigation_shortcuts_enabled=False,
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
            navigation_shortcuts_enabled=False,
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
            navigation_shortcuts_enabled=False,
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
            # 这些用例验证 Planner 决策循环本身，关闭导航捷径避免目标被接管。
            navigation_shortcuts_enabled=False,
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

    async def test_observation_summary_exposes_hint_for_editable_fields(self) -> None:
        """空输入框 text==hint 场景：hint 进观察摘要，模型才能用 hint 策略定位。"""
        adapter = FakeDeviceAdapter()
        adapter.custom_ui_xml = (
            '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            '<node text="搜索设置项" hint="搜索设置项" resource-id="android:id/search_src_text" '
            'class="android.widget.AutoCompleteTextView" package="com.android.settings" '
            'clickable="true" enabled="true" visible-to-user="true" bounds="[0,0][2,1]"/>'
            '<node text="Plain" resource-id="plain" class="android.widget.TextView" '
            'package="com.android.settings" clickable="false" enabled="true" '
            'visible-to-user="true" bounds="[0,1][2,2]"/>'
            '</hierarchy>'
        ).encode()
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        runner = AgentRunner(
            adapter,
            artifacts,
            MockLLMPlanner(valid_llm_payload()),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
            navigation_shortcuts_enabled=False,
        )
        observation = await adapter.observe("fake:android-001", artifacts)

        payload = runner._summarize_observation(observation).to_dict()

        search_item = next(
            item for item in payload["ui_summary"] if "search_src_text" in item["resource_id"]
        )
        self.assertEqual("搜索设置项", search_item["hint"])
        plain_item = next(item for item in payload["ui_summary"] if item["text"] == "Plain")
        self.assertNotIn("hint", plain_item)

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
            # 这些用例验证 Planner 决策循环本身，关闭导航捷径避免目标被接管。
            navigation_shortcuts_enabled=False,
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
        self.assertIn("provider_latency_ms", decision_schema["properties"])
        self.assertIn("provider_attempt_count", decision_schema["properties"])
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

    def _runner_for(
        self, adapter: DeviceAdapter, planner: Planner | None = None
    ) -> AgentRunner:
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        return AgentRunner(
            adapter,
            artifacts,
            planner if planner is not None else RuleBasedPlanner(),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
            # 这些用例验证 Planner 决策循环本身，关闭导航捷径避免目标被接管。
            navigation_shortcuts_enabled=False,
        )

    async def test_observe_retry_succeeds_after_transient_ui_tree_failure(self) -> None:
        """首次 observe 抛 UI_TREE_INVALID、二次成功时，任务有界重试并正常继续。"""
        adapter = _FlakyObserveAdapter(failures=1)

        task = await self._runner_for(adapter).run(
            "fake:android-001", "open display settings", confirmed=True
        )

        self.assertEqual("succeeded", task.status.value)
        self.assertEqual(1, adapter.failed_observe_calls)
        self.assertGreater(adapter.observe_calls, 1)

    async def test_observe_retry_succeeds_after_transient_observation_failure(self) -> None:
        """OBSERVATION_FAILED 同属可重试的瞬时观察错误。"""
        adapter = _FlakyObserveAdapter(failures=1, code="OBSERVATION_FAILED")

        task = await self._runner_for(adapter).run(
            "fake:android-001", "open display settings", confirmed=True
        )

        self.assertEqual("succeeded", task.status.value)
        self.assertEqual(1, adapter.failed_observe_calls)

    async def test_observe_retry_exhausted_terminates_with_evidence(self) -> None:
        """持续观察失败在最多 2 次重试后以明确终态结束，失败轮次证据保留。"""
        adapter = _FlakyObserveAdapter(failures=None)

        task = await self._runner_for(adapter).run(
            "fake:android-001", "open display settings", confirmed=True, max_rounds=3
        )

        self.assertEqual("failed", task.status.value)
        assert task.error is not None
        self.assertEqual("UI_TREE_INVALID", task.error["code"])
        # 1 次首次尝试 + 2 次重试，不超过重试上限
        self.assertEqual(3, adapter.observe_calls)
        self.assertEqual(1, len(task.steps))
        self.assertEqual("failed", task.steps[0].status.value)
        self.assertEqual("UI_TREE_INVALID", task.steps[0].error["code"])

    async def test_observe_retry_respects_cancellation(self) -> None:
        """重试窗口内收到取消请求时，不再发起新的观察尝试。"""
        adapter = _FlakyObserveAdapter(failures=None)

        task = await self._runner_for(adapter).run(
            "fake:android-001",
            "open display settings",
            confirmed=True,
            max_rounds=3,
            cancellation_requested=lambda: adapter.observe_calls >= 1,
        )

        self.assertEqual("cancelled", task.status.value)
        self.assertEqual(1, adapter.observe_calls)

    async def test_observe_retry_respects_deadline(self) -> None:
        """重试窗口内超过 Deadline 时，任务以 timed_out 结束且不再观察。"""
        adapter = _FlakyObserveAdapter(failures=None)

        task = await self._runner_for(adapter).run(
            "fake:android-001",
            "open display settings",
            confirmed=True,
            max_rounds=3,
            deadline_exceeded=lambda: adapter.observe_calls >= 1,
        )

        self.assertEqual("timed_out", task.status.value)
        self.assertEqual(1, adapter.observe_calls)

    async def test_observe_does_not_retry_non_transient_device_error(self) -> None:
        """设备 Session 变化等连接性错误不属于瞬时故障，必须立即终止。"""
        adapter = _FlakyObserveAdapter(failures=None, code="DEVICE_SESSION_CHANGED")

        task = await self._runner_for(adapter).run(
            "fake:android-001", "open display settings", confirmed=True, max_rounds=3
        )

        self.assertEqual("failed", task.status.value)
        assert task.error is not None
        self.assertEqual("DEVICE_SESSION_CHANGED", task.error["code"])
        self.assertEqual(1, adapter.observe_calls)

    async def test_empty_hierarchy_recovers_after_transient_skeleton_dump(self) -> None:
        """骨架树在有界重试内变为有语义节点时，任务继续且 Planner 只在恢复后调用。"""
        adapter = _EmptyThenPopulatedAdapter(empty_observations=1)
        planner = _CountingPlanner(RuleBasedPlanner())

        task = await self._runner_for(adapter, planner).run(
            "fake:android-001", "open display settings", confirmed=True
        )

        self.assertEqual("succeeded", task.status.value)
        self.assertGreaterEqual(adapter.observe_calls, 2)
        self.assertGreaterEqual(planner.calls, 1)

    async def test_persistent_empty_hierarchy_fails_without_planning(self) -> None:
        """持续空树以 UI_TREE_EMPTY 失败，不进入 Planner，也不记 NO_PROGRESS。"""
        adapter = _EmptyThenPopulatedAdapter(empty_observations=None)
        planner = _CountingPlanner(RuleBasedPlanner())

        task = await self._runner_for(adapter, planner).run(
            "fake:android-001", "open display settings", confirmed=True, max_rounds=3
        )

        self.assertEqual("failed", task.status.value)
        assert task.error is not None
        self.assertEqual("UI_TREE_EMPTY", task.error["code"])
        self.assertNotEqual("NO_PROGRESS", task.error["code"])
        self.assertEqual(3, adapter.observe_calls)
        self.assertEqual(0, planner.calls)
        self.assertEqual(1, len(task.steps))
        assert task.steps[0].error is not None
        details = task.steps[0].error["details"]
        self.assertRegex(details["observation_id"], r"^obs_[a-f0-9]{32}$")
        self.assertRegex(details["screenshot_artifact_id"], r"^artifact_[a-f0-9]{32}$")
        self.assertEqual(0, details["semantic_candidate_count"])
        self.assertEqual(0, details["locatable_node_count"])
        self.assertIsInstance(details["node_count"], int)
        self.assertNotIn("ui_xml", details)
        self.assertNotIn("text", details)

    async def test_empty_hierarchy_retry_respects_cancellation(self) -> None:
        adapter = _EmptyThenPopulatedAdapter(empty_observations=None)

        task = await self._runner_for(adapter).run(
            "fake:android-001",
            "open display settings",
            confirmed=True,
            max_rounds=3,
            cancellation_requested=lambda: adapter.observe_calls >= 1,
        )

        self.assertEqual("cancelled", task.status.value)
        self.assertEqual(1, adapter.observe_calls)

    async def test_empty_hierarchy_retry_respects_deadline(self) -> None:
        adapter = _EmptyThenPopulatedAdapter(empty_observations=None)

        task = await self._runner_for(adapter).run(
            "fake:android-001",
            "open display settings",
            confirmed=True,
            max_rounds=3,
            deadline_exceeded=lambda: adapter.observe_calls >= 1,
        )

        self.assertEqual("timed_out", task.status.value)
        self.assertEqual(1, adapter.observe_calls)

    async def test_tap_element_rejected_on_empty_hierarchy_before_dispatch(self) -> None:
        """观察层漏判时，语义点击仍不得到达 Adapter。"""
        adapter = FakeDeviceAdapter()
        adapter.custom_ui_xml = _SKELETON_UI_XML
        runner = self._runner_for(adapter)
        observation = await adapter.observe(
            "fake:android-001", ArtifactStore(Path(self.directory.name))
        )
        decision = AgentDecision(
            decision_id="decision_empty_tap",
            decision_type=AgentDecisionType.RUN_TOOL,
            skill_id="",
            tool_id="input.tap_element",
            arguments={
                "selector": {
                    "strategy": "text",
                    "value": "Display",
                    "match": "contains",
                    "resolve_clickable_ancestor": True,
                }
            },
            reason="Click a label that is not in the empty tree.",
            planner_id="guard.test",
        )

        with self.assertRaises(MobileAgentError) as raised:
            await runner._run_decision(
                "fake:android-001",
                observation,
                decision,
                confirmed=True,
                acceptance=None,
            )

        self.assertEqual("UI_TREE_EMPTY", raised.exception.code)
        self.assertFalse(
            any(action[0] == "input.tap" for action in adapter.actions)
        )

    async def test_back_is_allowed_on_empty_hierarchy(self) -> None:
        """返回不依赖当前树，空树上仍可派发。"""
        adapter = FakeDeviceAdapter()
        adapter.custom_ui_xml = _SKELETON_UI_XML
        runner = self._runner_for(adapter)
        observation = await adapter.observe(
            "fake:android-001", ArtifactStore(Path(self.directory.name))
        )
        decision = AgentDecision(
            decision_id="decision_empty_back",
            decision_type=AgentDecisionType.RUN_TOOL,
            skill_id="",
            tool_id="navigation.back",
            arguments={},
            reason="Leave the page that has no UI tree.",
            planner_id="guard.test",
        )

        result = await runner._run_decision(
            "fake:android-001",
            observation,
            decision,
            confirmed=True,
            acceptance=None,
        )

        self.assertIn("action_result", result)
        self.assertIn(("navigation.back", "fake:android-001"), adapter.actions)

    async def test_agent_runner_accepts_max_rounds_twelve(self) -> None:
        """轮次预算上限校准后，12 是合法输入且任务在演示 Planner 预算内完成。"""
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(Path(self.directory.name)),
        )

        task = await runtime.run_agent_task(
            "fake:android-001", "open display settings", confirmed=True, max_rounds=12
        )

        self.assertEqual("succeeded", task["status"])

    async def test_agent_runner_rejects_max_rounds_outside_budget(self) -> None:
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(Path(self.directory.name)),
        )

        for invalid in (0, 51):
            task = await runtime.run_agent_task(
                "fake:android-001",
                "open display settings",
                confirmed=True,
                max_rounds=invalid,
            )

            self.assertEqual("failed", task["status"])
            self.assertEqual("INVALID_ARGUMENT", task["error"]["code"])

    async def test_no_progress_exhaustion_does_not_reuse_completed_step_id(self) -> None:
        """M1：轮次预算耗尽时，追加的失败步骤不得复用上一轮已完成步骤的 step_id。"""
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
                        "reason": "Open settings.",
                    },
                    {
                        "decision_type": "run_tool",
                        "tool_id": "navigation.home",
                        "arguments": {},
                        "reason": "Go home without finishing.",
                    },
                ]
            ),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
            navigation_shortcuts_enabled=False,
        )

        task = await runner.run(
            "fake:android-001", "open display settings", confirmed=True, max_rounds=2
        )

        self.assertEqual("failed", task.status.value)
        assert task.error is not None
        self.assertEqual("NO_PROGRESS", task.error["code"])
        self.assertEqual(3, len(task.steps))
        self.assertEqual("failed", task.steps[-1].status.value)
        step_ids = [step.step_id for step in task.steps]
        self.assertEqual(len(step_ids), len(set(step_ids)))
        self.assertGreaterEqual(task.steps[-1].started_at, task.steps[-2].completed_at)

    def test_rule_planner_does_not_hard_fail_within_runner_budget(self) -> None:
        """M2：轮次预算由 Runner 统一把关（MAX_AGENT_ROUNDS）；Planner 不再 >6 轮硬拒。"""
        planner = RuleBasedPlanner()
        summary = AgentObservationSummary(
            observation_id="obs_test",
            foreground_app={"app_id": "com.android.settings", "activity": ".Main"},
            device_state="interactive",
        )

        for round_index in (7, MAX_AGENT_ROUNDS):
            decision = planner.decide("进入显示和亮度页面", summary, round_index)
            self.assertEqual("input.swipe", decision.tool_id)

    async def test_runner_completes_finish_at_round_eight_within_budget(self) -> None:
        """M2：max_rounds=8 时第 7、8 轮正常执行，第 8 轮 finish 成功收尾。"""
        adapter = FakeDeviceAdapter()
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        launch = {
            "decision_type": "run_tool",
            "tool_id": "app.launch",
            "arguments": {"app_id": "com.android.settings"},
            "reason": "Open settings.",
        }
        home = {
            "decision_type": "run_tool",
            "tool_id": "navigation.home",
            "arguments": {},
            "reason": "Return home.",
        }
        finish = {
            "decision_type": "finish",
            "arguments": {
                "expected_selector": {
                    "strategy": "text",
                    "value": "Fake home",
                    "match": "contains",
                }
            },
            "reason": "Back at the home screen.",
        }
        runner = AgentRunner(
            adapter,
            artifacts,
            MockLLMPlanner([launch, home, launch, home, launch, home, home, finish]),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
            navigation_shortcuts_enabled=False,
        )

        task = await runner.run(
            "fake:android-001", "open display settings", confirmed=True, max_rounds=8
        )

        self.assertEqual("succeeded", task.status.value)
        self.assertEqual(8, len(task.steps))
        self.assertEqual("finish", task.steps[-1].result["decision"]["decision_type"])

    async def test_shortcut_acceptance_observe_retries_transient_failure(self) -> None:
        """M3：捷径验收观察走带重试路径，瞬时 UI_TREE_INVALID 不应导致任务失败。"""
        acceptance = AgentGoalAcceptance(foreground_app_id="com.android.settings")

        def build(adapter: DeviceAdapter) -> AgentRunner:
            artifacts = ArtifactStore(Path(self.directory.name))
            tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
            return AgentRunner(
                adapter,
                artifacts,
                RuleBasedPlanner(),
                tools,
                SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
                # 捷径保持默认开启：本用例验证捷径路径的验收观察重试。
            )

        # 探针运行：app.navigate 自身有 before/after 观察，验收观察是最后一次。
        probe = _FailOnObserveCallsAdapter(set())
        probe_task = await build(probe).run(
            "fake:android-001", "打开显示设置", confirmed=True, acceptance=acceptance
        )
        self.assertEqual("succeeded", probe_task.status.value)
        verification_call = probe.observe_calls
        self.assertGreater(verification_call, 1)

        adapter = _FailOnObserveCallsAdapter({verification_call})
        task = await build(adapter).run(
            "fake:android-001", "打开显示设置", confirmed=True, acceptance=acceptance
        )

        self.assertEqual("succeeded", task.status.value)
        self.assertEqual("runtime_shortcut", task.completion_source)
        self.assertEqual(1, adapter.failed_observe_calls)

    async def test_run_skill_acceptance_observe_retries_transient_failure(self) -> None:
        """M3：RUN_SKILL 后的验收观察同样走带重试路径，瞬时故障不应终止任务。"""
        decision = {
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
                    "value": "Display settings",
                    "match": "contains",
                },
            },
            "reason": "Open display settings.",
        }
        acceptance = AgentGoalAcceptance(
            foreground_app_id="com.android.settings",
            foreground_activity=".DisplaySettings",
        )

        def build(adapter: DeviceAdapter) -> AgentRunner:
            artifacts = ArtifactStore(Path(self.directory.name))
            tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
            return AgentRunner(
                adapter,
                artifacts,
                MockLLMPlanner(dict(decision)),
                tools,
                SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
                navigation_shortcuts_enabled=False,
            )

        # 探针运行：确定验收观察是整轮最后一次 observe 调用。
        probe = _FailOnObserveCallsAdapter(set())
        probe_task = await build(probe).run(
            "fake:android-001", "进入显示设置", confirmed=True, acceptance=acceptance
        )
        self.assertEqual("succeeded", probe_task.status.value)
        verification_call = probe.observe_calls

        adapter = _FailOnObserveCallsAdapter({verification_call})
        task = await build(adapter).run(
            "fake:android-001", "进入显示设置", confirmed=True, acceptance=acceptance
        )

        self.assertEqual("succeeded", task.status.value)
        self.assertEqual("runtime_acceptance", task.completion_source)
        self.assertEqual(1, adapter.failed_observe_calls)

    def test_navigation_shortcut_result_predicates(self) -> None:
        """M6：命中导航关键词但含结果类谓词时不走捷径；纯导航目标行为不变。"""
        self.assertEqual(
            NavigationTarget.SETTINGS_DISPLAY, match_navigation_shortcut("打开显示设置")
        )
        self.assertEqual(
            NavigationTarget.SETTINGS_DISPLAY, match_navigation_shortcut("打开显示与亮度页面")
        )
        self.assertEqual(
            NavigationTarget.SETTINGS_BLUETOOTH, match_navigation_shortcut("打开蓝牙设置")
        )
        self.assertIsNone(match_navigation_shortcut("打开显示与亮度页面并告诉我当前亮度值"))
        self.assertIsNone(match_navigation_shortcut("打开WiFi设置，查一下当前连接的SSID"))
        self.assertIsNone(
            match_navigation_shortcut("open display settings and tell me the brightness")
        )

    async def test_result_predicate_goal_bypasses_navigation_shortcut(self) -> None:
        """M6：含结果类谓词的导航目标降级到模型主循环，不被捷径截胡。"""
        adapter = FakeDeviceAdapter()
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        runner = AgentRunner(
            adapter,
            artifacts,
            MockLLMPlanner(
                {
                    "decision_type": "finish",
                    "arguments": {
                        "expected_selector": {
                            "strategy": "text",
                            "value": "Fake home",
                            "match": "contains",
                        },
                        "answer": "当前亮度值为 50%",
                    },
                    "reason": "Report the brightness value.",
                }
            ),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
            # 捷径保持默认开启：含结果谓词的目标应绕过捷径进入 Planner 循环。
        )

        task = await runner.run(
            "fake:android-001", "打开显示与亮度页面并告诉我当前亮度值", confirmed=True
        )

        self.assertEqual("succeeded", task.status.value)
        self.assertEqual("planner_finish", task.completion_source)
        self.assertEqual({"answer": "当前亮度值为 50%"}, task.result)
        self.assertFalse(any(action[0] == "app.navigate" for action in adapter.actions))

    async def test_cancellation_during_blocking_model_call_responds_promptly(self) -> None:
        """M4：阻塞式模型调用进行中发起取消，2s 内到达 cancelled，不等 Provider 返回。"""
        adapter = FakeDeviceAdapter()
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        release = threading.Event()
        self.addCleanup(release.set)
        runner = AgentRunner(
            adapter,
            artifacts,
            _SlowPlanner(release, delay_seconds=30.0),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
            navigation_shortcuts_enabled=False,
        )
        started_at = time.monotonic()

        task = await runner.run(
            "fake:android-001",
            "open display settings",
            confirmed=True,
            cancellation_requested=lambda: time.monotonic() - started_at > 0.5,
        )
        elapsed = time.monotonic() - started_at

        self.assertEqual("cancelled", task.status.value)
        assert task.error is not None
        self.assertEqual("TASK_CANCELLED", task.error["code"])
        self.assertLess(elapsed, 2.0)
        # 取消时无任何已完成模型轮次；被放弃线程的迟到结果不落地。
        self.assertEqual((), task.steps)

    async def test_deadline_during_blocking_model_call_times_out_promptly(self) -> None:
        """M4：Deadline 在阻塞式模型调用期间到期即 timed_out，不等 Provider 返回。"""
        adapter = FakeDeviceAdapter()
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        release = threading.Event()
        self.addCleanup(release.set)
        runner = AgentRunner(
            adapter,
            artifacts,
            _SlowPlanner(release, delay_seconds=30.0),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
            navigation_shortcuts_enabled=False,
        )
        started_at = time.monotonic()

        task = await runner.run(
            "fake:android-001",
            "open display settings",
            confirmed=True,
            deadline_exceeded=lambda: time.monotonic() - started_at > 0.5,
        )
        elapsed = time.monotonic() - started_at

        self.assertEqual("timed_out", task.status.value)
        assert task.error is not None
        self.assertEqual("TASK_DEADLINE_EXCEEDED", task.error["code"])
        self.assertLess(elapsed, 2.0)
        self.assertEqual((), task.steps)

    async def test_shortcut_acceptance_failure_falls_back_to_model_loop(self) -> None:
        """M5：捷径导航成功但验收失败时，shortcut_step 先落盘，任务回退模型主循环继续。"""
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
                        "reason": "Open the settings main page.",
                    },
                    {
                        "decision_type": "finish",
                        "arguments": {
                            "expected_selector": {
                                "strategy": "text",
                                "value": "Display",
                                "match": "exact",
                                "package": "com.android.settings",
                            }
                        },
                        "reason": "The goal is complete.",
                    },
                ]
            ),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
            # 捷径保持默认开启：验收失败应回退到模型主循环而非终结。
        )
        # 捷径到达 .DisplaySettings，与验收要求的 .MainActivity 不符 → TARGET_NOT_FOUND。
        acceptance = AgentGoalAcceptance(
            foreground_app_id="com.android.settings",
            foreground_activity=".MainActivity",
        )

        task = await runner.run(
            "fake:android-001", "打开显示设置", confirmed=True, acceptance=acceptance
        )

        self.assertEqual("succeeded", task.status.value)
        self.assertEqual("runtime_acceptance", task.completion_source)
        self.assertEqual(3, len(task.steps))
        shortcut_step = task.steps[0]
        self.assertEqual("agent.shortcut", shortcut_step.name)
        self.assertEqual("succeeded", shortcut_step.status.value)
        assert shortcut_step.result is not None
        self.assertEqual("app.navigate", shortcut_step.result["skill_id"])
        # 步骤序号在捷径回退后仍单调唯一，不与模型轮次冲突。
        self.assertEqual([1, 2, 3], [step.sequence for step in task.steps])
        self.assertEqual(2, task.evidence_summary["rounds"])
        self.assertTrue(any(action[0] == "app.navigate" for action in adapter.actions))
        self.assertTrue(any(action[0] == "app.launch" for action in adapter.actions))

    async def test_shortcut_step_preserved_when_fallback_task_fails(self) -> None:
        """M5：回退后模型循环仍失败时，报告保留 shortcut_step 作为设备副作用证据。"""
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
                )
            ),
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
            # 捷径保持默认开启：验收失败回退后模型不可用，任务失败但证据保留。
        )
        acceptance = AgentGoalAcceptance(
            foreground_app_id="com.android.settings",
            foreground_activity=".MainActivity",
        )

        task = await runner.run(
            "fake:android-001", "打开显示设置", confirmed=True, acceptance=acceptance
        )

        self.assertEqual("failed", task.status.value)
        assert task.error is not None
        self.assertEqual("MODEL_UNAVAILABLE", task.error["code"])
        self.assertEqual(2, len(task.steps))
        shortcut_step = task.steps[0]
        self.assertEqual("agent.shortcut", shortcut_step.name)
        self.assertEqual("succeeded", shortcut_step.status.value)
        assert shortcut_step.result is not None
        self.assertEqual("app.navigate", shortcut_step.result["skill_id"])
        self.assertTrue(any(action[0] == "app.navigate" for action in adapter.actions))

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


_SKELETON_UI_XML = (
    b'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
    b'<node text="" resource-id="" class="android.widget.FrameLayout" '
    b'package="com.example.app" clickable="false" enabled="true" '
    b'visible-to-user="true" bounds="[0,0][2,3]"/></hierarchy>'
)


class _CountingPlanner:
    """Record how many times decide() runs; used to prove empty trees skip the Planner."""

    def __init__(self, inner: Planner) -> None:
        self._inner = inner
        self.calls = 0

    @property
    def planner_id(self) -> str:
        return self._inner.planner_id

    def decide(
        self, goal: str, observation: AgentObservationSummary, round_index: int
    ) -> AgentDecision:
        self.calls += 1
        return self._inner.decide(goal, observation, round_index)


class _EmptyThenPopulatedAdapter:
    """First N observes return a skeleton dump; afterwards delegate to FakeDeviceAdapter.

    empty_observations=None means every observe stays empty.
    """

    def __init__(self, empty_observations: int | None) -> None:
        self.observe_calls = 0
        self._empty_observations = empty_observations
        self._inner = FakeDeviceAdapter()

    async def observe(self, device_id: str, artifacts: ArtifactWriter) -> Observation:
        self.observe_calls += 1
        if (
            self._empty_observations is None
            or self.observe_calls <= self._empty_observations
        ):
            self._inner.custom_ui_xml = _SKELETON_UI_XML
        else:
            self._inner.custom_ui_xml = None
        return await self._inner.observe(device_id, artifacts)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _FlakyObserveAdapter:
    """Adapter whose observe raises a device error for a bounded number of calls.

    failures=None 表示 observe 始终失败；其余方法委托给 FakeDeviceAdapter，
    以便观察恢复后任务能够继续完成。
    """

    def __init__(self, failures: int | None, code: str = "UI_TREE_INVALID") -> None:
        self.observe_calls = 0
        self.failed_observe_calls = 0
        self._failures = failures
        self._code = code
        self._inner = FakeDeviceAdapter()

    async def observe(self, device_id: str, artifacts: ArtifactWriter) -> Observation:
        self.observe_calls += 1
        if self._failures is None or self.observe_calls <= self._failures:
            self.failed_observe_calls += 1
            raise MobileAgentError(
                code=self._code,
                category=ErrorCategory.DEVICE,
                message="注入的观察故障",
            )
        return await self._inner.observe(device_id, artifacts)

    async def list_devices(self) -> list[Device]:
        return await self._inner.list_devices()

    async def launch_app(self, device_id: str, app_id: str) -> None:
        await self._inner.launch_app(device_id, app_id)

    async def press_back(self, device_id: str) -> None:
        await self._inner.press_back(device_id)

    async def press_home(self, device_id: str) -> None:
        await self._inner.press_home(device_id)

    async def tap(self, device_id: str, x: int, y: int) -> None:
        await self._inner.tap(device_id, x, y)

    async def swipe(
        self, device_id: str, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int
    ) -> None:
        await self._inner.swipe(device_id, start_x, start_y, end_x, end_y, duration_ms)

    async def input_text(self, device_id: str, text: str) -> None:
        await self._inner.input_text(device_id, text)

    async def list_installed_apps(self, device_id: str) -> tuple[str, ...]:
        return await self._inner.list_installed_apps(device_id)

    async def inspect_installed_app(self, device_id: str, app_id: str) -> InstalledApp:
        return await self._inner.inspect_installed_app(device_id, app_id)

    async def install_apk(self, device_id: str, apk_path: Path, replace_existing: bool) -> None:
        await self._inner.install_apk(device_id, apk_path, replace_existing)

    async def uninstall_app(self, device_id: str, app_id: str, keep_data: bool) -> None:
        await self._inner.uninstall_app(device_id, app_id, keep_data)

    async def inspect_app_runtime_state(self, device_id: str, app: InstalledApp) -> AppRuntimeState:
        return await self._inner.inspect_app_runtime_state(device_id, app)

    async def force_stop_app(self, device_id: str, app_id: str) -> None:
        await self._inner.force_stop_app(device_id, app_id)

    async def clear_app_data(self, device_id: str, app_id: str) -> None:
        await self._inner.clear_app_data(device_id, app_id)

    async def collect_logs(self, device_id: str, max_lines: int, minimum_level: DeviceLogLevel) -> bytes:
        return await self._inner.collect_logs(device_id, max_lines, minimum_level)

    async def capture_performance(self, device_id: str) -> DevicePerformanceSnapshot:
        return await self._inner.capture_performance(device_id)


class _FailOnObserveCallsAdapter:
    """在指定 observe 调用序号注入一次瞬时观察故障，其余方法委托 FakeDeviceAdapter。

    用于验证捷径验收与 RUN_SKILL 验收的观察路径同样享有有界重试；
    fail_on_calls 为空集时退化为纯计数探针。
    """

    def __init__(self, fail_on_calls: set[int], code: str = "UI_TREE_INVALID") -> None:
        self.observe_calls = 0
        self.failed_observe_calls = 0
        self._fail_on_calls = frozenset(fail_on_calls)
        self._code = code
        self._inner = FakeDeviceAdapter()

    async def observe(self, device_id: str, artifacts: ArtifactWriter) -> Observation:
        self.observe_calls += 1
        if self.observe_calls in self._fail_on_calls:
            self.failed_observe_calls += 1
            raise MobileAgentError(
                code=self._code,
                category=ErrorCategory.DEVICE,
                message="注入的观察故障",
            )
        return await self._inner.observe(device_id, artifacts)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _SlowPlanner:
    """模拟慢速 Provider 的阻塞式 Planner：decide 在 release 前挂起，纯等待无副作用。

    用于复现 M4：取消/Deadline 在模型调用进行中到达时，不应等到调用返回才生效。
    """

    planner_id = "slow.preview"

    def __init__(self, release: threading.Event, delay_seconds: float) -> None:
        self._release = release
        self._delay_seconds = delay_seconds

    def decide(
        self, goal: str, observation: AgentObservationSummary, round_index: int
    ) -> AgentDecision:
        """Block until released or the delay elapses, then return a finish decision."""

        self._release.wait(self._delay_seconds)
        return AgentDecision(
            decision_id="decision_slow",
            decision_type=AgentDecisionType.FINISH,
            skill_id="",
            tool_id="",
            arguments={
                "expected_selector": {
                    "strategy": "text",
                    "value": "Fake home",
                    "match": "contains",
                }
            },
            reason="The slow provider finally responded.",
            planner_id=self.planner_id,
            confidence=1.0,
            source="llm",
        )


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


_RESULT_PAGE_XML = (
    b'<?xml version="1.0"?><hierarchy>'
    b'<node text="ResultPage" resource-id="result_title" class="android.widget.TextView" '
    b'package="com.example.fake" clickable="false" enabled="true" '
    b'visible-to-user="true" bounds="[0,0][2,1]"/>'
    b"</hierarchy>"
)


class AgentRunnerMemoryResultTests(unittest.IsolatedAsyncioTestCase):
    """ITER-0061：跨轮工作记忆（scratchpad）与结构化任务结果（answer）。"""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _build(self, adapter: FakeDeviceAdapter, planner: MockLLMPlanner) -> AgentRunner:
        adapter.custom_ui_xml = _RESULT_PAGE_XML
        artifacts = ArtifactStore(Path(self.directory.name))
        tools = ToolRuntime(adapter, artifacts, ToolRegistry(), PolicyEngine())
        return AgentRunner(
            adapter,
            artifacts,
            planner,
            tools,
            SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)),
            navigation_shortcuts_enabled=False,
        )

    @staticmethod
    def _finish(arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "decision_type": "finish",
            "arguments": {
                "expected_selector": {
                    "strategy": "text",
                    "value": "ResultPage",
                    "match": "exact",
                    "package": "com.example.fake",
                },
                **(arguments or {}),
            },
            "reason": "Done.",
        }

    async def test_scratchpad_flows_into_next_round_and_answer_persists(self) -> None:
        adapter = FakeDeviceAdapter()
        runner = self._build(
            adapter,
            MockLLMPlanner(
                [
                    {
                        "decision_type": "run_tool",
                        "tool_id": "navigation.back",
                        "arguments": {},
                        "reason": "记录后返回。",
                        "scratchpad": "京东 iPhone 17 到手价 ¥5999",
                    },
                    self._finish({"answer": "京东 iPhone 17 到手价 ¥5999"}),
                ]
            ),
        )

        task = await runner.run("fake:android-001", "查价并带回", confirmed=True)

        self.assertEqual("succeeded", task.status.value)
        # 第 1 轮摘要尚无记忆；第 2 轮摘要携带第 1 轮写入的 scratchpad。
        self.assertIsNone(task.steps[0].result["observation"]["scratchpad"])
        self.assertEqual(
            "京东 iPhone 17 到手价 ¥5999",
            task.steps[1].result["observation"]["scratchpad"],
        )
        self.assertEqual({"answer": "京东 iPhone 17 到手价 ¥5999"}, task.result)
        self.assertEqual(
            "京东 iPhone 17 到手价 ¥5999", task.to_dict()["result"]["answer"]
        )

    async def test_scratchpad_empty_string_clears(self) -> None:
        adapter = FakeDeviceAdapter()
        runner = self._build(
            adapter,
            MockLLMPlanner(
                [
                    {
                        "decision_type": "run_tool",
                        "tool_id": "navigation.back",
                        "arguments": {},
                        "scratchpad": "临时笔记",
                    },
                    {
                        "decision_type": "run_tool",
                        "tool_id": "navigation.home",
                        "arguments": {},
                        "scratchpad": "",
                    },
                    self._finish(),
                ]
            ),
        )

        task = await runner.run("fake:android-001", "写入后清空", confirmed=True)

        self.assertEqual("succeeded", task.status.value)
        self.assertEqual("临时笔记", task.steps[1].result["observation"]["scratchpad"])
        self.assertIsNone(task.steps[2].result["observation"]["scratchpad"])

    async def test_finish_without_answer_leaves_result_absent(self) -> None:
        adapter = FakeDeviceAdapter()
        runner = self._build(adapter, MockLLMPlanner([self._finish()]))

        task = await runner.run("fake:android-001", "纯操作", confirmed=True)

        self.assertEqual("succeeded", task.status.value)
        self.assertIsNone(task.result)
        self.assertNotIn("result", task.to_dict())

    async def test_scratchpad_does_not_leak_across_tasks(self) -> None:
        adapter = FakeDeviceAdapter()
        planner = MockLLMPlanner(
            [
                {
                    "decision_type": "run_tool",
                    "tool_id": "navigation.back",
                    "arguments": {},
                    "scratchpad": "上一任务的笔记",
                },
                self._finish(),
            ]
        )
        runner = self._build(adapter, planner)

        first = await runner.run("fake:android-001", "任务一", confirmed=True)
        second = await runner.run("fake:android-001", "任务二", confirmed=True)

        self.assertEqual("succeeded", first.status.value)
        self.assertEqual("succeeded", second.status.value)
        # 第二个任务的首轮摘要不携带上一任务的 scratchpad。
        self.assertIsNone(second.steps[0].result["observation"]["scratchpad"])
