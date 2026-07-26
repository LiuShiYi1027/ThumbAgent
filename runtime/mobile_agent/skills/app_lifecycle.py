"""Deterministic application lifecycle Skills."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from mobile_agent.domain.app_lifecycle import (
    AppDataClearApproval,
    AppLifecycleResult,
    AppRuntimeState,
)
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.skills.open_app import OpenAppSkill
from mobile_agent.tools.app_lifecycle import AppLifecycleTool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AppStateInspectSkill:
    skill_id = "app.state.inspect"
    version = "1.0.0"

    def __init__(self, tool: AppLifecycleTool) -> None:
        self._tool = tool

    async def invoke(self, device_id: str, app_id: str) -> AppRuntimeState:
        _, state = await self._tool.inspect(device_id, app_id)
        return state


class AppLaunchSkill:
    skill_id = "app.open"
    version = "1.0.0"

    def __init__(
        self, open_app: OpenAppSkill, lifecycle: AppLifecycleTool
    ) -> None:
        self._open_app = open_app
        self._lifecycle = lifecycle

    async def invoke(self, device_id: str, app_id: str) -> AppLifecycleResult:
        started_at = _now()
        result = await self._open_app.invoke(device_id, app_id)
        if not result.success:
            raise MobileAgentError(
                "APP_LAUNCH_NOT_VERIFIED",
                ErrorCategory.DEVICE,
                "应用启动后未进入前台",
            )
        app, state = await self._lifecycle.inspect(device_id, app_id)
        if not state.foreground:
            raise MobileAgentError(
                "APP_LAUNCH_NOT_VERIFIED",
                ErrorCategory.DEVICE,
                "应用启动后未能验证前台状态",
            )
        return AppLifecycleResult(
            f"skillcall_{uuid.uuid4().hex}",
            self.skill_id,
            device_id,
            "launch",
            app,
            state,
            None,
            started_at,
            _now(),
        )


class AppStopSkill:
    skill_id = "app.stop"
    version = "1.0.0"

    def __init__(self, tool: AppLifecycleTool) -> None:
        self._tool = tool

    async def invoke(
        self, device_id: str, app_id: str, confirmed: bool
    ) -> AppLifecycleResult:
        started_at = _now()
        app, state = await self._tool.stop(device_id, app_id, confirmed)
        return AppLifecycleResult(
            f"skillcall_{uuid.uuid4().hex}",
            self.skill_id,
            device_id,
            "stop",
            app,
            state,
            None,
            started_at,
            _now(),
        )


class AppDataClearSkill:
    skill_id = "app.data.clear"
    version = "1.0.0"

    def __init__(self, tool: AppLifecycleTool) -> None:
        self._tool = tool

    async def invoke(
        self, approval: AppDataClearApproval, confirmed: bool
    ) -> AppLifecycleResult:
        started_at = _now()
        app, state = await self._tool.clear_data(approval, confirmed)
        return AppLifecycleResult(
            f"skillcall_{uuid.uuid4().hex}",
            self.skill_id,
            approval.device_id,
            "clear_data",
            app,
            state,
            True,
            started_at,
            _now(),
        )
