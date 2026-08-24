from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mobile_agent.devices.adapters.android.notification_parser import (
    parse_notification_records,
)
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService

DUMPSYS_SAMPLE = """Notification Service (System) :

  Notification List:
    NotificationRecord(0x08904a1: pkg=com.android.systemui user=UserHandle{0} key=0|com.android.systemui|46|null|10224 isUpdate=false importance=3):
      when=1752300000000
      extras={
        android.title=String (USB debugging connected)
        android.text=String (Tap to disable USB debugging. This is a long body that must never be captured.)
      }
    NotificationRecord(0x08904b2: pkg=com.tencent.mm user=UserHandle{0} key=0|com.tencent.mm|7|null|10205 isUpdate=false importance=4):
      extras={
        android.title=String (微信)
        android.text=String (张三: 晚上一起吃饭吗？)
      }
"""


class NotificationParserTests(unittest.TestCase):
    def test_parses_records_and_drops_body_text(self) -> None:
        records = parse_notification_records(DUMPSYS_SAMPLE)

        self.assertIsNotNone(records)
        assert records is not None
        self.assertEqual(2, len(records))
        package, title, posted = records[0]
        self.assertEqual("com.android.systemui", package)
        self.assertEqual("USB debugging connected", title)
        self.assertEqual(1752300000000, posted)
        second_package, second_title, second_posted = records[1]
        self.assertEqual("com.tencent.mm", second_package)
        self.assertEqual("微信", second_title)
        self.assertIsNone(second_posted)
        self.assertNotIn("晚上一起吃饭吗", str(records))

    def test_zero_notifications_returns_empty_list(self) -> None:
        self.assertEqual([], parse_notification_records("Notification List:\n"))

    def test_unrecognizable_output_returns_none(self) -> None:
        self.assertIsNone(parse_notification_records("completely unexpected format"))
        self.assertIsNone(parse_notification_records(""))

    def test_bracket_wrapped_title_from_vendor_rom(self) -> None:
        """部分厂商 ROM（如 MagicOS）用 String [...] 而非 String (...) 包装标题。"""
        sample = """Notification List:
    NotificationRecord(0x0001: pkg=com.quark.browser user=UserHandle{0} key=0|com.quark.browser|9|null|10206):
      postTime=1752300000000
      extras={
        android.title=String [下载完成]
        android.text=String [正文内容必须被丢弃]
      }
"""
        records = parse_notification_records(sample)

        self.assertIsNotNone(records)
        assert records is not None
        self.assertEqual(
            [("com.quark.browser", "下载完成", 1752300000000)], records
        )
        self.assertNotIn("正文内容必须被丢弃", str(records))

    def test_length_only_title_marker_is_treated_as_missing(self) -> None:
        """厂商脱敏的 `String [length=N]` 只是长度标记，不能冒充标题。"""
        sample = """Notification List:
    NotificationRecord(0x0001: pkg=com.quark.browser user=UserHandle{0} key=0|com.quark.browser|9|null|10206):
      when=1752300000000
      extras={
        android.title=String [length=19]
        android.text=String [length=57]
      }
"""
        records = parse_notification_records(sample)

        self.assertIsNotNone(records)
        assert records is not None
        self.assertEqual([("com.quark.browser", None, 1752300000000)], records)
        self.assertNotIn("length=19", str(records))


class DeviceNotificationsReadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.artifacts = ArtifactStore(Path(self.directory.name))

    async def test_success_returns_bounded_minimized_result(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        result = await runtime.read_device_notifications(
            "fake:android-001", 20, confirmed=True
        )

        self.assertTrue(result["success"])
        self.assertEqual("verified", result["verification"])
        self.assertEqual(2, result["total_matched"])
        self.assertFalse(result["truncated"])
        first = result["notifications"][0]
        self.assertEqual("com.android.systemui", first["package"])
        self.assertLessEqual(len(first["title"] or ""), 32)
        self.assertEqual("device_notifications", result["artifact"]["kind"])
        self.assertEqual(
            [("device.notifications.capture", "fake:android-001")], adapter.actions
        )
        content = self.artifacts.resolve(result["artifact"]["relative_path"]).read_text()
        self.assertIn("com.android.systemui", content)

    async def test_title_is_truncated_to_contract_limit(self) -> None:
        adapter = LongTitleAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        result = await runtime.read_device_notifications(
            "fake:android-001", 20, confirmed=True
        )

        self.assertEqual(32, len(result["notifications"][0]["title"]))

    async def test_bound_is_enforced_and_marked_truncated(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        result = await runtime.read_device_notifications(
            "fake:android-001", 1, confirmed=True
        )

        self.assertEqual(1, len(result["notifications"]))
        self.assertEqual(2, result["total_matched"])
        self.assertTrue(result["truncated"])

    async def test_invalid_arguments_are_rejected_before_adapter_io(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        for bad in (0, 51, "20", True):
            with self.assertRaises(MobileAgentError) as raised:
                await runtime.read_device_notifications(
                    "fake:android-001", bad, confirmed=True
                )
            self.assertEqual("INVALID_ARGUMENT", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_policy_requires_explicit_confirmation(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.read_device_notifications(
                "fake:android-001", 20, confirmed=False
            )

        self.assertEqual("CONFIRMATION_REQUIRED", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_missing_capability_is_rejected(self) -> None:
        device = Device(
            device_id="fake:no-notifications",
            platform=Platform.ANDROID,
            name="No notifications",
            model="fake",
            os_version="15",
            connection=ConnectionState.ONLINE,
            capabilities=("device.inspect@1",),
        )
        adapter = FakeDeviceAdapter([device])
        runtime = RuntimeService(adapter, self.artifacts)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.read_device_notifications(
                device.device_id, 20, confirmed=True
            )

        self.assertEqual("CAPABILITY_UNAVAILABLE", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_empty_and_failed_reads_use_distinct_errors(self) -> None:
        empty_runtime = RuntimeService(EmptyNotificationsAdapter(), self.artifacts)
        with self.assertRaises(MobileAgentError) as raised_empty:
            await empty_runtime.read_device_notifications(
                "fake:android-001", 20, confirmed=True
            )
        self.assertEqual("NOTIFICATIONS_READ_EMPTY", raised_empty.exception.code)

        failed_runtime = RuntimeService(FailingNotificationsAdapter(), self.artifacts)
        with self.assertRaises(MobileAgentError) as raised_failed:
            await failed_runtime.read_device_notifications(
                "fake:android-001", 20, confirmed=True
            )
        self.assertEqual("NOTIFICATIONS_READ_FAILED", raised_failed.exception.code)

    async def test_low_level_tool_cannot_use_generic_action_endpoint(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.invoke_tool(
                "device.notifications.capture",
                "fake:android-001",
                {"max_notifications": 20},
                confirmed=True,
            )

        self.assertEqual("TOOL_REQUIRES_SKILL", raised.exception.code)
        self.assertEqual([], adapter.actions)

    def test_result_contract_and_manifest_are_bounded(self) -> None:
        root = Path(__file__).resolve().parents[2]
        schema = json.loads(
            (
                root / "contracts/schemas/device-notifications-result.schema.json"
            ).read_text()
        )
        artifact = json.loads(
            (root / "contracts/schemas/artifact.schema.json").read_text()
        )
        manifest = json.loads(
            (
                root
                / "runtime/mobile_agent/skills/manifests/device.notifications.read.json"
            ).read_text()
        )

        self.assertEqual(
            "device.notifications.read", schema["properties"]["skill_id"]["const"]
        )
        self.assertEqual(50, schema["properties"]["notifications"]["maxItems"])
        self.assertEqual(
            32,
            schema["properties"]["notifications"]["items"]["properties"]["title"][
                "maxLength"
            ],
        )
        self.assertIn("device_notifications", artifact["properties"]["kind"]["enum"])
        self.assertEqual(
            ["notifications.read@1"], manifest["required_capabilities"]
        )
        self.assertEqual(
            ["device.notifications.capture"], manifest["tool_allowlist"]
        )
        self.assertEqual("medium", manifest["risk"])


class LongTitleAdapter(FakeDeviceAdapter):
    async def read_notifications(
        self, device_id: str
    ) -> list[tuple[str, str | None, int | None]]:
        return [("com.example.fake", "x" * 100, None)]


class EmptyNotificationsAdapter(FakeDeviceAdapter):
    async def read_notifications(
        self, device_id: str
    ) -> list[tuple[str, str | None, int | None]]:
        raise MobileAgentError(
            code="NOTIFICATIONS_READ_EMPTY",
            category=ErrorCategory.DEVICE,
            message="设备当前没有活动通知",
        )


class FailingNotificationsAdapter(FakeDeviceAdapter):
    async def read_notifications(
        self, device_id: str
    ) -> list[tuple[str, str | None, int | None]]:
        raise MobileAgentError(
            code="NOTIFICATIONS_READ_FAILED",
            category=ErrorCategory.DEVICE,
            message="设备通知读取失败",
        )


if __name__ == "__main__":
    unittest.main()
