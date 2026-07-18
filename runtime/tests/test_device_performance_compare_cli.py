from __future__ import annotations

import unittest

from mobile_agent.cli.device_performance_compare import render_comparison


class DevicePerformanceCompareCliTests(unittest.TestCase):
    def test_renders_delta_trend_and_two_point_warning(self) -> None:
        comparison = {
            "device_id": "adb:001",
            "baseline": {"task_id": "task_baseline"},
            "candidate": {"task_id": "task_candidate"},
            "interval_seconds": 60,
            "same_device_session": True,
            "metrics": {
                "cpu_total_usage_percent": {
                    "baseline_value": 10,
                    "candidate_value": 15,
                    "delta": 5,
                    "trend": "increased",
                    "unit": "percentage_points",
                }
            },
        }

        report = render_comparison(comparison)

        self.assertIn("CPU total", report)
        self.assertIn("delta 5", report)
        self.assertIn("same device session", report)
        self.assertIn("not causality or regression", report)


if __name__ == "__main__":
    unittest.main()
