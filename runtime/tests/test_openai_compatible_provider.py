from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import patch

from mobile_agent.agent import AgentObservationSummary
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.providers import (
    HttpModelTransport,
    OpenAICompatiblePlanner,
    OpenAICompatiblePlannerConfig,
)


class OpenAICompatiblePlannerTests(unittest.TestCase):
    def test_compiler_builds_reviewable_goal_spec_without_tool_path(self) -> None:
        transport = FakeTransport(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "execution_goal": "打开系统设置，找到蓝牙入口并进入蓝牙页面",
                                    "assumptions": ["蓝牙指系统设置页面"],
                                    "confidence": 0.91,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }
        )
        planner = OpenAICompatiblePlanner(test_config(), transport)

        spec = planner.compile("进入蓝牙设置页面")

        self.assertEqual("进入蓝牙设置页面", spec.source_goal)
        self.assertEqual("llm", spec.source)
        self.assertTrue(spec.confirmation_required)
        self.assertNotIn("observation", transport.last_body["messages"][1]["content"])
        self.assertNotIn("test-secret-token", json.dumps(transport.last_body))

    def test_compiler_rejects_model_tool_calls(self) -> None:
        transport = FakeTransport(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "execution_goal": "进入蓝牙页面",
                                    "assumptions": [],
                                    "confidence": 0.8,
                                    "tool_calls": ["input.tap"],
                                }
                            )
                        }
                    }
                ]
            }
        )

        with self.assertRaises(MobileAgentError) as raised:
            OpenAICompatiblePlanner(test_config(), transport).compile("进入蓝牙设置页面")

        self.assertEqual("MODEL_OUTPUT_INVALID", raised.exception.code)

    def test_planner_builds_request_and_parses_valid_structured_response(self) -> None:
        transport = FakeTransport(valid_response())
        planner = OpenAICompatiblePlanner(test_config(), transport)

        decision = planner.decide("open display settings", observation_summary(), 1)

        self.assertEqual("settings.scroll_navigate", decision.skill_id)
        self.assertEqual("openai_compatible.preview", decision.planner_id)
        self.assertEqual("llm", decision.source)
        self.assertEqual(0.72, decision.confidence)
        self.assertEqual("https://model.example/v1/chat/completions", transport.last_url)
        self.assertEqual("Bearer test-secret-token", transport.last_headers["Authorization"])
        self.assertEqual("test-model", transport.last_body["model"])
        user_message = transport.last_body["messages"][1]["content"]
        self.assertIn("open display settings", user_message)
        self.assertIn("obs_test", user_message)
        self.assertNotIn("test-secret-token", json.dumps(transport.last_body))

    def test_invalid_non_json_content_returns_model_output_invalid_without_token(self) -> None:
        transport = FakeTransport(
            {
                "choices": [
                    {
                        "message": {
                            "content": "not-json",
                        }
                    }
                ]
            }
        )
        planner = OpenAICompatiblePlanner(test_config(), transport)

        with self.assertRaises(MobileAgentError) as raised:
            planner.decide("open display settings", observation_summary(), 1)

        self.assertEqual("MODEL_OUTPUT_INVALID", raised.exception.code)
        self.assertNotIn("test-secret-token", str(raised.exception.to_dict()))
        self.assertIn("response_id", raised.exception.details)
        self.assertEqual(8, raised.exception.details["content_chars"])
        self.assertEqual("not-json", raised.exception.details["content_preview"])

    def test_invalid_decision_payload_includes_safe_shape_diagnostics(self) -> None:
        transport = FakeTransport(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "decision_type": "run_skill",
                                    "skill_id": "settings.scroll_navigate",
                                    "arguments": {"target": {"text": "亮度"}},
                                    "reason": "missing selectors",
                                },
                                ensure_ascii=False,
                            ),
                        }
                    }
                ]
            }
        )
        planner = OpenAICompatiblePlanner(test_config(), transport)

        with self.assertRaises(MobileAgentError) as raised:
            planner.decide("进入显示和亮度页面", observation_summary(), 1)

        details = raised.exception.details
        self.assertEqual("MODEL_OUTPUT_INVALID", raised.exception.code)
        self.assertEqual(["arguments", "decision_type", "reason", "skill_id"], details["payload_keys"])
        self.assertEqual(["target"], details["argument_keys"])
        self.assertEqual("settings.scroll_navigate", details["payload_summary"]["skill_id"])
        self.assertNotIn("test-secret-token", str(raised.exception.to_dict()))

    def test_planner_accepts_markdown_fenced_json_content(self) -> None:
        transport = FakeTransport(
            {
                "choices": [
                    {
                        "message": {
                            "content": "```json\n"
                            + json.dumps(valid_payload(), ensure_ascii=False)
                            + "\n```",
                        }
                    }
                ]
            }
        )
        planner = OpenAICompatiblePlanner(test_config(), transport)

        decision = planner.decide("进入显示和亮度页面", observation_summary(), 1)

        self.assertEqual("settings.scroll_navigate", decision.skill_id)
        self.assertEqual("llm", decision.source)

    def test_planner_accepts_decision_wrapped_content(self) -> None:
        transport = FakeTransport(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"decision": valid_payload()},
                                ensure_ascii=False,
                            ),
                        }
                    }
                ]
            }
        )
        planner = OpenAICompatiblePlanner(test_config(), transport)

        decision = planner.decide("进入显示和亮度页面", observation_summary(), 1)

        self.assertEqual("settings.scroll_navigate", decision.skill_id)
        self.assertEqual(0.72, decision.confidence)

    def test_transport_failure_maps_to_model_unavailable_without_token(self) -> None:
        transport = FailingTransport()
        planner = OpenAICompatiblePlanner(test_config(), transport)

        with self.assertRaises(MobileAgentError) as raised:
            planner.decide("open display settings", observation_summary(), 1)

        self.assertEqual("MODEL_UNAVAILABLE", raised.exception.code)
        self.assertEqual("connection", raised.exception.details["failure_kind"])
        self.assertEqual(1, raised.exception.details["provider_retry_count"])
        self.assertEqual(2, transport.calls)
        self.assertNotIn("test-secret-token", str(raised.exception.to_dict()))

    def test_provider_retries_one_transient_request_without_device_action(self) -> None:
        transport = SequencedTransport([OSError("temporary network failure"), valid_response()])
        planner = OpenAICompatiblePlanner(test_config(), transport)

        decision = planner.decide("open display settings", observation_summary(), 1)

        self.assertEqual(1, decision.provider_retry_count)
        self.assertEqual(2, len(transport.bodies))

    def test_http_transport_preserves_safe_timeout_diagnostics(self) -> None:
        transport = HttpModelTransport()

        with patch(
            "mobile_agent.providers.openai_compatible.urlopen",
            side_effect=TimeoutError("secret test-secret-token"),
        ):
            with self.assertRaises(MobileAgentError) as raised:
                transport.post_json(
                    "https://model.example/v1/chat/completions",
                    {"Authorization": "Bearer test-secret-token"},
                    {"model": "m"},
                    30,
                )

        self.assertEqual("MODEL_UNAVAILABLE", raised.exception.code)
        self.assertTrue(raised.exception.retryable)
        self.assertEqual("timeout", raised.exception.details["failure_kind"])
        self.assertNotIn("test-secret-token", str(raised.exception.to_dict()))

    def test_provider_allows_bounded_multi_rounds(self) -> None:
        planner = OpenAICompatiblePlanner(test_config(), FakeTransport(valid_response()))

        decision = planner.decide("open display settings", observation_summary(), 2)

        self.assertEqual("settings.scroll_navigate", decision.skill_id)

    def test_request_includes_last_action_feedback_for_replanning(self) -> None:
        transport = FakeTransport(valid_response())
        planner = OpenAICompatiblePlanner(test_config(), transport)
        summary = AgentObservationSummary(
            observation_id="obs_test",
            foreground_app={"app_id": "com.android.settings", "activity": ".Main"},
            device_state="interactive",
            last_action_feedback={
                "schema_version": "1.0.0",
                "tool_id": "input.swipe",
                "arguments": {"direction": "up"},
                "effect": "unchanged",
                "basis": "ui_tree_and_foreground",
                "message": "页面未产生可观察变化；请调整动作或方向。",
            },
        )

        planner.decide("open display settings", summary, 3)

        user_message = transport.last_body["messages"][1]["content"]
        self.assertIn('"effect":"unchanged"', user_message)
        self.assertIn('"direction":"up"', user_message)

    def test_request_uses_already_redacted_observation_summary(self) -> None:
        transport = FakeTransport(valid_response())
        planner = OpenAICompatiblePlanner(test_config(), transport)
        summary = AgentObservationSummary(
            observation_id="obs_test",
            foreground_app={"app_id": "com.android.settings", "activity": ".Main"},
            device_state="interactive",
            ui_summary=(
                {
                    "text": "[REDACTED_PHONE]",
                    "content_description": "",
                    "resource_id": "android:id/title",
                    "class_name": "android.widget.TextView",
                    "clickable": False,
                    "clickable_ancestor": True,
                    "enabled": True,
                },
            ),
            ui_summary_total_candidates=1,
            ui_summary_truncated=False,
        )

        planner.decide("open display settings", summary, 2)

        user_message = transport.last_body["messages"][1]["content"]
        self.assertIn("[REDACTED_PHONE]", user_message)
        self.assertNotIn("150******20", user_message)

    def test_provider_rejects_rounds_outside_budget(self) -> None:
        planner = OpenAICompatiblePlanner(test_config(), FakeTransport(valid_response()))

        with self.assertRaises(MobileAgentError) as raised:
            planner.decide("open display settings", observation_summary(), 7)

        self.assertEqual("NO_PROGRESS", raised.exception.code)

    def test_provider_repairs_invalid_tool_arguments_once_without_device_action(self) -> None:
        invalid = {
            "decision_type": "run_tool",
            "tool_id": "input.tap_element",
            "arguments": {
                "selector": {
                    "strategy": "text",
                    "value": "显示和亮度",
                    "match": "contains",
                }
            },
            "reason": "Tap the visible target.",
        }
        valid = {
            **invalid,
            "arguments": {
                "selector": {
                    **invalid["arguments"]["selector"],
                    "resolve_clickable_ancestor": True,
                }
            },
        }
        transport = SequencedTransport([response_for(invalid), response_for(valid)])
        planner = OpenAICompatiblePlanner(test_config(), transport)

        decision = planner.decide("进入显示和亮度页面", observation_summary(), 1)

        self.assertEqual(2, len(transport.bodies))
        self.assertEqual(1, decision.repair_count)
        self.assertTrue(decision.arguments["selector"]["resolve_clickable_ancestor"])
        repair_message = transport.bodies[1]["messages"][-1]["content"]
        self.assertIn("MODEL_OUTPUT_INVALID", repair_message)
        self.assertIn("resolve_clickable_ancestor", repair_message)
        self.assertIn('"selector_error_field"', repair_message)
        self.assertNotIn("test-secret-token", json.dumps(transport.bodies))

    def test_missing_reason_does_not_trigger_model_repair(self) -> None:
        payload = valid_payload()
        payload.pop("reason")
        transport = SequencedTransport([response_for(payload)])
        planner = OpenAICompatiblePlanner(test_config(), transport)

        decision = planner.decide("进入显示和亮度页面", observation_summary(), 1)

        self.assertEqual("模型未提供决策说明。", decision.reason)
        self.assertEqual(1, len(transport.bodies))
        self.assertEqual(0, decision.repair_count)

    def test_invalid_payload_summary_omits_selector_value(self) -> None:
        sensitive_value = "private-screen-text-123"
        invalid = {
            "decision_type": "finish",
            "arguments": {
                "expected_selector": {
                    "strategy": "text",
                    "value": sensitive_value,
                    "match": "exact",
                    "package": "com.android.settings",
                }
            },
            "reason": {"unexpected": True},
        }
        planner = OpenAICompatiblePlanner(
            test_config(),
            SequencedTransport([response_for(invalid), response_for(invalid)]),
        )

        with self.assertRaises(MobileAgentError) as raised:
            planner.decide("进入显示和亮度页面", observation_summary(), 1)

        selector_summary = raised.exception.details["payload_summary"]["expected_selector"]
        self.assertNotIn("value", selector_summary)
        self.assertNotIn(sensitive_value, str(raised.exception.to_dict()))


