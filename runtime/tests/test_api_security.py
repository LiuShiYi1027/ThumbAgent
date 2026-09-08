from __future__ import annotations

import asyncio
import re
import unittest
import threading
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import NoReturn

from mobile_agent.api.server import RuntimeRequestHandler
from mobile_agent.api.server import _TOOL_INVOKE_ROUTE
from mobile_agent.api.server import _query_int
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.artifact import ArtifactKind, ArtifactWriter
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.task import TaskRun, TaskStatus
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.goals import AgentGoalSpec
from mobile_agent.providers import ModelProviderSettings
from mobile_agent.runtime import RuntimeService
from mobile_agent.tasks.execution import (
    ExecutionStatus,
    InMemoryTaskExecutionStore,
    TaskExecution,
)


class ApiSecurityTests(unittest.TestCase):
    def test_post_async_agent_run_returns_accepted_execution(self) -> None:
        store = _ApiExecutionStore()
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(),
                ArtifactStore(Path(directory)),
                task_execution_store=store,
            )
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/tasks/agent.run/async"
            headers = Message()
            headers["Host"] = "127.0.0.1:8765"
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = "Bearer test-token"
            handler.headers = headers
            handler.server = SimpleNamespace(
                runtime=runtime,
                api_token="test-token",
                allowed_origins=frozenset(),
                server_port=8765,
            )
            handler._read_json = lambda: {
                "device_id": "fake:android-001",
                "goal": "open display settings",
                "confirmed": True,
            }
            captured: dict[str, object] = {}
            handler._write_json = lambda status, payload: captured.update(
                {"status": status, "payload": payload}
            )

            handler.do_POST()
            self.assertTrue(store.terminal.wait(2), "async API task did not finish")

        self.assertEqual(HTTPStatus.ACCEPTED, captured["status"])
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual("queued", payload["execution"]["status"])
        self.assertRegex(payload["execution"]["task_id"], r"^task_[a-f0-9]{32}$")

    def test_post_async_agent_run_max_rounds_boundary(self) -> None:
        """max_rounds 接受 1–50（含 50），拒绝 0 与 51。"""

        def post(max_rounds: object) -> tuple[HTTPStatus, dict[str, object], bool]:
            store = _ApiExecutionStore()
            with TemporaryDirectory() as directory:
                runtime = RuntimeService(
                    FakeDeviceAdapter(),
                    ArtifactStore(Path(directory)),
                    task_execution_store=store,
                )
                handler = object.__new__(RuntimeRequestHandler)
                handler.path = "/v1/tasks/agent.run/async"
                headers = Message()
                headers["Host"] = "127.0.0.1:8765"
                headers["Content-Type"] = "application/json"
                headers["Authorization"] = "Bearer test-token"
                handler.headers = headers
                handler.server = SimpleNamespace(
                    runtime=runtime,
                    api_token="test-token",
                    allowed_origins=frozenset(),
                    server_port=8765,
                )
                handler._read_json = lambda: {
                    "device_id": "fake:android-001",
                    "goal": "open display settings",
                    "confirmed": True,
                    "max_rounds": max_rounds,
                }
                captured: dict[str, object] = {}
                handler._write_json = lambda status, payload: captured.update(
                    {"status": status, "payload": payload}
                )

                handler.do_POST()
                finished = store.terminal.wait(2) if captured["status"] == HTTPStatus.ACCEPTED else False

            return captured["status"], captured["payload"], finished

        status, payload, finished = post(50)
        self.assertEqual(HTTPStatus.ACCEPTED, status)
        self.assertTrue(finished, "max_rounds=50 的异步任务未完成")

        for invalid in (0, 51):
            status, payload, _ = post(invalid)
            self.assertEqual(HTTPStatus.BAD_REQUEST, status)
            self.assertEqual("INVALID_ARGUMENT", payload["error"]["code"])

    def test_post_compiles_goal_without_device_action(self) -> None:
        adapter = FakeDeviceAdapter()
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                adapter,
                ArtifactStore(Path(directory)),
                goal_compiler=FakeGoalCompiler(),
            )
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/goals/compile"
            headers = Message()
            headers["Host"] = "127.0.0.1:8765"
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = "Bearer test-token"
            handler.headers = headers
            handler.server = SimpleNamespace(
                runtime=runtime,
                api_token="test-token",
                allowed_origins=frozenset(),
                server_port=8765,
            )
            handler._read_json = lambda: {"goal": "进入蓝牙设置页面"}
            captured: dict[str, object] = {}
            handler._write_json = lambda status, payload: captured.update(
                {"status": status, "payload": payload}
            )

            handler.do_POST()

        self.assertEqual(HTTPStatus.OK, captured["status"])
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual("llm", payload["goal_spec"]["source"])
        self.assertEqual([], adapter.actions)

    def _authorize(self, headers: dict[str, str]) -> tuple[bool, HTTPStatus | None]:
        handler = object.__new__(RuntimeRequestHandler)
        message = Message()
        for name, value in headers.items():
            message[name] = value
        handler.headers = message
        handler.server = SimpleNamespace(
            api_token="test-token",
            allowed_origins=frozenset({"tauri://localhost"}),
            server_port=8765,
        )
        captured: list[HTTPStatus] = []
        handler._write_json = lambda status, payload: captured.append(status)
        allowed = handler._authorize_post()
        return allowed, captured[0] if captured else None

    def test_post_requires_json_and_bearer_token(self) -> None:
        allowed, status = self._authorize({"Content-Type": "text/plain"})
        self.assertFalse(allowed)
        self.assertEqual(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, status)

        allowed, status = self._authorize({"Content-Type": "application/json"})
        self.assertFalse(allowed)
        self.assertEqual(HTTPStatus.UNAUTHORIZED, status)

    def test_post_rejects_web_origin_and_allows_tauri_or_cli(self) -> None:
        base = {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-token",
        }
        allowed, status = self._authorize({**base, "Origin": "https://evil.example"})
        self.assertFalse(allowed)
        self.assertEqual(HTTPStatus.FORBIDDEN, status)

        self.assertEqual((True, None), self._authorize({**base, "Origin": "tauri://localhost"}))
        self.assertEqual((True, None), self._authorize(base))

        allowed, status = self._authorize({**base, "Origin": "http://127.0.0.1:8765"})
        self.assertTrue(allowed)
        self.assertIsNone(status)

    def test_query_int_accepts_single_bounded_value(self) -> None:
        self.assertEqual(20, _query_int("", "limit", 20))
        self.assertEqual(5, _query_int("limit=5", "limit", 20))
        with self.assertRaises(ValueError):
            _query_int("limit=0", "limit", 20)
        with self.assertRaises(ValueError):
            _query_int("limit=101", "limit", 20)
        with self.assertRaises(ValueError):
            _query_int("limit=abc", "limit", 20)

    def _artifact_get_handler(
        self,
        directory: str,
        path: str,
        token: str | None,
    ) -> tuple[RuntimeRequestHandler, dict[str, object]]:
        handler = object.__new__(RuntimeRequestHandler)
        handler.path = path
        headers = Message()
        headers["Host"] = "127.0.0.1:8765"
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        handler.headers = headers
        handler.server = SimpleNamespace(
            runtime=RuntimeService(FakeDeviceAdapter(), ArtifactStore(Path(directory))),
            api_token="test-token",
            allowed_origins=frozenset(),
            server_port=8765,
        )
        captured: dict[str, object] = {}
        handler._write_json = lambda status, payload: captured.update(
            {"status": status, "payload": payload}
        )
        handler._write_png = lambda status, body: captured.update(
            {"status": status, "png": body}
        )
        return handler, captured

    def test_get_artifact_content_requires_token(self) -> None:
        with TemporaryDirectory() as directory:
            for token in (None, "wrong-token"):
                handler, captured = self._artifact_get_handler(
                    directory, f"/v1/artifacts/artifact_{'0' * 32}/content", token
                )

                handler.do_GET()

                self.assertEqual(HTTPStatus.UNAUTHORIZED, captured["status"])
                self.assertEqual("UNAUTHORIZED", captured["payload"]["error"]["code"])

    def test_get_artifact_content_serves_screenshot_png(self) -> None:
        data = b"\x89PNG\r\n\x1a\n" + b"fixture-image-body"
        with TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory))
            artifact = store.write(ArtifactKind.SCREENSHOT, "image/png", data, ".png")
            handler, captured = self._artifact_get_handler(
                directory, f"/v1/artifacts/{artifact.artifact_id}/content", "test-token"
            )

            handler.do_GET()

        self.assertEqual(HTTPStatus.OK, captured["status"])
        self.assertEqual(data, captured["png"])

    def test_get_artifact_content_unknown_id_returns_404(self) -> None:
        with TemporaryDirectory() as directory:
            handler, captured = self._artifact_get_handler(
                directory, f"/v1/artifacts/artifact_{'f' * 32}/content", "test-token"
            )

            handler.do_GET()

        self.assertEqual(HTTPStatus.NOT_FOUND, captured["status"])
        self.assertEqual("ARTIFACT_NOT_FOUND", captured["payload"]["error"]["code"])

    def test_get_artifact_content_rejects_non_id_path(self) -> None:
        with TemporaryDirectory() as directory:
            handler, captured = self._artifact_get_handler(
                directory, "/v1/artifacts/../../etc/passwd/content", "test-token"
            )

            handler.do_GET()

        # 不匹配内容端点路由，落入通用 404；且不触发任何文件读取
        self.assertEqual(HTTPStatus.NOT_FOUND, captured["status"])
        self.assertEqual("RESOURCE_NOT_FOUND", captured["payload"]["error"]["code"])

    def test_get_model_provider_status_returns_redacted_payload(self) -> None:
        with TemporaryDirectory() as directory:
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/model-provider/status"
            handler.headers = _loopback_host_headers()
            handler.server = SimpleNamespace(
                runtime=RuntimeService(
                    FakeDeviceAdapter(),
                    ArtifactStore(Path(directory)),
                    model_provider_settings=ModelProviderSettings(
                        enabled=True,
                        provider="openai_compatible",
                        base_url="https://model.example/v1",
                        model="test-model",
                        api_key_ref="model-key",
                    ),
                )
            )
            captured: dict[str, object] = {}

            def write_json(status: HTTPStatus, payload: object) -> None:
                captured["status"] = status
                captured["payload"] = payload

            handler._write_json = write_json

            handler.do_GET()

        self.assertEqual(HTTPStatus.OK, captured["status"])
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        model_provider = payload["model_provider"]
        self.assertTrue(model_provider["enabled"])
        self.assertEqual("openai_compatible", model_provider["provider"])
        self.assertTrue(model_provider["api_key_ref_configured"])
        self.assertNotIn("model-key", str(model_provider))

    def test_get_readiness_returns_renderable_device_snapshot(self) -> None:
        with TemporaryDirectory() as directory:
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/readiness"
            handler.headers = _loopback_host_headers()
            handler.server = SimpleNamespace(
                runtime=RuntimeService(
                    FakeDeviceAdapter(), ArtifactStore(Path(directory))
                )
            )
            captured: dict[str, object] = {}
            handler._write_json = lambda status, payload: captured.update(
                {"status": status, "payload": payload}
            )

            handler.do_GET()

        self.assertEqual(HTTPStatus.OK, captured["status"])
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual("ready", payload["readiness"]["status"])
        self.assertEqual(
            "ready", payload["readiness"]["devices"][0]["status"]
        )

    def test_get_device_inspection_decodes_id_and_returns_capabilities(self) -> None:
        with TemporaryDirectory() as directory:
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/devices/fake%3Aandroid-001/inspection"
            handler.headers = _loopback_host_headers()
            handler.server = SimpleNamespace(
                runtime=RuntimeService(
                    FakeDeviceAdapter(), ArtifactStore(Path(directory))
                )
            )
            captured: dict[str, object] = {}
            handler._write_json = lambda status, payload: captured.update(
                {"status": status, "payload": payload}
            )

            handler.do_GET()

        self.assertEqual(HTTPStatus.OK, captured["status"])
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual(
            "fake:android-001",
            payload["inspection"]["availability"]["device"]["device_id"],
        )
        self.assertEqual(20, len(payload["inspection"]["capabilities"]))

    def test_get_app_inventory_is_bounded_and_supports_prefix(self) -> None:
        with TemporaryDirectory() as directory:
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/devices/fake%3Aandroid-001/apps?limit=500&prefix=com.example"
            handler.headers = _loopback_host_headers()
            handler.server = SimpleNamespace(
                runtime=RuntimeService(
                    FakeDeviceAdapter(), ArtifactStore(Path(directory))
                )
            )
            captured: dict[str, object] = {}
            handler._write_json = lambda status, payload: captured.update(
                {"status": status, "payload": payload}
            )

            handler.do_GET()

        self.assertEqual(HTTPStatus.OK, captured["status"])
        inventory = captured["payload"]["inventory"]
        self.assertEqual(["com.example.fake"], [app["app_id"] for app in inventory["apps"]])
        self.assertFalse(inventory["truncated"])

    def test_get_app_inventory_rejects_blank_or_unknown_query(self) -> None:
        for query in ("prefix=", "unknown=value"):
            with self.subTest(query=query), TemporaryDirectory() as directory:
                handler = object.__new__(RuntimeRequestHandler)
                handler.path = f"/v1/devices/fake%3Aandroid-001/apps?{query}"
                handler.headers = _loopback_host_headers()
                handler.server = SimpleNamespace(
                    runtime=RuntimeService(
                        FakeDeviceAdapter(), ArtifactStore(Path(directory))
                    )
                )
                captured: dict[str, object] = {}
                handler._write_json = lambda status, payload: captured.update(
                    {"status": status, "payload": payload}
                )

                handler.do_GET()

            self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])

    def test_post_collects_confirmed_bounded_device_logs(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/skills/device.logs.collect/invoke"
            headers = Message()
            headers["Host"] = "127.0.0.1:8765"
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = "Bearer test-token"
            handler.headers = headers
            handler.server = SimpleNamespace(
                runtime=runtime,
                api_token="test-token",
                allowed_origins=frozenset(),
                server_port=8765,
            )
            handler._read_json = lambda: {
                "device_id": "fake:android-001",
                "max_lines": 100,
                "minimum_level": "warn",
                "confirmed": True,
            }
            captured: dict[str, object] = {}
            handler._write_json = lambda status, payload: captured.update(
                {"status": status, "payload": payload}
            )

            handler.do_POST()

        self.assertEqual(HTTPStatus.OK, captured["status"])
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual("device.logs.collect", payload["result"]["skill_id"])
        self.assertNotIn("user@example.com", str(payload))

    def test_post_device_logs_rejects_non_string_level(self) -> None:
        with TemporaryDirectory() as directory:
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/skills/device.logs.collect/invoke"
            headers = Message()
            headers["Host"] = "127.0.0.1:8765"
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = "Bearer test-token"
            handler.headers = headers
            handler.server = SimpleNamespace(
                runtime=RuntimeService(
                    FakeDeviceAdapter(), ArtifactStore(Path(directory))
                ),
                api_token="test-token",
                allowed_origins=frozenset(),
                server_port=8765,
            )
            handler._read_json = lambda: {
                "device_id": "fake:android-001",
                "minimum_level": ["info"],
                "confirmed": True,
            }
            captured: dict[str, object] = {}
            handler._write_json = lambda status, payload: captured.update(
                {"status": status, "payload": payload}
            )

            handler.do_POST()

        self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])

    def test_post_async_device_logs_returns_accepted_execution(self) -> None:
        store = _ApiExecutionStore()
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(),
                ArtifactStore(Path(directory)),
                task_execution_store=store,
            )
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/tasks/device.logs.collect/async"
            headers = Message()
            headers["Host"] = "127.0.0.1:8765"
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = "Bearer test-token"
            headers["Idempotency-Key"] = "api-log-task"
            handler.headers = headers
            handler.server = SimpleNamespace(
                runtime=runtime,
                api_token="test-token",
                allowed_origins=frozenset(),
                server_port=8765,
            )
            handler._read_json = lambda: {
                "device_id": "fake:android-001",
                "max_lines": 100,
                "minimum_level": "info",
                "confirmed": True,
                "deadline_seconds": 60,
            }
            captured: dict[str, object] = {}
            handler._write_json = lambda status, payload: captured.update(
                {"status": status, "payload": payload}
            )

            handler.do_POST()
            self.assertTrue(store.terminal.wait(2), "async log API task did not finish")

        self.assertEqual(HTTPStatus.ACCEPTED, captured["status"])
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual("device.logs.collect", payload["execution"]["task_type"])

    def test_post_performance_snapshot_returns_aggregate_result(self) -> None:
        with TemporaryDirectory() as directory:
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/skills/device.performance.snapshot/invoke"
            headers = Message()
            headers["Host"] = "127.0.0.1:8765"
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = "Bearer test-token"
            handler.headers = headers
            handler.server = SimpleNamespace(
                runtime=RuntimeService(
                    FakeDeviceAdapter(), ArtifactStore(Path(directory))
                ),
                api_token="test-token",
                allowed_origins=frozenset(),
                server_port=8765,
            )
            handler._read_json = lambda: {"device_id": "fake:android-001"}
            captured: dict[str, object] = {}
            handler._write_json = lambda status, payload: captured.update(
                {"status": status, "payload": payload}
            )

            handler.do_POST()

        self.assertEqual(HTTPStatus.OK, captured["status"])
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual(
            12.5, payload["result"]["snapshot"]["cpu"]["total_usage_percent"]
        )

    def test_post_async_performance_returns_accepted_execution(self) -> None:
        store = _ApiExecutionStore()
        with TemporaryDirectory() as directory:
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/tasks/device.performance.snapshot/async"
            headers = Message()
            headers["Host"] = "127.0.0.1:8765"
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = "Bearer test-token"
            headers["Idempotency-Key"] = "api-performance"
            handler.headers = headers
            handler.server = SimpleNamespace(
                runtime=RuntimeService(
                    FakeDeviceAdapter(),
                    ArtifactStore(Path(directory)),
                    task_execution_store=store,
                ),
                api_token="test-token",
                allowed_origins=frozenset(),
                server_port=8765,
            )
            handler._read_json = lambda: {
                "device_id": "fake:android-001",
                "deadline_seconds": 90,
            }
            captured: dict[str, object] = {}
            handler._write_json = lambda status, payload: captured.update(
                {"status": status, "payload": payload}
            )

            handler.do_POST()
            self.assertTrue(store.terminal.wait(2), "performance API task did not finish")

        self.assertEqual(HTTPStatus.ACCEPTED, captured["status"])
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual(
            "device.performance.snapshot", payload["execution"]["task_type"]
        )

    def test_post_performance_rejects_unknown_input_field(self) -> None:
        with TemporaryDirectory() as directory:
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/skills/device.performance.snapshot/invoke"
            headers = Message()
            headers["Host"] = "127.0.0.1:8765"
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = "Bearer test-token"
            handler.headers = headers
            handler.server = SimpleNamespace(
                runtime=RuntimeService(
                    FakeDeviceAdapter(), ArtifactStore(Path(directory))
                ),
                api_token="test-token",
                allowed_origins=frozenset(),
                server_port=8765,
            )
            handler._read_json = lambda: {
                "device_id": "fake:android-001",
                "raw_command": "dumpsys all",
            }
            captured: dict[str, object] = {}
            handler._write_json = lambda status, payload: captured.update(
                {"status": status, "payload": payload}
            )

            handler.do_POST()

        self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])

    def test_post_evaluates_stored_task_without_replaying_device_actions(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )
            _, task_payload = runtime.run_agent_task_sync(
                "fake:android-001", "open display settings", confirmed=True
            )
            task_id = task_payload["task"]["task_id"]
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = f"/v1/tasks/{task_id}/evaluate"
            headers = Message()
            headers["Host"] = "127.0.0.1:8765"
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = "Bearer test-token"
            handler.headers = headers
            handler.server = SimpleNamespace(
                runtime=runtime,
                api_token="test-token",
                allowed_origins=frozenset(),
                server_port=8765,
            )
            handler._read_json = lambda: {
                "scenario": {
                    "schema_version": "1.0.0",
                    "scenario_id": "settings.display.live.v1",
                    "goal": "open display settings",
                    "acceptance": {"foreground_app_id": "com.android.settings"},
                    "forbidden_tools": [],
                    "max_rounds": 6,
                }
            }
            captured: dict[str, object] = {}

            def write_json(status: HTTPStatus, payload: object) -> None:
                captured["status"] = status
                captured["payload"] = payload

            handler._write_json = write_json

            handler.do_POST()

        self.assertEqual(HTTPStatus.OK, captured["status"])
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertTrue(payload["evaluation"]["passed"])

    def test_post_agent_run_accepts_runtime_owned_acceptance(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(),
                ArtifactStore(Path(directory)),
                navigation_shortcuts_enabled=False,
            )
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/tasks/agent.run"
            headers = Message()
            headers["Host"] = "127.0.0.1:8765"
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = "Bearer test-token"
            handler.headers = headers
            handler.server = SimpleNamespace(
                runtime=runtime,
                api_token="test-token",
                allowed_origins=frozenset(),
                server_port=8765,
            )
            handler._read_json = lambda: {
                "device_id": "fake:android-001",
                "goal": "open display settings",
                "confirmed": True,
                "acceptance": {
                    "foreground_app_id": "com.android.settings",
                    "foreground_activity": ".DisplaySettings",
                    "expected_selector": {
                        "strategy": "resource_id",
                        "value": "settings_title",
                        "match": "exact",
                        "package": "com.android.settings",
                    },
                },
            }
            captured: dict[str, object] = {}
            handler._write_json = lambda status, payload: captured.update(
                {"status": status, "payload": payload}
            )

            handler.do_POST()

        self.assertEqual(HTTPStatus.OK, captured["status"])
        payload = captured["payload"]
        self.assertIsInstance(payload, dict)
        self.assertEqual(
            "runtime_acceptance", payload["task"]["completion_source"]
        )

    def test_invalid_runtime_acceptance_is_rejected_before_device_action(self) -> None:
        adapter = FakeDeviceAdapter()
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(adapter, ArtifactStore(Path(directory)))

            status, payload = runtime.run_agent_task_sync(
                "fake:android-001",
                "open display settings",
                confirmed=True,
                acceptance={},
            )

        self.assertEqual(HTTPStatus.BAD_REQUEST, status)
        self.assertEqual("INVALID_ARGUMENT", payload["error"]["code"])
        self.assertEqual([], adapter.actions)

    def test_post_performance_comparison_validates_and_forwards_task_ids(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = _PerformanceComparisonRuntime(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/performance-comparisons"
            headers = Message()
            headers["Host"] = "127.0.0.1:8765"
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = "Bearer test-token"
            handler.headers = headers
            handler.server = SimpleNamespace(
                runtime=runtime,
                api_token="test-token",
                allowed_origins=frozenset(),
                server_port=8765,
            )
            baseline = "task_11111111111111111111111111111111"
            candidate = "task_22222222222222222222222222222222"
            handler._read_json = lambda: {
                "baseline_task_id": baseline,
                "candidate_task_id": candidate,
            }
            captured: dict[str, object] = {}
            handler._write_json = lambda status, payload: captured.update(
                {"status": status, "payload": payload}
            )

            handler.do_POST()

        self.assertEqual(HTTPStatus.OK, captured["status"])
        self.assertEqual((baseline, candidate), runtime.arguments)

    def test_post_performance_comparison_rejects_unknown_fields(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = _PerformanceComparisonRuntime(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/performance-comparisons"
            headers = Message()
            headers["Host"] = "127.0.0.1:8765"
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = "Bearer test-token"
            handler.headers = headers
            handler.server = SimpleNamespace(
                runtime=runtime,
                api_token="test-token",
                allowed_origins=frozenset(),
                server_port=8765,
            )
            handler._read_json = lambda: {
                "baseline_task_id": "task_11111111111111111111111111111111",
                "candidate_task_id": "task_22222222222222222222222222222222",
                "raw": True,
            }
            captured: dict[str, object] = {}
            handler._write_json = lambda status, payload: captured.update(
                {"status": status, "payload": payload}
            )

            handler.do_POST()

        self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])
        self.assertIsNone(runtime.arguments)

    def test_pause_and_resume_require_bearer_token(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )
            for action in ("pause", "resume"):
                captured = _post_execution_control(
                    runtime,
                    f"/v1/task-executions/task_00000000000000000000000000000009/{action}",
                    token=None,
                    body={},
                )
                self.assertEqual(HTTPStatus.UNAUTHORIZED, captured["status"])

    def test_pause_and_resume_unknown_task_return_not_found(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )
            for action in ("pause", "resume"):
                captured = _post_execution_control(
                    runtime,
                    f"/v1/task-executions/task_00000000000000000000000000000009/{action}",
                    token="test-token",
                    body={},
                )
                self.assertEqual(HTTPStatus.NOT_FOUND, captured["status"])

    def test_pause_rejects_non_empty_body(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )
            captured = _post_execution_control(
                runtime,
                "/v1/task-executions/task_00000000000000000000000000000009/pause",
                token="test-token",
                body={"note": "unexpected"},
            )
            self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])

    def test_pause_then_resume_running_task_returns_accepted(self) -> None:
        """端点链路：RUNNING 任务 pause/resume 均 202 且翻转 pause_requested。"""
        store = _ApiExecutionStore()
        probing = threading.Event()
        release = threading.Event()

        async def hold(
            task_id: str,
            on_step: object,
            cancelled: object,
            deadline_exceeded: object,
        ) -> TaskRun:
            probing.set()
            await asyncio.to_thread(release.wait)
            cancelled()
            return TaskRun(
                task_id=task_id,
                task_type="agent.run",
                device_id="fake:android-001",
                goal="hold",
                status=TaskStatus.SUCCEEDED,
                started_at="2026-08-20T00:00:00Z",
                completed_at="2026-08-20T00:00:01Z",
                steps=(),
                evidence_summary={},
            )

        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(),
                ArtifactStore(Path(directory)),
                task_execution_store=store,
            )
            execution = runtime._task_executor.submit(
                "fake:android-001", "hold", hold, lambda task: None
            )
            self.addCleanup(release.set)
            self.assertTrue(probing.wait(2), "task did not start")

            paused = _post_execution_control(
                runtime,
                f"/v1/task-executions/{execution.task_id}/pause",
                token="test-token",
                body={},
            )
            self.assertEqual(HTTPStatus.ACCEPTED, paused["status"])
            self.assertTrue(paused["payload"]["execution"]["pause_requested"])

            resumed = _post_execution_control(
                runtime,
                f"/v1/task-executions/{execution.task_id}/resume",
                token="test-token",
                body={},
            )
            self.assertEqual(HTTPStatus.ACCEPTED, resumed["status"])
            self.assertFalse(resumed["payload"]["execution"]["pause_requested"])

            release.set()
            self.assertTrue(store.terminal.wait(2), "held task did not finish")


