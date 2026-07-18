from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from mobile_agent.agent import AgentObservationSummary, RuleBasedPlanner
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.providers import (
    EnvironmentSecretResolver,
    ModelProviderSettings,
    OpenAICompatiblePlanner,
    build_planner_from_settings,
    load_model_provider_settings,
    model_provider_status,
)


class ModelProviderConfigTests(unittest.TestCase):
    def test_default_settings_return_rule_based_planner_without_secret_lookup(self) -> None:
        resolver = FakeSecretResolver({"model-key": "secret-value"})

        planner = build_planner_from_settings(secret_resolver=resolver)

        self.assertIsInstance(planner, RuleBasedPlanner)
        self.assertEqual([], resolver.requests)

    def test_enabled_openai_compatible_settings_build_provider(self) -> None:
        resolver = FakeSecretResolver({"model-key": "secret-value"})
        transport = FakeTransport(valid_response())

        planner = build_planner_from_settings(
            enabled_settings(),
            secret_resolver=resolver,
            transport=transport,
        )

        self.assertIsInstance(planner, OpenAICompatiblePlanner)
        decision = planner.decide("open display settings", observation_summary(), 1)
        self.assertEqual("settings.scroll_navigate", decision.skill_id)
        self.assertEqual(["model-key"], resolver.requests)
        self.assertEqual("Bearer secret-value", transport.last_headers["Authorization"])

    def test_enabled_settings_require_explicit_fields(self) -> None:
        invalid_settings = [
            ModelProviderSettings(enabled=True, provider="rule_based"),
            ModelProviderSettings(enabled=True, provider="openai_compatible", base_url="ftp://x", model="m", api_key_ref="ref"),
            ModelProviderSettings(enabled=True, provider="openai_compatible", base_url="https://x", model="", api_key_ref="ref"),
            ModelProviderSettings(enabled=True, provider="openai_compatible", base_url="https://x", model="m", api_key_ref=""),
            ModelProviderSettings(enabled=True, provider="openai_compatible", base_url="https://x", model="m", api_key_ref="ref", timeout_seconds=0),
        ]

        for settings in invalid_settings:
            with self.subTest(settings=settings):
                with self.assertRaises(MobileAgentError) as raised:
                    build_planner_from_settings(settings, secret_resolver=FakeSecretResolver({}))
                self.assertEqual("INVALID_ARGUMENT", raised.exception.code)
                self.assertNotIn("secret-value", str(raised.exception.to_dict()))

    def test_secret_resolver_failure_maps_to_model_unavailable_without_secret(self) -> None:
        resolver = FailingSecretResolver("secret-value")

        with self.assertRaises(MobileAgentError) as raised:
            build_planner_from_settings(enabled_settings(), secret_resolver=resolver)

        self.assertEqual("MODEL_UNAVAILABLE", raised.exception.code)
        self.assertNotIn("secret-value", str(raised.exception.to_dict()))
        self.assertNotIn("model-key", str(raised.exception.to_dict()))

    def test_model_provider_status_is_redacted(self) -> None:
        status = model_provider_status(enabled_settings())

        self.assertEqual(
            {
                "enabled": True,
                "provider": "openai_compatible",
                "model": "test-model",
                "base_url_configured": True,
                "api_key_ref_configured": True,
                "timeout_seconds": 12,
                "status": "configured",
            },
            status,
        )
        self.assertNotIn("model-key", str(status))

    def test_default_model_provider_status_is_disabled_rule_based(self) -> None:
        status = model_provider_status()

        self.assertFalse(status["enabled"])
        self.assertEqual("rule_based", status["provider"])
        self.assertEqual("", status["model"])
        self.assertFalse(status["api_key_ref_configured"])

    def test_load_model_provider_settings_defaults_to_disabled_when_file_missing(self) -> None:
        with TemporaryDirectory() as directory:
            settings = load_model_provider_settings(Path(directory) / "missing.json", {})

        self.assertEqual(ModelProviderSettings(), settings)

    def test_load_model_provider_settings_reads_file_and_environment_overrides(self) -> None:
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "model-provider.json"
            config_path.write_text(
                json.dumps(
                    {
                        "enabled": True,
                        "provider": "openai_compatible",
                        "base_url": "https://file.example/v1",
                        "model": "file-model",
                        "api_key_ref": "env:MOBILE_AGENT_MODEL_SECRET_FILE",
                        "timeout_seconds": 20,
                    }
                ),
                encoding="utf-8",
            )

            settings = load_model_provider_settings(
                config_path,
                {
                    "MOBILE_AGENT_MODEL_NAME": "env-model",
                    "MOBILE_AGENT_MODEL_API_KEY_REF": "env:MOBILE_AGENT_MODEL_SECRET_ENV",
                },
            )

        self.assertTrue(settings.enabled)
        self.assertEqual("openai_compatible", settings.provider)
        self.assertEqual("https://file.example/v1", settings.base_url)
        self.assertEqual("env-model", settings.model)
        self.assertEqual("env:MOBILE_AGENT_MODEL_SECRET_ENV", settings.api_key_ref)
        self.assertEqual(20, settings.timeout_seconds)

    def test_load_model_provider_settings_rejects_invalid_config_without_path_leak(self) -> None:
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "model-provider.json"
            config_path.write_text("{not-json", encoding="utf-8")

            with self.assertRaises(MobileAgentError) as raised:
                load_model_provider_settings(config_path, {})

        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)
        self.assertNotIn(str(config_path), str(raised.exception.to_dict()))

    def test_environment_secret_resolver_allows_scoped_references_only(self) -> None:
        resolver = EnvironmentSecretResolver(
            {"MOBILE_AGENT_MODEL_SECRET_TEST": "test-secret-value"}
        )

        self.assertEqual(
            "test-secret-value",
            resolver.resolve("env:MOBILE_AGENT_MODEL_SECRET_TEST"),
        )

        invalid_references = [
            "env:OPENAI_API_KEY",
            "plain-ref",
            "env:MOBILE_AGENT_MODEL_SECRET_MISSING",
        ]
        for reference in invalid_references:
            with self.subTest(reference=reference):
                with self.assertRaises(MobileAgentError) as raised:
                    resolver.resolve(reference)
                self.assertEqual("MODEL_UNAVAILABLE", raised.exception.code)
                self.assertNotIn("test-secret-value", str(raised.exception.to_dict()))


