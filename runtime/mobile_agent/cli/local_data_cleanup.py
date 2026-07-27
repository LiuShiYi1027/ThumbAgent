"""Submit one explicitly confirmed local Artifact cleanup task."""

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
        description="Permanently delete one approved expired Artifact set"
    )
    parser.add_argument("approval_id")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--deadline-seconds", type=float, default=120)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--token", required=True)
    args = parser.parse_args(argv)
    if not args.confirm:
        parser.error("--confirm is required for permanent local data deletion")
    request = Request(
        f"{args.base_url.rstrip('/')}/v1/tasks/local.data.cleanup/async",
        data=json.dumps(
            {
                "approval_id": args.approval_id,
                "confirmed": True,
                "deadline_seconds": args.deadline_seconds,
            }
        ).encode(),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {args.token}",
            "Idempotency-Key": f"cli-{uuid.uuid4().hex}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            execution = json.loads(response.read().decode())["execution"]
    except (KeyError, TypeError, ValueError, HTTPError, URLError) as error:
        print(f"failed to submit local cleanup: {error}", file=sys.stderr)
        return 1
    print(render_submission(execution), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
