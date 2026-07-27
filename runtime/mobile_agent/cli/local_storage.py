"""Show aggregate local Artifact storage without reading content."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect local Artifact storage")
    parser.add_argument("--retention-days", type=int, default=7)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    args = parser.parse_args(argv)
    request = Request(
        f"{args.base_url.rstrip('/')}/v1/storage?"
        f"{urlencode({'retention_days': args.retention_days})}",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            storage = json.loads(response.read().decode())["storage"]
    except (KeyError, TypeError, ValueError, HTTPError, URLError) as error:
        print(f"failed to inspect local storage: {error}", file=sys.stderr)
        return 1
    print(
        f"Artifacts: {storage['total_count']} / {storage['total_bytes']} bytes\n"
        f"Expired:   {storage['expired_count']} / {storage['expired_bytes']} bytes\n"
        f"Retention: {storage['retention_days']} days\n"
        f"Oldest:    {storage.get('oldest_created_at') or '-'}\n"
        f"Newest:    {storage.get('newest_created_at') or '-'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
