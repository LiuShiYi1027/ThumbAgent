"""MCP 2025-11-25 JSON-RPC server over newline-delimited stdio."""

from __future__ import annotations

import json
import time
from collections import deque
from collections.abc import Callable
from typing import Any, Protocol, TextIO

from mobile_agent import __version__
from mobile_agent.mcp.api_client import RuntimeApiError
from mobile_agent.mcp.tools import TOOLS, McpToolDefinition, load_input_schemas, validate_arguments


PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = frozenset(
    {PROTOCOL_VERSION, "2025-06-18", "2025-03-26", "2024-11-05"}
)
MAX_MESSAGE_BYTES = 1024 * 1024


class McpRuntimeClient(Protocol):
    """Application-facing operations required by the MCP interface."""

    def readiness(self) -> dict[str, Any]: ...
    def list_devices(self) -> dict[str, Any]: ...
    def inspect_device(self, device_id: str) -> dict[str, Any]: ...
    def submit_agent(self, arguments: dict[str, Any]) -> dict[str, Any]: ...
    def list_tasks(self, limit: int) -> dict[str, Any]: ...
    def get_task_execution(self, task_id: str) -> dict[str, Any]: ...
    def get_task_report(self, task_id: str) -> dict[str, Any]: ...
    def cancel_task(self, task_id: str) -> dict[str, Any]: ...
    def collect_logs(self, arguments: dict[str, Any]) -> dict[str, Any]: ...
    def capture_performance(self, arguments: dict[str, Any]) -> dict[str, Any]: ...
    def compare_performance(self, arguments: dict[str, Any]) -> dict[str, Any]: ...


