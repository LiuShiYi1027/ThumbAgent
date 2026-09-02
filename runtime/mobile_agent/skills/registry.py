"""Custom skill registry: application layer over SQLite persistence.

ITER-0062 / ADR-0021. The registry owns the trust boundary: it re-parses every
DSL document, derives the risk itself (never trusting the document's own risk
declaration), protects built-in skill ids from being shadowed, and emits audit
events whose payloads carry the document digest — never the DSL source text.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mobile_agent.domain.action import RiskLevel
from mobile_agent.domain.errors import ErrorCategory, ErrorOutcome, MobileAgentError
from mobile_agent.domain.skill_dsl import SkillDslDocument, parse_skill_dsl_document
from mobile_agent.skills.dsl_risk import derive_skill_risk
from mobile_agent.storage.skills import SQLiteCustomSkillStore, StoredSkillRow

BUILTIN_MANIFESTS_DIR = Path(__file__).resolve().parent / "manifests"

AuditEmitter = Callable[[str, dict[str, Any]], None]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def builtin_skill_ids() -> frozenset[str]:
    """内置 Skill id 清单：skills/manifests/*.json 的文件名即内置 id。"""

    return frozenset(path.stem for path in BUILTIN_MANIFESTS_DIR.glob("*.json"))


def skill_not_found(skill_id: str, skill_version: str | None) -> MobileAgentError:
    """Build the stable not-found error for registry lookups."""

    return MobileAgentError(
        code="SKILL_NOT_FOUND",
        category=ErrorCategory.VALIDATION,
        message="自定义 Skill 不存在或已删除",
        details={"skill_id": skill_id, "skill_version": skill_version},
    )


def skill_builtin_protected(skill_id: str) -> MobileAgentError:
    """Build the stable rejection for shadowing a built-in skill id."""

    return MobileAgentError(
        code="SKILL_BUILTIN_PROTECTED",
        category=ErrorCategory.VALIDATION,
        message="内置 Skill id 受保护，不能注册同名自定义 Skill",
        outcome=ErrorOutcome.REJECTED,
        details={"skill_id": skill_id},
    )


@dataclass(frozen=True, slots=True)
class CustomSkillRecord:
    """One registered custom skill version as seen by the application layer."""

    skill_id: str
    skill_version: str
    document: SkillDslDocument
    document_json: str
    document_sha256: str
    derived_risk: RiskLevel
    enabled: bool
    source: str
    created_at: str
    updated_at: str


class CustomSkillRegistry:
    """Register, query, enable/disable and delete declarative custom skills."""

    def __init__(
        self,
        store: SQLiteCustomSkillStore,
        *,
        emit_audit: AuditEmitter | None = None,
    ) -> None:
        self._store = store
        self._emit_audit = emit_audit if emit_audit is not None else _noop_audit

    def register(self, payload: dict[str, Any], source: str) -> CustomSkillRecord:
        """Validate, derive risk for, and persist one immutable skill version."""

        document = parse_skill_dsl_document(payload)
        if document.skill_id in builtin_skill_ids():
            raise skill_builtin_protected(document.skill_id)
        derived_risk = derive_skill_risk(document)
        document_json = _canonical_json(payload)
        document_sha256 = hashlib.sha256(document_json.encode("utf-8")).hexdigest()
        now = _now()
        row = StoredSkillRow(
            skill_id=document.skill_id,
            skill_version=document.skill_version,
            document_json=document_json,
            document_sha256=document_sha256,
            derived_risk=derived_risk.value,
            enabled=True,
            source=source,
            created_at=now,
            updated_at=now,
        )
        self._store.insert(row)
        self._emit_audit(
            "skill.registered",
            {
                "skill_id": document.skill_id,
                "skill_version": document.skill_version,
                "document_sha256": document_sha256,
                "derived_risk": derived_risk.value,
                "source": source,
            },
        )
        return _to_record(row)

    def get(self, skill_id: str, version: str | None = None) -> CustomSkillRecord:
        """Return one version; version=None resolves to the latest semver."""

        if version is not None:
            row = self._store.fetch(skill_id, version)
            if row is None:
                raise skill_not_found(skill_id, version)
            return _to_record(row)
        versions = self._store.fetch_versions(skill_id)
        if not versions:
            raise skill_not_found(skill_id, None)
        return _to_record(max(versions, key=lambda row: _version_key(row.skill_version)))

    def list(self) -> list[CustomSkillRecord]:
        """Return every registered version ordered by id and version."""

        return [_to_record(row) for row in self._store.fetch_all()]

    def set_enabled(
        self, skill_id: str, version: str, enabled: bool
    ) -> CustomSkillRecord:
        """Enable or disable one version; the flag survives restarts."""

        row = self._store.fetch(skill_id, version)
        if row is None:
            raise skill_not_found(skill_id, version)
        self._store.set_enabled(skill_id, version, enabled, _now())
        self._emit_audit(
            "skill.enabled" if enabled else "skill.disabled",
            {
                "skill_id": skill_id,
                "skill_version": version,
                "document_sha256": row.document_sha256,
            },
        )
        updated = self._store.fetch(skill_id, version)
        if updated is None:  # pragma: no cover - 刚更新过的行不会消失
            raise skill_not_found(skill_id, version)
        return _to_record(updated)

    def delete(self, skill_id: str, version: str) -> None:
        """Delete one version permanently."""

        row = self._store.fetch(skill_id, version)
        if row is None:
            raise skill_not_found(skill_id, version)
        self._store.delete(skill_id, version)
        self._emit_audit(
            "skill.deleted",
            {
                "skill_id": skill_id,
                "skill_version": version,
                "document_sha256": row.document_sha256,
            },
        )


def _noop_audit(event: str, payload: dict[str, Any]) -> None:
    del event, payload


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _version_key(skill_version: str) -> tuple[int, int, int]:
    parts = skill_version.split(".")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def _to_record(row: StoredSkillRow) -> CustomSkillRecord:
    return CustomSkillRecord(
        skill_id=row.skill_id,
        skill_version=row.skill_version,
        document=parse_skill_dsl_document(json.loads(row.document_json)),
        document_json=row.document_json,
        document_sha256=row.document_sha256,
        derived_risk=RiskLevel(row.derived_risk),
        enabled=row.enabled,
        source=row.source,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
