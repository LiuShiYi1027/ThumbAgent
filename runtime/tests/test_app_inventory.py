from __future__ import annotations

import json
import unittest
from pathlib import Path

from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.devices.adapters.android.app_parser import (
    parse_package_details,
    parse_package_list,
)
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.tools.app_inventory import AppInventoryTool
from mobile_agent.tools.runtime import ToolRegistry
from runtime.tests.fakes import FakeProcessRunner, result


class AndroidAppInventoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_fixed_commands_and_returns_structured_metadata(self) -> None:
        list_command = (
            "-s", "serial-1", "shell", "pm", "list", "packages", "--user", "0"
        )
        inspect_command = (
            "-s", "serial-1", "shell", "dumpsys", "package", "com.example.shop"
        )
        process = FakeProcessRunner(
            {
                list_command: result(
                    list_command,
                    "package:com.example.shop\nmalformed\npackage:com.android.settings\n",
                ),
                inspect_command: result(
                    inspect_command,
                    "Package [com.example.shop]\n  versionCode=42 minSdk=23\n"
                    "  versionName=2.1.0\n  installerPackageName=com.android.vending\n"
                    "  enabled=0\n  flags=[ HAS_CODE ]\n  signatures=private-data\n",
                ),
            }
        )
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))

        apps = await adapter.list_installed_apps("adb:serial-1")
        app = await adapter.inspect_installed_app("adb:serial-1", "com.example.shop")

        self.assertEqual(("com.android.settings", "com.example.shop"), apps)
        self.assertEqual("2.1.0", app.version_name)
        self.assertEqual(42, app.version_code)
        self.assertEqual("com.android.vending", app.installer_app_id)
        self.assertTrue(app.enabled)
        self.assertFalse(app.system_app)
        self.assertEqual([list_command, inspect_command], [call[1] for call in process.calls])
        self.assertNotIn("signatures", str(app.to_dict()))

    async def test_rejects_invalid_app_id_before_process_call(self) -> None:
        process = FakeProcessRunner({})
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))
        with self.assertRaises(MobileAgentError) as raised:
            await adapter.inspect_installed_app("adb:serial-1", "bad package;id")
        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)
        self.assertEqual([], process.calls)


class AppInventoryToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_lists_bounded_prefix_and_inspects_app(self) -> None:
        adapter = FakeDeviceAdapter()
        tool = AppInventoryTool(adapter, ToolRegistry(), PolicyEngine())

        inventory = await tool.list("fake:android-001", 1, "com.")
        app = await tool.inspect("fake:android-001", "com.example.fake")

        self.assertEqual(2, inventory.total_matched)
        self.assertTrue(inventory.truncated)
        self.assertEqual("com.android.settings", inventory.apps[0].app_id)
        self.assertEqual("1.0", app.version_name)

    async def test_invalid_request_is_rejected_before_adapter_access(self) -> None:
        adapter = FakeDeviceAdapter()
        tool = AppInventoryTool(adapter, ToolRegistry(), PolicyEngine())
        with self.assertRaises(MobileAgentError) as raised:
            await tool.list("fake:android-001", 0)
        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_missing_capability_is_rejected(self) -> None:
        device = Device(
            "fake:limited", Platform.ANDROID, "Limited", "limited", "15",
            ConnectionState.ONLINE, ("device.inspect@1",),
        )
        adapter = FakeDeviceAdapter([device])
        tool = AppInventoryTool(adapter, ToolRegistry(), PolicyEngine())
        with self.assertRaises(MobileAgentError) as raised:
            await tool.list("fake:limited")
        self.assertEqual("CAPABILITY_UNAVAILABLE", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_policy_rejection_is_preserved_before_package_read(self) -> None:
        class RejectingPolicy:
            def authorize(self, risk: object, confirmed: bool = False) -> None:
                del risk, confirmed
                raise MobileAgentError(
                    code="ACTION_REJECTED_BY_POLICY",
                    category=ErrorCategory.POLICY,
                    message="test policy rejection",
                )

        adapter = FakeDeviceAdapter()
        tool = AppInventoryTool(adapter, ToolRegistry(), RejectingPolicy())  # type: ignore[arg-type]
        with self.assertRaises(MobileAgentError) as raised:
            await tool.list("fake:android-001")
        self.assertEqual("ACTION_REJECTED_BY_POLICY", raised.exception.code)
        self.assertEqual([], adapter.actions)

    def test_contracts_and_manifest_are_strict(self) -> None:
        root = Path(__file__).resolve().parents[2]
        result_schema = json.loads(
            (root / "contracts/schemas/app-inventory-result.schema.json").read_text()
        )
        list_manifest = json.loads(
            (root / "runtime/mobile_agent/skills/manifests/app.list.json").read_text()
        )
        inspect_manifest = json.loads(
            (root / "runtime/mobile_agent/skills/manifests/app.inspect.json").read_text()
        )
        self.assertEqual("1.0.0", result_schema["properties"]["schema_version"]["const"])
        self.assertEqual(["app.inspect@1"], list_manifest["required_capabilities"])
        self.assertEqual(["app.list"], list_manifest["tool_allowlist"])
        self.assertEqual(["app.inspect"], inspect_manifest["tool_allowlist"])
        self.assertEqual("low", inspect_manifest["risk"])


class AppParserTests(unittest.TestCase):
    def test_parsers_ignore_malformed_and_missing_optional_fields(self) -> None:
        self.assertEqual(("com.example.ok",), parse_package_list(
            "package:com.example.ok\npackage:bad value\npackage:com.example.ok\n"
        ))
        self.assertEqual(
            {"app_id": "com.example.ok", "version_name": None, "version_code": None,
             "installer_app_id": None, "enabled": None, "system_app": None},
            parse_package_details("com.example.ok", "Package [com.example.ok]").to_dict(),
        )


if __name__ == "__main__":
    unittest.main()
