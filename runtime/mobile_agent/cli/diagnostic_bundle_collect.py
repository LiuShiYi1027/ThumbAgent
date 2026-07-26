"""Submit a bounded local diagnostic evidence bundle through Runtime API."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mobile_agent.cli.device_logs_collect import render_submission


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Collect screenshot, UI tree, redacted logs and aggregate performance"
    )
    parser.add_argument("device_id")
    parser.add_argument("--app-id")
    parser.add_argument("--max-log-lines", type=int, default=500)
    parser.add_argument(
        "--minimum-log-level",
        choices=("verbose", "debug", "info", "warn", "error", "fatal"),
        default="info",
    )
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--deadline-seconds", type=float, default=120.0)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--token", default="")
    args = parser.parse_args(argv)
    if not args.confirm:
        parser.error(
            "--confirm is required because screenshot, UI tree and logs are captured"
        )
    if not args.token:
        parser.error("--token is required for this local API request")
    body: dict[str, object] = {
        "device_id": args.device_id,
        "max_log_lines": args.max_log_lines,
        "minimum_log_level": args.minimum_log_level,
        "confirmed": True,
        "deadline_seconds": args.deadline_seconds,
    }
    if args.app_id:
        body["app_id"] = args.app_id
    request = Request(
        f"{args.base_url.rstrip('/')}/v1/tasks/device.diagnostics.bundle/async",
        data=json.dumps(body).encode(),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {args.token}",
            "Idempotency-Key": f"cli-{uuid.uuid4()}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode())
        execution = payload["execution"]
        if not isinstance(execution, dict):
            raise ValueError("invalid execution shape")
    except (KeyError, TypeError, ValueError, HTTPError, URLError) as error:
        print(f"failed to submit diagnostic bundle: {error}", file=sys.stderr)
        return 1
    print(render_submission(execution), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
