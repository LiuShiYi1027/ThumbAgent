"""Deterministic comparison of two aggregate performance snapshots."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError


class MetricTrend(str, Enum):
    """Direction after applying a metric-specific noise threshold."""

    INCREASED = "increased"
    DECREASED = "decreased"
    STABLE = "stable"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class MetricDelta:
    """A unit-preserving two-point delta without health judgement."""

    baseline_value: float | None
    candidate_value: float | None
    unit: str
    stable_threshold: float

    @property
    def delta(self) -> float | None:
        if self.baseline_value is None or self.candidate_value is None:
            return None
        return round(self.candidate_value - self.baseline_value, 4)

    @property
    def trend(self) -> MetricTrend:
        delta = self.delta
        if delta is None:
            return MetricTrend.UNAVAILABLE
        if delta > self.stable_threshold:
            return MetricTrend.INCREASED
        if delta < -self.stable_threshold:
            return MetricTrend.DECREASED
        return MetricTrend.STABLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_value": self.baseline_value,
            "candidate_value": self.candidate_value,
            "delta": self.delta,
            "unit": self.unit,
            "stable_threshold": self.stable_threshold,
            "trend": self.trend.value,
        }


@dataclass(frozen=True, slots=True)
class PerformanceSnapshotRef:
    """Minimal provenance for one snapshot used by a comparison."""

    task_id: str
    snapshot_id: str
    captured_at: str
    device_session_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "snapshot_id": self.snapshot_id,
            "captured_at": self.captured_at,
            "device_session_id": self.device_session_id,
        }


@dataclass(frozen=True, slots=True)
class DevicePerformanceComparison:
    """Structured comparison that explicitly remains a two-point estimate."""

    comparison_id: str
    device_id: str
    baseline: PerformanceSnapshotRef
    candidate: PerformanceSnapshotRef
    interval_seconds: float
    same_device_session: bool | None
    metrics: dict[str, MetricDelta]
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        grouped: dict[str, list[str]] = {
            trend.value: [] for trend in MetricTrend
        }
        for metric_id, metric in self.metrics.items():
            grouped[metric.trend.value].append(metric_id)
        return {
            "schema_version": self.schema_version,
            "comparison_id": self.comparison_id,
            "device_id": self.device_id,
            "baseline": self.baseline.to_dict(),
            "candidate": self.candidate.to_dict(),
            "interval_seconds": self.interval_seconds,
            "same_device_session": self.same_device_session,
            "method": {"kind": "two_point_delta", "single_point_samples": True},
            "metrics": {
                metric_id: metric.to_dict()
                for metric_id, metric in self.metrics.items()
            },
            "summary": grouped,
        }


def compare_performance_tasks(
    baseline_task: dict[str, Any], candidate_task: dict[str, Any]
) -> DevicePerformanceComparison:
    """Validate and compare two successful performance TaskRun dictionaries."""

    baseline_snapshot = _extract_snapshot(baseline_task, "baseline")
    candidate_snapshot = _extract_snapshot(candidate_task, "candidate")
    baseline_device = _required_string(baseline_task, "device_id")
    candidate_device = _required_string(candidate_task, "device_id")
    if baseline_device != candidate_device:
        raise _invalid("device_mismatch")

    baseline_time = _timestamp(_required_string(baseline_snapshot, "captured_at"))
    candidate_time = _timestamp(_required_string(candidate_snapshot, "captured_at"))
    interval = (candidate_time - baseline_time).total_seconds()
    if interval < 0:
        raise _invalid("candidate_precedes_baseline")

    baseline_session = _optional_string(baseline_task.get("device_session_id"))
    candidate_session = _optional_string(candidate_task.get("device_session_id"))
    same_session = (
        baseline_session == candidate_session
        if baseline_session is not None and candidate_session is not None
        else None
    )
    metrics = {
        "cpu_total_usage_percent": _metric(
            baseline_snapshot, candidate_snapshot, ("cpu", "total_usage_percent"),
            "percentage_points", 1.0
        ),
        "memory_used_percent": _metric(
            baseline_snapshot, candidate_snapshot, ("memory", "used_percent"),
            "percentage_points", 1.0
        ),
        "memory_free_bytes": _metric(
            baseline_snapshot, candidate_snapshot, ("memory", "free_bytes"),
            "bytes", float(16 * 1024 * 1024)
        ),
        "battery_level_percent": _metric(
            baseline_snapshot, candidate_snapshot, ("battery", "level_percent"),
            "percentage_points", 1.0
        ),
        "battery_temperature_celsius": _metric(
            baseline_snapshot, candidate_snapshot,
            ("battery", "temperature_celsius"), "celsius", 0.5, nullable=True
        ),
        "load_average_1m": _metric(
            baseline_snapshot, candidate_snapshot, ("system", "load_average_1m"),
            "load", 0.1
        ),
    }
    return DevicePerformanceComparison(
        comparison_id=f"perfcompare_{uuid.uuid4().hex}",
        device_id=baseline_device,
        baseline=_snapshot_ref(baseline_task, baseline_snapshot),
        candidate=_snapshot_ref(candidate_task, candidate_snapshot),
        interval_seconds=round(interval, 3),
        same_device_session=same_session,
        metrics=metrics,
    )


def _extract_snapshot(task: dict[str, Any], role: str) -> dict[str, Any]:
    if task.get("task_type") != "device.performance.snapshot":
        raise _invalid(f"{role}_task_type")
    if task.get("status") != "succeeded":
        raise _invalid(f"{role}_task_not_succeeded")
    steps = task.get("steps")
    if not isinstance(steps, list) or not steps:
        raise _invalid(f"{role}_snapshot_missing")
    result = steps[0].get("result") if isinstance(steps[0], dict) else None
    snapshot = result.get("snapshot") if isinstance(result, dict) else None
    if not isinstance(snapshot, dict):
        raise _invalid(f"{role}_snapshot_missing")
    return snapshot


def _snapshot_ref(
    task: dict[str, Any], snapshot: dict[str, Any]
) -> PerformanceSnapshotRef:
    return PerformanceSnapshotRef(
        task_id=_required_string(task, "task_id"),
        snapshot_id=_required_string(snapshot, "snapshot_id"),
        captured_at=_required_string(snapshot, "captured_at"),
        device_session_id=_optional_string(task.get("device_session_id")),
    )


def _metric(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    path: tuple[str, str],
    unit: str,
    threshold: float,
    *,
    nullable: bool = False,
) -> MetricDelta:
    baseline_value = _number_at(baseline, path, nullable=nullable)
    candidate_value = _number_at(candidate, path, nullable=nullable)
    return MetricDelta(baseline_value, candidate_value, unit, threshold)


def _number_at(
    value: dict[str, Any], path: tuple[str, str], *, nullable: bool
) -> float | None:
    parent = value.get(path[0])
    raw = parent.get(path[1]) if isinstance(parent, dict) else None
    if nullable and raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise _invalid("snapshot_shape_invalid")
    return float(raw)


def _required_string(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise _invalid("snapshot_shape_invalid")
    return result


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise _invalid("snapshot_timestamp_invalid") from error


def _invalid(reason: str) -> MobileAgentError:
    return MobileAgentError(
        code="INVALID_ARGUMENT",
        category=ErrorCategory.VALIDATION,
        message="性能快照无法比较",
        retryable=False,
        suggested_action="请选择同一设备上按时间顺序完成的两个性能快照任务",
        details={"reason": reason},
    )
