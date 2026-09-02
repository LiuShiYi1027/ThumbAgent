"""SQLite-backed persistence for declarative custom skills (ITER-0062, ADR-0021)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mobile_agent.domain.errors import ErrorCategory, ErrorOutcome, MobileAgentError
from mobile_agent.storage.sqlite import migrate_database


@dataclass(frozen=True, slots=True)
class StoredSkillRow:
    """One persisted custom skill version row (raw storage shape)."""

    skill_id: str
    skill_version: str
    document_json: str
    document_sha256: str
    derived_risk: str
    enabled: bool
    source: str
    created_at: str
    updated_at: str


def skill_version_conflict(skill_id: str, skill_version: str) -> MobileAgentError:
    """Build the stable conflict error for re-registering an immutable version."""

    return MobileAgentError(
        code="SKILL_VERSION_CONFLICT",
        category=ErrorCategory.VALIDATION,
        message="同一 Skill 的版本不可变，已存在的版本不能重复注册",
        outcome=ErrorOutcome.REJECTED,
        details={"skill_id": skill_id, "skill_version": skill_version},
    )


def _storage_error(message: str) -> MobileAgentError:
    return MobileAgentError(
        code="STORAGE_ERROR",
        category=ErrorCategory.STORAGE,
        message=message,
    )


class SQLiteCustomSkillStore:
    """Persist custom skill DSL documents and lifecycle state to SQLite."""

    def __init__(self, path: Path) -> None:
        self._path = path.expanduser().resolve()
        migrate_database(self._path)

    @property
    def path(self) -> Path:
        return self._path

    def insert(self, row: StoredSkillRow) -> None:
        """Insert one immutable (skill_id, skill_version) row.

        版本不可变：联合主键冲突以 SKILL_VERSION_CONFLICT 拒绝，不做覆盖。
        """

        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO custom_skills(
                        skill_id, skill_version, document_json, document_sha256,
                        derived_risk, enabled, source, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.skill_id,
                        row.skill_version,
                        row.document_json,
                        row.document_sha256,
                        row.derived_risk,
                        1 if row.enabled else 0,
                        row.source,
                        row.created_at,
                        row.updated_at,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise skill_version_conflict(row.skill_id, row.skill_version) from error
        except sqlite3.Error as error:
            raise _storage_error("无法保存自定义 Skill") from error

    def fetch(self, skill_id: str, skill_version: str) -> StoredSkillRow | None:
        """Return one version row, or None when absent."""

        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT skill_id, skill_version, document_json, document_sha256,
                           derived_risk, enabled, source, created_at, updated_at
                    FROM custom_skills
                    WHERE skill_id = ? AND skill_version = ?
                    """,
                    (skill_id, skill_version),
                ).fetchone()
        except sqlite3.Error as error:
            raise _storage_error("无法读取自定义 Skill") from error
        return _to_stored_row(row) if row is not None else None

    def fetch_versions(self, skill_id: str) -> list[StoredSkillRow]:
        """Return every stored version of one skill."""

        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT skill_id, skill_version, document_json, document_sha256,
                           derived_risk, enabled, source, created_at, updated_at
                    FROM custom_skills
                    WHERE skill_id = ?
                    ORDER BY skill_version ASC
                    """,
                    (skill_id,),
                ).fetchall()
        except sqlite3.Error as error:
            raise _storage_error("无法读取自定义 Skill") from error
        return [_to_stored_row(row) for row in rows]

    def fetch_all(self) -> list[StoredSkillRow]:
        """Return every stored custom skill row ordered by id and version."""

        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT skill_id, skill_version, document_json, document_sha256,
                           derived_risk, enabled, source, created_at, updated_at
                    FROM custom_skills
                    ORDER BY skill_id ASC, skill_version ASC
                    """
                ).fetchall()
        except sqlite3.Error as error:
            raise _storage_error("无法读取自定义 Skill 列表") from error
        return [_to_stored_row(row) for row in rows]

    def set_enabled(
        self, skill_id: str, skill_version: str, enabled: bool, updated_at: str
    ) -> bool:
        """Flip the enabled flag; False when the version row does not exist."""

        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE custom_skills
                    SET enabled = ?, updated_at = ?
                    WHERE skill_id = ? AND skill_version = ?
                    """,
                    (1 if enabled else 0, updated_at, skill_id, skill_version),
                )
        except sqlite3.Error as error:
            raise _storage_error("无法更新自定义 Skill 状态") from error
        return cursor.rowcount > 0

    def delete(self, skill_id: str, skill_version: str) -> bool:
        """Delete one version row; False when it does not exist."""

        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    DELETE FROM custom_skills
                    WHERE skill_id = ? AND skill_version = ?
                    """,
                    (skill_id, skill_version),
                )
        except sqlite3.Error as error:
            raise _storage_error("无法删除自定义 Skill") from error
        return cursor.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _to_stored_row(row: tuple[object, ...]) -> StoredSkillRow:
    return StoredSkillRow(
        skill_id=str(row[0]),
        skill_version=str(row[1]),
        document_json=str(row[2]),
        document_sha256=str(row[3]),
        derived_risk=str(row[4]),
        enabled=bool(row[5]),
        source=str(row[6]),
        created_at=str(row[7]),
        updated_at=str(row[8]),
    )


