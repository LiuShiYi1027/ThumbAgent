"""Public contracts for one bounded local diagnostic evidence bundle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mobile_agent.domain.app_lifecycle import AppRuntimeState
from mobile_agent.domain.artifact import Artifact


@dataclass(frozen=True, slots=True)
class DiagnosticBundleResult:
    """Verified result containing metadata only, never inline evidence content."""

    skill_call_id: str
    device_id: str
    foreground_app: dict[str, Any]
    app_state: AppRuntimeState | None
    log_summary: dict[str, Any]
    performance_summary: dict[str, Any]
    source_artifacts: tuple[Artifact, ...]
    bundle_artifact: Artifact
    started_at: str
    completed_at: str

    def to_dict(self) -> dict[str, Any]:
        evidence = (*self.source_artifacts, self.bundle_artifact)
        return {
            "schema_version": "1.0.0",
            "skill_call_id": self.skill_call_id,
            "skill_id": "device.diagnostics.bundle",
            "skill_version": "1.0.0",
            "device_id": self.device_id,
            "success": True,
            "status": "succeeded",
            "verification": "verified",
            "app_state": self.app_state.to_dict() if self.app_state else None,
            "foreground_app": dict(self.foreground_app),
            "log_summary": dict(self.log_summary),
            "performance_summary": dict(self.performance_summary),
            "source_artifacts": [
                artifact.to_dict() for artifact in self.source_artifacts
            ],
            "bundle_artifact": self.bundle_artifact.to_dict(),
            "evidence_refs": [artifact.artifact_id for artifact in evidence],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }
