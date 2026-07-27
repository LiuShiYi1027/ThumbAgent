"""Deterministic local.data.cleanup Skill."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from mobile_agent.domain.local_data import (
    LocalDataCleanupApproval,
    LocalDataCleanupResult,
)
from mobile_agent.tools.local_data import LocalDataTool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class LocalDataCleanupSkill:
    """Delete exactly the Artifact set bound to one claimed Approval."""

    skill_id = "local.data.cleanup"
    version = "1.0.0"

    def __init__(self, tool: LocalDataTool) -> None:
        self._tool = tool

    async def invoke(
        self,
        approval: LocalDataCleanupApproval,
        confirmed: bool,
        cancellation_requested: Callable[[], bool] | None = None,
        deadline_exceeded: Callable[[], bool] | None = None,
    ) -> LocalDataCleanupResult:
        started_at = _now()
        deleted, deleted_bytes = self._tool.cleanup(
            approval,
            confirmed,
            cancellation_requested,
            deadline_exceeded,
        )
        return LocalDataCleanupResult(
            f"skillcall_{uuid.uuid4().hex}",
            approval.retention_days,
            approval.cutoff_at,
            deleted,
            deleted_bytes,
            started_at,
            _now(),
        )