class FakeGoalCompiler:
    compiler_id = "test.goal-compiler"

    def compile(self, goal: str) -> AgentGoalSpec:
        return AgentGoalSpec(
            source_goal=goal,
            execution_goal="打开系统设置，找到蓝牙入口并进入蓝牙设置页面",
            assumptions=("蓝牙指系统设置页面",),
            confidence=0.9,
            compiler_id=self.compiler_id,
            source="llm",
            confirmation_required=True,
        )


class _PerformanceComparisonRuntime(RuntimeService):
    def __init__(
        self, adapter: FakeDeviceAdapter, artifacts: ArtifactStore
    ) -> None:
        super().__init__(adapter, artifacts)
        self.arguments: tuple[str, str] | None = None

    def compare_device_performance_sync(
        self, baseline_task_id: str, candidate_task_id: str
    ) -> tuple[HTTPStatus, dict[str, object]]:
        self.arguments = (baseline_task_id, candidate_task_id)
        return HTTPStatus.OK, {"comparison": {"schema_version": "1.0.0"}}


class _ApiExecutionStore(InMemoryTaskExecutionStore):
    def __init__(self) -> None:
        super().__init__()
        self.terminal = threading.Event()

    def save_execution(self, execution: TaskExecution) -> None:
        super().save_execution(execution)
        if execution.status in {
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.TIMED_OUT,
        }:
            self.terminal.set()


