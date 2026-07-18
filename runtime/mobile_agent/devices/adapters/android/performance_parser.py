"""Parse aggregate Android diagnostics while discarding process-level details."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.performance import DevicePerformanceSnapshot


_CPU_TOTAL = re.compile(r"(?im)^\s*([0-9]+(?:\.[0-9]+)?)%\s+TOTAL:")
_TOTAL_RAM = re.compile(r"(?im)^\s*Total RAM:\s*([0-9,]+)K\b")
_FREE_RAM = re.compile(r"(?im)^\s*Free RAM:\s*([0-9,]+)K\b")
_BATTERY_FIELD = re.compile(
    r"(?m)^\s*(level|scale|temperature|status|plugged):\s*(-?[0-9]+)\s*$"
)


def parse_performance_snapshot(
    device_id: str,
    cpuinfo: str,
    meminfo: str,
    battery: str,
    uptime: str,
    loadavg: str,
) -> DevicePerformanceSnapshot:
    """Return only aggregate values or fail without exposing raw diagnostic output."""

    try:
        cpu_matches = _CPU_TOTAL.findall(cpuinfo)
        if not cpu_matches:
            raise ValueError("cpu total")
        cpu_total = float(cpu_matches[-1])

        total_match = _TOTAL_RAM.search(meminfo)
        free_match = _FREE_RAM.search(meminfo)
        if total_match is None or free_match is None:
            raise ValueError("memory summary")
        total_bytes = int(total_match.group(1).replace(",", "")) * 1024
        free_bytes = int(free_match.group(1).replace(",", "")) * 1024
        if total_bytes <= 0 or free_bytes < 0 or free_bytes > total_bytes:
            raise ValueError("memory range")

        battery_fields = {
            key: int(value) for key, value in _BATTERY_FIELD.findall(battery)
        }
        level = battery_fields["level"]
        scale = battery_fields["scale"]
        if scale <= 0:
            raise ValueError("battery scale")
        level_percent = round(level * 100 / scale, 2)
        if level_percent < 0 or level_percent > 100:
            raise ValueError("battery level")
        temperature_raw = battery_fields.get("temperature")
        temperature = (
            round(temperature_raw / 10, 1)
            if temperature_raw is not None
            else None
        )
        if temperature is not None and not -100 <= temperature <= 200:
            raise ValueError("battery temperature")

        uptime_fields = uptime.split()
        load_fields = loadavg.split()
        if not uptime_fields or len(load_fields) < 3:
            raise ValueError("system metrics")
        uptime_seconds = float(uptime_fields[0])
        load_1m, load_5m, load_15m = (float(value) for value in load_fields[:3])
        if uptime_seconds < 0 or min(load_1m, load_5m, load_15m) < 0:
            raise ValueError("system range")
        if cpu_total < 0 or cpu_total > 100:
            raise ValueError("cpu range")
    except (KeyError, ValueError, OverflowError) as error:
        raise MobileAgentError(
            code="PERFORMANCE_SNAPSHOT_FAILED",
            category=ErrorCategory.DEVICE,
            message="无法解析设备聚合性能指标",
            retryable=True,
            suggested_action="确认设备在线并稍后重试",
        ) from error

    return DevicePerformanceSnapshot(
        snapshot_id=f"perf_{uuid.uuid4().hex}",
        device_id=device_id,
        captured_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        cpu_total_usage_percent=round(cpu_total, 2),
        memory_total_bytes=total_bytes,
        memory_free_bytes=free_bytes,
        battery_level_percent=level_percent,
        battery_temperature_celsius=temperature,
        battery_status={
            2: "charging",
            3: "discharging",
            4: "not_charging",
            5: "full",
        }.get(battery_fields.get("status", 1), "unknown"),
        battery_plugged={
            0: "none",
            1: "ac",
            2: "usb",
            4: "wireless",
            8: "dock",
        }.get(battery_fields.get("plugged", -1), "unknown"),
        uptime_seconds=round(uptime_seconds, 2),
        load_average_1m=load_1m,
        load_average_5m=load_5m,
        load_average_15m=load_15m,
    )
