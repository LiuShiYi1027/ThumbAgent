"""API-level tests for the ITER-0054 model provider settings endpoints."""

from __future__ import annotations

import json
import os
import unittest
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any
from unittest import mock

from mobile_agent.api.server import RuntimeRequestHandler
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService

_ENV_OVERRIDE_NAMES = (
    "MOBILE_AGENT_MODEL_ENABLED",
    "MOBILE_AGENT_MODEL_PROVIDER",
    "MOBILE_AGENT_MODEL_BASE_URL",
    "MOBILE_AGENT_MODEL_NAME",
    "MOBILE_AGENT_MODEL_API_KEY_REF",
    "MOBILE_AGENT_MODEL_TIMEOUT_SECONDS",
)

_VALID_ENABLED_BODY: dict[str, Any] = {
    "enabled": True,
    "provider": "openai_compatible",
    "base_url": "https://model.example/v1",
    "model": "test-model",
    "api_key_ref": "env:MOBILE_AGENT_MODEL_SECRET_DESKTOP",
    "timeout_seconds": 30,
}


class ModelProviderSettingsApiTests(unittest.TestCase):
    def test_get_config_returns_defaults_without_token_when_file_missing(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = _make_runtime(Path(directory))
            with _clean_model_env():
                captured = _get_config(runtime)

        self.assertEqual(HTTPStatus.OK, captured["status"])
        config = captured["payload"]["config"]
        self.assertFalse(config["enabled"])
        self.assertEqual("rule_based", config["provider"])
        self.assertEqual("", config["api_key_ref"])
        self.assertTrue(config["config_file"].endswith("model-provider.json"))
        self.assertFalse(config["env_override"])

    def test_get_config_reports_env_override_marker(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = _make_runtime(Path(directory))
            with _clean_model_env(), mock.patch.dict(
                os.environ, {"MOBILE_AGENT_MODEL_NAME": "env-model"}
            ):
                captured = _get_config(runtime)

        self.assertEqual(HTTPStatus.OK, captured["status"])
        self.assertTrue(captured["payload"]["config"]["env_override"])

    def test_post_config_requires_token(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = _make_runtime(Path(directory))
            captured = _post_config(runtime, None, dict(_VALID_ENABLED_BODY))

        self.assertEqual(HTTPStatus.UNAUTHORIZED, captured["status"])

    def test_post_config_saves_valid_settings_and_get_reads_them_back(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = _make_runtime(Path(directory))
            with _clean_model_env():
                posted = _post_config(runtime, "test-token", dict(_VALID_ENABLED_BODY))
                fetched = _get_config(runtime)
            config_path = Path(directory) / "model-provider.json"
            raw = config_path.read_text(encoding="utf-8")
            mode = config_path.stat().st_mode & 0o777

        self.assertEqual(HTTPStatus.OK, posted["status"])
        self.assertTrue(posted["payload"]["saved"])
        self.assertTrue(posted["payload"]["restart_required"])
        self.assertEqual(0o600, mode)
        self.assertNotIn("sk-live-secret", raw)
        config = fetched["payload"]["config"]
        self.assertTrue(config["enabled"])
        self.assertEqual("openai_compatible", config["provider"])
        self.assertEqual("https://model.example/v1", config["base_url"])
        self.assertEqual("test-model", config["model"])
        self.assertEqual(
            "env:MOBILE_AGENT_MODEL_SECRET_DESKTOP", config["api_key_ref"]
        )
        self.assertEqual(30.0, config["timeout_seconds"])

    def test_post_config_rejects_invalid_payloads(self) -> None:
        invalid_payloads = [
            # 缺 enabled
            {"provider": "openai_compatible"},
            # 未知字段（密钥值伪装字段也不允许）
            {**_VALID_ENABLED_BODY, "api_key": "sk-live-secret"},
            # 非法 base_url
            {**_VALID_ENABLED_BODY, "base_url": "ftp://model.example"},
            # timeout 越界
            {**_VALID_ENABLED_BODY, "timeout_seconds": 0},
            {**_VALID_ENABLED_BODY, "timeout_seconds": 121},
            # enabled 但缺 model
            {**_VALID_ENABLED_BODY, "model": ""},
            # api_key_ref 必须是 env:MOBILE_AGENT_MODEL_SECRET_* 引用
            {**_VALID_ENABLED_BODY, "api_key_ref": "sk-live-secret"},
            {**_VALID_ENABLED_BODY, "api_key_ref": "env:OPENAI_API_KEY"},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with TemporaryDirectory() as directory:
                    runtime = _make_runtime(Path(directory))
                    captured = _post_config(runtime, "test-token", payload)
                    config_path = Path(directory) / "model-provider.json"

                self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])
                self.assertEqual(
                    "INVALID_ARGUMENT", captured["payload"]["error"]["code"]
                )
                self.assertNotIn(
                    "sk-live-secret", str(captured["payload"])
                )
                self.assertFalse(config_path.exists())

    def test_post_config_allows_disabled_partial_settings(self) -> None:
        with TemporaryDirectory() as directory:
            runtime = _make_runtime(Path(directory))
            captured = _post_config(
                runtime,
                "test-token",
                {"enabled": False, "base_url": "https://draft.example/v1"},
            )

        self.assertEqual(HTTPStatus.OK, captured["status"])
        self.assertFalse(captured["payload"]["config"]["enabled"])
        self.assertEqual(
            "https://draft.example/v1", captured["payload"]["config"]["base_url"]
        )


def _make_runtime(directory: Path) -> RuntimeService:
    return RuntimeService(
        FakeDeviceAdapter(),
        ArtifactStore(directory / "artifacts"),
    )


def _get_config(runtime: RuntimeService) -> dict[str, Any]:
    handler = object.__new__(RuntimeRequestHandler)
    handler.path = "/v1/model-provider/config"
    handler.headers = Message()
    handler.server = SimpleNamespace(
        runtime=runtime,
        api_token="test-token",
        allowed_origins=frozenset(),
        server_port=8765,
    )
    captured: dict[str, Any] = {}
    handler._write_json = lambda status, payload: captured.update(
        {"status": status, "payload": payload}
    )
    handler.do_GET()
    return captured


def _post_config(
    runtime: RuntimeService, token: str | None, body: dict[str, Any]
) -> dict[str, Any]:
    handler = object.__new__(RuntimeRequestHandler)
    handler.path = "/v1/model-provider/config"
    headers = Message()
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
    captured: dict[str, Any] = {}
    handler._write_json = lambda status, payload: captured.update(
        {"status": status, "payload": payload}
    )
    handler.do_POST()
    return captured


class _clean_model_env:
    """确保测试不受宿主环境里的 MOBILE_AGENT_MODEL_* 变量影响。"""

    def __enter__(self) -> None:
        self._patcher = mock.patch.dict(
            os.environ,
            {name: "" for name in _ENV_OVERRIDE_NAMES},
        )
        self._patcher.start()

    def __exit__(self, *args: object) -> None:
        self._patcher.stop()


if __name__ == "__main__":
    unittest.main()
