"""Deterministic app.uninstall Skill."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from mobile_agent.domain.app_removal import AppRemovalApproval, AppRemovalResult
from mobile_agent.tools.app_removal import AppRemovalTool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AppRemovalSkill:
    skill_id = "app.uninstall"
    version = "1.0.0"

    def __init__(self, tool: AppRemovalTool) -> None:
        self._tool = tool

    async def invoke(
        self, approval: AppRemovalApproval, confirmed: bool
    ) -> AppRemovalResult:
        started_at = _now()
        await self._tool.execute(approval, confirmed)
        return AppRemovalResult(
            f"skillcall_{uuid.uuid4().hex}",
            approval.device_id,
            approval.app,
            approval.keep_data,
            started_at,
            _now(),
        )
