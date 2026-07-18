"""Render one device's current capability inspection."""

from __future__ import annotations

import argparse
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote

from mobile_agent.cli.task_report import _fetch_json


def render_device_inspection(inspection: dict[str, Any]) -> str:
    """Render safe capability, policy and availability metadata."""

    availability = inspection.get("availability")
    availability = availability if isinstance(availability, dict) else {}
    device = availability.get("device")
    device = device if isinstance(device, dict) else {}
    lines = [
        "Mobile Agent Device Inspection",
        "==============================",
        f"Device:       {device.get('name') or device.get('device_id', '-')}",
        f"Device ID:    {device.get('device_id', '-')}",
        f"Platform:     {device.get('platform', '-')}",
        f"OS / Model:   {device.get('os_version', '-')} / {device.get('model', '-')}",
        f"Connection:   {device.get('connection', '-')}",
        f"Session:      {device.get('session_id') or '-'}",
        f"Availability: {availability.get('status', '-')}",
    ]
    owner = availability.get("lease_owner_id")
    if owner:
        lines.append(f"Lease owner:  {owner}")
    lines.extend(["", "Capabilities", "------------"])
    capabilities = inspection.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        lines.append("(no capability metadata)")
        return "\n".join(lines) + "\n"
    for capability in capabilities:
        if not isinstance(capability, dict):
            continue
        confirmation = " · confirmation required" if capability.get("confirmation_required") else ""
        lines.append(
            f"- {capability.get('capability', '-')} "
            f"[{capability.get('availability', '-')}] · risk={capability.get('risk', '-')}"
            f"{confirmation}"
        )
        tools = capability.get("tools")
        if isinstance(tools, list) and tools:
            lines.append(f"  tools: {', '.join(str(item) for item in tools)}")
        requirements = capability.get("requirements")
        if isinstance(requirements, list) and requirements:
            lines.append(f"  requires: {'; '.join(str(item) for item in requirements)}")
        limitations = capability.get("limitations")
        if isinstance(limitations, list) and limitations:
            lines.append(f"  limits: {'; '.join(str(item) for item in limitations)}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect one Mobile Agent device")
    parser.add_argument("device_id")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--token", default="", help="Optional local API bearer token")
    args = parser.parse_args(argv)
    try:
        payload = _fetch_json(
            args.base_url,
            f"/v1/devices/{quote(args.device_id, safe='')}/inspection",
            args.token,
        )
        inspection = payload["inspection"]
    except (KeyError, TypeError, ValueError, HTTPError, URLError) as error:
        print(f"failed to inspect device: {error}", file=sys.stderr)
        return 1
    if not isinstance(inspection, dict):
        print("failed to inspect device: invalid response shape", file=sys.stderr)
        return 1
    print(render_device_inspection(inspection), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