def _post_execution_control(
    runtime: RuntimeService, path: str, token: str | None, body: dict[str, object]
) -> dict[str, object]:
    """以可控输入驱动 do_POST 的暂停/恢复路由并捕获响应。"""

    handler = object.__new__(RuntimeRequestHandler)
    handler.path = path
    headers = Message()
    headers["Host"] = "127.0.0.1:8765"
    headers["Content-Type"] = "application/json"
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    handler.headers = headers
    handler.server = SimpleNamespace(
        runtime=runtime,
        api_token="test-token",
        allowed_origins=frozenset(),
        server_port=8765,
    )
    handler._read_json = lambda: body
    captured: dict[str, object] = {}
    handler._write_json = lambda status, payload: captured.update(
        {"status": status, "payload": payload}
    )
    handler.do_POST()
    return captured


_LOOPBACK_HOST = "127.0.0.1:8765"
_INTERFACE_ERROR_KEYS = {
    "code",
    "category",
    "message",
    "retryable",
    "outcome",
    "suggested_action",
    "details",
}


def _loopback_host_headers() -> Message:
    """直连 handler 的测试默认携带 loopback Host 头（对齐真实 HTTP 客户端）。"""

    message = Message()
    message["Host"] = _LOOPBACK_HOST
    return message


def _driven_handler(
    runtime: RuntimeService,
    path: str,
    *,
    host: str | None = _LOOPBACK_HOST,
    token: str | None = "test-token",
    content_type: str = "application/json",
    body: dict[str, object] | None = None,
) -> tuple[RuntimeRequestHandler, dict[str, object]]:
    """构造直连 do_GET/do_POST 的 handler 并捕获 JSON 响应。"""

    handler = object.__new__(RuntimeRequestHandler)
    handler.path = path
    headers = Message()
    if host is not None:
        headers["Host"] = host
    if body is not None:
        headers["Content-Type"] = content_type
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
    handler.headers = headers
    handler.server = SimpleNamespace(
        runtime=runtime,
        api_token="test-token",
        allowed_origins=frozenset(),
        server_port=8765,
    )
    if body is not None:
        handler._read_json = lambda: body
    captured: dict[str, object] = {}
    handler._write_json = lambda status, payload: captured.update(
        {"status": status, "payload": payload}
    )
    return handler, captured


