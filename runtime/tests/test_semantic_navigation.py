from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.skills.open_app import OpenAppSkill
from mobile_agent.skills.settings_navigate import SettingsNavigateSkill, SettingsScrollNavigateSkill
from mobile_agent.tools.runtime import ToolRegistry, ToolRuntime


ROOT = Path(__file__).resolve().parents[2]
TARGET = {
    "strategy": "text",
    "value": "Display",
    "resolve_clickable_ancestor": True,
}
EXPECTED = {"strategy": "text", "value": "Display settings"}


class FailedSettingsLaunchAdapter(FakeDeviceAdapter):
    async def launch_app(self, device_id: str, app_id: str) -> None:
        self.actions.append(("app.launch", device_id, app_id))


def settings_page(*nodes: str) -> bytes:
    return f"<hierarchy>{''.join(nodes)}</hierarchy>".encode()


def settings_text(text: str, resource_id: str) -> str:
    return (
        f'<node text="{text}" resource-id="{resource_id}" class="android.widget.TextView" '
        'package="com.android.settings" clickable="false" enabled="true" visible-to-user="true" '
        'bounds="[0,0][2,1]"/>'
    )


class ScrollingSettingsAdapter(FakeDeviceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self._pages = [
            settings_page(settings_text("Top", "top")),
            settings_page(
                '<node text="" resource-id="target_row" class="android.view.View" '
                'package="com.android.settings" clickable="true" enabled="true" '
                'visible-to-user="true" bounds="[0,0][2,3]">'
                + settings_text("Advanced", "advanced_title")
                + "</node>"
            ),
        ]
        self._page_index = 0
        self.custom_ui_xml = self._pages[0]

    async def swipe(
        self, device_id: str, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int
    ) -> None:
        await super().swipe(device_id, start_x, start_y, end_x, end_y, duration_ms)
        self._page_index = min(self._page_index + 1, len(self._pages) - 1)
        self.custom_ui_xml = self._pages[self._page_index]

    async def tap(self, device_id: str, x: int, y: int) -> None:
        await super().tap(device_id, x, y)
        if self.foreground_app == "com.android.settings" and (x, y) == (1, 1):
            self.foreground_activity = ".AdvancedSettings"
            self.custom_ui_xml = settings_page(settings_text("Advanced settings", "advanced_page"))


class DirectionalScrollingSettingsAdapter(FakeDeviceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.custom_ui_xml = settings_page(settings_text("Bottom", "bottom"))

    async def swipe(
        self, device_id: str, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int
    ) -> None:
        await super().swipe(device_id, start_x, start_y, end_x, end_y, duration_ms)
        if end_y > start_y:
            self.custom_ui_xml = settings_page(
                '<node text="" resource-id="target_row" class="android.view.View" '
                'package="com.android.settings" clickable="true" enabled="true" '
                'visible-to-user="true" bounds="[0,0][2,3]">'
                + settings_text("Advanced", "advanced_title")
                + "</node>"
            )

    async def tap(self, device_id: str, x: int, y: int) -> None:
        await super().tap(device_id, x, y)
        if self.foreground_app == "com.android.settings" and (x, y) == (1, 1):
            self.foreground_activity = ".AdvancedSettings"
            self.custom_ui_xml = settings_page(settings_text("Advanced settings", "advanced_page"))


class SemanticNavigationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.adapter = FakeDeviceAdapter()
        self.tools = ToolRuntime(
            self.adapter,
            ArtifactStore(Path(self.directory.name)),
            ToolRegistry(),
            PolicyEngine(),
        )

    async def test_tap_element_requires_confirmation_and_records_resolved_ancestor(self) -> None:
        await OpenAppSkill(self.tools).invoke("fake:android-001", "com.android.settings")
        with self.assertRaises(MobileAgentError) as denied:
            await self.tools.execute(
                "input.tap_element", "fake:android-001", {"selector": TARGET}
            )
        self.assertEqual("CONFIRMATION_REQUIRED", denied.exception.code)

        action = await self.tools.execute(
            "input.tap_element",
            "fake:android-001",
            {"selector": TARGET},
            confirmed=True,
        )
        self.assertIsNotNone(action.ui_match)
        assert action.ui_match is not None
        self.assertEqual("settings_display", action.ui_match.matched_node.resource_id)
        self.assertEqual("settings_list", action.ui_match.target_node.resource_id)
        self.assertEqual((1, 1), (action.ui_match.tap_x, action.ui_match.tap_y))

    async def test_settings_navigation_skill_verifies_expected_page(self) -> None:
        result = await SettingsNavigateSkill(
            self.tools, OpenAppSkill(self.tools)
        ).invoke("fake:android-001", TARGET, EXPECTED, confirmed=True)

        self.assertTrue(result.success)
        self.assertEqual("Display settings", result.verified_node.text)
        self.assertEqual(".DisplaySettings", result.verified_observation.foreground_app.activity)

    async def test_navigation_result_to_dict_serializes_full_chain(self) -> None:
        """Regression: UiSelector.to_dict() used super() with slots=True,
        which crashes on serialization.  The API endpoint calls to_dict()
        on the full NavigationResult, so this must not raise."""
        result = await SettingsNavigateSkill(
            self.tools, OpenAppSkill(self.tools)
        ).invoke("fake:android-001", TARGET, EXPECTED, confirmed=True)

        serialized = result.to_dict()

        self.assertTrue(serialized["success"])
        tap_selector = serialized["tap_action"]["ui_match"]["selector"]
        self.assertEqual("Display", tap_selector["value"])
        self.assertTrue(tap_selector["resolve_clickable_ancestor"])
        self.assertEqual("com.android.settings", tap_selector["package"])

    async def test_navigation_stops_when_settings_open_is_not_verified(self) -> None:
        adapter = FailedSettingsLaunchAdapter()
        tools = ToolRuntime(
            adapter,
            ArtifactStore(Path(self.directory.name)),
            ToolRegistry(),
            PolicyEngine(),
        )
        with self.assertRaises(MobileAgentError) as raised:
            await SettingsNavigateSkill(tools, OpenAppSkill(tools)).invoke(
                "fake:android-001", TARGET, EXPECTED, confirmed=True
            )
        self.assertEqual("APP_OPEN_FAILED", raised.exception.code)
        self.assertEqual(1, len(adapter.actions))

    async def test_navigation_rejects_selector_for_another_package(self) -> None:
        with self.assertRaises(MobileAgentError) as raised:
            await SettingsNavigateSkill(self.tools, OpenAppSkill(self.tools)).invoke(
                "fake:android-001",
                {**TARGET, "package": "com.example.other"},
                EXPECTED,
                confirmed=True,
            )
        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)

    async def test_scroll_navigation_finds_target_before_tapping(self) -> None:
        adapter = ScrollingSettingsAdapter()
        tools = ToolRuntime(
            adapter,
            ArtifactStore(Path(self.directory.name)),
            ToolRegistry(),
            PolicyEngine(),
        )

        result = await SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)).invoke(
            "fake:android-001",
            {
                "strategy": "text",
                "value": "Advanced",
                "resolve_clickable_ancestor": True,
            },
            {"strategy": "text", "value": "Advanced settings"},
            max_scrolls=1,
            confirmed=True,
            distance_percent=0.35,
            duration_ms=900,
            settle_seconds=0,
        )

        self.assertTrue(result.success)
        self.assertEqual("settings.scroll_navigate", result.skill_id)
        self.assertEqual("Advanced settings", result.verified_node.text)
        self.assertEqual("input.swipe", adapter.actions[1][0])
        self.assertEqual(900, adapter.actions[1][-1])
        self.assertEqual("input.tap", adapter.actions[2][0])

    async def test_scroll_navigation_falls_back_to_opposite_direction_on_no_progress(self) -> None:
        adapter = DirectionalScrollingSettingsAdapter()
        tools = ToolRuntime(
            adapter,
            ArtifactStore(Path(self.directory.name)),
            ToolRegistry(),
            PolicyEngine(),
        )

        result = await SettingsScrollNavigateSkill(tools, OpenAppSkill(tools)).invoke(
            "fake:android-001",
            {
                "strategy": "text",
                "value": "Advanced",
                "resolve_clickable_ancestor": True,
            },
            {"strategy": "text", "value": "Advanced settings"},
            direction="up",
            max_scrolls=1,
            confirmed=True,
            distance_percent=0.35,
            duration_ms=900,
            settle_seconds=0,
        )

        self.assertTrue(result.success)
        self.assertEqual("Advanced settings", result.verified_node.text)
        swipe_actions = [action for action in adapter.actions if action[0] == "input.swipe"]
        self.assertEqual(2, len(swipe_actions))
        self.assertGreater(swipe_actions[1][5], swipe_actions[1][3])

    async def test_wait_is_bounded_and_returns_not_found(self) -> None:
        with self.assertRaises(MobileAgentError) as raised:
            await self.tools.wait_for_element(
                "fake:android-001",
                {"strategy": "text", "value": "Never appears"},
                timeout_seconds=0.01,
                poll_interval=0.005,
            )
        self.assertEqual("TARGET_NOT_FOUND", raised.exception.code)

    def test_ui_contracts_and_navigation_contract_are_versioned(self) -> None:
        for name in (
            "ui-node.schema.json",
            "ui-selector.schema.json",
            "ui-match.schema.json",
            "navigation-result.schema.json",
        ):
            schema = json.loads((ROOT / "contracts/schemas" / name).read_text(encoding="utf-8"))
            self.assertIn("$id", schema)
