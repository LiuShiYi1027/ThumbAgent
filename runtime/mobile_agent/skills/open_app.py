"""Deterministic app.open@1 Skill."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from mobile_agent.domain.action import ActionStatus, SkillResult, VerificationStatus
from mobile_agent.tools.runtime import ToolRuntime


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class OpenAppSkill:
    skill_id = "app.open"
    version = "1.0.0"

    def __init__(self, tools: ToolRuntime) -> None:
        self._tools = tools

    async def invoke(self, device_id: str, app_id: str) -> SkillResult:
        started_at = _now()
        action = await self._tools.execute(
            "app.launch", device_id, {"app_id": app_id}, confirmed=False
        )
        success = (
            action.status is ActionStatus.SUCCEEDED
            and action.verification is VerificationStatus.VERIFIED
        )
        return SkillResult(
            skill_call_id=f"skillcall_{uuid.uuid4().hex}",
            skill_id=self.skill_id,
            skill_version=self.version,
            success=success,
            status=action.status,
            started_at=started_at,
            completed_at=_now(),
            action=action,
        )