@dataclass(frozen=True, slots=True)
class StoredSkillAuditRow:
    """One persisted skill audit event (raw storage shape, append-only)."""

    audit_id: int
    event_type: str
    skill_id: str
    skill_version: str | None
    document_sha256: str | None
    payload_json: str
    created_at: str


class SQLiteSkillAuditStore:
    """Persist custom skill lifecycle audit events to SQLite (ADR-0021 决策 9).

    append 的签名与 Registry 的 AuditEmitter 回调一致，可直接装配为
    emit_audit；payload 只携带文档 SHA-256 等元数据，不写入 DSL 原文。
    """

    def __init__(self, path: Path) -> None:
        self._path = path.expanduser().resolve()
        migrate_database(self._path)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, event_type: str, payload: dict[str, Any]) -> StoredSkillAuditRow:
        """Append one audit event; payload must carry a string skill_id."""

        skill_id = payload.get("skill_id")
        if not isinstance(skill_id, str) or not skill_id:
            raise _storage_error("审计事件缺少 skill_id")
        skill_version = payload.get("skill_version")
        document_sha256 = payload.get("document_sha256")
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload_json = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO skill_audit(
                        event_type, skill_id, skill_version,
                        document_sha256, payload_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_type,
                        skill_id,
                        skill_version if isinstance(skill_version, str) else None,
                        (
                            document_sha256
                            if isinstance(document_sha256, str)
                            else None
                        ),
                        payload_json,
                        created_at,
                    ),
                )
                audit_id = int(cursor.lastrowid or 0)
        except sqlite3.Error as error:
            raise _storage_error("无法保存 Skill 审计事件") from error
        return StoredSkillAuditRow(
            audit_id=audit_id,
            event_type=event_type,
            skill_id=skill_id,
            skill_version=skill_version if isinstance(skill_version, str) else None,
            document_sha256=(
                document_sha256 if isinstance(document_sha256, str) else None
            ),
            payload_json=payload_json,
            created_at=created_at,
        )

    def list_by_skill(self, skill_id: str) -> list[StoredSkillAuditRow]:
        """Return one skill's audit events in append order."""

        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT id, event_type, skill_id, skill_version,
                           document_sha256, payload_json, created_at
                    FROM skill_audit
                    WHERE skill_id = ?
                    ORDER BY id ASC
                    """,
                    (skill_id,),
                ).fetchall()
        except sqlite3.Error as error:
            raise _storage_error("无法读取 Skill 审计事件") from error
        return [
            StoredSkillAuditRow(
                audit_id=int(row[0]),
                event_type=str(row[1]),
                skill_id=str(row[2]),
                skill_version=str(row[3]) if row[3] is not None else None,
                document_sha256=str(row[4]) if row[4] is not None else None,
                payload_json=str(row[5]),
                created_at=str(row[6]),
            )
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
