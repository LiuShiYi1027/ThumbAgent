from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from email.message import Message
from http import HTTPStatus
from types import SimpleNamespace

from mobile_agent.api.idempotency import stable_idempotency_key
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
        self.assertIn("collectDiagnosticBundle", TASK_UI_HTML)
        self.assertIn("/v1/tasks/device.diagnostics.bundle/async", TASK_UI_HTML)
        self.assertIn('id="localStorageCard"', TASK_UI_HTML)
        self.assertIn("/v1/storage?retention_days=", TASK_UI_HTML)
        self.assertIn("/v1/storage/cleanup/prepare", TASK_UI_HTML)
        self.assertIn("/v1/tasks/local.data.cleanup/async", TASK_UI_HTML)
        self.assertIn("globalThis.confirm", TASK_UI_HTML)
        self.assertIn("artifactAvailabilitySummary", TASK_UI_HTML)
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
        self.assertIn("provider_attempt_count", TASK_UI_HTML)
        self.assertIn("provider_latency_ms", TASK_UI_HTML)
        self.assertIn("failure_phase", TASK_UI_HTML)
        self.assertIn("total_elapsed_ms", TASK_UI_HTML)
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

    def test_get_ui_without_token_returns_unauthorized(self) -> None:
        for path in ("/ui", "/ui/"):
            with self.subTest(path=path):
                handler, captured = _ui_get_handler(path)

                handler.do_GET()

                self.assertEqual(HTTPStatus.UNAUTHORIZED, captured["status"])
                payload = captured["payload"]
                assert isinstance(payload, dict)
                self.assertEqual("UNAUTHORIZED", payload["error"]["code"])
                self.assertNotIn("html", captured)
                self.assertNotIn("test-token", json.dumps(payload, ensure_ascii=False))

    def test_get_ui_with_wrong_token_returns_unauthorized(self) -> None:
        handler, captured = _ui_get_handler("/ui?token=wrong-token")

        handler.do_GET()

        self.assertEqual(HTTPStatus.UNAUTHORIZED, captured["status"])
        self.assertNotIn("html", captured)

    def test_get_ui_with_valid_token_serves_embedded_page(self) -> None:
        handler, captured = _ui_get_handler("/ui?token=test-token")

        handler.do_GET()

        self.assertEqual(HTTPStatus.OK, captured["status"])
        html = captured["html"]
        assert isinstance(html, str)
        self.assertIn(json.dumps("test-token"), html)
        self.assertNotIn("__MOBILE_AGENT_API_TOKEN__", html)

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


def _ui_get_handler(path: str) -> tuple[RuntimeRequestHandler, dict[str, object]]:
    handler = object.__new__(RuntimeRequestHandler)
    handler.path = path
    handler.headers = Message()
    handler.headers["Host"] = "127.0.0.1:8765"
    handler.server = SimpleNamespace(api_token="test-token")
    captured: dict[str, object] = {}
    handler._write_html = lambda status, html: captured.update(
        {"status": status, "html": html}
    )
    handler._write_json = lambda status, payload: captured.update(
        {"status": status, "payload": payload}
    )
    return handler, captured


def _extract_idempotency_block() -> str:
    """提取内嵌 JS 中与服务端同算法的幂等键派生实现。"""

    match = re.search(
        r"// idempotency-key-derivation:start\n(?P<body>.*?)// idempotency-key-derivation:end",
        TASK_UI_HTML,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("TASK_UI_HTML 缺少幂等键派生实现标记块")
    return match.group("body")


class WebUiIdempotencyKeyTests(unittest.TestCase):
    """Web UI 幂等键：与服务端 stable_idempotency_key 同算法（webui- 前缀）。"""

    def test_embedded_js_uses_stable_webui_derivation(self) -> None:
        self.assertNotIn("newIdempotencyKey", TASK_UI_HTML)
        block = _extract_idempotency_block()
        self.assertIn("crypto.subtle.digest", block)
        self.assertIn('"SHA-256"', block)
        self.assertIn("webui-", block)
        self.assertIn("TextEncoder", block)
        # 与服务端 canonical JSON 对齐：键排序 + 紧凑分隔符
        self.assertIn(".sort()", block)
        # 5 个提交点都改为 await 派生稳定键（crypto.subtle.digest 是 async）
        self.assertEqual(5, TASK_UI_HTML.count("await stableIdempotencyKey("))

    @unittest.skipUnless(shutil.which("node"), "node 不可用，跳过跨语言一致性")
    def test_js_derivation_matches_server_for_shared_vectors(self) -> None:
        vectors = [
            (
                "/v1/tasks/agent.run/async",
                {
                    "goal": "打开设置",
                    "device_id": "adb:001",
                    "confirmed": True,
                    "max_rounds": 6,
                    "deadline_seconds": 600,
                },
            ),
            (
                "/v1/tasks/device.logs.collect/async",
                {
                    "device_id": "adb:001",
                    "max_lines": 500,
                    "minimum_level": "info",
                    "confirmed": True,
                    "deadline_seconds": 60,
                },
            ),
            (
                "/v1/tasks/device.performance.snapshot/async",
                {"device_id": "adb:001", "deadline_seconds": 90},
            ),
            (
                "/v1/tasks/local.data.cleanup/async",
                {
                    "approval_id": "approval_0123456789abcdef",
                    "confirmed": True,
                    "deadline_seconds": 120,
                },
            ),
            (
                "/v1/tasks/settings.scroll_navigate/async",
                {
                    "device_id": "adb:001",
                    "target_selector": {
                        "value": "亮度",
                        "strategy": "text",
                        "match": "contains",
                    },
                },
            ),
        ]
        script = (
            _extract_idempotency_block()
            + "\nconst vectors = JSON.parse(require('fs').readFileSync(0, 'utf8'));\n"
            + "(async () => {\n"
            + "  const out = [];\n"
            + "  for (const { endpoint, params } of vectors) {\n"
            + "    out.push(await stableIdempotencyKey(endpoint, params));\n"
            + "    out.push(await stableIdempotencyKey(endpoint, params));\n"
            + "  }\n"
            + "  process.stdout.write(JSON.stringify(out));\n"
            + "})().catch((error) => { console.error(error); process.exit(1); });\n"
        )
        completed = subprocess.run(
            ["node", "-e", script],
            input=json.dumps(
                [{"endpoint": endpoint, "params": params} for endpoint, params in vectors]
            ),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        js_keys = json.loads(completed.stdout)
        self.assertEqual(2 * len(vectors), len(js_keys))
        for index, (endpoint, params) in enumerate(vectors):
            with self.subTest(endpoint=endpoint):
                expected = stable_idempotency_key("webui", endpoint, params)
                first, second = js_keys[2 * index : 2 * index + 2]
                self.assertEqual(first, second, "同参数两次调用必须派生同一键")
                self.assertEqual(expected, first)
        self.assertNotEqual(js_keys[0], js_keys[2], "异参数必须派生异键")


class _FakeWriter:
    def __init__(self) -> None:
        self.data = b""

    def write(self, data: bytes) -> None:
        self.data += data
