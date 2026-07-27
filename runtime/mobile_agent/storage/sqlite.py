"""SQLite-backed task persistence."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.task import TaskRun
from mobile_agent.tasks.store import derive_task_events, task_not_found, task_summary


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def migrate_database(path: Path) -> None:
    """Apply all recorded SQLite migrations to a local database."""

    database_path = path.expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(database_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            applied = _applied_revisions(connection)
            for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
                revision = migration.stem
                if revision in applied:
                    continue
                connection.executescript(migration.read_text(encoding="utf-8"))
    except sqlite3.Error as error:
        raise MobileAgentError(
            code="STORAGE_ERROR",
            category=ErrorCategory.STORAGE,
            message="无法迁移本地任务数据库",
        ) from error


def _applied_revisions(connection: sqlite3.Connection) -> set[str]:
    cursor = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    )
    if cursor.fetchone() is None:
        return set()
    rows = connection.execute("SELECT revision FROM schema_migrations").fetchall()
    return {str(row[0]) for row in rows}


class SQLiteTaskStore:
    """Persist completed task runs and compact events to SQLite."""

    def __init__(self, path: Path) -> None:
        self._path = path.expanduser().resolve()
        migrate_database(self._path)

    @property
    def path(self) -> Path:
        return self._path

    def save(self, task: TaskRun) -> None:
        """Persist a completed task run and its derived event sequence."""

        task_dict = task.to_dict()
        events = derive_task_events(task)
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO tasks(
                        task_id, task_type, device_id, status, started_at, completed_at, task_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task.task_id,
                        task.task_type,
                        task.device_id,
                        task.status.value,
                        task.started_at,
                        task.completed_at,
                        _json_dumps(task_dict),
                    ),
                )
                connection.execute("DELETE FROM task_events WHERE task_id = ?", (task.task_id,))
                connection.executemany(
                    """
                    INSERT INTO task_events(
                        event_id, task_id, sequence, event_type, occurred_at, event_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            event.event_id,
                            event.task_id,
                            event.sequence,
                            event.event_type.value,
                            event.occurred_at,
                            _json_dumps(event.to_dict()),
                        )
                        for event in events
                    ],
                )
        except sqlite3.Error as error:
            raise MobileAgentError(
                code="STORAGE_ERROR",
                category=ErrorCategory.STORAGE,
                message="无法保存本地任务记录",
            ) from error

    def get_task_dict(self, task_id: str) -> dict[str, object]:
        """Return a stored task as a serializable dictionary."""

        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT task_json FROM tasks WHERE task_id = ?",
                    (task_id,),
                ).fetchone()
        except sqlite3.Error as error:
            raise MobileAgentError(
                code="STORAGE_ERROR",
                category=ErrorCategory.STORAGE,
                message="无法读取本地任务记录",
            ) from error
        if row is None:
            raise task_not_found(task_id)
        return _json_object(str(row[0]))

    def list_event_dicts(self, task_id: str) -> list[dict[str, object]]:
        """Return stored task events ordered by sequence."""

        try:
            with self._connect() as connection:
                task_row = connection.execute(
                    "SELECT task_id FROM tasks WHERE task_id = ?",
                    (task_id,),
                ).fetchone()
                if task_row is None:
                    raise task_not_found(task_id)
                rows = connection.execute(
                    """
                    SELECT event_json FROM task_events
                    WHERE task_id = ?
                    ORDER BY sequence ASC
                    """,
                    (task_id,),
                ).fetchall()
        except MobileAgentError:
            raise
        except sqlite3.Error as error:
            raise MobileAgentError(
                code="STORAGE_ERROR",
                category=ErrorCategory.STORAGE,
                message="无法读取本地任务事件",
            ) from error
        return [_json_object(str(row[0])) for row in rows]

    def list_task_summaries(self, limit: int = 20) -> list[dict[str, object]]:
        """Return recent task summaries ordered by completion time descending."""

        safe_limit = max(1, min(limit, 100)) if not isinstance(limit, bool) else 20
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT task_json FROM tasks
                    ORDER BY completed_at DESC, task_id DESC
                    LIMIT ?
                    """,
                    (safe_limit,),
                ).fetchall()
        except sqlite3.Error as error:
            raise MobileAgentError(
                code="STORAGE_ERROR",
                category=ErrorCategory.STORAGE,
                message="无法读取本地任务列表",
            ) from error
        return [task_summary(_json_object(str(row[0]))) for row in rows]

    def list_deleted_artifact_ids(self) -> set[str]:
        """Return cleanup tombstones derived from immutable TaskRun reports."""

        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT task_json FROM tasks WHERE task_type = ?",
                    ("local.data.cleanup",),
                ).fetchall()
        except sqlite3.Error as error:
            raise MobileAgentError(
                code="STORAGE_ERROR",
                category=ErrorCategory.STORAGE,
                message="无法读取本地清理审计记录",
            ) from error
        deleted: set[str] = set()
        for row in rows:
            task = _json_object(str(row[0]))
            summary = task.get("evidence_summary")
            values = (
                summary.get("deleted_artifact_ids")
                if isinstance(summary, dict)
                else None
            )
            if isinstance(values, list):
                deleted.update(
                    item
                    for item in values
                    if isinstance(item, str) and item.startswith("artifact_")
                )
        return deleted

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _json_dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_object(raw: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise MobileAgentError(
            code="STORAGE_ERROR",
            category=ErrorCategory.STORAGE,
            message="本地任务记录已损坏",
        ) from error
    if not isinstance(value, dict):
        raise MobileAgentError(
            code="STORAGE_ERROR",
            category=ErrorCategory.STORAGE,
            message="本地任务记录格式无效",
        )
    return value
