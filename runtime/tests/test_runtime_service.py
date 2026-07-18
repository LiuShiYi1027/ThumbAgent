from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from mobile_agent import __version__
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.providers import ModelProviderSettings, OpenAICompatiblePlanner
from mobile_agent.runtime import RuntimeService, build_runtime_planner


class RuntimeServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.runtime = RuntimeService(
            FakeDeviceAdapter(), ArtifactStore(Path(self.directory.name))
        )

    async def test_health_has_explicit_versions(self) -> None:
        self.assertEqual(
            {"status": "ok", "runtime_version": __version__, "api_version": "v1"},
            self.runtime.health(),
        )

    async def test_device_list_uses_public_contract(self) -> None:
        devices = await self.runtime.list_devices()
        self.assertEqual("1.0.0", devices[0]["schema_version"])
        self.assertEqual("android", devices[0]["platform"])
        self.assertRegex(devices[0]["session_id"], r"^session_[a-f0-9]{32}$")

    async def test_model_provider_status_defaults_to_disabled(self) -> None:
        status, payload = self.runtime.model_provider_status_sync()

        self.assertEqual(200, status.value)
        model_provider = payload["model_provider"]
        self.assertFalse(model_provider["enabled"])
        self.assertEqual("rule_based", model_provider["provider"])
        self.assertFalse(model_provider["api_key_ref_configured"])
        self.assertEqual("disabled", model_provider["status"])

    async def test_model_provider_status_reports_unavailable_without_reference_value(self) -> None:
        error = MobileAgentError(
            code="MODEL_UNAVAILABLE",
            category=ErrorCategory.EXECUTION,
            message="模型密钥引用未解析到值",
            details={"has_api_key_ref": True},
        )
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(Path(self.directory.name)),
            model_provider_settings=enabled_settings(),
            model_provider_runtime_status="unavailable",
            model_provider_error=error,
        )

        status, payload = runtime.model_provider_status_sync()

        self.assertEqual(200, status.value)
        model_provider = payload["model_provider"]
        self.assertEqual("unavailable", model_provider["status"])
        self.assertEqual("MODEL_UNAVAILABLE", model_provider["error"]["code"])
        self.assertNotIn("model-key", str(model_provider))

    async def test_build_runtime_planner_uses_model_when_enabled_and_secret_resolves(self) -> None:
        with patch.dict(
            "os.environ",
            {"MOBILE_AGENT_MODEL_SECRET_TEST": "secret-value"},
            clear=True,
        ):
            planner, status, error = build_runtime_planner(enabled_settings())

        self.assertIsInstance(planner, OpenAICompatiblePlanner)
        self.assertEqual("active", status)
        self.assertIsNone(error)

    async def test_build_runtime_planner_preserves_unavailable_model_error(self) -> None:
        planner, status, error = build_runtime_planner(enabled_settings())

        self.assertEqual("model.unavailable", planner.planner_id)
        self.assertEqual("unavailable", status)
        self.assertIsNotNone(error)
        assert error is not None
        self.assertEqual("MODEL_UNAVAILABLE", error.code)
        self.assertNotIn("model-key", str(error.to_dict()))

    async def test_observe_returns_artifact_references_without_inline_content(self) -> None:
        observation = await self.runtime.observe("fake:android-001")

        self.assertEqual("1.0.0", observation["schema_version"])
        self.assertEqual("image/png", observation["screen"]["screenshot"]["content_type"])
        self.assertNotIn("data", observation["screen"]["screenshot"])
        self.assertEqual("application/xml", observation["ui_tree"]["artifact"]["content_type"])


def enabled_settings() -> ModelProviderSettings:
    return ModelProviderSettings(
        enabled=True,
        provider="openai_compatible",
        base_url="https://model.example/v1",
        model="test-model",
        api_key_ref="env:MOBILE_AGENT_MODEL_SECRET_TEST",
        timeout_seconds=12,
    )
