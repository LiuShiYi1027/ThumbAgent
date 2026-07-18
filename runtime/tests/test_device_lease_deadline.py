from __future__ import annotations

import asyncio
import tempfile
import threading
import unittest
from pathlib import Path

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.devices.lease import DeviceLeaseManager
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.domain.task import TaskStatus
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService
from mobile_agent.tasks.execution import (
    ExecutionStatus,
    InMemoryTaskExecutionStore,
    TaskExecution,
)


class _NotifyingStore(InMemoryTaskExecutionStore):
    def __init__(self) -> None:
        super().__init__()
        self.terminal = threading.Event()

    def save_execution(self, execution: TaskExecution) -> None:
        super().save_execution(execution)
        if execution.status in {
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.TIMED_OUT,
        }:
            self.terminal.set()


class _BlockingObserveAdapter(FakeDeviceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.observe_started = threading.Event()
        self.observe_release = threading.Event()

    async def observe(self, device_id: str, artifacts: ArtifactStore):
        self.observe_started.set()
        await asyncio.to_thread(self.observe_release.wait)
        return await super().observe(device_id, artifacts)


class _DeadlineObserveAdapter(FakeDeviceAdapter):
    def __init__(self, clock: list[float]) -> None:
        super().__init__()
        self._clock = clock

    async def observe(self, device_id: str, artifacts: ArtifactStore):
        observation = await super().observe(device_id, artifacts)
        self._clock[0] = 2.0
        return observation


class DeviceLeaseDeadlineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_lease_blocks_second_owner_even_after_diagnostic_expiry(self) -> None:
        now = [10.0]
        manager = DeviceLeaseManager(lambda: now[0])

        with manager.hold("fake:android-001", "task_first", 5.0):
            now[0] = 20.0
            with self.assertRaises(MobileAgentError) as raised:
                manager.hold("fake:android-001", "task_second", 5.0)

            self.assertEqual("DEVICE_LOCKED", raised.exception.code)
            self.assertTrue(raised.exception.details["lease_expired"])

        with manager.hold("fake:android-001", "task_second", 5.0) as lease:
            self.assertEqual("task_second", lease.owner_id)

    def test_sync_agent_and_direct_tool_share_exclusive_device_lease(self) -> None:
        adapter = FakeDeviceAdapter()
        manager = DeviceLeaseManager()
        runtime = RuntimeService(
            adapter,
            ArtifactStore(self.root / "artifacts"),
            device_lease_manager=manager,
        )

        with manager.hold("fake:android-001", "task_external", 30.0):
            agent_status, agent_payload = runtime.run_agent_task_sync(
                "fake:android-001", "open display settings", confirmed=True
            )
            tool_status, tool_payload = runtime.invoke_tool_sync(
                "navigation.home", "fake:android-001", {}, confirmed=True
            )

        self.assertEqual(409, agent_status.value)
        self.assertEqual("DEVICE_LOCKED", agent_payload["error"]["code"])
        self.assertEqual(409, tool_status.value)
        self.assertEqual("DEVICE_LOCKED", tool_payload["error"]["code"])
        self.assertEqual([], adapter.actions)

        released_status, _ = runtime.invoke_tool_sync(
            "navigation.home", "fake:android-001", {}, confirmed=True
        )
        self.assertEqual(200, released_status.value)

    def test_async_agent_records_device_locked_without_device_action(self) -> None:
        adapter = FakeDeviceAdapter()
        manager = DeviceLeaseManager()
        store = _NotifyingStore()
        runtime = RuntimeService(
            adapter,
            ArtifactStore(self.root / "artifacts"),
            task_execution_store=store,
            device_lease_manager=manager,
        )

        with manager.hold("fake:android-001", "task_external", 30.0):
            status, payload = runtime.submit_agent_task_sync(
                "fake:android-001",
                "open display settings",
                confirmed=True,
                deadline_seconds=30,
            )
            self.assertTrue(store.terminal.wait(2), "locked async task did not finish")

        task_id = payload["execution"]["task_id"]
        execution = runtime.get_task_execution(task_id)
        task = runtime.get_task(task_id)
        self.assertEqual(202, status.value)
        self.assertEqual("failed", execution["status"])
        self.assertEqual("DEVICE_LOCKED", execution["error"]["code"])
        self.assertEqual("DEVICE_LOCKED", task["error"]["code"])
        self.assertEqual([], task["steps"])
        self.assertEqual([], adapter.actions)

    def test_deadline_stops_agent_before_observation_or_action(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, ArtifactStore(self.root / "artifacts"))

        task = asyncio.run(
            runtime._agent_runner.run(  # noqa: SLF001 - deadline integration seam
                "fake:android-001",
                "open display settings",
                confirmed=True,
                deadline_exceeded=lambda: True,
                deadline_seconds=5,
            )
        )

        self.assertEqual(TaskStatus.TIMED_OUT, task.status)
        self.assertEqual("TASK_DEADLINE_EXCEEDED", task.error["code"])
        self.assertEqual(5, task.deadline_seconds)
        self.assertEqual((), task.steps)
        self.assertEqual([], adapter.actions)

    def test_deadline_after_verified_action_keeps_step_evidence_and_stops(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, ArtifactStore(self.root / "artifacts"))
        checks = iter((False, False, False, True))

        task = asyncio.run(
            runtime._agent_runner.run(  # noqa: SLF001 - deadline integration seam
                "fake:android-001",
                "open display settings",
                confirmed=True,
                deadline_exceeded=lambda: next(checks),
                deadline_seconds=5,
            )
        )

        self.assertEqual(TaskStatus.TIMED_OUT, task.status)
        self.assertEqual("TASK_DEADLINE_EXCEEDED", task.error["code"])
        self.assertEqual(1, len(task.steps))
        self.assertEqual(TaskStatus.SUCCEEDED, task.steps[0].status)
        self.assertEqual("app.launch", adapter.actions[0][0])
        self.assertEqual(1, len(adapter.actions))

    def test_invalid_deadline_is_rejected_before_queue_or_device(self) -> None:
        adapter = FakeDeviceAdapter()
        runtime = RuntimeService(adapter, ArtifactStore(self.root / "artifacts"))

        status, payload = runtime.submit_agent_task_sync(
            "fake:android-001",
            "open display settings",
            confirmed=True,
            deadline_seconds=0,
        )

        self.assertEqual(400, status.value)
        self.assertEqual("INVALID_ARGUMENT", payload["error"]["code"])
        self.assertEqual([], adapter.actions)

    def test_sync_deadline_releases_lease_for_next_writer(self) -> None:
        clock = [0.0]
        adapter = _DeadlineObserveAdapter(clock)
        manager = DeviceLeaseManager(lambda: clock[0])
        runtime = RuntimeService(
            adapter,
            ArtifactStore(self.root / "artifacts"),
            device_lease_manager=manager,
            monotonic_clock=lambda: clock[0],
        )

        status, payload = runtime.run_agent_task_sync(
            "fake:android-001",
            "open display settings",
            confirmed=True,
            deadline_seconds=1,
        )

        self.assertEqual(200, status.value)
        self.assertEqual("timed_out", payload["task"]["status"])
        self.assertIsNone(manager.current("fake:android-001"))
        next_status, _ = runtime.invoke_tool_sync(
            "navigation.home", "fake:android-001", {}, confirmed=True
        )
        self.assertEqual(200, next_status.value)

    def test_running_cancellation_releases_agent_lease(self) -> None:
        adapter = _BlockingObserveAdapter()
        manager = DeviceLeaseManager()
        store = _NotifyingStore()
        runtime = RuntimeService(
            adapter,
            ArtifactStore(self.root / "artifacts"),
            task_execution_store=store,
            device_lease_manager=manager,
        )
        _, payload = runtime.submit_agent_task_sync(
            "fake:android-001",
            "open display settings",
            confirmed=True,
            deadline_seconds=30,
        )
        task_id = payload["execution"]["task_id"]
        self.assertTrue(adapter.observe_started.wait(2), "observe did not start")

        runtime.cancel_task_execution(task_id)
        adapter.observe_release.set()
        self.assertTrue(store.terminal.wait(2), "cancelled task did not finish")

        self.assertEqual("cancelled", runtime.get_task_execution(task_id)["status"])
        self.assertIsNone(manager.current("fake:android-001"))
