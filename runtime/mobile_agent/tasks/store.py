"""Task stores and event derivation helpers."""

from __future__ import annotations

import threading
import uuid
from typing import Protocol

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.task import TaskEvent, TaskEventType, TaskRun


class TaskStore(Protocol):
    """Persistence boundary for completed task runs and compact events."""

    def save(self, task: TaskRun) -> None:
        """Persist a completed task run."""

    def get_task_dict(self, task_id: str) -> dict[str, object]:
        """Return a stored task as a serializable dictionary."""

    def list_event_dicts(self, task_id: str) -> list[dict[str, object]]:
        """Return stored task events as serializable dictionaries."""

    def list_task_summaries(self, limit: int = 20) -> list[dict[str, object]]:
        """Return recent task summaries ordered by completion time descending."""

    def list_deleted_artifact_ids(self) -> set[str]:
        """Return Artifact IDs recorded by completed local cleanup tasks."""


class InMemoryTaskStore:
    """Keep completed task runs and compact events for this process lifetime."""

    def __init__(self) -> None:
        self._runs: dict[str, TaskRun] = {}
        self._events: dict[str, tuple[TaskEvent, ...]] = {}
        self._lock = threading.Lock()

    def save(self, task: TaskRun) -> None:
        """Store a task run and derive its compact event log."""

        events = derive_task_events(task)
        with self._lock:
            self._runs[task.task_id] = task
            self._events[task.task_id] = events

    def get(self, task_id: str) -> TaskRun:
        """Return a stored task run or raise a structured not-found error."""

        with self._lock:
            task = self._runs.get(task_id)
        if task is None:
            raise task_not_found(task_id)
        return task

    def get_task_dict(self, task_id: str) -> dict[str, object]:
        """Return a stored task as a serializable dictionary."""

        return self.get(task_id).to_dict()

    def list_task_summaries(self, limit: int = 20) -> list[dict[str, object]]:
        """Return recent task summaries ordered by completion time descending."""

        safe_limit = _safe_limit(limit)
        with self._lock:
            tasks = sorted(
                self._runs.values(),
                key=lambda task: task.completed_at,
                reverse=True,
            )[:safe_limit]
        return [task_summary(task.to_dict()) for task in tasks]

    def list_events(self, task_id: str) -> tuple[TaskEvent, ...]:
        """Return stored task events in sequence order."""

        with self._lock:
            events = self._events.get(task_id)
        if events is None:
            raise task_not_found(task_id)
        return events

    def list_event_dicts(self, task_id: str) -> list[dict[str, object]]:
        """Return stored task events as serializable dictionaries."""

        return [event.to_dict() for event in self.list_events(task_id)]

    def list_deleted_artifact_ids(self) -> set[str]:
        with self._lock:
            tasks = tuple(self._runs.values())
        deleted: set[str] = set()
        for task in tasks:
            if task.task_type != "local.data.cleanup":
                continue
            values = task.evidence_summary.get("deleted_artifact_ids")
            if isinstance(values, list):
                deleted.update(
                    item
                    for item in values
                    if isinstance(item, str) and item.startswith("artifact_")
                )
        return deleted


def task_not_found(task_id: str) -> MobileAgentError:
    """Build the stable not-found error used by all task stores."""

    return MobileAgentError(
        code="TASK_NOT_FOUND",
        category=ErrorCategory.VALIDATION,
        message="任务不存在或已不在当前 Runtime 生命周期内",
        details={"task_id": task_id},
    )


def task_summary(task: dict[str, object]) -> dict[str, object]:
    """Build the compact task summary used by list views."""

    return {
        "schema_version": task.get("schema_version", "1.0.0"),
        "task_id": task.get("task_id", ""),
        "task_type": task.get("task_type", ""),
        "device_id": task.get("device_id", ""),
        "goal": task.get("goal", ""),
        "status": task.get("status", ""),
        "started_at": task.get("started_at", ""),
        "completed_at": task.get("completed_at", ""),
    }


def _safe_limit(limit: int) -> int:
    if isinstance(limit, bool):
        return 20
    return max(1, min(limit, 100))


def derive_task_events(task: TaskRun) -> tuple[TaskEvent, ...]:
    """Derive a compact event sequence from a completed task run."""

    events: list[TaskEvent] = [
        TaskEvent(
            event_id=f"event_{uuid.uuid4().hex}",
            task_id=task.task_id,
            device_id=task.device_id,
            sequence=1,
            event_type=TaskEventType.STARTED,
            occurred_at=task.started_at,
            payload={
                "task_type": task.task_type,
                "goal": task.goal,
            },
        )
    ]
    next_sequence = 2
    for step in task.steps:
        payload = {
            "step_id": step.step_id,
            "kind": step.kind,
            "name": step.name,
            "status": step.status.value,
        }
        if step.error is not None:
            payload["error_code"] = step.error.get("code", "")
        events.append(
            TaskEvent(
                event_id=f"event_{uuid.uuid4().hex}",
                task_id=task.task_id,
                device_id=task.device_id,
                sequence=next_sequence,
                event_type=TaskEventType.STEP_COMPLETED,
                occurred_at=step.completed_at,
                payload=payload,
            )
        )
        next_sequence += 1
    completed_payload = {"status": task.status.value}
    if task.error is not None:
        completed_payload["error_code"] = task.error.get("code", "")
    events.append(
        TaskEvent(
            event_id=f"event_{uuid.uuid4().hex}",
            task_id=task.task_id,
            device_id=task.device_id,
            sequence=next_sequence,
            event_type=TaskEventType.COMPLETED,
            occurred_at=task.completed_at,
            payload=completed_payload,
        )
    )
    return tuple(events)
