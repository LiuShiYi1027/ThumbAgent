"""SQLite persistence for asynchronous execution state and live events."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.task import TaskEvent, TaskEventType
from mobile_agent.storage.sqlite import migrate_database
from mobile_agent.tasks.execution import (
    ExecutionStatus,
    TaskExecution,
    terminal_execution_conflict,
)
from mobile_agent.tasks.store import task_not_found


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class SQLiteTaskExecutionStore:
    """Persist live execution state independently from terminal TaskRun reports."""

    def __init__(self, path: Path) -> None:
        self._path = path.expanduser().resolve()
        migrate_database(self._path)

    def create_execution(
        self,
        execution: TaskExecution,
        idempotency_key: str | None,
        request_fingerprint: str,
    ) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO task_executions(
                        task_id, task_type, device_id, status, submitted_at,
                        started_at, completed_at, idempotency_key,
                        request_fingerprint, execution_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        execution.task_id,
                        execution.task_type,
                        execution.device_id,
                        execution.status.value,
                        execution.submitted_at,
                        execution.started_at,
                        execution.completed_at,
                        idempotency_key,
                        request_fingerprint,
                        _json_dumps(execution.to_dict()),
                    ),
                )
        except sqlite3.Error as error:
            raise _storage_error("无法创建异步任务状态") from error

    def save_execution(self, execution: TaskExecution) -> None:
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO task_executions(
                        task_id, task_type, device_id, status, submitted_at,
                        started_at, completed_at, execution_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(task_id) DO UPDATE SET
                        status = excluded.status,
                        started_at = excluded.started_at,
                        completed_at = excluded.completed_at,
                        execution_json = excluded.execution_json
                    WHERE task_executions.status NOT IN (
                        'succeeded', 'failed', 'cancelled', 'timed_out'
                    )
                    """,
                    (
                        execution.task_id,
                        execution.task_type,
                        execution.device_id,
                        execution.status.value,
                        execution.submitted_at,
                        execution.started_at,
                        execution.completed_at,
                        _json_dumps(execution.to_dict()),
                    ),
                )
                if cursor.rowcount == 0:
                    # 数据库层终态防线：已有终态行时 UPSERT 不生效。
                    # 同内容重写幂等；不同内容覆盖以 TASK_STATE_CONFLICT 拒绝。
                    # 恢复流程的终态采纳走 recover_incomplete_executions 的
                    # 专用 UPDATE，不经过本方法。
                    row = connection.execute(
                        "SELECT execution_json FROM task_executions WHERE task_id = ?",
                        (execution.task_id,),
                    ).fetchone()
                    if (
                        row is not None
                        and TaskExecution.from_dict(_json_object(str(row[0])))
                        == execution
                    ):
                        return
                    raise terminal_execution_conflict(execution.task_id)
        except sqlite3.Error as error:
            raise _storage_error("无法保存异步任务状态") from error

    def get_execution(self, task_id: str) -> TaskExecution:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT execution_json FROM task_executions WHERE task_id = ?",
                    (task_id,),
                ).fetchone()
        except sqlite3.Error as error:
            raise _storage_error("无法读取异步任务状态") from error
        if row is None:
            raise task_not_found(task_id)
        return TaskExecution.from_dict(_json_object(str(row[0])))

    def append_execution_event(self, event: TaskEvent) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO task_execution_events(
                        event_id, task_id, sequence, event_type, occurred_at, event_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.task_id,
                        event.sequence,
                        event.event_type.value,
                        event.occurred_at,
                        _json_dumps(event.to_dict()),
                    ),
                )
        except sqlite3.Error as error:
            raise _storage_error("无法保存异步任务事件") from error

    def list_execution_events(self, task_id: str) -> list[dict[str, object]]:
        self.get_execution(task_id)
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT event_json FROM task_execution_events
                    WHERE task_id = ? ORDER BY sequence ASC
                    """,
                    (task_id,),
                ).fetchall()
        except sqlite3.Error as error:
            raise _storage_error("无法读取异步任务事件") from error
        return [_json_object(str(row[0])) for row in rows]

    def recover_incomplete_executions(self) -> None:
        """Fail interrupted work on startup without replaying device actions."""

        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT execution_json FROM task_executions
                    WHERE status IN ('queued', 'running', 'paused', 'cancelling')
                    """
                ).fetchall()
                for row in rows:
                    execution = TaskExecution.from_dict(_json_object(str(row[0])))
                    completed_at = _now()
                    terminal_run = _terminal_task_run(connection, execution.task_id)
                    if terminal_run is not None:
                        # 崩溃窗口：终态 TaskRun 已落库而 execution 仍非终态。
                        # 采纳 TaskStore 终态（TaskRun 只在完成后写入），不得
                        # 写入与报告矛盾的 TASK_INTERRUPTED。
                        adopted_status = ExecutionStatus(str(terminal_run["status"]))
                        run_error = terminal_run.get("error")
                        run_completed_at = terminal_run.get("completed_at")
                        adopted = replace(
                            execution,
                            status=adopted_status,
                            completed_at=(
                                str(run_completed_at)
                                if run_completed_at
                                else completed_at
                            ),
                            result_available=True,
                            error=run_error if isinstance(run_error, dict) else None,
                        )
                        connection.execute(
                            """
                            UPDATE task_executions
                            SET status = ?, completed_at = ?, execution_json = ?
                            WHERE task_id = ?
                            """,
                            (
                                adopted.status.value,
                                adopted.completed_at,
                                _json_dumps(adopted.to_dict()),
                                adopted.task_id,
                            ),
                        )
                        has_completed_event = int(
                            connection.execute(
                                """
                                SELECT COUNT(*) FROM task_execution_events
                                WHERE task_id = ? AND event_type = ?
                                """,
                                (adopted.task_id, TaskEventType.COMPLETED.value),
                            ).fetchone()[0]
                        )
                        if not has_completed_event:
                            adopted_payload: dict[str, object] = {
                                "status": adopted_status.value,
                                "recovered": True,
                            }
                            if adopted.error is not None:
                                adopted_payload["error_code"] = str(
                                    adopted.error.get("code", "")
                                )
                            _insert_recovery_event(
                                connection, adopted, completed_at, adopted_payload
                            )
                        continue
                    error = {
                        "code": "TASK_INTERRUPTED",
                        "category": "execution",
                        "message": "Runtime 重启中断了未完成任务；为避免重复设备动作，任务未自动恢复",
                        "retryable": False,
                        "outcome": (
                            "known_failure"
                            if execution.status is ExecutionStatus.QUEUED
                            else "unknown_outcome"
                        ),
                    }
                    recovered = replace(
                        execution,
                        status=ExecutionStatus.FAILED,
                        completed_at=completed_at,
                        error=error,
                    )
                    connection.execute(
                        """
                        UPDATE task_executions
                        SET status = ?, completed_at = ?, execution_json = ?
                        WHERE task_id = ?
                        """,
                        (
                            recovered.status.value,
                            completed_at,
                            _json_dumps(recovered.to_dict()),
                            recovered.task_id,
                        ),
                    )
                    _insert_recovery_event(
                        connection,
                        recovered,
                        completed_at,
                        {"status": "failed", "error_code": "TASK_INTERRUPTED"},
                    )
        except sqlite3.Error as error:
            raise _storage_error("无法恢复 Runtime 重启前的任务状态") from error

    def get_idempotent_execution(
        self, idempotency_key: str
    ) -> tuple[TaskExecution, str] | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT execution_json, request_fingerprint
                    FROM task_executions WHERE idempotency_key = ?
                    """,
                    (idempotency_key,),
                ).fetchone()
        except sqlite3.Error as error:
            raise _storage_error("无法读取异步任务幂等记录") from error
        if row is None:
            return None
        return TaskExecution.from_dict(_json_object(str(row[0]))), str(row[1])

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _terminal_task_run(
    connection: sqlite3.Connection, task_id: str
) -> dict[str, object] | None:
    """Return the terminal TaskRun recorded by the co-located TaskStore, if any.

    部署中 SQLiteTaskStore 与 SQLiteTaskExecutionStore 共用同一数据库文件
    （build_default_runtime），TaskStore 只持久化终态 TaskRun，因此命中即终态。
    """

    row = connection.execute(
        "SELECT task_json FROM tasks WHERE task_id = ?", (task_id,)
    ).fetchone()
    if row is None:
        return None
    return _json_object(str(row[0]))


def _insert_recovery_event(
    connection: sqlite3.Connection,
    execution: TaskExecution,
    occurred_at: str,
    payload: dict[str, object],
) -> None:
    sequence = (
        int(
            connection.execute(
                "SELECT COUNT(*) FROM task_execution_events WHERE task_id = ?",
                (execution.task_id,),
            ).fetchone()[0]
        )
        + 1
    )
    event = TaskEvent(
        event_id=f"event_{uuid.uuid4().hex}",
        task_id=execution.task_id,
        device_id=execution.device_id,
        sequence=sequence,
        event_type=TaskEventType.COMPLETED,
        occurred_at=occurred_at,
        payload=payload,
    )
    connection.execute(
        """
        INSERT INTO task_execution_events(
            event_id, task_id, sequence, event_type, occurred_at, event_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            event.event_id,
            event.task_id,
            event.sequence,
            event.event_type.value,
            event.occurred_at,
            _json_dumps(event.to_dict()),
        ),
    )


def _json_dumps(value: dict[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_object(raw: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise _storage_error("异步任务记录已损坏") from error
    if not isinstance(value, dict):
        raise _storage_error("异步任务记录格式无效")
    return value


def _storage_error(message: str) -> MobileAgentError:
    return MobileAgentError(
        code="STORAGE_ERROR",
        category=ErrorCategory.STORAGE,
        message=message,
    )
