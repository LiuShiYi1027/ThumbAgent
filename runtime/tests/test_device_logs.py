from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.device_log import DeviceLogLevel
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService
from mobile_agent.tools.log_capture import MAX_LOG_ARTIFACT_BYTES


class DeviceLogSkillTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.artifacts = ArtifactStore(Path(self.directory.name))

    async def test_success_redacts_sensitive_values_and_returns_only_artifact_reference(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        result = await runtime.collect_device_logs(
            "fake:android-001", 100, "info", confirmed=True
        )

        self.assertTrue(result["success"])
        self.assertEqual("verified", result["verification"])
        self.assertEqual("device_log", result["artifact"]["kind"])
        self.assertEqual(1, result["redaction_count"])
        self.assertNotIn("user@example.com", str(result))
        content = self.artifacts.resolve(result["artifact"]["relative_path"]).read_text()
        self.assertIn("[REDACTED_EMAIL]", content)
        self.assertNotIn("user@example.com", content)
        self.assertEqual(
            [("device.logs.capture", "fake:android-001", 100, "info")],
            adapter.actions,
        )

    async def test_invalid_arguments_are_rejected_before_adapter_io(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.collect_device_logs(
                "fake:android-001", 0, "info", confirmed=True
            )

        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_missing_capability_is_rejected(self) -> None:
        device = Device(
            device_id="fake:no-logs",
            platform=Platform.ANDROID,
            name="No logs",
            model="fake",
            os_version="15",
            connection=ConnectionState.ONLINE,
            capabilities=("device.inspect@1",),
        )
        adapter = FakeDeviceAdapter([device])
        runtime = RuntimeService(adapter, self.artifacts)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.collect_device_logs(
                device.device_id, 100, "info", confirmed=True
            )

        self.assertEqual("CAPABILITY_UNAVAILABLE", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_policy_requires_explicit_confirmation(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.collect_device_logs(
                "fake:android-001", 100, "info", confirmed=False
            )

        self.assertEqual("CONFIRMATION_REQUIRED", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_low_level_tool_cannot_use_generic_action_endpoint(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.invoke_tool(
                "device.logs.capture",
                "fake:android-001",
                {"max_lines": 100, "minimum_level": "info"},
                confirmed=True,
            )

        self.assertEqual("TOOL_REQUIRES_SKILL", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_offline_device_is_rejected_before_capture(self) -> None:
        device = Device(
            device_id="fake:offline",
            platform=Platform.ANDROID,
            name="Offline",
            model="fake",
            os_version="15",
            connection=ConnectionState.OFFLINE,
            capabilities=("logs.collect@1",),
        )
        adapter = FakeDeviceAdapter([device])
        runtime = RuntimeService(adapter, self.artifacts)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.collect_device_logs(
                device.device_id, 100, "info", confirmed=True
            )

        self.assertEqual("DEVICE_OFFLINE", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_adapter_failure_is_preserved(self) -> None:
        adapter = FailingLogAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.collect_device_logs(
                "fake:android-001", 100, "info", confirmed=True
            )

        self.assertEqual("LOG_CAPTURE_FAILED", raised.exception.code)

    async def test_cancellation_propagates_at_adapter_wait(self) -> None:
        adapter = BlockingLogAdapter()
        runtime = RuntimeService(adapter, self.artifacts)
        task = asyncio.create_task(
            runtime.collect_device_logs(
                "fake:android-001", 100, "info", confirmed=True
            )
        )
        await adapter.started.wait()

        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_output_is_truncated_to_artifact_limit(self) -> None:
        adapter = LargeLogAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        result = await runtime.collect_device_logs(
            "fake:android-001", 2000, "debug", confirmed=True
        )

        self.assertTrue(result["truncated"])
        self.assertLessEqual(result["captured_bytes"], MAX_LOG_ARTIFACT_BYTES)

    def test_result_contract_declares_bounded_artifact_output(self) -> None:
        root = Path(__file__).resolve().parents[2]
        schema = json.loads(
            (root / "contracts/schemas/device-log-capture-result.schema.json").read_text()
        )
        artifact = json.loads(
            (root / "contracts/schemas/artifact.schema.json").read_text()
        )

        self.assertEqual("device.logs.collect", schema["properties"]["skill_id"]["const"])
        self.assertEqual(
            MAX_LOG_ARTIFACT_BYTES,
            schema["properties"]["captured_bytes"]["maximum"],
        )
        self.assertIn("device_log", artifact["properties"]["kind"]["enum"])
        self.assertIn("text/plain", artifact["properties"]["content_type"]["enum"])

    def test_skill_manifest_declares_tool_capability_risk_and_verification(self) -> None:
        root = Path(__file__).resolve().parents[2]
        manifest_schema = json.loads(
            (root / "contracts/schemas/skill-manifest.schema.json").read_text()
        )
        manifest = json.loads(
            (
                root
                / "runtime/mobile_agent/skills/manifests/device.logs.collect.json"
            ).read_text()
        )

        self.assertEqual("device.logs.collect", manifest["id"])
        self.assertTrue(set(manifest_schema["required"]).issubset(manifest))
        self.assertEqual(["logs.collect@1"], manifest["required_capabilities"])
        self.assertEqual(["device.logs.capture"], manifest["tool_allowlist"])
        self.assertEqual("medium", manifest["risk"])
        self.assertEqual("non_empty_redacted_artifact", manifest["verification"])


class FailingLogAdapter(FakeDeviceAdapter):
    async def collect_logs(
        self, device_id: str, max_lines: int, minimum_level: DeviceLogLevel
    ) -> bytes:
        raise MobileAgentError(
            code="LOG_CAPTURE_FAILED",
            category=ErrorCategory.DEVICE,
            message="设备日志采集失败",
        )


class BlockingLogAdapter(FakeDeviceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()

    async def collect_logs(
        self, device_id: str, max_lines: int, minimum_level: DeviceLogLevel
    ) -> bytes:
        self.started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


class LargeLogAdapter(FakeDeviceAdapter):
    async def collect_logs(
        self, device_id: str, max_lines: int, minimum_level: DeviceLogLevel
    ) -> bytes:
        return b"x" * (MAX_LOG_ARTIFACT_BYTES + 4096)


if __name__ == "__main__":
    unittest.main()
