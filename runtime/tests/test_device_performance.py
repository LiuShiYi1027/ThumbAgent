from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mobile_agent.devices.adapters.android.performance_parser import (
    parse_performance_snapshot,
)
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.action import RiskLevel
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.performance import DevicePerformanceSnapshot
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.runtime import RuntimeService
from mobile_agent.skills.device_performance import DevicePerformanceSnapshotSkill
from mobile_agent.tools.performance_capture import DevicePerformanceCaptureTool
from mobile_agent.tools.runtime import ToolRegistry


CPU = " 6.7% TOTAL: 2.0% user + 4.7% kernel\n"
MEMORY = " Total RAM: 11,418,812K\n Free RAM: 5,559,932K\n"
BATTERY = " status: 2\n level: 100\n scale: 100\n temperature: 310\n"
UPTIME = "3600.50 1200.00\n"
LOAD = "1.00 0.80 0.60 1/100 123\n"


class PerformanceParserTests(unittest.TestCase):
    def test_parses_only_aggregate_metrics(self) -> None:
        snapshot = parse_performance_snapshot(
            "adb:001", CPU, MEMORY, BATTERY, UPTIME, LOAD
        )

        payload = snapshot.to_dict()
        self.assertEqual(6.7, payload["cpu"]["total_usage_percent"])
        self.assertEqual(11_418_812 * 1024, payload["memory"]["total_bytes"])
        self.assertEqual(100.0, payload["battery"]["level_percent"])
        self.assertEqual(31.0, payload["battery"]["temperature_celsius"])
        self.assertEqual(1.0, payload["system"]["load_average_1m"])
        self.assertNotIn("process", str(payload).lower())

    def test_invalid_output_returns_safe_error_without_raw_details(self) -> None:
        with self.assertRaises(MobileAgentError) as raised:
            parse_performance_snapshot(
                "adb:001", "secret-process-name", "", "", "", ""
            )

        self.assertEqual("PERFORMANCE_SNAPSHOT_FAILED", raised.exception.code)
        self.assertNotIn("secret-process-name", str(raised.exception.to_dict()))


class DevicePerformanceSkillTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.artifacts = ArtifactStore(Path(self.directory.name))

    async def test_success_persists_normalized_json_without_raw_diagnostics(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        result = await runtime.capture_device_performance("fake:android-001")

        self.assertTrue(result["success"])
        self.assertEqual("device_performance", result["artifact"]["kind"])
        self.assertEqual(12.5, result["snapshot"]["cpu"]["total_usage_percent"])
        content = json.loads(
            self.artifacts.resolve(result["artifact"]["relative_path"]).read_text()
        )
        self.assertEqual(result["snapshot"], content)
        self.assertNotIn("process", str(content).lower())
        self.assertEqual(
            [("device.performance.capture", "fake:android-001")], adapter.actions
        )

    async def test_missing_capability_is_rejected_before_capture(self) -> None:
        device = Device(
            device_id="fake:no-performance",
            platform=Platform.ANDROID,
            name="No performance",
            model="fake",
            os_version="15",
            connection=ConnectionState.ONLINE,
            capabilities=("device.inspect@1",),
        )
        adapter = FakeDeviceAdapter([device])
        runtime = RuntimeService(adapter, self.artifacts)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.capture_device_performance(device.device_id)

        self.assertEqual("CAPABILITY_UNAVAILABLE", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_policy_rejection_is_preserved_before_adapter_capture(self) -> None:
        adapter = FakeDeviceAdapter()
        tool = DevicePerformanceCaptureTool(
            adapter,
            self.artifacts,
            ToolRegistry(),
            _RejectingPolicy(),
        )
        skill = DevicePerformanceSnapshotSkill(tool)

        with self.assertRaises(MobileAgentError) as raised:
            await skill.invoke("fake:android-001")

        self.assertEqual("ACTION_REJECTED_BY_POLICY", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_low_level_tool_cannot_use_generic_action_pipeline(self) -> None:
        runtime = RuntimeService(FakeDeviceAdapter(), self.artifacts)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.invoke_tool(
                "device.performance.capture", "fake:android-001", {}
            )

        self.assertEqual("TOOL_REQUIRES_SKILL", raised.exception.code)

    async def test_offline_device_is_rejected_before_capture(self) -> None:
        device = Device(
            device_id="fake:offline-performance",
            platform=Platform.ANDROID,
            name="Offline",
            model="fake",
            os_version="15",
            connection=ConnectionState.OFFLINE,
            capabilities=("performance.snapshot@1",),
        )
        adapter = FakeDeviceAdapter([device])
        runtime = RuntimeService(adapter, self.artifacts)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.capture_device_performance(device.device_id)

        self.assertEqual("DEVICE_OFFLINE", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_cancellation_propagates_during_adapter_io(self) -> None:
        adapter = _BlockingPerformanceAdapter()
        runtime = RuntimeService(adapter, self.artifacts)
        task = asyncio.create_task(
            runtime.capture_device_performance("fake:android-001")
        )
        await adapter.started.wait()

        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await task

    def test_contracts_and_manifest_are_versioned(self) -> None:
        root = Path(__file__).resolve().parents[2]
        snapshot = json.loads(
            (root / "contracts/schemas/device-performance-snapshot.schema.json").read_text()
        )
        result = json.loads(
            (
                root
                / "contracts/schemas/device-performance-snapshot-result.schema.json"
            ).read_text()
        )
        manifest = json.loads(
            (
                root
                / "runtime/mobile_agent/skills/manifests/device.performance.snapshot.json"
            ).read_text()
        )

        self.assertEqual("1.0.0", snapshot["properties"]["schema_version"]["const"])
        self.assertEqual(
            "device.performance.snapshot", result["properties"]["skill_id"]["const"]
        )
        self.assertEqual("low", manifest["risk"])
        self.assertEqual(["performance.snapshot@1"], manifest["required_capabilities"])


class _RejectingPolicy(PolicyEngine):
    def authorize(self, risk: RiskLevel, confirmed: bool = False) -> None:
        raise MobileAgentError(
            code="ACTION_REJECTED_BY_POLICY",
            category=ErrorCategory.POLICY,
            message="测试策略拒绝",
        )


class _BlockingPerformanceAdapter(FakeDeviceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()

    async def capture_performance(
        self, device_id: str
    ) -> DevicePerformanceSnapshot:
        self.started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


if __name__ == "__main__":
    unittest.main()