class HostHeaderValidationTests(unittest.TestCase):
    """H2：所有请求校验 Host 头，非 loopback 一律 403（DNS rebinding 防线）。"""

    def test_get_accepts_loopback_host_on_any_port(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )
            for host in (
                "127.0.0.1:8765",
                "127.0.0.1:1",
                "localhost",
                "localhost:8765",
                "[::1]",
                "[::1]:8765",
            ):
                with self.subTest(host=host):
                    handler, captured = _driven_handler(
                        runtime, "/v1/health", host=host
                    )
                    handler.do_GET()
                    self.assertEqual(HTTPStatus.OK, captured["status"])

    def test_get_rejects_foreign_or_malformed_host(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )
            for host in (
                "evil.com",
                "127.0.0.1.evil.com",
                "evil.com:8765",
                "127.0.0.1:",
                None,
            ):
                with self.subTest(host=host):
                    handler, captured = _driven_handler(
                        runtime, "/v1/health", host=host
                    )
                    handler.do_GET()
                    self.assertEqual(HTTPStatus.FORBIDDEN, captured["status"])
                    payload = captured["payload"]
                    self.assertIsInstance(payload, dict)
                    self.assertEqual(
                        "HOST_NOT_ALLOWED", payload["error"]["code"]
                    )
                    self.assertEqual(
                        _INTERFACE_ERROR_KEYS, set(payload["error"])
                    )

    def test_post_rejects_foreign_host_despite_valid_token(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )
            handler, captured = _driven_handler(
                runtime,
                "/v1/goals/compile",
                host="evil.com:8765",
                body={"goal": "进入蓝牙设置"},
            )
            handler.do_POST()
        self.assertEqual(HTTPStatus.FORBIDDEN, captured["status"])
        self.assertEqual(
            "HOST_NOT_ALLOWED", captured["payload"]["error"]["code"]
        )


