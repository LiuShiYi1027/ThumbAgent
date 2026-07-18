from __future__ import annotations

import unittest

from mobile_agent.cli.device_logs_collect import render_result, render_submission


class DeviceLogsCliTests(unittest.TestCase):
    def test_renders_metadata_without_log_content(self) -> None:
        report = render_result(
            {
                "device_id": "adb:001",
                "status": "succeeded",
                "minimum_level": "info",
                "captured_bytes": 128,
                "truncated": False,
                "redaction_count": 2,
                "artifact": {
                    "artifact_id": "artifact_123",
                    "relative_path": "2026/07/15/artifact_123.log",
                },
            }
        )

        self.assertIn("adb:001", report)
        self.assertIn("artifact_123", report)
        self.assertIn("Redactions:  2", report)
        self.assertNotIn("log contents", report)

    def test_renders_async_task_submission(self) -> None:
        report = render_submission(
            {
                "task_id": "task_123",
                "task_type": "device.logs.collect",
                "status": "queued",
                "device_id": "adb:001",
                "deadline_seconds": 60,
            }
        )

        self.assertIn("task_123", report)
        self.assertIn("device.logs.collect", report)
        self.assertIn("queued", report)
        self.assertIn("task_report", report)


if __name__ == "__main__":
    unittest.main()
