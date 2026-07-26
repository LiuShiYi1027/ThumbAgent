from __future__ import annotations

import json
import tempfile
import time
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

from mobile_agent.api.server import RuntimeRequestHandler
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.mcp.api_client import RuntimeApiClient
from mobile_agent.mcp.server import PROTOCOL_VERSION, McpServer
from mobile_agent.runtime import RuntimeService
from runtime.tests.test_apk_install import _write_apk


class McpRuntimeIntegrationTests(unittest.TestCase):
    def test_mcp_prepares_and_installs_scoped_apk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "apks"
            root.mkdir()
            apk = _write_apk(root)
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory) / "artifacts"),
                apk_root=root,
            )
            server = McpServer(RuntimeApiClient(
                "http://127.0.0.1:8765", "integration-token",
                _InProcessHttpTransport(runtime),
            ))
            _ready(server)
            approval = server.handle(_request(3, "tools/call", {
                "name": "mobile_prepare_apk_install",
                "arguments": {
                    "device_id": "fake:android-001", "apk_path": str(apk),
                    "expected_app_id": "com.example.installed",
                },
            }))["result"]["structuredContent"]["approval"]
            submitted = server.handle(_request(4, "tools/call", {
                "name": "mobile_install_apk",
                "arguments": {"approval_id": approval["approval_id"], "confirmed": True},
            }))["result"]["structuredContent"]["execution"]
            deadline = time.monotonic() + 2
            execution = {}
            while time.monotonic() < deadline:
                execution = runtime.get_task_execution(submitted["task_id"])
                if execution["status"] in {"succeeded", "failed"}:
                    break
                time.sleep(0.01)
            report = runtime.get_task(submitted["task_id"])

        self.assertEqual("succeeded", execution["status"])
        self.assertEqual("com.example.installed", report["evidence_summary"]["app"]["app_id"])

    def test_mcp_prepares_and_uninstalls_scoped_non_system_app(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory) / "artifacts")
            )
            server = McpServer(
                RuntimeApiClient(
                    "http://127.0.0.1:8765",
                    "integration-token",
                    _InProcessHttpTransport(runtime),
                )
            )
            _ready(server)
            approval = server.handle(
                _request(
                    3,
                    "tools/call",
                    {
                        "name": "mobile_prepare_app_uninstall",
                        "arguments": {
                            "device_id": "fake:android-001",
                            "app_id": "com.example.fake",
                            "keep_data": False,
                        },
                    },
                )
            )["result"]["structuredContent"]["approval"]
            self.assertTrue(approval["application_data_will_be_deleted"])
            submitted = server.handle(
                _request(
                    4,
                    "tools/call",
                    {
                        "name": "mobile_uninstall_app",
                        "arguments": {
                            "approval_id": approval["approval_id"],
                            "confirmed": True,
                        },
                    },
                )
            )["result"]["structuredContent"]["execution"]
            deadline = time.monotonic() + 2
            execution = {}
            while time.monotonic() < deadline:
                execution = runtime.get_task_execution(submitted["task_id"])
                if execution["status"] in {"succeeded", "failed"}:
                    break
                time.sleep(0.01)
            report = runtime.get_task(submitted["task_id"])

        self.assertEqual("succeeded", execution["status"])
        self.assertEqual(
            "com.example.fake",
            report["evidence_summary"]["removed_app"]["app_id"],
        )
        self.assertEqual("absent", report["evidence_summary"]["post_removal_state"])

    def test_mcp_lists_and_inspects_apps_through_local_api(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory) / "artifacts")
            )
            server = McpServer(
                RuntimeApiClient(
                    "http://127.0.0.1:8765",
                    "integration-token",
                    _InProcessHttpTransport(runtime),
                )
            )
            _ready(server)

            listed = server.handle(_request(3, "tools/call", {
                "name": "mobile_list_apps",
                "arguments": {"device_id": "fake:android-001", "limit": 1},
            }))["result"]["structuredContent"]["inventory"]
            inspected = server.handle(_request(4, "tools/call", {
                "name": "mobile_inspect_app",
                "arguments": {
                    "device_id": "fake:android-001", "app_id": "com.example.fake"
                },
            }))["result"]["structuredContent"]["app"]

        self.assertEqual(1, len(listed["apps"]))
        self.assertTrue(listed["truncated"])
        self.assertEqual("1.0", inspected["version_name"])

    def test_mcp_submits_and_reads_performance_task_through_local_api(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory) / "artifacts")
            )
            server = McpServer(
                RuntimeApiClient(
                    "http://127.0.0.1:8765",
                    "integration-token",
                    _InProcessHttpTransport(runtime),
                )
            )
            _ready(server)

            submitted = server.handle(
                _request(
                    3,
                    "tools/call",
                    {
                        "name": "mobile_capture_device_performance",
                        "arguments": {"device_id": "fake:android-001"},
                    },
                )
            )
            task_id = submitted["result"]["structuredContent"]["execution"]["task_id"]
            execution: dict[str, Any] = {}
            deadline = time.monotonic() + 2
            request_id = 4
            while time.monotonic() < deadline:
                response = server.handle(
                    _request(
                        request_id,
                        "tools/call",
                        {
                            "name": "mobile_get_task_execution",
                            "arguments": {"task_id": task_id},
                        },
                    )
                )
                execution = response["result"]["structuredContent"]["execution"]
                if execution["status"] in {"succeeded", "failed"}:
                    break
                request_id += 1
                time.sleep(0.01)
            report = server.handle(
                _request(
                    request_id + 1,
                    "tools/call",
                    {
                        "name": "mobile_get_task_report",
                        "arguments": {"task_id": task_id},
                    },
                )
            )["result"]["structuredContent"]["task"]

        self.assertEqual("succeeded", execution["status"])
        self.assertEqual("device.performance.snapshot", report["task_type"])
        self.assertEqual(12.5, report["evidence_summary"]["cpu_total_usage_percent"])
        self.assertNotIn("dumpsys", str(report).lower())


class _InProcessHttpTransport:
    """Exercise the real HTTP handler without opening a test socket."""

    def __init__(self, runtime: RuntimeService) -> None:
        self.runtime = runtime

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout: float,
    ) -> tuple[int, bytes]:
        del timeout
        handler = object.__new__(RuntimeRequestHandler)
        parsed = urlparse(url)
        handler.path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        message = Message()
        for key, value in headers.items():
            message[key] = value
        handler.headers = message
        handler.server = SimpleNamespace(
            runtime=self.runtime,
            api_token="integration-token",
            allowed_origins=frozenset(),
            server_port=8765,
        )
        if body is not None:
            payload = json.loads(body)
            handler._read_json = lambda: payload
        captured: dict[str, Any] = {}
        handler._write_json = lambda status, payload: captured.update(
            {"status": status.value, "payload": payload}
        )
        if method == "GET":
            handler.do_GET()
        else:
            handler.do_POST()
        return int(captured["status"]), json.dumps(captured["payload"]).encode()


def _ready(server: McpServer) -> None:
    server.handle(
        _request(
            1,
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "integration-test", "version": "1"},
            },
        )
    )
    server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})


def _request(request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


if __name__ == "__main__":
    unittest.main()
