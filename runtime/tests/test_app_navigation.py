from __future__ import annotations

import json
import unittest
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.capability import CapabilityCatalog
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.navigation import (
    NAVIGATION_TARGETS,
    NavigationTarget,
    navigation_target_matches,
    parse_navigation_target,
)
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService


class NavigationTargetContractTests(unittest.TestCase):
    def test_parse_accepts_only_registered_enum_ids(self) -> None:
        target = parse_navigation_target("settings.wifi")
        self.assertEqual(NavigationTarget.SETTINGS_WIFI, target)

        with self.assertRaises(MobileAgentError) as raised:
            parse_navigation_target("settings.nope")
        self.assertEqual("NAVIGATION_ACTION_UNKNOWN", raised.exception.code)

        with self.assertRaises(MobileAgentError) as raised:
            parse_navigation_target(123)
        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)

    def test_every_target_has_verification_metadata(self) -> None:
        for target in NavigationTarget:
            spec = NAVIGATION_TARGETS[target]
            self.assertEqual("com.android.settings", spec.expected_app_id)
            self.assertTrue(spec.label)

    def test_verification_matches_app_and_activity_token(self) -> None:
        spec = NAVIGATION_TARGETS[NavigationTarget.SETTINGS_WIFI]
        self.assertTrue(
            navigation_target_matches(
                spec, "com.android.settings", ".Settings$WifiSettingsActivity"
            )
        )
        self.assertFalse(
            navigation_target_matches(
                spec, "com.android.settings", ".Settings$DisplaySettingsActivity"
            )
        )
        self.assertFalse(
            navigation_target_matches(spec, "com.example.fake", ".WifiSettingsActivity")
        )

    def test_home_target_verifies_on_app_alone(self) -> None:
        spec = NAVIGATION_TARGETS[NavigationTarget.SETTINGS_HOME]
        self.assertTrue(
            navigation_target_matches(spec, "com.android.settings", ".Anything")
        )

    def test_capability_catalog_registers_navigation_metadata(self) -> None:
        definition = CapabilityCatalog().get("app.navigate@1")
        self.assertEqual("low", definition.risk.value)
        self.assertEqual("conditional", definition.idempotency.value)
        self.assertEqual("required", definition.verification.value)


class AppNavigateSkillTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.artifacts = ArtifactStore(Path(self.directory.name))

    async def test_success_returns_verified_result_with_evidence(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        result = await runtime.navigate_app("fake:android-001", "settings.wifi")

        self.assertTrue(result["success"])
        self.assertEqual("verified", result["verification"])
        self.assertEqual("settings.wifi", result["target"])
        self.assertEqual(
            "com.android.settings", result["foreground_app"]["app_id"]
        )
        self.assertIn("Wifi", result["foreground_app"]["activity"])
        self.assertTrue(result["evidence_refs"])
        self.assertEqual(
            [("app.navigate", "fake:android-001", "settings.wifi")],
            [action for action in adapter.actions if action[0] == "app.navigate"],
        )

    async def test_unknown_target_is_rejected_before_device_io(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.navigate_app("fake:android-001", "settings.root_shell")

        self.assertEqual("NAVIGATION_ACTION_UNKNOWN", raised.exception.code)
        self.assertEqual([], adapter.actions)

    def test_unknown_target_maps_to_http_400_not_503(self) -> None:
        """未知枚举 ID 是客户端参数错误，不能映射为服务端 503。"""
        runtime = RuntimeService(FakeDeviceAdapter(), self.artifacts)

        status, payload = runtime.navigate_app_sync(
            "fake:android-001", "settings.root_shell"
        )

        self.assertEqual(HTTPStatus.BAD_REQUEST, status)
        self.assertEqual("NAVIGATION_ACTION_UNKNOWN", payload["error"]["code"])

    async def test_verification_failure_raises_navigation_not_verified(self) -> None:
        adapter = StuckHomeAdapter()
        runtime = RuntimeService(adapter, self.artifacts)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.navigate_app("fake:android-001", "settings.wifi")

        self.assertEqual("NAVIGATION_NOT_VERIFIED", raised.exception.code)
        self.assertEqual("unknown_outcome", raised.exception.outcome.value)

    async def test_missing_capability_is_rejected(self) -> None:
        device = Device(
            device_id="fake:no-nav",
            platform=Platform.ANDROID,
            name="No nav",
            model="fake",
            os_version="15",
            connection=ConnectionState.ONLINE,
            capabilities=("device.inspect@1",),
        )
        adapter = FakeDeviceAdapter([device])
        runtime = RuntimeService(adapter, self.artifacts)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.navigate_app(device.device_id, "settings.wifi")

        self.assertEqual("CAPABILITY_UNAVAILABLE", raised.exception.code)
        self.assertEqual([], adapter.actions)

    def test_result_contract_declares_enumerated_targets(self) -> None:
        root = Path(__file__).resolve().parents[2]
        schema = json.loads(
            (root / "contracts/schemas/app-navigation-result.schema.json").read_text()
        )
        manifest = json.loads(
            (
                root / "runtime/mobile_agent/skills/manifests/app.navigate.json"
            ).read_text()
        )

        self.assertEqual("app.navigate", schema["properties"]["skill_id"]["const"])
        self.assertEqual(
            {target.value for target in NavigationTarget},
            set(schema["properties"]["target"]["enum"]),
        )
        self.assertEqual(
            set(schema["properties"]["target"]["enum"]),
            set(manifest["input_schema"]["properties"]["target"]["enum"]),
        )
        self.assertEqual(["app.navigate@1"], manifest["required_capabilities"])
        self.assertEqual(["app.navigate"], manifest["tool_allowlist"])
        self.assertEqual("low", manifest["risk"])


class StuckHomeAdapter(FakeDeviceAdapter):
    """Simulate a navigation command that succeeds but never reaches the target."""

    async def navigate_to(self, device_id: str, target: NavigationTarget) -> None:
        self.actions.append(("app.navigate", device_id, target.value))
        self.foreground_app = "com.example.launcher"
        self.foreground_activity = ".Launcher"


if __name__ == "__main__":
    unittest.main()
