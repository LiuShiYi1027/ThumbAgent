from __future__ import annotations

import json
import unittest
from typing import Any

from mobile_agent.mcp.api_client import MAX_RESPONSE_BYTES, RuntimeApiClient, RuntimeApiError


class McpApiClientTests(unittest.TestCase):
    def test_rejects_non_loopback_runtime_url(self) -> None:
        with self.assertRaises(ValueError):
            RuntimeApiClient("https://example.com", "token")

    def test_agent_submission_uses_fixed_endpoint_auth_and_idempotency(self) -> None:
        transport = _Transport({"execution": {"task_id": "task_1"}})
        client = RuntimeApiClient("http://127.0.0.1:8765", "secret-token", transport)

        result = client.submit_agent(
            {
                "device_id": "adb:001",
                "goal": "打开设置",
                "confirmed": True,
            }
        )

        self.assertEqual("task_1", result["execution"]["task_id"])
        method, url, headers, body, timeout = transport.calls[0]
        self.assertEqual("POST", method)
        self.assertEqual("http://127.0.0.1:8765/v1/tasks/agent.run/async", url)
        self.assertEqual("Bearer secret-token", headers["Authorization"])
        self.assertRegex(headers["Idempotency-Key"], r"^mcp-[a-f0-9]{32}$")
        self.assertEqual("adb:001", json.loads(body.decode())["device_id"])
        self.assertEqual(30.0, timeout)

    def test_runtime_domain_error_is_preserved_without_http_body_leak(self) -> None:
        error = {
            "code": "DEVICE_OFFLINE",
            "category": "device",
            "message": "设备离线",
            "retryable": True,
            "outcome": "known_failure",
            "suggested_action": "重连",
            "details": {},
        }
        transport = _Transport({"error": error}, status=503)
        client = RuntimeApiClient("http://localhost:8765", "token", transport)

        with self.assertRaises(RuntimeApiError) as raised:
            client.list_devices()

        self.assertEqual(error, raised.exception.error)

    def test_invalid_or_oversized_runtime_response_is_safe(self) -> None:
        invalid = RuntimeApiClient(
            "http://localhost:8765",
            "token",
            lambda *_: (200, b"not-json secret-body"),
        )
        oversized = RuntimeApiClient(
            "http://localhost:8765",
            "token",
            lambda *_: (200, b"x" * (MAX_RESPONSE_BYTES + 1)),
        )

        with self.assertRaises(RuntimeApiError) as invalid_error:
            invalid.list_devices()
        with self.assertRaises(RuntimeApiError) as oversized_error:
            oversized.list_devices()

        self.assertEqual("RUNTIME_UNAVAILABLE", invalid_error.exception.error["code"])
        self.assertNotIn("secret-body", str(invalid_error.exception.error))
        self.assertEqual(
            "RUNTIME_RESPONSE_TOO_LARGE", oversized_error.exception.error["code"]
        )


class _Transport:
    def __init__(self, payload: dict[str, Any], status: int = 200) -> None:
        self.payload = payload
        self.status = status
        self.calls: list[tuple[str, str, dict[str, str], bytes, float]] = []

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout: float,
    ) -> tuple[int, bytes]:
        self.calls.append((method, url, headers, body or b"", timeout))
        return self.status, json.dumps(self.payload).encode()


if __name__ == "__main__":
    unittest.main()
