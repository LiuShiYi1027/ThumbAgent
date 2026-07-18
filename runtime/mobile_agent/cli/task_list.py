"""Render recent Mobile Agent tasks."""

from __future__ import annotations

import argparse
import sys
from typing import Any
from urllib.error import HTTPError, URLError

from mobile_agent.cli.task_report import _fetch_json


def render_task_list(tasks: list[dict[str, Any]]) -> str:
    """Render recent task summaries as a compact terminal list."""

    lines = ["Recent Mobile Agent Tasks", "========================="]
    if not tasks:
        lines.append("(no tasks)")
        return "\n".join(lines) + "\n"
    lines.append("completed_at                 status     type                      task_id")
    lines.append("------------                 ------     ----                      -------")
    for task in tasks:
        completed_at = _short(str(task.get("completed_at", "-")), 27)
        status = _short(str(task.get("status", "-")), 10)
        task_type = _short(str(task.get("task_type", "-")), 25)
        task_id = str(task.get("task_id", "-"))
        lines.append(f"{completed_at:<27} {status:<10} {task_type:<25} {task_id}")
        goal = task.get("goal")
        if isinstance(goal, str) and goal:
            lines.append(f"  goal: {_short(goal, 100)}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List recent Mobile Agent tasks")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--token", default="", help="Optional local API bearer token")
    parser.add_argument("--limit", default=20, type=int)
    args = parser.parse_args(argv)
    if args.limit < 1 or args.limit > 100:
        print("limit must be between 1 and 100", file=sys.stderr)
        return 2
    try:
        payload = _fetch_json(args.base_url, f"/v1/tasks?limit={args.limit}", args.token)
        tasks = payload["tasks"]
    except (KeyError, TypeError, ValueError, HTTPError, URLError) as error:
        print(f"failed to load task list: {error}", file=sys.stderr)
        return 1
    if not isinstance(tasks, list):
        print("failed to load task list: invalid response shape", file=sys.stderr)
        return 1
    print(render_task_list([task for task in tasks if isinstance(task, dict)]), end="")
    return 0


def _short(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "…"


if __name__ == "__main__":
    raise SystemExit(main())
