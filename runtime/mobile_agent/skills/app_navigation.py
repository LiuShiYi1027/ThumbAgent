"""Deterministic app.navigate@1 Skill: one registered system page, verified."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from mobile_agent.domain.action import ActionStatus
from mobile_agent.domain.errors import ErrorCategory, ErrorOutcome, MobileAgentError
from mobile_agent.domain.navigation import (
    NAVIGATION_TARGETS,
    AppNavigationResult,
    parse_navigation_target,
)
from mobile_agent.tools.runtime import ToolRuntime


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AppNavigateSkill:
    """Navigate to an allowlisted system page through the registered Tool."""

    skill_id = "app.navigate"
    version = "1.0.0"

    def __init__(self, tools: ToolRuntime) -> None:
        self._tools = tools

    async def invoke(self, device_id: str, target: str) -> AppNavigationResult:
        parsed = parse_navigation_target(target)
        spec = NAVIGATION_TARGETS[parsed]
        started_at = _now()
        action = await self._tools.execute(
            "app.navigate", device_id, {"target": parsed.value}
        )
        if action.status is not ActionStatus.SUCCEEDED:
            raise MobileAgentError(
                code="NAVIGATION_NOT_VERIFIED",
                category=ErrorCategory.EXECUTION,
                message="导航执行后未到达目标系统页面",
                outcome=ErrorOutcome.UNKNOWN_OUTCOME,
                suggested_action="重新观察设备当前页面后人工确认",
                details={"target": parsed.value},
            )
        after = action.after
        evidence_refs = tuple(
            dict.fromkeys(
                (
                    after.screen.screenshot.artifact_id,
                    after.ui_tree.artifact.artifact_id,
                )
            )
        )
        return AppNavigationResult(
            skill_call_id=f"skillcall_{uuid.uuid4().hex}",
            device_id=device_id,
            target=parsed,
            label=spec.label,
            foreground_app_id=after.foreground_app.app_id,
            foreground_activity=after.foreground_app.activity,
            evidence_refs=evidence_refs,
            started_at=started_at,
            completed_at=_now(),
        )
