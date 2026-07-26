"""Deterministic installed application inventory Skill."""

from __future__ import annotations

from mobile_agent.domain.app import AppInventory, InstalledApp
from mobile_agent.tools.app_inventory import AppInventoryTool


class AppListSkill:
    """List installed applications without changing device state."""

    skill_id = "app.list"
    version = "1.0.0"

    def __init__(self, tool: AppInventoryTool) -> None:
        self._tool = tool

    async def list(
        self, device_id: str, limit: int = 200, prefix: str | None = None
    ) -> AppInventory:
        return await self._tool.list(device_id, limit, prefix)


class AppInspectSkill:
    """Inspect one installed application without changing device state."""

    skill_id = "app.inspect"
    version = "1.0.0"

    def __init__(self, tool: AppInventoryTool) -> None:
        self._tool = tool

    async def invoke(self, device_id: str, app_id: str) -> InstalledApp:
        return await self._tool.inspect(device_id, app_id)
