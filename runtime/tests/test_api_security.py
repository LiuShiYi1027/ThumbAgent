from __future__ import annotations

import unittest
import threading
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from mobile_agent.api.server import RuntimeRequestHandler
from mobile_agent.api.server import _query_int
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.artifact import ArtifactKind
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
        """max_rounds 接受 1–12（含 12），拒绝 0 与 13。"""

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

        status, payload, finished = post(12)
        self.assertEqual(HTTPStatus.ACCEPTED, status)
        self.assertTrue(finished, "max_rounds=12 的异步任务未完成")

        for invalid in (0, 13):
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
        self.assertEqual(17, len(payload["inspection"]["capabilities"]))

    def test_get_app_inventory_is_bounded_and_supports_prefix(self) -> None:
        with TemporaryDirectory() as directory:
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/devices/fake%3Aandroid-001/apps?limit=500&prefix=com.example"
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
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )
            handler = object.__new__(RuntimeRequestHandler)
            handler.path = "/v1/tasks/agent.run"
            headers = Message()
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
