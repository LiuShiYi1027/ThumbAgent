"""Prepare a read-only scoped local Artifact cleanup approval."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview expired local Artifacts without deleting them"
    )
    parser.add_argument("--retention-days", type=int, default=7)
    parser.add_argument("--max-artifacts", type=int, default=500)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--token", required=True)
    args = parser.parse_args(argv)
    request = Request(
        f"{args.base_url.rstrip('/')}/v1/storage/cleanup/prepare",
        data=json.dumps(
            {
                "retention_days": args.retention_days,
                "max_artifacts": args.max_artifacts,
            }
        ).encode(),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {args.token}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            approval = json.loads(response.read().decode())["approval"]
    except (KeyError, TypeError, ValueError, HTTPError, URLError) as error:
        print(f"failed to prepare local cleanup: {error}", file=sys.stderr)
        return 1
    print(
        f"Approval:  {approval['approval_id']}\n"
        f"Candidates:{approval['candidate_count']} / "
        f"{approval['candidate_bytes']} bytes\n"
        f"Cutoff:    {approval['cutoff_at']}\n"
        f"Truncated: {approval['truncated']}\n"
        f"Expires:   {approval['expires_at']}\n"
        "No files were deleted."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
