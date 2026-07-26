"""Bounded localhost REST client used by the MCP interface adapter."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen


MAX_RESPONSE_BYTES = 2 * 1024 * 1024
HttpTransport = Callable[
    [str, str, dict[str, str], bytes | None, float], tuple[int, bytes]
]


@dataclass(frozen=True, slots=True)
class RuntimeApiError(Exception):
    """Safe Runtime API error exposed as an MCP tool execution error."""

    error: dict[str, Any]


class RuntimeApiClient:
    """Call only fixed endpoints on an authenticated loopback Runtime."""

    def __init__(
        self,
        base_url: str,
        token: str,
        transport: HttpTransport | None = None,
    ) -> None:
        self._base_url = _validated_base_url(base_url)
        if not token:
            raise ValueError("MOBILE_AGENT_API_TOKEN is required")
        self._token = token
        self._transport = transport or _urlopen_transport

    def readiness(self) -> dict[str, Any]:
        return self._request("GET", "/v1/readiness")

    def list_devices(self) -> dict[str, Any]:
        return self._request("GET", "/v1/devices")

    def inspect_device(self, device_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/devices/{quote(device_id, safe='')}/inspection")

    def list_apps(self, device_id: str, limit: int, prefix: str | None) -> dict[str, Any]:
        query: dict[str, str | int] = {"limit": limit}
        if prefix is not None:
            query["prefix"] = prefix
        return self._request(
            "GET", f"/v1/devices/{quote(device_id, safe='')}/apps?{urlencode(query)}"
        )

    def inspect_app(self, device_id: str, app_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/v1/devices/{quote(device_id, safe='')}/apps/{quote(app_id, safe='')}",
        )

    def prepare_apk_install(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/apps/install/prepare", arguments)

    def install_apk(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST", "/v1/tasks/app.install/async", arguments,
            idempotent_submission=True,
        )

    def prepare_app_removal(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/apps/uninstall/prepare", arguments)

    def uninstall_app(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/tasks/app.uninstall/async",
            arguments,
            idempotent_submission=True,
        )

    def submit_agent(self, arguments: dict[str, Any]) -> dict[str, Any]:
        body = {
            "device_id": arguments["device_id"],
            "goal": arguments["goal"],
            "confirmed": arguments["confirmed"],
            "max_rounds": arguments.get("max_rounds", 6),
            "deadline_seconds": arguments.get("deadline_seconds", 600),
        }
        return self._request(
            "POST", "/v1/tasks/agent.run/async", body, idempotent_submission=True
        )

    def list_tasks(self, limit: int) -> dict[str, Any]:
        return self._request("GET", f"/v1/tasks?{urlencode({'limit': limit})}")

    def get_task_execution(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/task-executions/{task_id}")

    def get_task_report(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/tasks/{task_id}")

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v1/task-executions/{task_id}/cancel", {})

    def collect_logs(self, arguments: dict[str, Any]) -> dict[str, Any]:
        body = {
            "device_id": arguments["device_id"],
            "max_lines": arguments.get("max_lines", 500),
            "minimum_level": arguments.get("minimum_level", "info"),
            "confirmed": arguments["confirmed"],
            "deadline_seconds": arguments.get("deadline_seconds", 60),
        }
        return self._request(
            "POST",
            "/v1/tasks/device.logs.collect/async",
            body,
            idempotent_submission=True,
        )

    def capture_performance(self, arguments: dict[str, Any]) -> dict[str, Any]:
        body = {
            "device_id": arguments["device_id"],
            "deadline_seconds": arguments.get("deadline_seconds", 90),
        }
        return self._request(
            "POST",
            "/v1/tasks/device.performance.snapshot/async",
            body,
            idempotent_submission=True,
        )

    def compare_performance(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/performance-comparisons", arguments)

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        idempotent_submission: bool = False,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }
        encoded: bytes | None = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        if idempotent_submission:
            headers["Idempotency-Key"] = f"mcp-{uuid.uuid4().hex}"
        try:
            status, raw = self._transport(
                method, f"{self._base_url}{path}", headers, encoded, 30.0
            )
        except (OSError, TimeoutError, URLError) as error:
            raise RuntimeApiError(_unavailable_error()) from error
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeApiError(
                {
                    "code": "RUNTIME_RESPONSE_TOO_LARGE",
                    "category": "execution",
                    "message": "Runtime 响应超过 MCP 本地限制",
                    "retryable": False,
                    "outcome": "known_failure",
                    "suggested_action": "缩小查询范围后重试",
                    "details": {},
                }
            )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeApiError(_unavailable_error()) from error
        if not isinstance(payload, dict):
            raise RuntimeApiError(_unavailable_error())
        if status >= 400:
            domain_error = payload.get("error")
            if not isinstance(domain_error, dict):
                domain_error = _unavailable_error()
            raise RuntimeApiError(dict(domain_error))
        return payload


def _validated_base_url(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("MCP Runtime base URL must be an HTTP loopback origin")
    return value.rstrip("/")


def _urlopen_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    timeout: float,
) -> tuple[int, bytes]:
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            return response.status, raw
    except HTTPError as error:
        return error.code, error.read(MAX_RESPONSE_BYTES + 1)


def _unavailable_error() -> dict[str, Any]:
    return {
        "code": "RUNTIME_UNAVAILABLE",
        "category": "execution",
        "message": "无法连接本地 Mobile Agent Runtime",
        "retryable": True,
        "outcome": "known_failure",
        "suggested_action": "确认 Runtime 已启动且 MCP 配置中的地址和令牌一致",
        "details": {},
    }
