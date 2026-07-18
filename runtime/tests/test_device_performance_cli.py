from __future__ import annotations

import unittest

from mobile_agent.cli.device_performance_snapshot import render_result


class DevicePerformanceCliTests(unittest.TestCase):
    def test_renders_aggregate_metrics_and_artifact(self) -> None:
        report = render_result(
            {
                "device_id": "adb:001",
                "snapshot": {
                    "cpu": {"total_usage_percent": 10.5},
                    "memory": {"used_percent": 60.0},
                    "battery": {
                        "level_percent": 80,
                        "temperature_celsius": 31.0,
                    },
                    "system": {
                        "load_average_1m": 1.0,
                        "load_average_5m": 0.8,
                        "load_average_15m": 0.6,
                        "uptime_seconds": 3600,
                    },
                },
                "artifact": {
                    "artifact_id": "artifact_123",
                    "relative_path": "2026/07/15/artifact_123.json",
                },
            }
        )

        self.assertIn("CPU total:    10.5%", report)
        self.assertIn("Memory used:  60.0%", report)
        self.assertIn("artifact_123", report)


if __name__ == "__main__":
    unittest.main()
