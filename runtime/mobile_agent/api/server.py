"""Minimal local HTTP interface for the runtime foundation iteration."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evidence.artifacts import default_artifact_root
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
        if not self._authorize_post():
            return
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

    def _authorize_post(self) -> bool:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self._write_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                {"error": {"code": "INVALID_CONTENT_TYPE", "message": "需要 application/json"}},
            )
            return False
        expected = getattr(self.server, "api_token", "")
        authorization = self.headers.get("Authorization", "")
        supplied = authorization[7:] if authorization.startswith("Bearer ") else ""
        if not expected or not secrets.compare_digest(supplied, expected):
            self._write_json(
                HTTPStatus.UNAUTHORIZED,
                {"error": {"code": "UNAUTHORIZED", "message": "缺少有效的本地 API 令牌"}},
            )
            return False
        origin = self.headers.get("Origin")
        allowed_origins = getattr(self.server, "allowed_origins", frozenset())
        if origin is not None and origin not in allowed_origins:
            parsed = urlparse(origin)
            if not (parsed.scheme == "tauri" and parsed.hostname == "localhost"):
                self._write_json(
                    HTTPStatus.FORBIDDEN,
                    {"error": {"code": "ORIGIN_REJECTED", "message": "请求来源未获授权"}},
                )
                return False
        return True

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


def create_server(
    host: str = "127.0.0.1", port: int = 8765, api_token: str | None = None
) -> ThreadingHTTPServer:
    """Create a loopback-only HTTP server."""

    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("The V1 runtime may only listen on loopback")
    server = ThreadingHTTPServer((host, port), RuntimeRequestHandler)
    server.api_token = api_token or secrets.token_urlsafe(32)  # type: ignore[attr-defined]
    server.allowed_origins = frozenset({"tauri://localhost"})  # type: ignore[attr-defined]
    return server


def _write_runtime_token(token: str) -> Path:
    data_dir = os.environ.get("MOBILE_AGENT_DATA_DIR")
    root = Path(data_dir) if data_dir else default_artifact_root().parent
    root.mkdir(parents=True, exist_ok=True)
    path = root / "runtime-token"
    path.write_text(token, encoding="utf-8")
    path.chmod(0o600)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Mobile Agent local runtime")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    configured_token = os.environ.get("MOBILE_AGENT_API_TOKEN")
    token = configured_token or secrets.token_urlsafe(32)
    token_file = None if configured_token else _write_runtime_token(token)
    server = create_server(args.host, args.port, token)
    print(f"Mobile Agent runtime listening on http://{args.host}:{server.server_port}")
    if token_file is not None:
        print(f"Local API token written to {token_file}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if token_file is not None:
            token_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
