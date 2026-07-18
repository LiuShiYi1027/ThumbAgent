"""Compare two stored aggregate performance snapshot tasks."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def render_comparison(comparison: dict[str, Any]) -> str:
    """Render direction and delta without interpreting them as regressions."""

    metrics = comparison.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    lines = [
        "Mobile Agent Performance Comparison",
        "===================================",
        f"Device:    {comparison.get('device_id', '-')}",
        f"Baseline:  {(comparison.get('baseline') or {}).get('task_id', '-')}",
        f"Candidate: {(comparison.get('candidate') or {}).get('task_id', '-')}",
        f"Interval:  {comparison.get('interval_seconds', '-')} seconds",
        f"Session:   {_session_label(comparison.get('same_device_session'))}",
        "",
    ]
    labels = (
        ("cpu_total_usage_percent", "CPU total"),
        ("memory_used_percent", "Memory used"),
        ("memory_free_bytes", "Memory free"),
        ("battery_level_percent", "Battery level"),
        ("battery_temperature_celsius", "Battery temp"),
        ("load_average_1m", "Load average 1m"),
    )
    for metric_id, label in labels:
        metric = metrics.get(metric_id)
        metric = metric if isinstance(metric, dict) else {}
        lines.append(
            f"{label:<16} {metric.get('baseline_value', '-')} -> "
            f"{metric.get('candidate_value', '-')} "
            f"(delta {metric.get('delta', '-')}, {metric.get('trend', '-')}, "
            f"{metric.get('unit', '-')})"
        )
    lines.extend(("", "Note: two point samples show direction, not causality or regression.", ""))
    return "\n".join(lines)


def _session_label(value: object) -> str:
    if value is True:
        return "same device session"
    if value is False:
        return "different device sessions"
    return "session unavailable"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare two completed performance snapshot tasks"
    )
    parser.add_argument("baseline_task_id")
    parser.add_argument("candidate_task_id")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--token", default="", help="Local API bearer token")
    args = parser.parse_args(argv)
    if not args.token:
        parser.error("--token is required for this local API request")
    request = Request(
        f"{args.base_url.rstrip('/')}/v1/performance-comparisons",
        data=json.dumps(
            {
                "baseline_task_id": args.baseline_task_id,
                "candidate_task_id": args.candidate_task_id,
            }
        ).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {args.token}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        comparison = payload["comparison"]
        if not isinstance(comparison, dict):
            raise ValueError("invalid comparison shape")
    except (KeyError, TypeError, ValueError, HTTPError, URLError) as error:
        print(f"failed to compare device performance: {error}", file=sys.stderr)
        return 1
    print(render_comparison(comparison), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
