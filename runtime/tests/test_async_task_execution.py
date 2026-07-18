from __future__ import annotations

import asyncio
import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.device_log import DeviceLogLevel
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.domain.task import TaskRun, TaskStatus
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService
from mobile_agent.storage.execution import SQLiteTaskExecutionStore
from mobile_agent.tasks.execution import (
    AsyncTaskExecutor,
    ExecutionStatus,
    InMemoryTaskExecutionStore,
    TaskExecution,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class _NotifyingExecutionStore(InMemoryTaskExecutionStore):
    def __init__(self) -> None:
        super().__init__()
        self.running = threading.Event()
        self.terminal = threading.Event()

    def save_execution(self, execution: TaskExecution) -> None:
        super().save_execution(execution)
        if execution.status is ExecutionStatus.RUNNING:
            self.running.set()
        if execution.status in {
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.TIMED_OUT,
        }:
            self.terminal.set()


class AsyncTaskExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_runtime_submit_returns_accepted_and_persists_incremental_events(self) -> None:
        store = _NotifyingExecutionStore()
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(self.root / "artifacts"),
            task_execution_store=store,
        )

        status, payload = runtime.submit_agent_task_sync(
            "fake:android-001", "open display settings", confirmed=True
        )

        self.assertEqual(202, status.value)
        task_id = payload["execution"]["task_id"]
        self.assertEqual("queued", payload["execution"]["status"])
        self.assertTrue(store.terminal.wait(2), "asynchronous task did not finish")
        execution = runtime.get_task_execution(task_id)
        events = runtime.list_task_execution_events(task_id)
        task = runtime.get_task(task_id)
        self.assertEqual("succeeded", execution["status"])
        self.assertTrue(execution["result_available"])
        self.assertEqual(600.0, execution["deadline_seconds"])
        self.assertIsNotNone(execution["deadline_at"])
        self.assertRegex(execution["device_session_id"], r"^session_[a-f0-9]{32}$")
        self.assertEqual("succeeded", task["status"])
        self.assertEqual(600.0, task["deadline_seconds"])
        self.assertEqual(execution["device_session_id"], task["device_session_id"])
        self.assertEqual("task.queued", events[0]["event_type"])
        self.assertEqual("task.started", events[1]["event_type"])
        self.assertEqual("task.completed", events[-1]["event_type"])
        self.assertEqual(
            [1, 2, 3, 4, 5, 6], [event["sequence"] for event in events]
        )

    def test_async_execution_contracts_are_versioned(self) -> None:
        execution_schema = json.loads(
            (Path(__file__).resolve().parents[2] / "contracts/schemas/task-execution.schema.json").read_text(
                encoding="utf-8"
            )
        )
        event_schema = json.loads(
            (Path(__file__).resolve().parents[2] / "contracts/schemas/task-event.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            "https://mobile-agent.local/schemas/task-execution/v1.json",
            execution_schema["$id"],
        )
        self.assertIn("cancelling", execution_schema["properties"]["status"]["enum"])
        self.assertIn("timed_out", execution_schema["properties"]["status"]["enum"])
        self.assertIn("deadline_seconds", execution_schema["required"])
        self.assertIn("deadline_at", execution_schema["required"])
        self.assertIn("device_session_id", execution_schema["required"])
        self.assertIn(
            "device.logs.collect",
            execution_schema["properties"]["task_type"]["enum"],
        )
        self.assertIn(
            "device.performance.snapshot",
            execution_schema["properties"]["task_type"]["enum"],
        )
        self.assertIn(
            "task.cancel_requested",
            event_schema["properties"]["event_type"]["enum"],
        )

    def test_running_execution_exposes_session_after_write_ownership(self) -> None:
        store = _NotifyingExecutionStore()
        executor = AsyncTaskExecutor(store)
        session_bound = threading.Event()
        release = threading.Event()

        async def run(
            task_id: str,
            on_step: object,
            cancelled: object,
            deadline_exceeded: object,
        ) -> TaskRun:
            executor.bind_device_session(
                task_id, "session_00000000000000000000000000000001"
            )
            session_bound.set()
            await asyncio.to_thread(release.wait)
            return _task(task_id, "bound", TaskStatus.SUCCEEDED)

        execution = executor.submit(
            "fake:android-001", "bound", run, lambda task: None
        )
        self.addCleanup(release.set)

        self.assertTrue(session_bound.wait(2), "device session was not bound")
        running = executor.get(execution.task_id)
        self.assertEqual(ExecutionStatus.RUNNING, running.status)
        self.assertEqual(
            "session_00000000000000000000000000000001",
            running.device_session_id,
        )
        release.set()
        self.assertTrue(store.terminal.wait(2), "bound task did not finish")

    def test_async_device_logs_persists_task_events_and_artifact_evidence(self) -> None:
        store = _NotifyingExecutionStore()
        artifacts = ArtifactStore(self.root / "artifacts")
        runtime = RuntimeService(
            FakeDeviceAdapter(), artifacts, task_execution_store=store
        )

        status, payload = runtime.submit_device_logs_task_sync(
            "fake:android-001",
            max_lines=100,
            minimum_level="warn",
            confirmed=True,
        )

        self.assertEqual(202, status.value)
        task_id = payload["execution"]["task_id"]
        self.assertEqual("device.logs.collect", payload["execution"]["task_type"])
        self.assertTrue(store.terminal.wait(2), "log task did not finish")
        execution = runtime.get_task_execution(task_id)
        task = runtime.get_task(task_id)
        events = runtime.list_task_execution_events(task_id)
        self.assertEqual("succeeded", execution["status"])
        self.assertTrue(execution["result_available"])
        self.assertEqual("device.logs.collect", task["task_type"])
        self.assertEqual("diagnostic", task["steps"][0]["kind"])
        self.assertEqual("device.logs.collect", task["steps"][0]["name"])
        artifact_id = task["evidence_summary"]["artifact_refs"][0]
        self.assertRegex(artifact_id, r"^artifact_[a-f0-9]{32}$")
        relative_path = task["steps"][0]["result"]["artifact"]["relative_path"]
        self.assertTrue(artifacts.resolve(relative_path).is_file())
        self.assertEqual(
            ["task.queued", "task.started", "task.step_completed", "task.completed"],
            [event["event_type"] for event in events],
        )

    def test_async_performance_snapshot_persists_aggregate_evidence(self) -> None:
        store = _NotifyingExecutionStore()
        artifacts = ArtifactStore(self.root / "performance-artifacts")
        runtime = RuntimeService(
            FakeDeviceAdapter(), artifacts, task_execution_store=store
        )

        status, payload = runtime.submit_device_performance_task_sync(
            "fake:android-001", idempotency_key="performance-test"
        )

        self.assertEqual(202, status.value)
        task_id = payload["execution"]["task_id"]
        self.assertEqual(
            "device.performance.snapshot", payload["execution"]["task_type"]
        )
        self.assertTrue(store.terminal.wait(2), "performance task did not finish")
        execution = runtime.get_task_execution(task_id)
        task = runtime.get_task(task_id)
        self.assertEqual("succeeded", execution["status"])
        self.assertEqual("device.performance.snapshot", task["task_type"])
        self.assertEqual(12.5, task["evidence_summary"]["cpu_total_usage_percent"])
        self.assertEqual(62.5, task["evidence_summary"]["memory_used_percent"])
        self.assertEqual(31.0, task["evidence_summary"]["battery_temperature_celsius"])
        artifact_path = task["steps"][0]["result"]["artifact"]["relative_path"]
        self.assertTrue(artifacts.resolve(artifact_path).is_file())

    def test_async_performance_idempotency_fingerprints_deadline(self) -> None:
        store = _NotifyingExecutionStore()
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(self.root / "performance-idempotency"),
            task_execution_store=store,
        )

        _, first = runtime.submit_device_performance_task_sync(
            "fake:android-001", "performance-same", 90
        )
        _, second = runtime.submit_device_performance_task_sync(
            "fake:android-001", "performance-same", 90
        )
        conflict_status, conflict = runtime.submit_device_performance_task_sync(
            "fake:android-001", "performance-same", 120
        )

        self.assertEqual(
            first["execution"]["task_id"], second["execution"]["task_id"]
        )
        self.assertEqual(409, conflict_status.value)
        self.assertEqual("IDEMPOTENCY_CONFLICT", conflict["error"]["code"])
        self.assertTrue(store.terminal.wait(2), "performance task did not finish")

    def test_async_device_logs_requires_confirmation_before_queue(self) -> None:
        runtime = RuntimeService(
            FakeDeviceAdapter(), ArtifactStore(self.root / "artifacts")
        )

        status, payload = runtime.submit_device_logs_task_sync(
            "fake:android-001", confirmed=False
        )

        self.assertEqual(403, status.value)
        self.assertEqual("CONFIRMATION_REQUIRED", payload["error"]["code"])

    def test_running_device_log_task_cancels_after_current_adb_boundary(self) -> None:
        store = _NotifyingExecutionStore()
        adapter = _BlockingLogAdapter()
        runtime = RuntimeService(
            adapter,
            ArtifactStore(self.root / "artifacts"),
            task_execution_store=store,
        )
        _, payload = runtime.submit_device_logs_task_sync(
            "fake:android-001", confirmed=True
        )
        task_id = payload["execution"]["task_id"]
        self.addCleanup(adapter.release.set)
        self.assertTrue(adapter.started.wait(2), "log capture did not start")

        cancelling = runtime.cancel_task_execution(task_id)
        adapter.release.set()

        self.assertEqual("cancelling", cancelling["status"])
        self.assertTrue(store.terminal.wait(2), "cancelled log task did not finish")
        execution = runtime.get_task_execution(task_id)
        task = runtime.get_task(task_id)
        self.assertEqual("cancelled", execution["status"])
        self.assertEqual("cancelled", task["status"])
        self.assertEqual("succeeded", task["steps"][0]["status"])
        self.assertTrue(task["evidence_summary"]["artifact_refs"])

    def test_async_device_logs_idempotency_uses_structured_request(self) -> None:
        store = _NotifyingExecutionStore()
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(self.root / "artifacts"),
            task_execution_store=store,
        )

        _, first = runtime.submit_device_logs_task_sync(
            "fake:android-001",
            max_lines=100,
            confirmed=True,
            idempotency_key="logs-same",
        )
        _, second = runtime.submit_device_logs_task_sync(
            "fake:android-001",
            max_lines=100,
            confirmed=True,
            idempotency_key="logs-same",
        )
        conflict_status, conflict = runtime.submit_device_logs_task_sync(
            "fake:android-001",
            max_lines=200,
            confirmed=True,
            idempotency_key="logs-same",
        )

        self.assertEqual(
            first["execution"]["task_id"], second["execution"]["task_id"]
        )
        self.assertEqual(409, conflict_status.value)
        self.assertEqual("IDEMPOTENCY_CONFLICT", conflict["error"]["code"])
        self.assertTrue(store.terminal.wait(2), "idempotent log task did not finish")

    def test_executor_rejects_unregistered_task_type(self) -> None:
        executor = AsyncTaskExecutor(InMemoryTaskExecutionStore())

        async def run(
            task_id: str,
            on_step: object,
            cancelled: object,
            deadline_exceeded: object,
        ) -> TaskRun:
            return _task(task_id, "unsafe", TaskStatus.SUCCEEDED)

        with self.assertRaises(MobileAgentError) as raised:
            executor.submit(
                "fake:android-001",
                "unsafe",
                run,
                lambda task: None,
                task_type="arbitrary.handler",
            )

        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)

    def test_idempotency_key_reuses_same_request_and_rejects_conflict(self) -> None:
        store = _NotifyingExecutionStore()
        runtime = RuntimeService(
            FakeDeviceAdapter(),
            ArtifactStore(self.root / "artifacts"),
            task_execution_store=store,
        )

        first_status, first = runtime.submit_agent_task_sync(
            "fake:android-001",
            "open display settings",
            confirmed=True,
            idempotency_key="test-same-request",
        )
        second_status, second = runtime.submit_agent_task_sync(
            "fake:android-001",
            "open display settings",
            confirmed=True,
            idempotency_key="test-same-request",
        )
        conflict_status, conflict = runtime.submit_agent_task_sync(
            "fake:android-001",
            "a different goal",
            confirmed=True,
            idempotency_key="test-same-request",
        )

        self.assertEqual(202, first_status.value)
        self.assertEqual(202, second_status.value)
        self.assertEqual(
            first["execution"]["task_id"], second["execution"]["task_id"]
        )
        self.assertEqual(409, conflict_status.value)
        self.assertEqual("IDEMPOTENCY_CONFLICT", conflict["error"]["code"])
        self.assertTrue(store.terminal.wait(2), "idempotent task did not finish")

    def test_queued_task_can_be_cancelled_without_running(self) -> None:
        store = _NotifyingExecutionStore()
        executor = AsyncTaskExecutor(store)
        release_first = threading.Event()
        completed: dict[str, TaskRun] = {}

        async def blocking_run(
            task_id: str,
            on_step: object,
            cancelled: object,
            deadline_exceeded: object,
        ) -> TaskRun:
            await asyncio.to_thread(release_first.wait)
            return _task(task_id, "first", TaskStatus.SUCCEEDED)

        async def second_run(
            task_id: str,
            on_step: object,
            cancelled: object,
            deadline_exceeded: object,
        ) -> TaskRun:
            self.fail("queued cancelled task must not run")

        first = executor.submit(
            "fake:android-001", "first", blocking_run, lambda task: completed.setdefault(task.task_id, task)
        )
        self.assertTrue(store.running.wait(2), "first task did not enter running")
        second = executor.submit(
            "fake:android-001", "second", second_run, lambda task: completed.setdefault(task.task_id, task)
        )

        cancelled = executor.cancel(second.task_id)
        release_first.set()

        self.assertEqual(ExecutionStatus.CANCELLED, cancelled.status)
        self.assertTrue(cancelled.result_available)
        self.assertEqual(TaskStatus.CANCELLED, completed[second.task_id].status)
        self.assertNotEqual(first.task_id, second.task_id)
        self.assertEqual(
            ["task.queued", "task.cancel_requested", "task.completed"],
            [event["event_type"] for event in executor.list_events(second.task_id)],
        )

    def test_runner_honors_cancellation_before_observation(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, ArtifactStore(self.root / "artifacts"))

        task = asyncio.run(
            runtime._agent_runner.run(  # noqa: SLF001 - cancellation integration seam
                "fake:android-001",
                "open display settings",
                confirmed=True,
                cancellation_requested=lambda: True,
            )
        )

        self.assertEqual(TaskStatus.CANCELLED, task.status)
        self.assertEqual("TASK_CANCELLED", task.error["code"])
        self.assertEqual((), task.steps)
        self.assertEqual([], adapter.actions)

    def test_sqlite_recovery_fails_interrupted_execution_without_replay(self) -> None:
        database = self.root / "mobile-agent.db"
        store = SQLiteTaskExecutionStore(database)
        execution = TaskExecution(
            task_id="task_00000000000000000000000000000001",
            task_type="agent.run",
            device_id="fake:android-001",
            goal="recover me",
            status=ExecutionStatus.RUNNING,
            submitted_at=_now(),
            started_at=_now(),
        )
        store.save_execution(execution)

        store.recover_incomplete_executions()

        recovered = store.get_execution(execution.task_id)
        events = store.list_execution_events(execution.task_id)
        self.assertEqual(ExecutionStatus.FAILED, recovered.status)
        self.assertEqual("TASK_INTERRUPTED", recovered.error["code"])
        self.assertEqual("unknown_outcome", recovered.error["outcome"])
        self.assertEqual("task.completed", events[-1]["event_type"])

    def test_sqlite_recovery_preserves_diagnostic_task_type(self) -> None:
        store = SQLiteTaskExecutionStore(self.root / "diagnostic.db")
        execution = TaskExecution(
            task_id="task_00000000000000000000000000000002",
            task_type="device.logs.collect",
            device_id="fake:android-001",
            goal="collect logs",
            status=ExecutionStatus.QUEUED,
            submitted_at=_now(),
        )
        store.save_execution(execution)

        store.recover_incomplete_executions()

        recovered = store.get_execution(execution.task_id)
        self.assertEqual("device.logs.collect", recovered.task_type)
        self.assertEqual(ExecutionStatus.FAILED, recovered.status)
        self.assertEqual("TASK_INTERRUPTED", recovered.error["code"])
        self.assertEqual("known_failure", recovered.error["outcome"])


def _task(task_id: str, goal: str, status: TaskStatus) -> TaskRun:
    completed_at = _now()
    return TaskRun(
        task_id=task_id,
        task_type="agent.run",
        device_id="fake:android-001",
        goal=goal,
        status=status,
        started_at=completed_at,
        completed_at=completed_at,
        steps=(),
        evidence_summary={},
    )


class _BlockingLogAdapter(FakeDeviceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    async def collect_logs(
        self, device_id: str, max_lines: int, minimum_level: DeviceLogLevel
    ) -> bytes:
        self.started.set()
        await asyncio.to_thread(self.release.wait)
        return b"07-15 10:00:00.000  100  100 W Test: completed\n"
