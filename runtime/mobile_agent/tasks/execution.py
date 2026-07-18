"""Asynchronous task execution state and cooperative cancellation."""

from __future__ import annotations

import asyncio
import queue
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Protocol

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.task import TaskEvent, TaskEventType, TaskRun, TaskStatus, TaskStep
from mobile_agent.tasks.store import task_not_found


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ExecutionStatus(str, Enum):
    """Lifecycle states for one submitted asynchronous task."""

    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


_TERMINAL = frozenset(
    {
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.TIMED_OUT,
    }
)

_SUPPORTED_TASK_TYPES = frozenset(
    {"agent.run", "device.logs.collect", "device.performance.snapshot"}
)


@dataclass(frozen=True, slots=True)
class TaskExecution:
    """Persistable state of a submitted task."""

    task_id: str
    task_type: str
    device_id: str
    goal: str
    status: ExecutionStatus
    submitted_at: str
    deadline_seconds: float = 600.0
    deadline_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    cancel_requested: bool = False
    result_available: bool = False
    error: dict[str, Any] | None = None
    device_session_id: str | None = None
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "device_id": self.device_id,
            "goal": self.goal,
            "status": self.status.value,
            "submitted_at": self.submitted_at,
            "deadline_seconds": self.deadline_seconds,
            "deadline_at": self.deadline_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "cancel_requested": self.cancel_requested,
            "result_available": self.result_available,
            "error": self.error,
            "device_session_id": self.device_session_id,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> TaskExecution:
        """Restore an execution written by this Runtime version."""

        return cls(
            task_id=str(value["task_id"]),
            task_type=str(value["task_type"]),
            device_id=str(value["device_id"]),
            goal=str(value["goal"]),
            status=ExecutionStatus(str(value["status"])),
            submitted_at=str(value["submitted_at"]),
            deadline_seconds=float(value.get("deadline_seconds", 600.0)),
            deadline_at=(str(value["deadline_at"]) if value.get("deadline_at") else None),
            started_at=str(value["started_at"]) if value.get("started_at") else None,
            completed_at=(
                str(value["completed_at"]) if value.get("completed_at") else None
            ),
            cancel_requested=bool(value.get("cancel_requested", False)),
            result_available=bool(value.get("result_available", False)),
            error=value.get("error") if isinstance(value.get("error"), dict) else None,
            device_session_id=(
                str(value["device_session_id"])
                if value.get("device_session_id")
                else None
            ),
        )


class TaskExecutionStore(Protocol):
    """Persistence boundary for live execution state and events."""

    def create_execution(
        self,
        execution: TaskExecution,
        idempotency_key: str | None,
        request_fingerprint: str,
    ) -> None: ...

    def save_execution(self, execution: TaskExecution) -> None: ...

    def get_execution(self, task_id: str) -> TaskExecution: ...

    def append_execution_event(self, event: TaskEvent) -> None: ...

    def list_execution_events(self, task_id: str) -> list[dict[str, object]]: ...

    def recover_incomplete_executions(self) -> None: ...

    def get_idempotent_execution(
        self, idempotency_key: str
    ) -> tuple[TaskExecution, str] | None: ...


class InMemoryTaskExecutionStore:
    """Thread-safe execution store used by tests and embedded runtimes."""

    def __init__(self) -> None:
        self._executions: dict[str, TaskExecution] = {}
        self._events: dict[str, list[TaskEvent]] = {}
        self._idempotency: dict[str, tuple[str, str]] = {}
        self._lock = threading.Lock()

    def create_execution(
        self,
        execution: TaskExecution,
        idempotency_key: str | None,
        request_fingerprint: str,
    ) -> None:
        with self._lock:
            self._executions[execution.task_id] = execution
            self._events.setdefault(execution.task_id, [])
            if idempotency_key is not None:
                self._idempotency[idempotency_key] = (
                    execution.task_id,
                    request_fingerprint,
                )

    def save_execution(self, execution: TaskExecution) -> None:
        with self._lock:
            self._executions[execution.task_id] = execution
            self._events.setdefault(execution.task_id, [])

    def get_execution(self, task_id: str) -> TaskExecution:
        with self._lock:
            execution = self._executions.get(task_id)
        if execution is None:
            raise task_not_found(task_id)
        return execution

    def append_execution_event(self, event: TaskEvent) -> None:
        with self._lock:
            self._events.setdefault(event.task_id, []).append(event)

    def list_execution_events(self, task_id: str) -> list[dict[str, object]]:
        self.get_execution(task_id)
        with self._lock:
            events = tuple(self._events.get(task_id, ()))
        return [event.to_dict() for event in events]

    def recover_incomplete_executions(self) -> None:
        return

    def get_idempotent_execution(
        self, idempotency_key: str
    ) -> tuple[TaskExecution, str] | None:
        with self._lock:
            reference = self._idempotency.get(idempotency_key)
            if reference is None:
                return None
            task_id, fingerprint = reference
            execution = self._executions[task_id]
        return execution, fingerprint