class FakeTransport:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.last_url = ""
        self.last_headers: dict[str, str] = {}
        self.last_body: dict[str, Any] = {}
        self.last_timeout = 0.0

    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        self.last_url = url
        self.last_headers = dict(headers)
        self.last_body = dict(body)
        self.last_timeout = timeout_seconds
        return self._response


class SequencedTransport:
    def __init__(self, responses: list[dict[str, Any] | Exception]) -> None:
        self._responses = list(responses)
        self.bodies: list[dict[str, Any]] = []

    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        self.bodies.append(dict(body))
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FailingTransport:
    def __init__(self) -> None:
        self.calls = 0

    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        self.calls += 1
        raise OSError("network unavailable with secret test-secret-token")


def test_config() -> OpenAICompatiblePlannerConfig:
    return OpenAICompatiblePlannerConfig(
        base_url="https://model.example/v1",
        model="test-model",
        api_key="test-secret-token",
        timeout_seconds=12.5,
    )


def observation_summary() -> AgentObservationSummary:
    return AgentObservationSummary(
        observation_id="obs_test",
        foreground_app={"app_id": "com.example.fake", "activity": ".Main"},
        device_state="interactive",
    )


def valid_response() -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(valid_payload())
                }
            }
        ]
    }


def response_for(payload: dict[str, Any]) -> dict[str, Any]:
    return {"choices": [{"message": {"content": json.dumps(payload)}}]}


def valid_payload() -> dict[str, Any]:
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
        },
        "reason": "The user wants to open display settings.",
        "confidence": 0.72,
    }
