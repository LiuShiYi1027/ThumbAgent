"""Safe deterministic navigation within Android Settings."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from mobile_agent.domain.action import (
    ActionResult,
    ActionStatus,
    SkillResult,
    VerificationStatus,
)
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.observation import Observation
from mobile_agent.skills.open_app import OpenAppSkill
from mobile_agent.tools.runtime import ToolRuntime
from mobile_agent.ui.model import UiNode


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class NavigationResult:
    skill_call_id: str
    started_at: str
    completed_at: str
    open_app: SkillResult
    tap_action: ActionResult
    verified_observation: Observation
    verified_node: UiNode
    skill_id: str = "settings.navigate"
    skill_version: str = "1.0.0"
    success: bool = True
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "skill_call_id": self.skill_call_id,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "success": self.success,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "open_app": self.open_app.to_dict(),
            "tap_action": self.tap_action.to_dict(),
            "verified_observation": self.verified_observation.to_dict(),
            "verified_node": self.verified_node.to_dict(),
        }


class SettingsNavigateSkill:
    skill_id = "settings.navigate"
    version = "1.0.0"

    def __init__(self, tools: ToolRuntime, open_app: OpenAppSkill) -> None:
        self._tools = tools
        self._open_app = open_app

    async def invoke(
        self,
        device_id: str,
        target_selector: dict[str, Any],
        expected_selector: dict[str, Any],
        confirmed: bool = False,
    ) -> NavigationResult:
        started_at = _now()
        opened = await self._open_app.invoke(device_id, "com.android.settings")
        if (
            not opened.success
            or opened.status is not ActionStatus.SUCCEEDED
            or opened.action.verification is not VerificationStatus.VERIFIED
            or opened.action.after.foreground_app.app_id != "com.android.settings"
        ):
            raise MobileAgentError(
                code="APP_OPEN_FAILED",
                category=ErrorCategory.EXECUTION,
                message="无法确认系统设置已打开",
            )
        safe_target = self._settings_selector(target_selector)
        safe_expected = self._settings_selector(expected_selector)
        await self._tools.wait_for_element(device_id, safe_target)
        tap_action = await self._tools.execute(
            "input.tap_element",
            device_id,
            {"selector": safe_target},
            confirmed=confirmed,
        )
        verified_observation, verified_node = await self._tools.wait_for_element(
            device_id, safe_expected
        )
        return NavigationResult(
            skill_call_id=f"skillcall_{uuid.uuid4().hex}",
            started_at=started_at,
            completed_at=_now(),
            open_app=opened,
            tap_action=tap_action,
            verified_observation=verified_observation,
            verified_node=verified_node,
        )

    @staticmethod
    def _settings_selector(selector: dict[str, Any]) -> dict[str, Any]:
        existing = selector.get("package")
        if existing is not None and existing != "com.android.settings":
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="设置导航 Selector 不能指向其他应用",
            )
        return {**selector, "package": "com.android.settings"}
