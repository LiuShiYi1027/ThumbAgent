"""Deterministic app.install Skill."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from mobile_agent.domain.apk import ApkInstallApproval, ApkInstallResult
from mobile_agent.tools.apk_install import ApkInstallTool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ApkInstallSkill:
    skill_id = "app.install"
    version = "1.0.0"

    def __init__(self, tool: ApkInstallTool) -> None:
        self._tool = tool

    async def invoke(
        self, approval: ApkInstallApproval, confirmed: bool
    ) -> ApkInstallResult:
        started_at = _now()
        app = await self._tool.execute(approval, confirmed)
        return ApkInstallResult(
            f"skillcall_{uuid.uuid4().hex}",
            approval.device_id,
            app,
            approval.package.sha256,
            approval.package.size_bytes,
            approval.replace_existing,
            started_at,
            _now(),
        )
