"""Task run result contracts for deterministic local task execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """Terminal task status shared by synchronous and asynchronous runners."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class TaskEventType(str, Enum):
    """Auditable task event types emitted by task execution stores."""

    QUEUED = "task.queued"
    STARTED = "task.started"
    STEP_COMPLETED = "task.step_completed"
    PAUSE_REQUESTED = "task.pause_requested"
    PAUSED = "task.paused"
    RESUMED = "task.resumed"
    CANCEL_REQUESTED = "task.cancel_requested"
    COMPLETED = "task.completed"


@dataclass(frozen=True, slots=True)
class TaskStep:
    """A single auditable task step."""

    step_id: str
    sequence: int
    kind: str
    name: str
    status: TaskStatus
    started_at: str
    completed_at: str
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "sequence": self.sequence,
            "kind": self.kind,
            "name": self.name,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class TaskEvent:
    """A compact task event safe for local clients to consume."""

    event_id: str
    task_id: str
    device_id: str
    sequence: int
    event_type: TaskEventType
    occurred_at: str
    payload: dict[str, Any]
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "task_id": self.task_id,
            "device_id": self.device_id,
            "sequence": self.sequence,
            "event_type": self.event_type.value,
            "occurred_at": self.occurred_at,
            "payload": self.payload,
        }


@dataclass(frozen=True, slots=True)
class TaskRun:
    """Completed deterministic task run with an evidence summary."""

    task_id: str
    task_type: str
    device_id: str
    goal: str
    status: TaskStatus
    started_at: str
    completed_at: str
    steps: tuple[TaskStep, ...]
    evidence_summary: dict[str, Any]
    error: dict[str, Any] | None = None
    goal_spec: dict[str, Any] | None = None
    goal_acceptance: dict[str, Any] | None = None
    completion_source: str | None = None
    deadline_seconds: float | None = None
    device_session_id: str | None = None
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "device_id": self.device_id,
            "goal": self.goal,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "steps": [step.to_dict() for step in self.steps],
            "evidence_summary": self.evidence_summary,
            "error": self.error,
        }
        if self.goal_spec is not None:
            payload["goal_spec"] = self.goal_spec
        if self.goal_acceptance is not None:
            payload["goal_acceptance"] = self.goal_acceptance
        if self.completion_source is not None:
            payload["completion_source"] = self.completion_source
        if self.deadline_seconds is not None:
            payload["deadline_seconds"] = self.deadline_seconds
        if self.device_session_id is not None:
            payload["device_session_id"] = self.device_session_id
        return payload
