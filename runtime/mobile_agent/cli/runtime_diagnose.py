"""Render Runtime and device readiness for terminal users."""

from __future__ import annotations

import argparse
import sys
from typing import Any
from urllib.error import HTTPError, URLError

from mobile_agent.cli.task_report import _fetch_json


def render_runtime_readiness(readiness: dict[str, Any]) -> str:
    """Render one public RuntimeReadiness snapshot without raw driver output."""

    gateway = readiness.get("gateway")
    gateway = gateway if isinstance(gateway, dict) else {}
    summary = readiness.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    lines = [
        "Mobile Agent Readiness",
        "======================",
        f"Status:  {readiness.get('status', '-')}",
        (
            "Gateway: "
            f"{gateway.get('platform', '-')} / {gateway.get('transport', '-')} "
            f"[{gateway.get('status', '-')}]"
        ),
        (
            "Devices: "
            f"{summary.get('total', 0)} total, {summary.get('ready', 0)} ready, "
            f"{summary.get('busy', 0)} busy, {summary.get('attention', 0)} attention"
        ),
    ]
    issues = readiness.get("issues")
    if isinstance(issues, list):
        for issue in issues:
            if isinstance(issue, dict):
                lines.extend(_issue_lines(issue, prefix="Runtime"))
    gateway_issue = gateway.get("issue")
    if isinstance(gateway_issue, dict) and gateway_issue not in (issues or []):
        lines.extend(_issue_lines(gateway_issue, prefix="Gateway"))
    lines.extend(["", "Device availability", "-------------------"])
    devices = readiness.get("devices")
    if not isinstance(devices, list) or not devices:
        lines.append("(no devices)")
        return "\n".join(lines) + "\n"
    for availability in devices:
        if not isinstance(availability, dict):
            continue
        device = availability.get("device")
        device = device if isinstance(device, dict) else {}
        lines.append(
            f"- [{availability.get('status', '-')}] "
            f"{device.get('name') or device.get('device_id', '-')} "
            f"({device.get('device_id', '-')})"
        )
        lines.append(
            f"  connection={device.get('connection', '-')} "
            f"session={device.get('session_id') or '-'}"
        )
        owner = availability.get("lease_owner_id")
        if owner:
            lines.append(f"  lease_owner={owner}")
        device_issues = availability.get("issues")
        if isinstance(device_issues, list):
            for issue in device_issues:
                if isinstance(issue, dict):
                    lines.extend(_issue_lines(issue, prefix="  Issue"))
    return "\n".join(lines) + "\n"


def _issue_lines(issue: dict[str, Any], prefix: str) -> list[str]:
    lines = [f"{prefix}: {issue.get('code', '-')} · {issue.get('message', '-')}"]
    action = issue.get("suggested_action")
    if isinstance(action, str) and action:
        lines.append(f"  Next: {action}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose Mobile Agent readiness")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--token", default="", help="Optional local API bearer token")
    args = parser.parse_args(argv)
    try:
        payload = _fetch_json(args.base_url, "/v1/readiness", args.token)
        readiness = payload["readiness"]
    except (KeyError, TypeError, ValueError, HTTPError, URLError) as error:
        print(f"failed to load Runtime readiness: {error}", file=sys.stderr)
        return 1
    if not isinstance(readiness, dict):
        print("failed to load Runtime readiness: invalid response shape", file=sys.stderr)
        return 1
    print(render_runtime_readiness(readiness), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