class FakeSecretResolver:
    def __init__(self, secrets: dict[str, str]) -> None:
        self._secrets = secrets
        self.requests: list[str] = []

    def resolve(self, reference: str) -> str:
        self.requests.append(reference)
        return self._secrets.get(reference, "")


class FailingSecretResolver:
    def __init__(self, secret: str) -> None:
        self._secret = secret

    def resolve(self, reference: str) -> str:
        raise RuntimeError(f"cannot read {self._secret}")


class FakeTransport:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.last_headers: dict[str, str] = {}

    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        self.last_headers = dict(headers)
        return self._response


def enabled_settings() -> ModelProviderSettings:
    return ModelProviderSettings(
        enabled=True,
        provider="openai_compatible",
        base_url="https://model.example/v1",
        model="test-model",
        api_key_ref="model-key",
        timeout_seconds=12,
    )


def observation_summary() -> AgentObservationSummary:
    return AgentObservationSummary(
        observation_id="obs_test",
        foreground_app={"app_id": "com.example.fake", "activity": ".Main"},
        device_state="interactive",
    )


def valid_response() -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "decision_type": "run_skill",
                            "skill_id": "settings.scroll_navigate",
                            "arguments": {
                                "target_selector": {
                                    "strategy": "text",
                                    "value": "Display",
                                    "match": "contains",
                                    "resolve_clickable_ancestor": True,
                                },
                                "expected_selector": {
                                    "strategy": "text",
                                    "value": "Display",
                                    "match": "contains",
                                },
                            },
                            "reason": "The user wants display settings.",
                            "confidence": 0.7,
                        }
                    )
                }
            }
        ]
    }
