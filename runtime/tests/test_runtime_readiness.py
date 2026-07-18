from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.devices.lease import DeviceLeaseManager
from mobile_agent.devices.unavailable import UnavailableDeviceAdapter
from mobile_agent.domain.artifact import ArtifactWriter
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.observation import Observation
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService, build_default_runtime


def _device(device_id: str, connection: ConnectionState) -> Device:
    return Device(
        device_id=device_id,
        platform=Platform.ANDROID,
        name=device_id,
        model="test",
        os_version="15",
        connection=connection,
        capabilities=("device.inspect@1",) if connection is ConnectionState.ONLINE else (),
    )


class _CountingFakeAdapter(FakeDeviceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.observation_count = 0

    async def observe(
        self, device_id: str, artifacts: ArtifactWriter
    ) -> Observation:
        self.observation_count += 1
        return await super().observe(device_id, artifacts)


class RuntimeReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_readiness_contract_is_versioned_and_reuses_device_contract(self) -> None:
        schema = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "contracts/schemas/runtime-readiness.schema.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(
            "https://mobile-agent.local/schemas/runtime-readiness/v1.json",
            schema["$id"],
        )
        self.assertEqual(
            "#/$defs/device_availability",
            schema["properties"]["devices"]["items"]["$ref"],
        )
        device_schema = schema["$defs"]["device_availability"]["properties"]["device"]
        self.assertEqual("device.schema.json", device_schema["$ref"])

    def test_ready_busy_and_unauthorized_devices_are_explained(self) -> None:
        manager = DeviceLeaseManager(monotonic_clock=lambda: 10.0)
        runtime = RuntimeService(
            FakeDeviceAdapter(
                [
                    _device("fake:ready", ConnectionState.ONLINE),
                    _device("fake:busy", ConnectionState.ONLINE),
                    _device("fake:unauthorized", ConnectionState.UNAUTHORIZED),
                ]
            ),
            ArtifactStore(self.root / "artifacts"),
            device_lease_manager=manager,
            monotonic_clock=lambda: 10.0,
        )
        devices = asyncio.run(runtime.list_devices())
        busy_session = next(
            item["session_id"] for item in devices if item["device_id"] == "fake:busy"
        )
        lease = manager.hold("fake:busy", "task_owner", 60, busy_session)
        lease.__enter__()
        self.addCleanup(lambda: lease.__exit__(None, None, None))

        readiness = asyncio.run(runtime.readiness())

        self.assertEqual("ready", readiness["status"])
        self.assertEqual(
            {"total": 3, "ready": 1, "busy": 1, "attention": 1},
            readiness["summary"],
        )
        by_id = {
            item["device"]["device_id"]: item for item in readiness["devices"]
        }
        self.assertEqual("ready", by_id["fake:ready"]["status"])
        self.assertEqual("busy", by_id["fake:busy"]["status"])
        self.assertEqual("task_owner", by_id["fake:busy"]["lease_owner_id"])
        self.assertEqual(
            "DEVICE_UNAUTHORIZED",
            by_id["fake:unauthorized"]["issues"][0]["code"],
        )

    def test_no_device_is_blocked_with_remediation(self) -> None:
        runtime = RuntimeService(
            FakeDeviceAdapter([]), ArtifactStore(self.root / "artifacts")
        )

        readiness = asyncio.run(runtime.readiness())

        self.assertEqual("blocked", readiness["status"])
        self.assertEqual("available", readiness["gateway"]["status"])
        self.assertEqual("DEVICE_NOT_FOUND", readiness["issues"][0]["code"])

    def test_readiness_does_not_observe_or_write_device(self) -> None:
        adapter = _CountingFakeAdapter()
        runtime = RuntimeService(adapter, ArtifactStore(self.root / "artifacts"))

        readiness = asyncio.run(runtime.readiness())

        self.assertEqual("ready", readiness["status"])
        self.assertEqual(0, adapter.observation_count)
        self.assertEqual([], adapter.actions)

    def test_unavailable_gateway_keeps_readiness_renderable(self) -> None:
        error = MobileAgentError(
            code="ADB_NOT_FOUND",
            category=ErrorCategory.DEVICE,
            message="未找到 Android Platform Tools",
            suggested_action="安装 adb 后重启 Runtime",
        )
        runtime = RuntimeService(
            UnavailableDeviceAdapter(error),
            ArtifactStore(self.root / "artifacts"),
            device_gateway_error=error,
            gateway_transport="adb",
        )

        status, payload = runtime.readiness_sync()

        self.assertEqual(200, status.value)
        self.assertEqual("blocked", payload["readiness"]["status"])
        self.assertEqual("unavailable", payload["readiness"]["gateway"]["status"])
        self.assertEqual(
            "ADB_NOT_FOUND", payload["readiness"]["gateway"]["issue"]["code"]
        )

    def test_default_runtime_starts_in_diagnostic_mode_without_adb(self) -> None:
        error = MobileAgentError(
            code="ADB_NOT_FOUND",
            category=ErrorCategory.DEVICE,
            message="未找到 Android Platform Tools",
            suggested_action="安装 adb",
        )
        with patch(
            "mobile_agent.runtime.default_artifact_root",
            return_value=self.root / "artifacts",
        ), patch("mobile_agent.runtime.AdbRunner", side_effect=error):
            runtime = build_default_runtime()

        readiness = asyncio.run(runtime.readiness())
        self.assertEqual("blocked", readiness["status"])
        self.assertIn("重启", readiness["gateway"]["issue"]["suggested_action"])


if __name__ == "__main__":
    unittest.main()
