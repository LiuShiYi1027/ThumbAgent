"""Parsers for bounded ADB command output."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from mobile_agent.domain.device import ConnectionState


@dataclass(frozen=True, slots=True)
class AdbDeviceRecord:
    serial: str
    connection: ConnectionState
    properties: dict[str, str] = field(default_factory=dict)


def parse_adb_devices(output: str) -> list[AdbDeviceRecord]:
    """Parse `adb devices -l`, ignoring daemon noise and malformed lines."""

    records: list[AdbDeviceRecord] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices attached") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, raw_state = parts[0], parts[1]
        state = {
            "device": ConnectionState.ONLINE,
            "offline": ConnectionState.OFFLINE,
            "unauthorized": ConnectionState.UNAUTHORIZED,
        }.get(raw_state, ConnectionState.UNKNOWN)
        properties: dict[str, str] = {}
        for token in parts[2:]:
            if ":" not in token:
                continue
            key, value = token.split(":", 1)
            if key and value:
                properties[key] = value
        records.append(AdbDeviceRecord(serial, state, properties))
    return records


def parse_foreground_app(output: str) -> tuple[str, str]:
    """Extract package and activity from supported dumpsys window/activity formats."""

    patterns = (
        r"mCurrentFocus=.*?\s([A-Za-z0-9._]+)/(\.?[A-Za-z0-9.$_]+)",
        r"mFocusedApp=.*?\s([A-Za-z0-9._]+)/(\.?[A-Za-z0-9.$_]+)",
        r"topResumedActivity=.*?\s([A-Za-z0-9._]+)/(\.?[A-Za-z0-9.$_]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            return match.group(1), match.group(2)
    return "", ""


def extract_ui_xml(output: bytes) -> bytes:
    """Extract the XML document from UIAutomator stdout noise."""

    start = output.find(b"<?xml")
    end_marker = b"</hierarchy>"
    end = output.rfind(end_marker)
    if start < 0 or end < start:
        return b""
    return output[start : end + len(end_marker)]
