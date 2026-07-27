"""Read-only local storage inventory and scoped Artifact cleanup."""

from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from mobile_agent.domain.action import RiskLevel
from mobile_agent.domain.artifact import ArtifactKind
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.local_data import (
    LocalArtifactEntry,
    LocalDataCleanupApproval,
    LocalStorageSummary,
    validate_cleanup_limit,
    validate_retention_days,
)
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.policy.engine import PolicyEngine


_ARTIFACT_NAME = re.compile(r"^(artifact_[a-f0-9]{32})(\.[a-z]+)$")
_KINDS = {
    ".png": ArtifactKind.SCREENSHOT,
    ".xml": ArtifactKind.UI_TREE,
    ".log": ArtifactKind.DEVICE_LOG,
    ".json": ArtifactKind.DEVICE_PERFORMANCE,
    ".zip": ArtifactKind.DIAGNOSTIC_BUNDLE,
}
_MAX_RETENTION_ARTIFACT_BYTES = 64 * 1024 * 1024


def _iso(timestamp: float) -> str:
    return (
        datetime.fromtimestamp(timestamp, timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


class LocalDataTool:
    """Operate only on generated Artifact files below one trusted store."""

    def __init__(
        self,
        artifacts: ArtifactStore,
        policy: PolicyEngine,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._artifacts = artifacts
        self._policy = policy
        self._clock = clock

    def summarize(self, retention_days: int) -> LocalStorageSummary:
        retention_days = validate_retention_days(retention_days)
        now = self._clock()
        cutoff = now - retention_days * 86400
        entries = self._scan(hash_contents=False)
        by_kind: dict[str, dict[str, int]] = {}
        for kind in ArtifactKind:
            by_kind[kind.value] = {"count": 0, "size_bytes": 0}
        for entry in entries:
            bucket = by_kind[entry.kind.value]
            bucket["count"] += 1
            bucket["size_bytes"] += entry.size_bytes
        expired = [item for item in entries if item.created_at_epoch < cutoff]
        times = [item.created_at_epoch for item in entries]
        return LocalStorageSummary(
            retention_days,
            _iso(now),
            len(entries),
            sum(item.size_bytes for item in entries),
            len(expired),
            sum(item.size_bytes for item in expired),
            _iso(min(times)) if times else None,
            _iso(max(times)) if times else None,
            by_kind,
        )

    def prepare(
        self, retention_days: int, max_artifacts: int
    ) -> tuple[float, tuple[LocalArtifactEntry, ...], bool]:
        retention_days = validate_retention_days(retention_days)
        max_artifacts = validate_cleanup_limit(max_artifacts)
        cutoff = self._clock() - retention_days * 86400
        expired = sorted(
            (
                item
                for item in self._scan(hash_contents=True)
                if item.created_at_epoch < cutoff
            ),
            key=lambda item: (item.created_at_epoch, item.artifact_id),
        )
        return cutoff, tuple(expired[:max_artifacts]), len(expired) > max_artifacts

    def cleanup(
        self,
        approval: LocalDataCleanupApproval,
        confirmed: bool,
        cancellation_requested: Callable[[], bool] | None = None,
        deadline_exceeded: Callable[[], bool] | None = None,
    ) -> tuple[tuple[str, ...], int]:
        self._policy.authorize(
            RiskLevel.HIGH, confirmed, high_risk_authorized=True
        )
        deleted: list[str] = []
        deleted_bytes = 0
        for candidate in approval.candidates:
            if (
                cancellation_requested is not None
                and cancellation_requested()
            ) or (deadline_exceeded is not None and deadline_exceeded()):
                break
            path = self._candidate_path(candidate)
            try:
                current_stat = path.stat()
                current_hash = _sha256(path)
            except OSError as error:
                raise _cleanup_changed(
                    candidate.artifact_id, deleted, deleted_bytes
                ) from error
            if (
                current_stat.st_nlink != 1
                or current_stat.st_size != candidate.size_bytes
                or current_hash != candidate.sha256
                or current_stat.st_mtime >= _parse_iso(approval.cutoff_at)
            ):
                raise _cleanup_changed(
                    candidate.artifact_id, deleted, deleted_bytes
                )
            try:
                path.unlink()
            except OSError as error:
                raise MobileAgentError(
                    "LOCAL_DATA_CLEANUP_FAILED",
                    ErrorCategory.STORAGE,
                    "无法删除已批准的本地 Artifact",
                    details={
                        "failed_artifact_id": candidate.artifact_id,
                        "deleted_artifact_ids": list(deleted),
                        "deleted_bytes": deleted_bytes,
                    },
                ) from error
            if path.exists():
                raise MobileAgentError(
                    "LOCAL_DATA_CLEANUP_NOT_VERIFIED",
                    ErrorCategory.STORAGE,
                    "本地 Artifact 删除后仍然存在",
                    details={
                        "failed_artifact_id": candidate.artifact_id,
                        "deleted_artifact_ids": list(deleted),
                        "deleted_bytes": deleted_bytes,
                    },
                )
            deleted.append(candidate.artifact_id)
            deleted_bytes += candidate.size_bytes
        return tuple(deleted), deleted_bytes

    def _scan(self, hash_contents: bool) -> tuple[LocalArtifactEntry, ...]:
        entries: list[LocalArtifactEntry] = []
        try:
            paths = tuple(self._artifacts.root.rglob("artifact_*"))
        except OSError as error:
            raise MobileAgentError(
                "STORAGE_ERROR", ErrorCategory.STORAGE, "无法扫描本地 Artifact"
            ) from error
        for path in paths:
            match = _ARTIFACT_NAME.fullmatch(path.name)
            kind = _KINDS.get(path.suffix.lower())
            if match is None or kind is None or path.is_symlink() or not path.is_file():
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(self._artifacts.root):
                continue
            try:
                stat = path.stat()
                if stat.st_nlink != 1:
                    continue
                if hash_contents and stat.st_size > _MAX_RETENTION_ARTIFACT_BYTES:
                    continue
                digest = _sha256(path) if hash_contents else ""
            except OSError as error:
                raise MobileAgentError(
                    "STORAGE_ERROR",
                    ErrorCategory.STORAGE,
                    "无法读取本地 Artifact 元数据",
                ) from error
            entries.append(
                LocalArtifactEntry(
                    match.group(1),
                    kind,
                    resolved.relative_to(self._artifacts.root).as_posix(),
                    stat.st_size,
                    digest,
                    stat.st_mtime,
                )
            )
        return tuple(entries)

    def _candidate_path(self, candidate: LocalArtifactEntry) -> Path:
        path = self._artifacts.root / candidate.relative_path
        if path.is_symlink():
            raise _cleanup_changed(candidate.artifact_id, [], 0)
        resolved = path.resolve()
        if (
            not resolved.is_relative_to(self._artifacts.root)
            or resolved.name != Path(candidate.relative_path).name
        ):
            raise _cleanup_changed(candidate.artifact_id, [], 0)
        return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_iso(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _cleanup_changed(
    artifact_id: str, deleted: list[str], deleted_bytes: int
) -> MobileAgentError:
    return MobileAgentError(
        "LOCAL_DATA_CLEANUP_SCOPE_CHANGED",
        ErrorCategory.STORAGE,
        "本地 Artifact 在确认后发生变化，原清理范围已失效",
        details={
            "failed_artifact_id": artifact_id,
            "deleted_artifact_ids": list(deleted),
            "deleted_bytes": deleted_bytes,
        },
        suggested_action="重新执行清理预检并确认新的影响摘要",
    )
