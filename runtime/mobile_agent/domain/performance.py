"""Aggregate, privacy-minimized device performance value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mobile_agent.domain.artifact import Artifact


@dataclass(frozen=True, slots=True)
class DevicePerformanceSnapshot:
    """A single aggregate sample with no process or application details."""

    snapshot_id: str
    device_id: str
    captured_at: str
    cpu_total_usage_percent: float
    memory_total_bytes: int
    memory_free_bytes: int
    battery_level_percent: float
    battery_temperature_celsius: float | None
    battery_status: str
    battery_plugged: str
    uptime_seconds: float
    load_average_1m: float
    load_average_5m: float
    load_average_15m: float
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        used_percent = round(
            (self.memory_total_bytes - self.memory_free_bytes)
            * 100
            / self.memory_total_bytes,
            2,
        )
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "device_id": self.device_id,
            "captured_at": self.captured_at,
            "cpu": {"total_usage_percent": self.cpu_total_usage_percent},
            "memory": {
                "total_bytes": self.memory_total_bytes,
                "free_bytes": self.memory_free_bytes,
                "used_percent": used_percent,
            },
            "battery": {
                "level_percent": self.battery_level_percent,
                "temperature_celsius": self.battery_temperature_celsius,
                "status": self.battery_status,
                "plugged": self.battery_plugged,
            },
            "system": {
                "uptime_seconds": self.uptime_seconds,
                "load_average_1m": self.load_average_1m,
                "load_average_5m": self.load_average_5m,
                "load_average_15m": self.load_average_15m,
            },
        }


@dataclass(frozen=True, slots=True)
class DevicePerformanceSnapshotResult:
    """Verified Skill output with a structured snapshot and local Artifact."""

    skill_call_id: str
    device_id: str
    snapshot: DevicePerformanceSnapshot
    artifact: Artifact
    started_at: str
    completed_at: str
    schema_version: str = "1.0.0"
    skill_id: str = "device.performance.snapshot"
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
            "snapshot": self.snapshot.to_dict(),
            "evidence_refs": [self.artifact.artifact_id],
            "artifact": self.artifact.to_dict(),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }
