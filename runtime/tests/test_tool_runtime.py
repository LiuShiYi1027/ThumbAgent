from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.action import ActionStatus, VerificationStatus
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.skills.open_app import OpenAppSkill
from mobile_agent.tools.runtime import ToolRegistry, ToolRuntime


ROOT = Path(__file__).resolve().parents[2]


class BrokenLaunchAdapter(FakeDeviceAdapter):
    async def launch_app(self, device_id: str, app_id: str) -> None:
        self.actions.append(("app.launch", device_id, app_id))


class ScrollingListAdapter(FakeDeviceAdapter):
    def __init__(self, pages: list[bytes]) -> None:
        super().__init__()
        self.foreground_app = "com.example.list"
        self.foreground_activity = ".ListActivity"
        self._pages = pages
        self._page_index = 0
        self.custom_ui_xml = pages[0]

    async def swipe(
        self, device_id: str, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int
    ) -> None:
        await super().swipe(device_id, start_x, start_y, end_x, end_y, duration_ms)
        if self._page_index < len(self._pages) - 1:
            self._page_index += 1
            self.custom_ui_xml = self._pages[self._page_index]


def list_page(*nodes: str) -> bytes:
    body = "".join(nodes)
    return f"<hierarchy>{body}</hierarchy>".encode()


def text_node(text: str, resource_id: str = "item") -> str:
    return (
        f'<node text="{text}" resource-id="{resource_id}" class="android.widget.TextView" '
        'package="com.example.list" clickable="false" enabled="true" visible-to-user="true" '
        'bounds="[0,0][2,1]"/>'
    )


class ToolRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.adapter = FakeDeviceAdapter()
        self.registry = ToolRegistry()
        self.runtime = ToolRuntime(
            self.adapter,
            ArtifactStore(Path(self.directory.name)),
            self.registry,
            PolicyEngine(),
        )

    async def test_open_app_skill_observes_executes_and_verifies(self) -> None:
        result = await OpenAppSkill(self.runtime).invoke("fake:android-001", "com.android.settings")

        self.assertTrue(result.success)
        self.assertEqual(ActionStatus.SUCCEEDED, result.status)
        self.assertEqual(VerificationStatus.VERIFIED, result.action.verification)
        self.assertEqual("com.example.fake", result.action.before.foreground_app.app_id)
        self.assertEqual("com.android.settings", result.action.after.foreground_app.app_id)
        self.assertEqual(("app.launch", "fake:android-001", "com.android.settings"), self.adapter.actions[0])

    async def test_tap_requires_confirmation_and_valid_screen_bounds(self) -> None:
        with self.assertRaises(MobileAgentError) as confirmation:
            await self.runtime.execute("input.tap", "fake:android-001", {"x": 1, "y": 1})
        self.assertEqual("CONFIRMATION_REQUIRED", confirmation.exception.code)

        result = await self.runtime.execute(
            "input.tap", "fake:android-001", {"x": 1, "y": 1}, confirmed=True
        )
        self.assertEqual(VerificationStatus.INCONCLUSIVE, result.verification)

        with self.assertRaises(MobileAgentError) as bounds:
            await self.runtime.execute(
                "input.tap", "fake:android-001", {"x": 2, "y": 3}, confirmed=True
            )
        self.assertEqual("INVALID_ARGUMENT", bounds.exception.code)

    async def test_swipe_requires_confirmation_and_uses_safe_semantic_arguments(self) -> None:
        with self.assertRaises(MobileAgentError) as confirmation:
            await self.runtime.execute("input.swipe", "fake:android-001", {"direction": "up"})
        self.assertEqual("CONFIRMATION_REQUIRED", confirmation.exception.code)

        result = await self.runtime.execute(
            "input.swipe",
            "fake:android-001",
            {"direction": "up", "distance_percent": 0.5, "duration_ms": 250},
            confirmed=True,
        )

        self.assertEqual(VerificationStatus.INCONCLUSIVE, result.verification)
        self.assertEqual(("input.swipe", "fake:android-001", 1, 2, 1, 1, 250), self.adapter.actions[0])

        invalid_payloads = (
            {"direction": "diagonal"},
            {"direction": "up", "distance_percent": 0.05},
            {"direction": "up", "distance_percent": 0.9},
            {"direction": "up", "duration_ms": 99},
            {"direction": "up", "duration_ms": 2001},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(MobileAgentError) as raised:
                    await self.runtime.execute("input.swipe", "fake:android-001", payload, confirmed=True)
                self.assertEqual("INVALID_ARGUMENT", raised.exception.code)

    async def test_text_requires_confirmation_editable_target_and_safe_text(self) -> None:
        self.adapter.foreground_app = "com.example.form"
        selector = {"strategy": "resource_id", "value": "search_box", "package": "com.example.form"}

        with self.assertRaises(MobileAgentError) as confirmation:
            await self.runtime.execute(
                "input.text", "fake:android-001", {"selector": selector, "text": "hello"}
            )
        self.assertEqual("CONFIRMATION_REQUIRED", confirmation.exception.code)

        result = await self.runtime.execute(
            "input.text",
            "fake:android-001",
            {"selector": selector, "text": "hello_1"},
            confirmed=True,
        )

        self.assertEqual(VerificationStatus.INCONCLUSIVE, result.verification)
        self.assertEqual(("input.tap", "fake:android-001", 1, 0), self.adapter.actions[0])
        self.assertEqual(("input.text", "fake:android-001", "hello_1"), self.adapter.actions[1])
        self.assertEqual("search_box", result.ui_match.matched_node.resource_id if result.ui_match else "")

        with self.assertRaises(MobileAgentError) as sensitive_value:
            await self.runtime.execute(
                "input.text",
                "fake:android-001",
                {"selector": selector, "text": "123456"},
                confirmed=True,
            )
        self.assertEqual("ACTION_REJECTED_BY_POLICY", sensitive_value.exception.code)

        with self.assertRaises(MobileAgentError) as unsafe_chars:
            await self.runtime.execute(
                "input.text",
                "fake:android-001",
                {"selector": selector, "text": "hello world"},
                confirmed=True,
            )
        self.assertEqual("INVALID_ARGUMENT", unsafe_chars.exception.code)

    async def test_text_rejects_non_editable_or_sensitive_targets(self) -> None:
        self.adapter.foreground_app = "com.example.form"
        sensitive = (
            b'<hierarchy><node text="" resource-id="password" class="android.widget.EditText" '
            b'package="com.example.form" clickable="true" enabled="true" visible-to-user="true" '
            b'bounds="[0,0][2,1]"/></hierarchy>'
        )

        original = self.adapter.custom_ui_xml
        self.adapter.custom_ui_xml = sensitive
        self.addCleanup(setattr, self.adapter, "custom_ui_xml", original)
        with self.assertRaises(MobileAgentError) as sensitive_target:
            await self.runtime.execute(
                "input.text",
                "fake:android-001",
                {
                    "selector": {
                        "strategy": "resource_id",
                        "value": "password",
                        "package": "com.example.form",
                    },
                    "text": "safe",
                },
                confirmed=True,
            )
        self.assertEqual("ACTION_REJECTED_BY_POLICY", sensitive_target.exception.code)

        self.adapter.custom_ui_xml = (
            b'<hierarchy><node text="Search" resource-id="label" class="android.widget.TextView" '
            b'package="com.example.form" clickable="false" enabled="true" visible-to-user="true" '
            b'bounds="[0,0][2,1]"/></hierarchy>'
        )
        with self.assertRaises(MobileAgentError) as not_editable:
            await self.runtime.execute(
                "input.text",
                "fake:android-001",
                {
                    "selector": {
                        "strategy": "resource_id",
                        "value": "label",
                        "package": "com.example.form",
                    },
                    "text": "safe",
                },
                confirmed=True,
            )
        self.assertEqual("TARGET_NOT_EDITABLE", not_editable.exception.code)

    async def test_find_element_with_scroll_requires_confirmation_and_finds_target(self) -> None:
        adapter = ScrollingListAdapter(
            [
                list_page(text_node("Top", "top")),
                list_page(text_node("Target", "target")),
            ]
        )
        tools = ToolRuntime(
            adapter,
            ArtifactStore(Path(self.directory.name)),
            ToolRegistry(),
            PolicyEngine(),
        )
        selector = {"strategy": "text", "value": "Target", "package": "com.example.list"}

        with self.assertRaises(MobileAgentError) as confirmation:
            await tools.find_element_with_scroll(
                "fake:android-001", selector, max_scrolls=1, timeout_seconds=2
            )
        self.assertEqual("CONFIRMATION_REQUIRED", confirmation.exception.code)

        observation, node = await tools.find_element_with_scroll(
            "fake:android-001", selector, max_scrolls=1, timeout_seconds=2, confirmed=True
        )

        self.assertEqual("Target", node.text)
        self.assertEqual("com.example.list", observation.foreground_app.app_id)
        self.assertEqual("input.swipe", adapter.actions[-1][0])

    async def test_find_element_with_scroll_stops_on_no_progress_or_no_budget(self) -> None:
        selector = {"strategy": "text", "value": "Missing", "package": "com.example.list"}
        no_budget = ToolRuntime(
            ScrollingListAdapter([list_page(text_node("Top", "top"))]),
            ArtifactStore(Path(self.directory.name)),
            ToolRegistry(),
            PolicyEngine(),
        )
        with self.assertRaises(MobileAgentError) as not_found:
            await no_budget.find_element_with_scroll(
                "fake:android-001", selector, max_scrolls=0, timeout_seconds=2
            )
        self.assertEqual("TARGET_NOT_FOUND", not_found.exception.code)

        adapter = ScrollingListAdapter([list_page(text_node("Top", "top"))])
        tools = ToolRuntime(
            adapter,
            ArtifactStore(Path(self.directory.name)),
            ToolRegistry(),
            PolicyEngine(),
        )
        with self.assertRaises(MobileAgentError) as no_progress:
            await tools.find_element_with_scroll(
                "fake:android-001", selector, max_scrolls=2, timeout_seconds=2, confirmed=True
            )
        self.assertEqual("NO_PROGRESS", no_progress.exception.code)
        self.assertEqual("input.swipe", adapter.actions[-1][0])

    async def test_find_element_with_scroll_rejects_ambiguous_target(self) -> None:
        adapter = ScrollingListAdapter(
            [list_page(text_node("Target", "one"), text_node("Target", "two"))]
        )
        tools = ToolRuntime(
            adapter,
            ArtifactStore(Path(self.directory.name)),
            ToolRegistry(),
            PolicyEngine(),
        )
        with self.assertRaises(MobileAgentError) as ambiguous:
            await tools.find_element_with_scroll(
                "fake:android-001",
                {"strategy": "text", "value": "Target", "package": "com.example.list"},
            )
        self.assertEqual("TARGET_AMBIGUOUS", ambiguous.exception.code)

    async def test_find_element_with_scroll_stops_when_device_is_offline(self) -> None:
        adapter = FakeDeviceAdapter(
            [
                Device(
                    "fake:offline",
                    Platform.ANDROID,
                    "Offline",
                    "offline",
                    "15",
                    ConnectionState.OFFLINE,
                    ("screen.observe@1", "input.swipe@1"),
                )
            ]
        )
        tools = ToolRuntime(
            adapter,
            ArtifactStore(Path(self.directory.name)),
            ToolRegistry(),
            PolicyEngine(),
        )

        with self.assertRaises(MobileAgentError) as offline:
            await tools.find_element_with_scroll(
                "fake:offline",
                {"strategy": "text", "value": "Missing"},
                max_scrolls=1,
                confirmed=True,
            )

        self.assertEqual("DEVICE_OFFLINE", offline.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_unknown_tool_is_rejected(self) -> None:
        with self.assertRaises(MobileAgentError) as raised:
            await self.runtime.execute("shell.execute", "fake:android-001", {})
        self.assertEqual("TOOL_NOT_FOUND", raised.exception.code)

    async def test_missing_capability_is_rejected_before_adapter_action(self) -> None:
        adapter = FakeDeviceAdapter(
            [
                Device(
                    "fake:limited",
                    Platform.ANDROID,
                    "Limited",
                    "limited",
                    "15",
                    ConnectionState.ONLINE,
                    ("screen.observe@1",),
                )
            ]
        )
        tools = ToolRuntime(
            adapter,
            ArtifactStore(Path(self.directory.name)),
            ToolRegistry(),
            PolicyEngine(),
        )
        with self.assertRaises(MobileAgentError) as raised:
            await tools.execute("app.launch", "fake:limited", {"app_id": "com.example.app"})
        self.assertEqual("CAPABILITY_UNAVAILABLE", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_open_app_skill_fails_when_foreground_verification_fails(self) -> None:
        adapter = BrokenLaunchAdapter()
        tools = ToolRuntime(
            adapter,
            ArtifactStore(Path(self.directory.name)),
            ToolRegistry(),
            PolicyEngine(),
        )

        result = await OpenAppSkill(tools).invoke("fake:android-001", "com.android.settings")

        self.assertFalse(result.success)
        self.assertEqual(ActionStatus.FAILED, result.status)
        self.assertEqual(VerificationStatus.NOT_VERIFIED, result.action.verification)

    def test_registry_risk_is_fixed_and_contracts_are_versioned(self) -> None:
        tap = self.registry.get("input.tap")
        swipe = self.registry.get("input.swipe")
        text = self.registry.get("input.text")
        self.assertEqual("medium", tap.risk.value)
        self.assertEqual("medium", swipe.risk.value)
        self.assertEqual("medium", text.risk.value)
        action_schema = json.loads(
            (ROOT / "contracts/schemas/action-result.schema.json").read_text(encoding="utf-8")
        )
        skill_schema = json.loads(
            (ROOT / "contracts/schemas/skill-result.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual("1.0.0", action_schema["properties"]["schema_version"]["const"])
        self.assertIn("input.swipe", action_schema["properties"]["tool_id"]["enum"])
        self.assertIn("input.text", action_schema["properties"]["tool_id"]["enum"])
        self.assertEqual("app.open", skill_schema["properties"]["skill_id"]["const"])