class ToolInvokeRouteTests(unittest.TestCase):
    """H3：工具 invoke 路由必须覆盖所有广告的 direct_invocation 工具。"""

    def test_tool_invoke_route_matches_underscored_tool_id(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )
            handler, captured = _driven_handler(
                runtime,
                "/v1/tools/input.tap_element/invoke",
                body={
                    "device_id": "fake:missing",
                    "arguments": {},
                    "confirmed": True,
                },
            )
            handler.do_POST()

        # 路由匹配后进入执行层，未知设备报 DEVICE_NOT_FOUND；
        # 修复前路由正则不含下划线，落入通用 RESOURCE_NOT_FOUND。
        self.assertEqual(HTTPStatus.NOT_FOUND, captured["status"])
        self.assertEqual(
            "DEVICE_NOT_FOUND", captured["payload"]["error"]["code"]
        )

    def test_every_advertised_direct_invocable_tool_matches_route(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )
            tools = runtime.list_tools()
        direct = [tool["tool_id"] for tool in tools if tool["direct_invocation"]]
        self.assertIn("input.tap_element", direct)
        for tool_id in direct:
            with self.subTest(tool_id=tool_id):
                self.assertIsNotNone(
                    re.fullmatch(_TOOL_INVOKE_ROUTE, f"/v1/tools/{tool_id}/invoke"),
                    f"{tool_id} 的 invoke 路径不匹配路由正则",
                )


