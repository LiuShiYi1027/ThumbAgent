from __future__ import annotations

import unittest
from email.message import Message
from http import HTTPStatus
from types import SimpleNamespace

from mobile_agent.api.server import RuntimeRequestHandler


class ApiSecurityTests(unittest.TestCase):
    def _authorize(self, headers: dict[str, str]) -> tuple[bool, HTTPStatus | None]:
        handler = object.__new__(RuntimeRequestHandler)
        message = Message()
        for name, value in headers.items():
            message[name] = value
        handler.headers = message
        handler.server = SimpleNamespace(
            api_token="test-token", allowed_origins=frozenset({"tauri://localhost"})
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
