from __future__ import annotations

import unittest

from mobile_agent.cli.device_inspect import render_device_inspection


class DeviceInspectCliTests(unittest.TestCase):
    def test_renders_device_capability_and_policy_metadata(self) -> None:
        report = render_device_inspection(
            {
                "availability": {
                    "status": "ready",
                    "device": {
                        "device_id": "adb:001",
                        "name": "Test phone",
                        "platform": "android",
                        "os_version": "16",
                        "model": "test",
                        "connection": "online",
                        "session_id": "session_1",
                    },
                    "lease_owner_id": None,
                },
                "capabilities": [
                    {
                        "capability": "input.tap@1",
                        "availability": "available",
                        "risk": "medium",
                        "confirmation_required": True,
                        "tools": ["input.tap", "input.tap_element"],
                        "requirements": ["设备在线", "用户明确确认"],
                        "limitations": ["系统安全区会拒绝"],
                    }
                ],
            }
        )

        self.assertIn("Test phone", report)
        self.assertIn("adb:001", report)
        self.assertIn("input.tap@1 [available]", report)
        self.assertIn("confirmation required", report)
        self.assertIn("input.tap_element", report)
        self.assertIn("系统安全区会拒绝", report)


if __name__ == "__main__":
    unittest.main()
