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
from mobile_agent.skills.settings_navigate import SettingsNavigateSkill
from mobile_agent.tools.runtime import ToolRegistry, ToolRuntime


ROOT = Path(__file__).resolve().parents[2]
TARGET = {
    "strategy": "text",
    "value": "Display",
    "resolve_clickable_ancestor": True,
}
EXPECTED = {"strategy": "text", "value": "Display settings"}


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
