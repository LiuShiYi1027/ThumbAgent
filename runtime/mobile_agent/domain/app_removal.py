"""Scoped application removal approval and result contracts."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Callable

from mobile_agent.domain.app import InstalledApp
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class AppRemovalApproval:
    approval_id: str
    device_id: str
    app: InstalledApp
    keep_data: bool
    prepared_at: str
    expires_at: str
    expires_at_epoch: float
    consumed_by_key: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "approval_id": self.approval_id,
            "device_id": self.device_id,
            "app": self.app.to_dict(),
            "keep_data": self.keep_data,
            "application_data_will_be_deleted": not self.keep_data,
            "prepared_at": self.prepared_at,
            "expires_at": self.expires_at,
            "confirmation_required": True,
        }


class AppRemovalApprovalStore:
    """Keep short-lived, single-use uninstall approvals in Runtime memory."""

    def __init__(
        self, clock: Callable[[], float] = time.time, ttl_seconds: float = 600
    ) -> None:
        self._clock = clock
        self._ttl = ttl_seconds
        self._items: dict[str, AppRemovalApproval] = {}
        self._lock = threading.Lock()

    def create(
        self, device_id: str, app: InstalledApp, keep_data: bool
    ) -> AppRemovalApproval:
        now = self._clock()
        approval = AppRemovalApproval(
            f"approval_{uuid.uuid4().hex}",
            device_id,
            app,
            keep_data,
            _iso(now),
            _iso(now + self._ttl),
            now + self._ttl,
        )
        with self._lock:
            self._items[approval.approval_id] = approval
        return approval

    def claim(self, approval_id: str, idempotency_key: str) -> AppRemovalApproval:
        with self._lock:
            approval = self._items.get(approval_id)
            if approval is None:
                raise _approval_error("卸载 Approval 不存在或 Runtime 已重启")
            if self._clock() >= approval.expires_at_epoch:
                raise _approval_error("卸载 Approval 已过期")
            if approval.consumed_by_key not in {None, idempotency_key}:
                raise _approval_error("卸载 Approval 已被另一请求使用")
            if approval.consumed_by_key is None:
                approval = replace(approval, consumed_by_key=idempotency_key)
                self._items[approval_id] = approval
            return approval


@dataclass(frozen=True, slots=True)
class AppRemovalResult:
    skill_call_id: str
    device_id: str
    removed_app: InstalledApp
    data_retained: bool
    started_at: str
    completed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "skill_call_id": self.skill_call_id,
            "skill_id": "app.uninstall",
            "skill_version": "1.0.0",
            "device_id": self.device_id,
            "success": True,
            "status": "succeeded",
            "verification": "verified",
            "removed_app": self.removed_app.to_dict(),
            "data_retained": self.data_retained,
            "evidence_refs": [],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


def _approval_error(message: str) -> MobileAgentError:
    return MobileAgentError(
        "APPROVAL_INVALID",
        ErrorCategory.POLICY,
        message,
        suggested_action="重新执行卸载预检并展示新的影响摘要",
    )