class InterfaceErrorEnvelopeTests(unittest.TestCase):
    """M10：接口层错误与 domain 错误共用同一完整信封形状。"""

    def test_post_interface_errors_use_full_envelope(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )

            handler, captured = _driven_handler(
                runtime, "/v1/no-such-endpoint", body={"device_id": "fake:android-001"}
            )
            handler.do_POST()
            self.assertEqual(HTTPStatus.NOT_FOUND, captured["status"])
            self.assertEqual(
                _INTERFACE_ERROR_KEYS, set(captured["payload"]["error"])
            )
            self.assertEqual(
                "RESOURCE_NOT_FOUND", captured["payload"]["error"]["code"]
            )

            handler, captured = _driven_handler(
                runtime,
                "/v1/tasks/agent.run",
                body={"device_id": "fake:android-001", "goal": 1},
            )
            handler.do_POST()
            self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])
            self.assertEqual(
                _INTERFACE_ERROR_KEYS, set(captured["payload"]["error"])
            )
            self.assertEqual(
                "INVALID_ARGUMENT", captured["payload"]["error"]["code"]
            )

            handler, captured = _driven_handler(
                runtime,
                "/v1/no-such-endpoint",
                token=None,
                body={"device_id": "fake:android-001"},
            )
            handler.do_POST()
            self.assertEqual(HTTPStatus.UNAUTHORIZED, captured["status"])
            self.assertEqual(
                _INTERFACE_ERROR_KEYS, set(captured["payload"]["error"])
            )
            self.assertEqual(
                "UNAUTHORIZED", captured["payload"]["error"]["code"]
            )

            handler, captured = _driven_handler(
                runtime,
                "/v1/no-such-endpoint",
                content_type="text/plain",
                body={"device_id": "fake:android-001"},
            )
            handler.do_POST()
            self.assertEqual(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE, captured["status"]
            )
            self.assertEqual(
                _INTERFACE_ERROR_KEYS, set(captured["payload"]["error"])
            )
            self.assertEqual(
                "INVALID_CONTENT_TYPE", captured["payload"]["error"]["code"]
            )

    def test_get_interface_errors_use_full_envelope(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )

            handler, captured = _driven_handler(runtime, "/v1/tasks?limit=abc")
            handler.do_GET()
            self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])
            self.assertEqual(
                _INTERFACE_ERROR_KEYS, set(captured["payload"]["error"])
            )
            self.assertEqual(
                "INVALID_ARGUMENT", captured["payload"]["error"]["code"]
            )

            handler, captured = _driven_handler(runtime, "/v1/nope")
            handler.do_GET()
            self.assertEqual(HTTPStatus.NOT_FOUND, captured["status"])
            self.assertEqual(
                _INTERFACE_ERROR_KEYS, set(captured["payload"]["error"])
            )
            self.assertEqual(
                "RESOURCE_NOT_FOUND", captured["payload"]["error"]["code"]
            )


