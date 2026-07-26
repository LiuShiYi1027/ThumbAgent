"""Deterministic one-click local diagnostic evidence bundle Skill."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from mobile_agent.domain.diagnostic_bundle import DiagnosticBundleResult
from mobile_agent.tools.diagnostic_bundle import DiagnosticBundleTool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class DiagnosticBundleSkill:
    skill_id = "device.diagnostics.bundle"
    version = "1.0.0"

    def __init__(self, tool: DiagnosticBundleTool) -> None:
        self._tool = tool

    async def invoke(
        self,
        device_id: str,
        app_id: str | None,
        max_log_lines: int,
        minimum_log_level: str,
        confirmed: bool,
    ) -> DiagnosticBundleResult:
        started_at = _now()
        (
            foreground,
            app_state,
            log_summary,
            performance_summary,
            sources,
            bundle,
        ) = await self._tool.execute(
            device_id,
            app_id,
            max_log_lines,
            minimum_log_level,
            confirmed,
        )
        return DiagnosticBundleResult(
            f"skillcall_{uuid.uuid4().hex}",
            device_id,
            foreground,
            app_state,
            log_summary,
            performance_summary,
            sources,
            bundle,
            started_at,
            _now(),
        )
