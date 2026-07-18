from __future__ import annotations

import unittest

from mobile_agent.cli.task_list import render_task_list


class TaskListCliTests(unittest.TestCase):
    def test_renders_recent_task_summaries(self) -> None:
        report = render_task_list(
            [
                {
                    "task_id": "task_11111111111111111111111111111111",
                    "task_type": "settings.scroll_navigate",
                    "status": "succeeded",
                    "completed_at": "2026-07-08T10:00:00Z",
                    "goal": "进入显示设置页面",
                }
            ]
        )

        self.assertIn("Recent Mobile Agent Tasks", report)
        self.assertIn("succeeded", report)
        self.assertIn("settings.scroll_navigate", report)
        self.assertIn("进入显示设置页面", report)
        self.assertIn("task_11111111111111111111111111111111", report)

    def test_renders_empty_state(self) -> None:
        self.assertIn("(no tasks)", render_task_list([]))