class _PolicyFailingObserveAdapter(FakeDeviceAdapter):
    async def observe(self, device_id: str, artifacts: ArtifactWriter) -> NoReturn:
        raise MobileAgentError(
            code="CONFIRMATION_REQUIRED",
            category=ErrorCategory.POLICY,
            message="需要用户确认",
        )


class _DiscoveryFailingAdapter(FakeDeviceAdapter):
    async def list_devices(self) -> NoReturn:
        raise MobileAgentError(
            code="ADB_NOT_FOUND",
            category=ErrorCategory.DEVICE,
            message="未找到 ADB 可执行文件",
        )


class StatusMappingTests(unittest.TestCase):
    """M11：list_devices_sync/observe_sync 复用统一 _error_response 映射。"""

    def test_observe_sync_maps_policy_rejection_to_forbidden(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                _PolicyFailingObserveAdapter(), ArtifactStore(Path(directory))
            )
            status, payload = runtime.observe_sync("fake:android-001")
        # 修复前自建映射把策略拒绝误报为 503
        self.assertEqual(HTTPStatus.FORBIDDEN, status)
        self.assertEqual("CONFIRMATION_REQUIRED", payload["error"]["code"])

    def test_list_devices_sync_maps_gateway_failure_to_unavailable(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                _DiscoveryFailingAdapter(), ArtifactStore(Path(directory))
            )
            status, payload = runtime.list_devices_sync()
        self.assertEqual(HTTPStatus.SERVICE_UNAVAILABLE, status)
        self.assertEqual("ADB_NOT_FOUND", payload["error"]["code"])

    def test_get_devices_surfaces_unavailable_after_dead_catch_removal(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                _DiscoveryFailingAdapter(), ArtifactStore(Path(directory))
            )
            handler, captured = _driven_handler(runtime, "/v1/devices")
            handler.do_GET()
        self.assertEqual(HTTPStatus.SERVICE_UNAVAILABLE, captured["status"])
        self.assertEqual("ADB_NOT_FOUND", captured["payload"]["error"]["code"])


