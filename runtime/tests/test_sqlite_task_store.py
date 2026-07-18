from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService
from mobile_agent.storage.sqlite import SQLiteTaskStore, migrate_database


TARGET = {
    "strategy": "text",
    "value": "Display",
    "resolve_clickable_ancestor": True,
}
EXPECTED = {"strategy": "text", "value": "Display settings"}


class SQLiteTaskStoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.database = self.root / "mobile-agent.db"

    async def test_persists_task_and_events_across_runtime_instances(self) -> None:
        store = SQLiteTaskStore(self.database)
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(self.root / "artifacts"),
            task_store=store,
        )
        task = await runtime.run_settings_scroll_navigation_task(
            "fake:android-001",
            TARGET,
            EXPECTED,
            confirmed=True,
        )

        restarted = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(self.root / "artifacts-after-restart"),
            task_store=SQLiteTaskStore(self.database),
        )
        stored = restarted.get_task(task["task_id"])
        events = restarted.list_task_events(task["task_id"])

        self.assertEqual(task["task_id"], stored["task_id"])
        self.assertEqual("succeeded", stored["status"])
        self.assertEqual(
            ["task.started", "task.step_completed", "task.completed"],
            [event["event_type"] for event in events],
        )
        self.assertEqual([1, 2, 3], [event["sequence"] for event in events])

    async def test_lists_recent_task_summaries_from_sqlite(self) -> None:
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(self.root / "artifacts"),
            task_store=SQLiteTaskStore(self.database),
        )
        first = await runtime.run_settings_scroll_navigation_task(
            "fake:android-001",
            TARGET,
            EXPECTED,
            confirmed=True,
            goal="first persisted task",
        )
        second = await runtime.run_settings_scroll_navigation_task(
            "fake:android-001",
            TARGET,
            EXPECTED,
            confirmed=False,
            goal="second persisted task",
        )

        summaries = runtime.list_tasks(limit=2)

        self.assertEqual([second["task_id"], first["task_id"]], [item["task_id"] for item in summaries])
        self.assertEqual("second persisted task", summaries[0]["goal"])
        self.assertNotIn("steps", summaries[0])

    def test_migration_is_recorded_and_idempotent(self) -> None:
        migrate_database(self.database)
        migrate_database(self.database)

        with sqlite3.connect(self.database) as connection:
            revisions = connection.execute(
                "SELECT revision FROM schema_migrations ORDER BY revision"
            ).fetchall()
            task_table = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'tasks'"
            ).fetchone()

        self.assertEqual(
            [("0001_task_store",), ("0002_task_executions",)], revisions
        )
        self.assertEqual(("tasks",), task_table)

    def test_missing_task_uses_stable_error_code(self) -> None:
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(self.root / "artifacts"),
            task_store=SQLiteTaskStore(self.database),
        )

        status, payload = runtime.get_task_sync("task_00000000000000000000000000000000")

        self.assertEqual(404, status.value)
        self.assertEqual("TASK_NOT_FOUND", payload["error"]["code"])
