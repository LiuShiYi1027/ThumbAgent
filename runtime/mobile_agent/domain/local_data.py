"""Local Artifact retention summaries and scoped cleanup approvals."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Callable

from mobile_agent.domain.artifact import ArtifactKind
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError


def _iso(timestamp: float) -> str:
    return (
        datetime.fromtimestamp(timestamp, timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True, slots=True)
class LocalArtifactEntry:
    """One immutable system-generated Artifact file eligible for retention."""

    artifact_id: str
    kind: ArtifactKind
    relative_path: str
    size_bytes: int
    sha256: str
    created_at_epoch: float

    @property
    def created_at(self) -> str:
        return _iso(self.created_at_epoch)


@dataclass(frozen=True, slots=True)
class LocalStorageSummary:
    """Bounded aggregate storage metadata with no Artifact content."""

    retention_days: int
    scanned_at: str
    total_count: int
    total_bytes: int
    expired_count: int
    expired_bytes: int
    oldest_created_at: str | None
    newest_created_at: str | None
    by_kind: dict[str, dict[str, int]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "artifact_root_label": "mobile-agent-data/artifacts",
            "retention_days": self.retention_days,
            "scanned_at": self.scanned_at,
            "total_count": self.total_count,
            "total_bytes": self.total_bytes,
            "expired_count": self.expired_count,
            "expired_bytes": self.expired_bytes,
            "oldest_created_at": self.oldest_created_at,
            "newest_created_at": self.newest_created_at,
            "by_kind": {key: dict(value) for key, value in self.by_kind.items()},
        }


@dataclass(frozen=True, slots=True)
class LocalDataCleanupApproval:
    """Short-lived exact set of expired Artifact files approved for deletion."""

    approval_id: str
    retention_days: int
    cutoff_at: str
    candidates: tuple[LocalArtifactEntry, ...]
    truncated: bool
    prepared_at: str
    expires_at: str
    expires_at_epoch: float
    consumed_by_key: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "approval_id": self.approval_id,
            "retention_days": self.retention_days,
            "cutoff_at": self.cutoff_at,
            "candidate_count": len(self.candidates),
            "candidate_bytes": sum(item.size_bytes for item in self.candidates),
            "truncated": self.truncated,
            "prepared_at": self.prepared_at,
            "expires_at": self.expires_at,
            "local_artifacts_will_be_permanently_deleted": True,
            "confirmation_required": True,
        }


class LocalDataCleanupApprovalStore:
    """Keep single-use local cleanup approvals in Runtime memory."""

    def __init__(
        self, clock: Callable[[], float] = time.time, ttl_seconds: float = 600
    ) -> None:
        self._clock = clock
        self._ttl = ttl_seconds
        self._items: dict[str, LocalDataCleanupApproval] = {}
        self._lock = threading.Lock()

    def create(
        self,
        retention_days: int,
        cutoff_epoch: float,
        candidates: tuple[LocalArtifactEntry, ...],
        truncated: bool,
    ) -> LocalDataCleanupApproval:
        now = self._clock()
        approval = LocalDataCleanupApproval(
            f"approval_{uuid.uuid4().hex}",
            retention_days,
            _iso(cutoff_epoch),
            candidates,
            truncated,
            _iso(now),
            _iso(now + self._ttl),
            now + self._ttl,
        )
        with self._lock:
            self._items[approval.approval_id] = approval
        return approval

    def claim(
        self, approval_id: str, idempotency_key: str
    ) -> LocalDataCleanupApproval:
        with self._lock:
            approval = self._items.get(approval_id)
            if approval is None:
                raise _approval_error("清理 Approval 不存在或 Runtime 已重启")
            if self._clock() >= approval.expires_at_epoch:
                raise _approval_error("清理 Approval 已过期")
            if approval.consumed_by_key not in {None, idempotency_key}:
                raise _approval_error("清理 Approval 已被另一请求使用")
            if approval.consumed_by_key is None:
                approval = replace(approval, consumed_by_key=idempotency_key)
                self._items[approval_id] = approval
            return approval


@dataclass(frozen=True, slots=True)
class LocalDataCleanupResult:
    """Verified result for one exact local Artifact deletion set."""

    skill_call_id: str
    retention_days: int
    cutoff_at: str
    deleted_artifact_ids: tuple[str, ...]
    deleted_bytes: int
    started_at: str
    completed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "skill_call_id": self.skill_call_id,
            "skill_id": "local.data.cleanup",
            "skill_version": "1.0.0",
            "success": True,
            "status": "succeeded",
            "verification": "artifacts_absent",
            "retention_days": self.retention_days,
            "cutoff_at": self.cutoff_at,
            "deleted_count": len(self.deleted_artifact_ids),
            "deleted_bytes": self.deleted_bytes,
            "deleted_artifact_ids": list(self.deleted_artifact_ids),
            "evidence_refs": [],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


def validate_retention_days(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 365:
        raise MobileAgentError(
            "INVALID_ARGUMENT",
            ErrorCategory.VALIDATION,
            "保留周期必须是 1 到 365 天的整数",
        )
    return value


def validate_cleanup_limit(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= 2000
    ):
        raise MobileAgentError(
            "INVALID_ARGUMENT",
            ErrorCategory.VALIDATION,
            "单次清理上限必须是 1 到 2000 的整数",
        )
    return value


def _approval_error(message: str) -> MobileAgentError:
    return MobileAgentError(
        "APPROVAL_INVALID",
        ErrorCategory.POLICY,
        message,
        suggested_action="重新执行本地数据清理预检并展示新的影响摘要",
    )