class InputValidationTests(unittest.TestCase):
    """M12：导航/Agent 端点拒绝未知字段，max_scrolls 限定 1-50。"""

    _SELECTOR = {"strategy": "text", "value": "亮度", "match": "contains"}

    def _post(
        self, runtime: RuntimeService, path: str, body: dict[str, object]
    ) -> dict[str, object]:
        handler, captured = _driven_handler(runtime, path, body=body)
        handler.do_POST()
        return captured

    def test_scroll_navigate_rejects_max_scrolls_out_of_bounds(self) -> None:
        for path in (
            "/v1/skills/settings.scroll_navigate/invoke",
            "/v1/tasks/settings.scroll_navigate/run",
        ):
            for max_scrolls in (0, 51):
                with (
                    self.subTest(path=path, max_scrolls=max_scrolls),
                    TemporaryDirectory() as directory,
                ):
                    runtime = RuntimeService(
                        FakeDeviceAdapter(), ArtifactStore(Path(directory))
                    )
                    captured = self._post(
                        runtime,
                        path,
                        {
                            "device_id": "fake:android-001",
                            "target_selector": dict(self._SELECTOR),
                            "expected_selector": dict(self._SELECTOR),
                            "confirmed": True,
                            "max_scrolls": max_scrolls,
                        },
                    )
                    self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])
                    self.assertEqual(
                        "INVALID_ARGUMENT", captured["payload"]["error"]["code"]
                    )

    def test_navigation_endpoints_reject_unknown_fields(self) -> None:
        base = {
            "device_id": "fake:android-001",
            "target_selector": dict(self._SELECTOR),
            "expected_selector": dict(self._SELECTOR),
            "confirmed": True,
        }
        for path in (
            "/v1/skills/settings.navigate/invoke",
            "/v1/skills/settings.scroll_navigate/invoke",
            "/v1/tasks/settings.scroll_navigate/run",
        ):
            with self.subTest(path=path), TemporaryDirectory() as directory:
                runtime = RuntimeService(
                    FakeDeviceAdapter(), ArtifactStore(Path(directory))
                )
                captured = self._post(runtime, path, {**base, "raw_command": "x"})
                self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])
                self.assertEqual(
                    "INVALID_ARGUMENT", captured["payload"]["error"]["code"]
                )

    def test_agent_run_rejects_unknown_fields(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )
            captured = self._post(
                runtime,
                "/v1/tasks/agent.run",
                {
                    "device_id": "fake:android-001",
                    "goal": "open display settings",
                    "confirmed": True,
                    "raw_command": "dumpsys all",
                },
            )
        self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])
        self.assertEqual("INVALID_ARGUMENT", captured["payload"]["error"]["code"])

    def test_agent_run_accepts_full_known_field_set(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(),
                ArtifactStore(Path(directory)),
                navigation_shortcuts_enabled=False,
            )
            captured = self._post(
                runtime,
                "/v1/tasks/agent.run",
                {
                    "device_id": "fake:android-001",
                    "goal": "open display settings",
                    "confirmed": True,
                    "max_rounds": 6,
                    "deadline_seconds": 600,
                    "acceptance": {
                        "foreground_app_id": "com.android.settings",
                    },
                    "goal_spec": None,
                    "goal_spec_confirmed": False,
                },
            )
        self.assertEqual(HTTPStatus.OK, captured["status"])
