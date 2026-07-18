from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService


ROOT = Path(__file__).resolve().parents[2]
TARGET = {
    "strategy": "text",
    "value": "Display",
    "resolve_clickable_ancestor": True,
}
EXPECTED = {"strategy": "text", "value": "Display settings"}


class TaskRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.runtime = RuntimeService(
            FakeDeviceAdapter(), ArtifactStore(Path(self.directory.name))
        )

    async def test_settings_scroll_navigation_task_returns_evidence_report(self) -> None:
        task = await self.runtime.run_settings_scroll_navigation_task(
            "fake:android-001",
            TARGET,
            EXPECTED,
            confirmed=True,
            goal="进入显示设置页面",
        )

        self.assertEqual("1.0.0", task["schema_version"])
        self.assertRegex(task["task_id"], r"^task_[a-f0-9]{32}$")
        self.assertEqual("settings.scroll_navigate", task["task_type"])
        self.assertEqual("进入显示设置页面", task["goal"])
        self.assertEqual("succeeded", task["status"])
        self.assertIsNone(task["error"])
        self.assertEqual(1, len(task["steps"]))
        self.assertEqual("settings.scroll_navigate", task["steps"][0]["name"])
        self.assertEqual("succeeded", task["steps"][0]["status"])
        self.assertEqual(
            "Display settings",
            task["evidence_summary"]["verified_node"]["text"],
        )
        self.assertEqual(
            "com.android.settings",
            task["evidence_summary"]["final_foreground_app"]["app_id"],
        )

    async def test_completed_task_can_be_queried_with_compact_events(self) -> None:
        task = await self.runtime.run_settings_scroll_navigation_task(
            "fake:android-001",
            TARGET,
            EXPECTED,
            confirmed=True,
        )

        stored = self.runtime.get_task(task["task_id"])
        events = self.runtime.list_task_events(task["task_id"])

        self.assertEqual(task["task_id"], stored["task_id"])
        self.assertEqual(
            ["task.started", "task.step_completed", "task.completed"],
            [event["event_type"] for event in events],
        )
        self.assertEqual([1, 2, 3], [event["sequence"] for event in events])
        self.assertEqual(task["task_id"], events[0]["task_id"])
        self.assertEqual("succeeded", events[-1]["payload"]["status"])

    async def test_recent_tasks_are_listed_as_summaries(self) -> None:
        first = await self.runtime.run_settings_scroll_navigation_task(
            "fake:android-001",
            TARGET,
            EXPECTED,
            confirmed=True,
            goal="first task",
        )
        second = await self.runtime.run_settings_scroll_navigation_task(
            "fake:android-001",
            TARGET,
            EXPECTED,
            confirmed=False,
            goal="second task",
        )

        summaries = self.runtime.list_tasks(limit=1)

        self.assertEqual(1, len(summaries))
        self.assertEqual(second["task_id"], summaries[0]["task_id"])
        self.assertEqual("second task", summaries[0]["goal"])
        self.assertNotIn("steps", summaries[0])
        self.assertNotEqual(first["task_id"], summaries[0]["task_id"])

    async def test_task_report_preserves_policy_rejection_as_failure_evidence(self) -> None:
        task = await self.runtime.run_settings_scroll_navigation_task(
            "fake:android-001",
            TARGET,
            EXPECTED,
            confirmed=False,
        )

        self.assertEqual("failed", task["status"])
        self.assertEqual("CONFIRMATION_REQUIRED", task["error"]["code"])
        self.assertEqual("failed", task["steps"][0]["status"])
        self.assertEqual("CONFIRMATION_REQUIRED", task["steps"][0]["error"]["code"])
        self.assertIsNone(task["steps"][0]["result"])

        events = self.runtime.list_task_events(task["task_id"])
        self.assertEqual("CONFIRMATION_REQUIRED", events[-1]["payload"]["error_code"])

    def test_missing_task_returns_not_found(self) -> None:
        status, payload = self.runtime.get_task_sync(
            "task_00000000000000000000000000000000"
        )

        self.assertEqual(404, status.value)
        self.assertEqual("TASK_NOT_FOUND", payload["error"]["code"])

    def test_task_contracts_are_versioned(self) -> None:
        schema = json.loads(
            (ROOT / "contracts/schemas/task-run.schema.json").read_text(encoding="utf-8")
        )
        event_schema = json.loads(
            (ROOT / "contracts/schemas/task-event.schema.json").read_text(encoding="utf-8")
        )

        self.assertEqual("https://mobile-agent.local/schemas/task-run/v1.json", schema["$id"])
        self.assertEqual("1.0.0", schema["properties"]["schema_version"]["const"])
        self.assertEqual(
            "https://mobile-agent.local/schemas/task-event/v1.json",
            event_schema["$id"],
        )
        self.assertIn("task.completed", event_schema["properties"]["event_type"]["enum"])
        self.assertIn(
            "device.logs.collect", schema["properties"]["task_type"]["enum"]
        )
        self.assertIn(
            "device.performance.snapshot",
            schema["properties"]["task_type"]["enum"],
        )

    def test_runtime_sync_wraps_task_report(self) -> None:
        status, payload = self.runtime.run_settings_scroll_navigation_task_sync(
            "fake:android-001",
            TARGET,
            EXPECTED,
            confirmed=True,
        )

        self.assertEqual(200, status.value)
        self.assertEqual("succeeded", payload["task"]["status"])
