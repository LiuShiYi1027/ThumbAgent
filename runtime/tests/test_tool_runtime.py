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
        self.assertEqual("medium", tap.risk.value)
        action_schema = json.loads(
            (ROOT / "contracts/schemas/action-result.schema.json").read_text(encoding="utf-8")
        )
        skill_schema = json.loads(
            (ROOT / "contracts/schemas/skill-result.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual("1.0.0", action_schema["properties"]["schema_version"]["const"])
        self.assertEqual("app.open", skill_schema["properties"]["skill_id"]["const"])
