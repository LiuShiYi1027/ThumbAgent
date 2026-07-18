"""Collect a bounded, redacted device log Artifact through the local API."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def render_result(result: dict[str, Any]) -> str:
    """Render metadata only; never print captured device log content."""

    artifact = result.get("artifact")
    artifact = artifact if isinstance(artifact, dict) else {}
    return "\n".join(
        (
            "Mobile Agent Device Log Capture",
            "===============================",
            f"Device:      {result.get('device_id', '-')}",
            f"Status:      {result.get('status', '-')}",
            f"Level:       {result.get('minimum_level', '-')}",
            f"Bytes:       {result.get('captured_bytes', '-')}",
            f"Truncated:   {result.get('truncated', '-')}",
            f"Redactions:  {result.get('redaction_count', '-')}",
            f"Artifact:    {artifact.get('artifact_id', '-')}",
            f"Local path:  {artifact.get('relative_path', '-')}",
            "",
        )
    )


def render_submission(execution: dict[str, Any]) -> str:
    """Render an asynchronous submission without waiting for device I/O."""

    return "\n".join(
        (
            "Mobile Agent Device Log Task",
            "============================",
            f"Task:         {execution.get('task_id', '-')}",
            f"Type:         {execution.get('task_type', '-')}",
            f"Status:       {execution.get('status', '-')}",
            f"Device:       {execution.get('device_id', '-')}",
            f"Deadline:     {execution.get('deadline_seconds', '-')} seconds",
            "Use task_report after completion or the task-execution API for live status.",
            "",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect a bounded device log snapshot")
    parser.add_argument("device_id")
    parser.add_argument("--max-lines", type=int, default=500)
    parser.add_argument(
        "--minimum-level",
        choices=("verbose", "debug", "info", "warn", "error", "fatal"),
        default="info",
    )
    parser.add_argument("--confirm", action="store_true", help="Confirm sensitive log capture")
    parser.add_argument(
        "--async-task",
        action="store_true",
        help="Submit a cancellable task and return its task_id immediately",
    )
    parser.add_argument("--deadline-seconds", type=float, default=60.0)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--token", default="", help="Local API bearer token")
    args = parser.parse_args(argv)
    if not args.confirm:
        parser.error("--confirm is required because device logs may contain sensitive data")
    if not args.token:
        parser.error("--token is required for this mutating local API request")
    request_body = {
        "device_id": args.device_id,
        "max_lines": args.max_lines,
        "minimum_level": args.minimum_level,
        "confirmed": True,
    }
    if args.async_task:
        request_body["deadline_seconds"] = args.deadline_seconds
    body = json.dumps(request_body).encode("utf-8")
    endpoint = (
        "/v1/tasks/device.logs.collect/async"
        if args.async_task
        else "/v1/skills/device.logs.collect/invoke"
    )
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {args.token}",
    }
    if args.async_task:
        headers["Idempotency-Key"] = f"cli-{uuid.uuid4()}"
    request = Request(
        f"{args.base_url.rstrip('/')}{endpoint}",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        key = "execution" if args.async_task else "result"
        result = payload[key]
        if not isinstance(result, dict):
            raise ValueError(f"invalid {key} shape")
    except (KeyError, TypeError, ValueError, HTTPError, URLError) as error:
        print(f"failed to collect device logs: {error}", file=sys.stderr)
        return 1
    print(render_submission(result) if args.async_task else render_result(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