RunFactory = Callable[
    [
        str,
        Callable[[TaskStep], None],
        Callable[[], bool],
        Callable[[], bool],
    ],
    Awaitable[TaskRun],
]
CompletionHandler = Callable[[TaskRun], None]


@dataclass(slots=True)
class _WorkItem:
    execution: TaskExecution
    run_factory: RunFactory
    completion_handler: CompletionHandler
    cancel_event: threading.Event


class AsyncTaskExecutor:
    """Run submitted tasks serially and expose durable progress snapshots."""

    def __init__(
        self,
        store: TaskExecutionStore,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._store = store
        self._monotonic = monotonic_clock
        self._store.recover_incomplete_executions()
        self._queue: queue.Queue[_WorkItem] = queue.Queue()
        self._items: dict[str, _WorkItem] = {}
        self._lock = threading.Lock()
        self._event_lock = threading.Lock()
        self._worker: threading.Thread | None = None

    def submit(
        self,
        device_id: str,
        goal: str,
        run_factory: RunFactory,
        completion_handler: CompletionHandler,
        idempotency_key: str | None = None,
        request_fingerprint: str = "",
        deadline_seconds: float = 600.0,
        task_type: str = "agent.run",
    ) -> TaskExecution:
        """Persist and enqueue one task, returning before device work begins."""

        if task_type not in _SUPPORTED_TASK_TYPES:
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="不支持的异步任务类型",
            )
        with self._lock:
            if idempotency_key is not None:
                existing = self._store.get_idempotent_execution(idempotency_key)
                if existing is not None:
                    execution, existing_fingerprint = existing
                    if existing_fingerprint != request_fingerprint:
                        raise MobileAgentError(
                            code="IDEMPOTENCY_CONFLICT",
                            category=ErrorCategory.VALIDATION,
                            message="相同 Idempotency-Key 已用于不同的任务请求",
                        )
                    return execution
            execution = TaskExecution(
                task_id=f"task_{uuid.uuid4().hex}",
                task_type=task_type,
                device_id=device_id,
                goal=goal,
                status=ExecutionStatus.QUEUED,
                submitted_at=_now(),
                deadline_seconds=deadline_seconds,
            )
            item = _WorkItem(
                execution, run_factory, completion_handler, threading.Event()
            )
            self._items[execution.task_id] = item
            self._store.create_execution(
                execution, idempotency_key, request_fingerprint
            )
        self._append_event(execution, TaskEventType.QUEUED, {})
        self._ensure_worker()
        self._queue.put(item)
        return execution

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._worker_loop,
                name="mobile-agent-task-worker",
                daemon=True,
            )
            self._worker.start()

    def get(self, task_id: str) -> TaskExecution:
        return self._store.get_execution(task_id)

    def list_events(self, task_id: str) -> list[dict[str, object]]:
        return self._store.list_execution_events(task_id)

    def bind_device_session(self, task_id: str, session_id: str) -> TaskExecution:
        """Persist the device session after execution acquires write ownership."""

        with self._lock:
            execution = self._store.get_execution(task_id)
            if execution.status not in {
                ExecutionStatus.RUNNING,
                ExecutionStatus.CANCELLING,
            }:
                raise MobileAgentError(
                    code="TASK_STATE_CONFLICT",
                    category=ErrorCategory.EXECUTION,
                    message="任务当前状态不能绑定设备会话",
                )
            updated = replace(execution, device_session_id=session_id)
            self._store.save_execution(updated)
            return updated

    def cancel(self, task_id: str) -> TaskExecution:
        """Request cooperative cancellation without undoing prior device actions."""

        with self._lock:
            execution = self._store.get_execution(task_id)
            if execution.status in _TERMINAL:
                return execution
            item = self._items.get(task_id)
            if item is None:
                raise MobileAgentError(
                    code="TASK_STATE_CONFLICT",
                    category=ErrorCategory.EXECUTION,
                    message="任务不在当前 Runtime 的可取消执行上下文中",
                )
            item.cancel_event.set()
            now = _now()
            if execution.status is ExecutionStatus.QUEUED:
                error = _cancelled_error()
                item.completion_handler(
                    TaskRun(
                        task_id=execution.task_id,
                        task_type=execution.task_type,
                        device_id=execution.device_id,
                        goal=execution.goal,
                        status=TaskStatus.CANCELLED,
                        started_at=execution.submitted_at,
                        completed_at=now,
                        steps=(),
                        evidence_summary={},
                        error=error,
                        deadline_seconds=execution.deadline_seconds,
                    )
                )
                updated = replace(
                    execution,
                    status=ExecutionStatus.CANCELLED,
                    cancel_requested=True,
                    completed_at=now,
                    result_available=True,
                    error=error,
                )
            else:
                updated = replace(
                    execution,
                    status=ExecutionStatus.CANCELLING,
                    cancel_requested=True,
                )
                self._store.save_execution(updated)
        self._append_event(updated, TaskEventType.CANCEL_REQUESTED, {})
        if updated.status is ExecutionStatus.CANCELLED:
            self._append_event(
                updated,
                TaskEventType.COMPLETED,
                {"status": "cancelled", "error_code": "TASK_CANCELLED"},
            )
            self._store.save_execution(updated)
        return updated

    def _worker_loop(self) -> None:
        while True:
            item = self._queue.get()
            try:
                with self._lock:
                    current = self._store.get_execution(item.execution.task_id)
                    if (
                        current.status is ExecutionStatus.CANCELLED
                        or item.cancel_event.is_set()
                    ):
                        continue
                    running = replace(
                        current,
                        status=ExecutionStatus.RUNNING,
                        started_at=_now(),
                        deadline_at=(
                            datetime.now(timezone.utc)
                            + timedelta(seconds=current.deadline_seconds)
                        ).isoformat().replace("+00:00", "Z"),
                    )
                    self._store.save_execution(running)
                self._append_event(running, TaskEventType.STARTED, {})
                deadline_monotonic = self._monotonic() + running.deadline_seconds

                def on_step(step: TaskStep) -> None:
                    payload: dict[str, Any] = {
                        "step_id": step.step_id,
                        "kind": step.kind,
                        "name": step.name,
                        "status": step.status.value,
                    }
                    if step.error is not None:
                        payload["error_code"] = step.error.get("code", "")
                    self._append_event(
                        self._store.get_execution(running.task_id),
                        TaskEventType.STEP_COMPLETED,
                        payload,
                        occurred_at=step.completed_at,
                    )

                task = asyncio.run(
                    item.run_factory(
                        running.task_id,
                        on_step,
                        item.cancel_event.is_set,
                        lambda: self._monotonic() >= deadline_monotonic,
                    )
                )
                item.completion_handler(task)
                status = {
                    TaskStatus.SUCCEEDED: ExecutionStatus.SUCCEEDED,
                    TaskStatus.FAILED: ExecutionStatus.FAILED,
                    TaskStatus.CANCELLED: ExecutionStatus.CANCELLED,
                    TaskStatus.TIMED_OUT: ExecutionStatus.TIMED_OUT,
                }[task.status]
                current = self._store.get_execution(running.task_id)
                final = replace(
                    current,
                    status=status,
                    completed_at=task.completed_at,
                    result_available=True,
                    error=task.error,
                    device_session_id=(
                        task.device_session_id or current.device_session_id
                    ),
                )
                payload = {"status": status.value}
                if task.error is not None:
                    payload["error_code"] = task.error.get("code", "")
                self._append_event(final, TaskEventType.COMPLETED, payload)
                self._store.save_execution(final)
            except Exception:
                failed = replace(
                    self._store.get_execution(item.execution.task_id),
                    status=ExecutionStatus.FAILED,
                    completed_at=_now(),
                    error={
                        "code": "INTERNAL_ERROR",
                        "category": "internal",
                        "message": "异步任务执行器发生内部错误",
                        "retryable": False,
                        "outcome": "known_failure",
                    },
                )
                self._append_event(
                    failed,
                    TaskEventType.COMPLETED,
                    {"status": "failed", "error_code": "INTERNAL_ERROR"},
                )
                self._store.save_execution(failed)
            finally:
                with self._lock:
                    self._items.pop(item.execution.task_id, None)
                self._queue.task_done()

    def _append_event(
        self,
        execution: TaskExecution,
        event_type: TaskEventType,
        payload: dict[str, Any],
        occurred_at: str | None = None,
    ) -> None:
        with self._event_lock:
            events = self._store.list_execution_events(execution.task_id)
            self._store.append_execution_event(
                TaskEvent(
                    event_id=f"event_{uuid.uuid4().hex}",
                    task_id=execution.task_id,
                    device_id=execution.device_id,
                    sequence=len(events) + 1,
                    event_type=event_type,
                    occurred_at=occurred_at or _now(),
                    payload=payload,
                )
            )


def _cancelled_error() -> dict[str, Any]:
    return {
        "code": "TASK_CANCELLED",
        "category": "execution",
        "message": "任务已按用户请求取消",
        "retryable": False,
        "outcome": "known_failure",
    }
