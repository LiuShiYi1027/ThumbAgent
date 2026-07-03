"""Action and Skill result contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from mobile_agent.domain.observation import Observation
from mobile_agent.ui.model import UiMatch


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PROHIBITED = "prohibited"


class Idempotency(str, Enum):
    SAFE = "safe"
    CONDITIONAL = "conditional"
    UNSAFE = "unsafe"


class ActionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN_OUTCOME = "unknown_outcome"
    REJECTED = "rejected"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    NOT_VERIFIED = "not_verified"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class ActionResult:
    action_id: str
    tool_id: str
    device_id: str
    status: ActionStatus
    verification: VerificationStatus
    started_at: str
    completed_at: str
    before: Observation
    after: Observation
    ui_match: UiMatch | None = None
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "action_id": self.action_id,
            "tool_id": self.tool_id,
            "device_id": self.device_id,
            "status": self.status.value,
            "verification": self.verification.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "ui_match": self.ui_match.to_dict() if self.ui_match else None,
        }


@dataclass(frozen=True, slots=True)
class SkillResult:
    skill_call_id: str
    skill_id: str
    skill_version: str
    success: bool
    status: ActionStatus
    started_at: str
    completed_at: str
    action: ActionResult
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "skill_call_id": self.skill_call_id,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "success": self.success,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "action": self.action.to_dict(),
        }
