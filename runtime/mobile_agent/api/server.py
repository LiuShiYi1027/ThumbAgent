"""Minimal local HTTP interface for the runtime foundation iteration."""

from __future__ import annotations

import argparse
import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.runtime import RuntimeService, build_default_runtime


class RuntimeRequestHandler(BaseHTTPRequestHandler):
    """Expose the initial health and device discovery endpoints on loopback."""

    runtime_factory: Callable[[], RuntimeService] = staticmethod(build_default_runtime)
    server_version = "MobileAgentRuntime/0.1"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/v1/health":
            self._write_json(HTTPStatus.OK, self.runtime_factory().health())
            return
        if self.path == "/v1/devices":
            try:
                status, payload = self.runtime_factory().list_devices_sync()
            except MobileAgentError as error:
                status, payload = HTTPStatus.SERVICE_UNAVAILABLE, {"error": error.to_dict()}
            self._write_json(status, payload)
            return
        if self.path == "/v1/tools":
            self._write_json(HTTPStatus.OK, {"tools": self.runtime_factory().list_tools()})
            return
        self._write_json(
            HTTPStatus.NOT_FOUND,
            {
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "category": "validation",
                    "message": "请求的本地资源不存在",
                    "retryable": False,
                    "outcome": "rejected",
                }
            },
        )

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        match = re.fullmatch(r"/v1/devices/([^/]+)/observe", self.path)
        if match:
            try:
                status, payload = self.runtime_factory().observe_sync(match.group(1))
            except MobileAgentError as error:
                status, payload = HTTPStatus.SERVICE_UNAVAILABLE, {"error": error.to_dict()}
            self._write_json(status, payload)
            return

        tool_match = re.fullmatch(r"/v1/tools/([a-z.]+)/invoke", self.path)
        skill_match = re.fullmatch(r"/v1/skills/app\.open/invoke", self.path)
        navigation_match = re.fullmatch(r"/v1/skills/settings\.navigate/invoke", self.path)
        try:
            body = self._read_json()
            device_id = body.get("device_id")
            if not isinstance(device_id, str):
                raise ValueError("device_id")
            if tool_match:
                arguments = body.get("arguments", {})
                confirmed = body.get("confirmed", False)
                if not isinstance(arguments, dict) or not isinstance(confirmed, bool):
                    raise ValueError("arguments/confirmed")
                status, payload = self.runtime_factory().invoke_tool_sync(
                    tool_match.group(1), device_id, arguments, confirmed
                )
            elif skill_match:
                app_id = body.get("app_id")
                if not isinstance(app_id, str):
                    raise ValueError("app_id")
                status, payload = self.runtime_factory().open_app_sync(device_id, app_id)
            elif navigation_match:
                target = body.get("target_selector")
                expected = body.get("expected_selector")
                confirmed = body.get("confirmed", False)
                if not isinstance(target, dict) or not isinstance(expected, dict):
                    raise ValueError("selectors")
                if not isinstance(confirmed, bool):
                    raise ValueError("confirmed")
                status, payload = self.runtime_factory().navigate_settings_sync(
                    device_id, target, expected, confirmed
                )
            else:
                status, payload = HTTPStatus.NOT_FOUND, {
                    "error": {"code": "RESOURCE_NOT_FOUND", "message": "资源不存在"}
                }
        except (ValueError, json.JSONDecodeError):
            status, payload = HTTPStatus.BAD_REQUEST, {
                "error": {"code": "INVALID_ARGUMENT", "message": "请求参数无效"}
            }
        except MobileAgentError as error:
            status, payload = HTTPStatus.SERVICE_UNAVAILABLE, {"error": error.to_dict()}
        self._write_json(status, payload)

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        length = int(raw_length)
        if length <= 0 or length > 65_536:
            raise ValueError("content length")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("json object")
        return payload

    def log_message(self, format: str, *args: Any) -> None:
        """Avoid leaking request details through default stderr logging."""

    def _write_json(self, status: HTTPStatus, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def create_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Create a loopback-only HTTP server."""

    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("The V1 runtime may only listen on loopback")
    return ThreadingHTTPServer((host, port), RuntimeRequestHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Mobile Agent local runtime")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    print(f"Mobile Agent runtime listening on http://{args.host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
