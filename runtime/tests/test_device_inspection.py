from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.devices.lease import DeviceLeaseManager
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService


class DeviceInspectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_contract_reuses_readiness_availability(self) -> None:
        schema = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "contracts/schemas/device-inspection.schema.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(
            "https://mobile-agent.local/schemas/device-inspection/v1.json",
            schema["$id"],
        )
        self.assertEqual(
            "runtime-readiness.schema.json#/$defs/device_availability",
            schema["properties"]["availability"]["$ref"],
        )

    def test_ready_device_exposes_capability_policy_metadata(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(
            adapter,
            ArtifactStore(self.root / "artifacts"),
            gateway_transport="fake",
        )

        inspection = asyncio.run(runtime.inspect_device("fake:android-001"))

        self.assertEqual("ready", inspection["availability"]["status"])
        self.assertEqual(17, len(inspection["capabilities"]))
        install = next(
            item for item in inspection["capabilities"]
            if item["capability"] == "app.install@1"
        )
        self.assertEqual("high", install["risk"])
        self.assertTrue(install["confirmation_required"])
        uninstall = next(
            item for item in inspection["capabilities"]
            if item["capability"] == "app.uninstall@1"
        )
        self.assertEqual("high", uninstall["risk"])
        self.assertEqual("unsafe", uninstall["idempotency"])
        by_id = {item["capability"]: item for item in inspection["capabilities"]}
        self.assertEqual("available", by_id["input.tap@1"]["availability"])
        self.assertEqual("medium", by_id["input.tap@1"]["risk"])
        self.assertTrue(by_id["input.tap@1"]["confirmation_required"])
        self.assertEqual(
            ["input.tap", "input.tap_element"], by_id["input.tap@1"]["tools"]
        )
        self.assertFalse(by_id["screen.observe@1"]["confirmation_required"])
        self.assertEqual("medium", by_id["logs.collect@1"]["risk"])
        self.assertEqual(
            ["device.logs.capture"], by_id["logs.collect@1"]["tools"]
        )
        self.assertEqual("low", by_id["performance.snapshot@1"]["risk"])
        self.assertFalse(
            by_id["performance.snapshot@1"]["confirmation_required"]
        )
        self.assertEqual([], adapter.actions)

    def test_busy_device_marks_advertised_capabilities_temporarily_unavailable(self) -> None:
        manager = DeviceLeaseManager()
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(self.root / "artifacts"),
            device_lease_manager=manager,
        )
        device = asyncio.run(runtime.list_devices())[0]
        lease = manager.hold(
            device["device_id"], "task_owner", 60, device["session_id"]
        )
        lease.__enter__()
        self.addCleanup(lambda: lease.__exit__(None, None, None))

        inspection = asyncio.run(runtime.inspect_device(device["device_id"]))

        self.assertEqual("busy", inspection["availability"]["status"])
        self.assertTrue(
            all(
                item["availability"] == "temporarily_unavailable"
                for item in inspection["capabilities"]
            )
        )

    def test_missing_device_returns_stable_error_without_observation(self) -> None:
        adapter = FakeDeviceAdapter([])
        runtime = RuntimeService(adapter, ArtifactStore(self.root / "artifacts"))

        with self.assertRaises(MobileAgentError) as raised:
            asyncio.run(runtime.inspect_device("fake:missing"))

        self.assertEqual("DEVICE_NOT_FOUND", raised.exception.code)
        self.assertEqual([], adapter.actions)

    def test_offline_device_reports_capabilities_as_unknown(self) -> None:
        device = Device(
            device_id="fake:offline",
            platform=Platform.ANDROID,
            name="Offline phone",
            model="test",
            os_version="",
            connection=ConnectionState.OFFLINE,
        )
        runtime = RuntimeService(
            FakeDeviceAdapter([device]), ArtifactStore(self.root / "artifacts")
        )

        inspection = asyncio.run(runtime.inspect_device(device.device_id))

        self.assertEqual("offline", inspection["availability"]["status"])
        self.assertTrue(
            all(
                item["availability"] == "unknown"
                for item in inspection["capabilities"]
            )
        )

    def test_tool_registry_metadata_comes_from_capability_catalog(self) -> None:
        runtime = RuntimeService(
            FakeDeviceAdapter(), ArtifactStore(self.root / "artifacts")
        )
        tools = {item["tool_id"]: item for item in runtime.list_tools()}
        inspection = asyncio.run(runtime.inspect_device("fake:android-001"))
        capabilities = {
            item["capability"]: item for item in inspection["capabilities"]
        }

        for tool in tools.values():
            capability = capabilities[tool["capability"]]
            self.assertEqual(capability["risk"], tool["risk"])
            self.assertEqual(capability["idempotency"], tool["idempotency"])


if __name__ == "__main__":
    unittest.main()
