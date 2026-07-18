"""Public value objects for bounded device log capture."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from mobile_agent.domain.artifact import Artifact


class DeviceLogLevel(str, Enum):
    """Portable minimum severity accepted by the V1 log capture Skill."""

    VERBOSE = "verbose"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


@dataclass(frozen=True, slots=True)
class DeviceLogCaptureResult:
    """Verified public result; raw device output is only exposed as an Artifact."""

    skill_call_id: str
    device_id: str
    minimum_level: DeviceLogLevel
    requested_max_lines: int
    captured_bytes: int
    truncated: bool
    redaction_count: int
    artifact: Artifact
    started_at: str
    completed_at: str
    schema_version: str = "1.0.0"
    skill_id: str = "device.logs.collect"
    skill_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "skill_call_id": self.skill_call_id,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "device_id": self.device_id,
            "success": True,
            "status": "succeeded",
            "verification": "verified",
            "source": "android_logcat",
            "minimum_level": self.minimum_level.value,
            "requested_max_lines": self.requested_max_lines,
            "captured_bytes": self.captured_bytes,
            "truncated": self.truncated,
            "redaction_count": self.redaction_count,
            "evidence_refs": [self.artifact.artifact_id],
            "artifact": self.artifact.to_dict(),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }
