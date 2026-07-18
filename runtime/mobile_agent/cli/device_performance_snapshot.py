"""Capture aggregate device performance through the local Runtime API."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mobile_agent.cli.device_logs_collect import render_submission


def render_result(result: dict[str, Any]) -> str:
    """Render aggregate metrics and Artifact metadata without raw diagnostics."""

    snapshot = result.get("snapshot")
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    cpu = snapshot.get("cpu") if isinstance(snapshot.get("cpu"), dict) else {}
    memory = (
        snapshot.get("memory") if isinstance(snapshot.get("memory"), dict) else {}
    )
    battery = (
        snapshot.get("battery") if isinstance(snapshot.get("battery"), dict) else {}
    )
    system = (
        snapshot.get("system") if isinstance(snapshot.get("system"), dict) else {}
    )
    artifact = result.get("artifact")
    artifact = artifact if isinstance(artifact, dict) else {}
    return "\n".join(
        (
            "Mobile Agent Performance Snapshot",
            "=================================",
            f"Device:       {result.get('device_id', '-')}",
            f"CPU total:    {cpu.get('total_usage_percent', '-')}%",
            f"Memory used:  {memory.get('used_percent', '-')}%",
            f"Battery:      {battery.get('level_percent', '-')}% / {battery.get('temperature_celsius', '-')} C",
            f"Load average: {system.get('load_average_1m', '-')} / {system.get('load_average_5m', '-')} / {system.get('load_average_15m', '-')}",
            f"Uptime:       {system.get('uptime_seconds', '-')} seconds",
            f"Artifact:     {artifact.get('artifact_id', '-')}",
            f"Local path:   {artifact.get('relative_path', '-')}",
            "",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture aggregate device performance")
    parser.add_argument("device_id")
    parser.add_argument("--async-task", action="store_true")
    parser.add_argument("--deadline-seconds", type=float, default=90.0)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--token", default="", help="Local API bearer token")
    args = parser.parse_args(argv)
    if not args.token:
        parser.error("--token is required for this local API request")
    body: dict[str, object] = {"device_id": args.device_id}
    endpoint = "/v1/skills/device.performance.snapshot/invoke"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {args.token}",
    }
    if args.async_task:
        endpoint = "/v1/tasks/device.performance.snapshot/async"
        body["deadline_seconds"] = args.deadline_seconds
        headers["Idempotency-Key"] = f"cli-{uuid.uuid4()}"
    request = Request(
        f"{args.base_url.rstrip('/')}{endpoint}",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
        key = "execution" if args.async_task else "result"
        result = payload[key]
        if not isinstance(result, dict):
            raise ValueError(f"invalid {key} shape")
    except (KeyError, TypeError, ValueError, HTTPError, URLError) as error:
        print(f"failed to capture device performance: {error}", file=sys.stderr)
        return 1
    print(render_submission(result) if args.async_task else render_result(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
