"""Framework-independent domain contracts."""

from mobile_agent.domain.artifact import Artifact, ArtifactKind
from mobile_agent.domain.action import ActionResult, ActionStatus, RiskLevel, SkillResult
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.errors import ErrorCategory, ErrorOutcome, MobileAgentError
from mobile_agent.domain.observation import DeviceState, Observation, Orientation

__all__ = [
    "ConnectionState",
    "Artifact",
    "ArtifactKind",
    "ActionResult",
    "ActionStatus",
    "RiskLevel",
    "SkillResult",
    "Device",
    "ErrorCategory",
    "ErrorOutcome",
    "MobileAgentError",
    "DeviceState",
    "Observation",
    "Orientation",
    "Platform",
]
