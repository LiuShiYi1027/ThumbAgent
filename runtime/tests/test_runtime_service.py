from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from mobile_agent import __version__
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.runtime import RuntimeService
from mobile_agent.evidence.artifacts import ArtifactStore


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

    async def test_observe_returns_artifact_references_without_inline_content(self) -> None:
        observation = await self.runtime.observe("fake:android-001")

        self.assertEqual("1.0.0", observation["schema_version"])
        self.assertEqual("image/png", observation["screen"]["screenshot"]["content_type"])
        self.assertNotIn("data", observation["screen"]["screenshot"])
        self.assertEqual("application/xml", observation["ui_tree"]["artifact"]["content_type"])
