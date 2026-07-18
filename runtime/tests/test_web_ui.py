from __future__ import annotations

import unittest
from http import HTTPStatus

from mobile_agent.api.server import RuntimeRequestHandler
from mobile_agent.web import TASK_UI_HTML


class WebUiTests(unittest.TestCase):
    def test_task_ui_contains_history_and_report_shell(self) -> None:
        self.assertIn("Mobile Agent Tasks", TASK_UI_HTML)
        self.assertIn('id="tasks"', TASK_UI_HTML)
        self.assertIn('id="detail"', TASK_UI_HTML)
        self.assertIn('id="runDemo"', TASK_UI_HTML)
        self.assertIn('id="runAgent"', TASK_UI_HTML)
        self.assertIn('id="cancelExecution"', TASK_UI_HTML)
        self.assertIn('id="compileGoal"', TASK_UI_HTML)
        self.assertIn('id="runCompiledGoal"', TASK_UI_HTML)
        self.assertIn('id="goalDraft"', TASK_UI_HTML)
        self.assertIn('id="agentGoal"', TASK_UI_HTML)
        self.assertIn('id="resetGoal"', TASK_UI_HTML)
        self.assertIn('id="deviceSelect"', TASK_UI_HTML)
        self.assertIn('id="modelProviderCard"', TASK_UI_HTML)
        self.assertIn('id="modelProviderStatus"', TASK_UI_HTML)
        self.assertIn('id="readinessCard"', TASK_UI_HTML)
        self.assertIn('id="readinessStatus"', TASK_UI_HTML)
        self.assertIn("/v1/readiness", TASK_UI_HTML)
        self.assertIn("readinessStateLabel", TASK_UI_HTML)
        self.assertIn("当前没有可执行任务的设备", TASK_UI_HTML)
        self.assertIn('id="deviceCards"', TASK_UI_HTML)
        self.assertIn('id="deviceInspection"', TASK_UI_HTML)
        self.assertIn("loadDeviceInspection", TASK_UI_HTML)
        self.assertIn("/inspection", TASK_UI_HTML)
        self.assertIn("renderCapability", TASK_UI_HTML)
        self.assertIn('id="collectLogs"', TASK_UI_HTML)
        self.assertIn('id="logLevel"', TASK_UI_HTML)
        self.assertIn("collectDeviceLogs", TASK_UI_HTML)
        self.assertIn("/v1/tasks/device.logs.collect/async", TASK_UI_HTML)
        self.assertIn("日志采集任务", TASK_UI_HTML)
        self.assertIn('id="capturePerformance"', TASK_UI_HTML)
        self.assertIn("captureDevicePerformance", TASK_UI_HTML)
        self.assertIn("/v1/tasks/device.performance.snapshot/async", TASK_UI_HTML)
        self.assertIn("性能快照任务", TASK_UI_HTML)
        self.assertIn("/v1/performance-comparisons", TASK_UI_HTML)
        self.assertIn("bindPerformanceComparison", TASK_UI_HTML)
        self.assertIn("两点快照只表示方向", TASK_UI_HTML)
        self.assertIn("模型 Provider", TASK_UI_HTML)
        self.assertIn("modelProviderStateLabel", TASK_UI_HTML)
        self.assertIn("modelProviderHelp", TASK_UI_HTML)
        self.assertIn("已接入模型 Planner", TASK_UI_HTML)
        self.assertIn("模型配置不可用", TASK_UI_HTML)
        self.assertIn("MOBILE_AGENT_MODEL_SECRET_*", TASK_UI_HTML)
        self.assertIn("Skill allowlist", TASK_UI_HTML)
        self.assertIn("/v1/tasks?limit=50", TASK_UI_HTML)
        self.assertIn("/v1/model-provider/status", TASK_UI_HTML)
        self.assertIn("/v1/tasks/settings.scroll_navigate/run", TASK_UI_HTML)
        self.assertIn("/v1/tasks/agent.run", TASK_UI_HTML)
        self.assertIn("/v1/tasks/agent.run/async", TASK_UI_HTML)
        self.assertIn("/v1/task-executions/", TASK_UI_HTML)
        self.assertIn("Idempotency-Key", TASK_UI_HTML)
        self.assertIn("deadline_seconds: 600", TASK_UI_HTML)
        self.assertIn("deadline_at", TASK_UI_HTML)
        self.assertIn("device_session_id", TASK_UI_HTML)
        self.assertIn("timed_out", TASK_UI_HTML)
        self.assertIn("实时事件", TASK_UI_HTML)
        self.assertIn("cancelExecution", TASK_UI_HTML)
        self.assertIn("/v1/goals/compile", TASK_UI_HTML)
        self.assertIn("goal_spec_confirmed", TASK_UI_HTML)
        self.assertIn("确认前不会操作设备", TASK_UI_HTML)
        self.assertIn("运行 Agent Preview", TASK_UI_HTML)
        self.assertIn("请选择设备并输入目标", TASK_UI_HTML)
        self.assertIn("max_rounds: 6", TASK_UI_HTML)
        self.assertIn("Authorization", TASK_UI_HTML)
        self.assertIn("显示/亮度", TASK_UI_HTML)
        self.assertIn('value: "亮度"', TASK_UI_HTML)
        self.assertIn('match: "contains"', TASK_UI_HTML)
        self.assertIn("distance_percent: 0.35", TASK_UI_HTML)
        self.assertIn("duration_ms: 900", TASK_UI_HTML)
        self.assertIn("renderStepDecision", TASK_UI_HTML)
        self.assertIn("renderActionFeedback", TASK_UI_HTML)
        self.assertIn("Decision:", TASK_UI_HTML)
        self.assertIn("页面进展", TASK_UI_HTML)
        self.assertIn("confidence", TASK_UI_HTML)
        self.assertIn("repair_count", TASK_UI_HTML)
        self.assertIn("模型修复", TASK_UI_HTML)
        self.assertIn("provider_retry_count", TASK_UI_HTML)
        self.assertIn("Provider 重试", TASK_UI_HTML)
        self.assertIn("renderErrorDiagnostics", TASK_UI_HTML)
        self.assertIn("completion_source", TASK_UI_HTML)
        self.assertIn("goal_acceptance", TASK_UI_HTML)
        self.assertIn("goal_spec", TASK_UI_HTML)
        self.assertIn("完成来源", TASK_UI_HTML)
        self.assertIn("failure_kind", TASK_UI_HTML)
        self.assertIn("safe_top", TASK_UI_HTML)
        self.assertIn("selector_error_field", TASK_UI_HTML)
        self.assertIn("selector_unknown_keys", TASK_UI_HTML)
        self.assertIn("诊断：", TASK_UI_HTML)
        self.assertIn("/events", TASK_UI_HTML)

    def test_write_html_uses_safe_headers(self) -> None:
        handler = object.__new__(RuntimeRequestHandler)
        captured: dict[str, object] = {"headers": []}

        def send_response(status: int) -> None:
            captured["status"] = status

        def send_header(name: str, value: str) -> None:
            headers = captured["headers"]
            assert isinstance(headers, list)
            headers.append((name, value))

        handler.send_response = send_response
        handler.send_header = send_header
        handler.end_headers = lambda: None
        handler.wfile = _FakeWriter()

        handler._write_html(HTTPStatus.OK, "<h1>ok</h1>")

        self.assertEqual(200, captured["status"])
        self.assertIn(("Content-Type", "text/html; charset=utf-8"), captured["headers"])
        self.assertIn(("Cache-Control", "no-store"), captured["headers"])
        self.assertEqual(b"<h1>ok</h1>", handler.wfile.data)


class _FakeWriter:
    def __init__(self) -> None:
        self.data = b""

    def write(self, data: bytes) -> None:
        self.data += data