class _ToolRateLimiter:
    """Bound sequential stdio tool calls to protect the local Runtime."""

    def __init__(
        self,
        maximum: int = 120,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._maximum = maximum
        self._window = window_seconds
        self._clock = clock
        self._calls: deque[float] = deque()

    def allow(self) -> bool:
        now = self._clock()
        while self._calls and now - self._calls[0] >= self._window:
            self._calls.popleft()
        if len(self._calls) >= self._maximum:
            return False
        self._calls.append(now)
        return True


class McpServer:
    """Serve a fixed catalog of goal-level tools backed by localhost REST."""

    def __init__(
        self,
        client: McpRuntimeClient,
        rate_limiter: _ToolRateLimiter | None = None,
    ) -> None:
        self._client = client
        self._schemas = load_input_schemas()
        self._tools = {tool.name: tool for tool in TOOLS}
        self._initialized = False
        self._ready = False
        self._rate_limiter = rate_limiter or _ToolRateLimiter()

    def handle(self, message: object) -> dict[str, Any] | None:
        """Handle one decoded JSON-RPC message and return a response if required."""

        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return _error(None, -32600, "Invalid Request")
        method = message.get("method")
        if not isinstance(method, str):
            return _error(message.get("id"), -32600, "Invalid Request")
        request_id = message.get("id")
        is_notification = "id" not in message
        if not is_notification and (
            isinstance(request_id, bool) or not isinstance(request_id, (str, int))
        ):
            return _error(None, -32600, "Invalid Request")
        params = message.get("params", {})
        if not isinstance(params, dict):
            return None if is_notification else _error(request_id, -32602, "Invalid params")

        if method == "initialize":
            if is_notification:
                return None
            return self._initialize(request_id, params)
        if method == "notifications/initialized":
            if self._initialized:
                self._ready = True
            return None
        if method == "notifications/cancelled":
            return None
        if method == "ping":
            return None if is_notification else _result(request_id, {})
        if not self._ready:
            return None if is_notification else _error(
                request_id, -32002, "Server is not initialized"
            )
        if method == "tools/list":
            if is_notification:
                return None
            cursor = params.get("cursor")
            if set(params) - {"cursor"} or (cursor is not None and cursor != ""):
                return _error(request_id, -32602, "Invalid params")
            return _result(
                request_id,
                {"tools": [tool.to_dict(self._schemas) for tool in TOOLS]},
            )
        if method == "tools/call":
            if is_notification:
                return None
            return self._call_tool(request_id, params)
        return None if is_notification else _error(request_id, -32601, "Method not found")

    def _initialize(self, request_id: str | int, params: dict[str, Any]) -> dict[str, Any]:
        if self._initialized:
            return _error(request_id, -32600, "Server already initialized")
        requested = params.get("protocolVersion")
        client_info = params.get("clientInfo")
        capabilities = params.get("capabilities")
        if (
            not isinstance(requested, str)
            or not isinstance(client_info, dict)
            or not isinstance(capabilities, dict)
        ):
            return _error(request_id, -32602, "Invalid initialize parameters")
        negotiated = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else PROTOCOL_VERSION
        self._initialized = True
        return _result(
            request_id,
            {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": "mobile-agent",
                    "title": "Mobile Agent Local Skills",
                    "version": __version__,
                },
                "instructions": (
                    "Use readiness and inspection before submitting device work. "
                    "Device actions and log collection require the MCP host to obtain explicit user confirmation. "
                    "Long-running work returns a Mobile Agent task_id; query execution and report tools for progress."
                ),
            },
        )

    def _call_tool(
        self, request_id: str | int, params: dict[str, Any]
    ) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments", {})
        metadata = params.get("_meta")
        if (
            not isinstance(name, str)
            or set(params) - {"name", "arguments", "_meta"}
            or (metadata is not None and not isinstance(metadata, dict))
        ):
            return _error(request_id, -32602, "Invalid params")
        tool = self._tools.get(name)
        if tool is None:
            return _error(request_id, -32602, "Unknown tool")
        invalid_fields = validate_arguments(self._schemas[tool.schema_key], arguments)
        if invalid_fields:
            return _result(
                request_id,
                _tool_error(
                    {
                        "code": "INVALID_ARGUMENT",
                        "category": "validation",
                        "message": "MCP Tool 参数无效",
                        "retryable": False,
                        "outcome": "rejected",
                        "suggested_action": "根据 Tool inputSchema 修正参数后重试",
                        "details": {"invalid_fields": invalid_fields},
                    }
                ),
            )
        if not self._rate_limiter.allow():
            return _result(
                request_id,
                _tool_error(
                    {
                        "code": "MCP_RATE_LIMITED",
                        "category": "execution",
                        "message": "MCP Tool 调用过于频繁",
                        "retryable": True,
                        "outcome": "known_failure",
                        "suggested_action": "稍后重试",
                        "details": {},
                    }
                ),
            )
        assert isinstance(arguments, dict)
        try:
            payload = self._invoke(tool, arguments)
        except RuntimeApiError as error:
            return _result(request_id, _tool_error(error.error))
        return _result(request_id, _tool_success(payload))

    def _invoke(
        self, tool: McpToolDefinition, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        handlers: dict[str, Callable[[], dict[str, Any]]] = {
            "mobile_runtime_readiness": self._client.readiness,
            "mobile_list_devices": self._client.list_devices,
            "mobile_inspect_device": lambda: self._client.inspect_device(
                arguments["device_id"]
            ),
            "mobile_run_agent": lambda: self._client.submit_agent(arguments),
            "mobile_list_tasks": lambda: self._client.list_tasks(arguments.get("limit", 20)),
            "mobile_get_task_execution": lambda: self._client.get_task_execution(
                arguments["task_id"]
            ),
            "mobile_get_task_report": lambda: self._client.get_task_report(
                arguments["task_id"]
            ),
            "mobile_cancel_task": lambda: self._client.cancel_task(arguments["task_id"]),
            "mobile_collect_device_logs": lambda: self._client.collect_logs(arguments),
            "mobile_capture_device_performance": lambda: self._client.capture_performance(
                arguments
            ),
            "mobile_compare_device_performance": lambda: self._client.compare_performance(
                arguments
            ),
        }
        return handlers[tool.name]()


def run_stdio(server: McpServer, stdin: TextIO, stdout: TextIO) -> None:
    """Run newline-delimited UTF-8 JSON-RPC without writing non-protocol stdout."""

    for line in stdin:
        if len(line.encode("utf-8")) > MAX_MESSAGE_BYTES:
            response = _error(None, -32600, "Message too large")
        else:
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                response = _error(None, -32700, "Parse error")
            else:
                try:
                    response = server.handle(message)
                except Exception:
                    response = _error(
                        message.get("id") if isinstance(message, dict) else None,
                        -32603,
                        "Internal error",
                    )
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
            stdout.write("\n")
            stdout.flush()


def _tool_success(payload: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": payload,
        "isError": False,
    }


def _tool_error(error: dict[str, Any]) -> dict[str, Any]:
    safe = {"error": error}
    text = json.dumps(safe, ensure_ascii=False, separators=(",", ":"))
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": safe,
        "isError": True,
    }


def _result(request_id: str | int, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(
    request_id: str | int | None, code: int, message: str
) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
