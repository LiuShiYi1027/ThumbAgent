from __future__ import annotations

import unittest

from mobile_agent.cli.runtime_diagnose import render_runtime_readiness


class RuntimeDiagnoseCliTests(unittest.TestCase):
    def test_renders_ready_and_busy_devices(self) -> None:
        report = render_runtime_readiness(
            {
                "status": "ready",
                "gateway": {
                    "platform": "android",
                    "transport": "adb",
                    "status": "available",
                    "issue": None,
                },
                "summary": {"total": 2, "ready": 1, "busy": 1, "attention": 0},
                "issues": [],
                "devices": [
                    {
                        "status": "ready",
                        "device": {
                            "device_id": "adb:ready",
                            "name": "Ready phone",
                            "connection": "online",
                            "session_id": "session_1",
                        },
                        "lease_owner_id": None,
                        "issues": [],
                    },
                    {
                        "status": "busy",
                        "device": {
                            "device_id": "adb:busy",
                            "name": "Busy phone",
                            "connection": "online",
                            "session_id": "session_2",
                        },
                        "lease_owner_id": "task_owner",
                        "issues": [
                            {
                                "code": "DEVICE_LOCKED",
                                "message": "设备正由另一个任务使用",
                                "suggested_action": "等待当前任务结束",
                            }
                        ],
                    },
                ],
            }
        )

        self.assertIn("Status:  ready", report)
        self.assertIn("android / adb [available]", report)
        self.assertIn("[ready] Ready phone", report)
        self.assertIn("lease_owner=task_owner", report)
        self.assertIn("DEVICE_LOCKED", report)

    def test_renders_blocked_gateway_remediation(self) -> None:
        issue = {
            "code": "ADB_NOT_FOUND",
            "message": "未找到 Android Platform Tools",
            "suggested_action": "安装 adb 后重启 Runtime",
        }
        report = render_runtime_readiness(
            {
                "status": "blocked",
                "gateway": {
                    "platform": "android",
                    "transport": "adb",
                    "status": "unavailable",
                    "issue": issue,
                },
                "summary": {"total": 0, "ready": 0, "busy": 0, "attention": 0},
                "issues": [issue],
                "devices": [],
            }
        )

        self.assertIn("Status:  blocked", report)
        self.assertIn("ADB_NOT_FOUND", report)
        self.assertIn("安装 adb 后重启 Runtime", report)
        self.assertIn("(no devices)", report)


if __name__ == "__main__":
    unittest.main()
