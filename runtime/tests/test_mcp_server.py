from __future__ import annotations

import io
import json
import unittest
from typing import Any

from mobile_agent.mcp.api_client import RuntimeApiError
from mobile_agent.mcp.server import (
    PROTOCOL_VERSION,
    McpServer,
    _ToolRateLimiter,
    run_stdio,
)


TASK_ID = "task_11111111111111111111111111111111"


class McpServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _FakeRuntimeClient()
        self.server = McpServer(self.client)

    def test_requires_initialize_and_initialized_notification(self) -> None:
        before = self.server.handle(_request(1, "tools/list", {}))
        initialize = self.server.handle(
            _request(
                2,
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            )
        )
        between = self.server.handle(_request(3, "tools/list", {}))
        notification = self.server.handle(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        after = self.server.handle(_request(4, "tools/list", {}))

        self.assertEqual(-32002, before["error"]["code"])
        self.assertEqual(PROTOCOL_VERSION, initialize["result"]["protocolVersion"])
        self.assertEqual({"tools": {"listChanged": False}}, initialize["result"]["capabilities"])
        self.assertEqual(-32002, between["error"]["code"])
        self.assertIsNone(notification)
        self.assertEqual(26, len(after["result"]["tools"]))

    def test_negotiates_supported_older_version_and_falls_back_for_unknown(self) -> None:
        older = McpServer(self.client).handle(
            _request(
                1,
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            )
        )
        unknown = McpServer(self.client).handle(
            _request(
                2,
                "initialize",
                {
                    "protocolVersion": "2099-01-01",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            )
        )

        self.assertEqual("2025-06-18", older["result"]["protocolVersion"])
        self.assertEqual(PROTOCOL_VERSION, unknown["result"]["protocolVersion"])

    def test_tools_list_accepts_standard_request_metadata(self) -> None:
        _ready(self.server)

        response = self.server.handle(
            _request(
                2,
                "tools/list",
                {"_meta": {"progressToken": "codex-startup"}},
            )
        )

        self.assertEqual(26, len(response["result"]["tools"]))

    def test_lists_only_goal_level_tools_with_annotations(self) -> None:
        _ready(self.server)

        response = self.server.handle(_request(3, "tools/list", {}))

        tools = response["result"]["tools"]
        names = {tool["name"] for tool in tools}
        self.assertIn("mobile_run_agent", names)
        self.assertIn("mobile_collect_device_logs", names)
        self.assertNotIn("input.tap", names)
        run_agent = next(tool for tool in tools if tool["name"] == "mobile_run_agent")
        self.assertFalse(run_agent["annotations"]["readOnlyHint"])
        self.assertEqual("forbidden", run_agent["execution"]["taskSupport"])
        self.assertEqual(True, run_agent["inputSchema"]["properties"]["confirmed"]["const"])
        self.assertIn("Do not automatically submit a replacement task", run_agent["description"])
        install = next(tool for tool in tools if tool["name"] == "mobile_install_apk")
        self.assertTrue(install["annotations"]["destructiveHint"])
        self.assertFalse(install["annotations"]["readOnlyHint"])
        uninstall = next(tool for tool in tools if tool["name"] == "mobile_uninstall_app")
        self.assertTrue(uninstall["annotations"]["destructiveHint"])
        self.assertIn("Do not automatically retry", uninstall["description"])
        inspect_state = next(
            tool for tool in tools if tool["name"] == "mobile_inspect_app_state"
        )
        self.assertTrue(inspect_state["annotations"]["readOnlyHint"])
        stop = next(tool for tool in tools if tool["name"] == "mobile_stop_app")
        self.assertFalse(stop["annotations"]["destructiveHint"])
        clear = next(tool for tool in tools if tool["name"] == "mobile_clear_app_data")
        self.assertTrue(clear["annotations"]["destructiveHint"])
        self.assertEqual(True, clear["inputSchema"]["properties"]["confirmed"]["const"])
        bundle = next(
            tool for tool in tools
            if tool["name"] == "mobile_collect_diagnostic_bundle"
        )
        self.assertFalse(bundle["annotations"]["readOnlyHint"])
        self.assertFalse(bundle["annotations"]["destructiveHint"])
        self.assertEqual(
            True, bundle["inputSchema"]["properties"]["confirmed"]["const"]
        )
        cleanup = next(
            tool for tool in tools if tool["name"] == "mobile_cleanup_local_data"
        )
        self.assertTrue(cleanup["annotations"]["destructiveHint"])
        self.assertFalse(cleanup["annotations"]["readOnlyHint"])
        self.assertEqual(
            True, cleanup["inputSchema"]["properties"]["confirmed"]["const"]
        )

    def test_calls_readiness_and_returns_structured_content(self) -> None:
        _ready(self.server)

        response = self.server.handle(
            _request(3, "tools/call", {"name": "mobile_runtime_readiness", "arguments": {}})
        )

        result = response["result"]
        self.assertFalse(result["isError"])
        self.assertEqual("ready", result["structuredContent"]["readiness"]["status"])
        self.assertEqual([("readiness", None)], self.client.calls)

    def test_rejects_missing_human_confirmation_before_runtime_call(self) -> None:
        _ready(self.server)

        response = self.server.handle(
            _request(
                3,
                "tools/call",
                {
                    "name": "mobile_run_agent",
                    "arguments": {
                        "device_id": "adb:001",
                        "goal": "打开设置",
                        "confirmed": False,
                    },
                },
            )
        )

        result = response["result"]
        self.assertTrue(result["isError"])
        self.assertEqual("INVALID_ARGUMENT", result["structuredContent"]["error"]["code"])
        self.assertEqual([], self.client.calls)

    def test_agent_submission_returns_mobile_task_handle(self) -> None:
        _ready(self.server)

        response = self.server.handle(
            _request(
                3,
                "tools/call",
                {
                    "name": "mobile_run_agent",
                    "arguments": {
                        "device_id": "adb:001",
                        "goal": "打开设置",
                        "confirmed": True,
                    },
                },
            )
        )

        self.assertFalse(response["result"]["isError"])
        self.assertEqual(TASK_ID, response["result"]["structuredContent"]["execution"]["task_id"])
        self.assertEqual("submit_agent", self.client.calls[0][0])

    def test_runtime_domain_error_is_a_tool_execution_error(self) -> None:
        _ready(self.server)
        self.client.error = {
            "code": "DEVICE_OFFLINE",
            "category": "device",
            "message": "设备已离线",
            "retryable": True,
            "outcome": "known_failure",
            "suggested_action": "重新连接设备",
            "details": {},
        }

        response = self.server.handle(
            _request(3, "tools/call", {"name": "mobile_list_devices", "arguments": {}})
        )

        self.assertTrue(response["result"]["isError"])
        self.assertEqual("DEVICE_OFFLINE", response["result"]["structuredContent"]["error"]["code"])
        self.assertNotIn("traceback", response["result"]["content"][0]["text"].lower())

    def test_unknown_tool_is_protocol_error(self) -> None:
        _ready(self.server)

        response = self.server.handle(
            _request(3, "tools/call", {"name": "shell.execute", "arguments": {}})
        )

        self.assertEqual(-32602, response["error"]["code"])
        self.assertEqual([], self.client.calls)

    def test_rate_limit_stops_runtime_dispatch(self) -> None:
        limiter = _ToolRateLimiter(maximum=1, window_seconds=60, clock=lambda: 1.0)
        server = McpServer(self.client, limiter)
        _ready(server)
        server.handle(
            _request(3, "tools/call", {"name": "mobile_runtime_readiness", "arguments": {}})
        )

        response = server.handle(
            _request(4, "tools/call", {"name": "mobile_list_devices", "arguments": {}})
        )

        self.assertEqual("MCP_RATE_LIMITED", response["result"]["structuredContent"]["error"]["code"])
        self.assertEqual(1, len(self.client.calls))

    def test_stdio_emits_only_newline_delimited_json_rpc(self) -> None:
        stdin = io.StringIO(
            "not-json\n"
            + json.dumps(
                _request(
                    1,
                    "initialize",
                    {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1"},
                    },
                )
            )
            + "\n"
        )
        stdout = io.StringIO()

        run_stdio(self.server, stdin, stdout)

        lines = stdout.getvalue().splitlines()
        self.assertEqual(2, len(lines))
        self.assertEqual(-32700, json.loads(lines[0])["error"]["code"])
        self.assertEqual(PROTOCOL_VERSION, json.loads(lines[1])["result"]["protocolVersion"])


class _FakeRuntimeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.error: dict[str, Any] | None = None

    def _result(self, name: str, value: object, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, value))
        if self.error is not None:
            raise RuntimeApiError(self.error)
        return payload

    def readiness(self) -> dict[str, Any]:
        return self._result("readiness", None, {"readiness": {"status": "ready"}})

    def list_devices(self) -> dict[str, Any]:
        return self._result("list_devices", None, {"devices": []})

    def local_storage(self, retention_days: int) -> dict[str, Any]:
        return self._result("local_storage", retention_days, {"storage": {}})

    def prepare_local_data_cleanup(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        return self._result(
            "prepare_local_data_cleanup", arguments, {"approval": {}}
        )

    def cleanup_local_data(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._result(
            "cleanup_local_data",
            arguments,
            {"execution": {"task_id": TASK_ID}},
        )

    def inspect_device(self, device_id: str) -> dict[str, Any]:
        return self._result("inspect_device", device_id, {"inspection": {}})

    def inspect_app_state(self, device_id: str, app_id: str) -> dict[str, Any]:
        return self._result("inspect_app_state", (device_id, app_id), {"state": {}})

    def launch_app(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._result(
            "launch_app", arguments, {"execution": {"task_id": TASK_ID}}
        )

    def stop_app(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._result(
            "stop_app", arguments, {"execution": {"task_id": TASK_ID}}
        )

    def prepare_app_data_clear(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._result("prepare_app_data_clear", arguments, {"approval": {}})

    def clear_app_data(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._result(
            "clear_app_data", arguments, {"execution": {"task_id": TASK_ID}}
        )

    def prepare_app_removal(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._result("prepare_app_removal", arguments, {"approval": {}})

    def uninstall_app(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._result(
            "uninstall_app", arguments, {"execution": {"task_id": TASK_ID}}
        )

    def submit_agent(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._result("submit_agent", arguments, {"execution": {"task_id": TASK_ID}})

    def list_tasks(self, limit: int) -> dict[str, Any]:
        return self._result("list_tasks", limit, {"tasks": []})

    def get_task_execution(self, task_id: str) -> dict[str, Any]:
        return self._result("get_task_execution", task_id, {"execution": {}})

    def get_task_report(self, task_id: str) -> dict[str, Any]:
        return self._result("get_task_report", task_id, {"task": {}})

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        return self._result("cancel_task", task_id, {"execution": {}})

    def collect_logs(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._result("collect_logs", arguments, {"execution": {"task_id": TASK_ID}})

    def capture_performance(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._result("capture_performance", arguments, {"execution": {"task_id": TASK_ID}})

    def compare_performance(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._result("compare_performance", arguments, {"comparison": {}})

    def collect_diagnostic_bundle(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        return self._result(
            "collect_diagnostic_bundle",
            arguments,
            {"execution": {"task_id": TASK_ID}},
        )


def _ready(server: McpServer) -> None:
    server.handle(
        _request(
            1,
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        )
    )
    server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})


def _request(request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


if __name__ == "__main__":
    unittest.main()
