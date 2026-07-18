"""Evaluate a stored live Agent task against a versioned scenario."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def render_evaluation_result(result: dict[str, Any]) -> str:
    """Render a compact terminal summary for one Agent evaluation."""

    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    failure_reasons = result.get("failure_reasons")
    if not isinstance(failure_reasons, list):
        failure_reasons = []
    used_tools = metrics.get("used_tools")
    if not isinstance(used_tools, list):
        used_tools = []
    lines = [
        "Mobile Agent Evaluation",
        "=======================",
        f"Scenario: {result.get('scenario_id', '-')}",
        f"Task:     {result.get('task_id', '-')}",
        f"Result:   {'PASSED' if result.get('passed') is True else 'FAILED'}",
        f"Rounds:   {metrics.get('round_count', 0)}",
        f"Tools:    {metrics.get('tool_call_count', 0)} ({', '.join(str(item) for item in used_tools) or '-'})",
        f"Progress: changed={metrics.get('changed_action_count', 0)}, unchanged={metrics.get('unchanged_action_count', 0)}",
        f"Repairs:  {metrics.get('model_repair_count', 0)}",
        f"Duration: {metrics.get('duration_ms', 0)} ms",
    ]
    if failure_reasons:
        lines.extend(["", "Failures", "--------"])
        lines.extend(f"- {reason}" for reason in failure_reasons)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate a completed live Agent task without replaying its action path"
    )
    parser.add_argument("task_id", help="Stored agent.run task id")
    parser.add_argument("--scenario", required=True, help="Path to scenario JSON")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--token", default="", help="Local API bearer token")
    args = parser.parse_args(argv)
    try:
        scenario = json.loads(Path(args.scenario).read_text(encoding="utf-8"))
        payload = _post_json(
            args.base_url,
            f"/v1/tasks/{args.task_id}/evaluate",
            {"scenario": scenario},
            args.token,
        )
        result = payload["evaluation"]
    except (OSError, KeyError, TypeError, ValueError, HTTPError, URLError) as error:
        print(f"failed to evaluate task: {error}", file=sys.stderr)
        return 1
    if not isinstance(result, dict):
        print("failed to evaluate task: invalid response shape", file=sys.stderr)
        return 1
    print(render_evaluation_result(result), end="")
    return 0 if result.get("passed") is True else 2


def _post_json(
    base_url: str,
    path: str,
    body: dict[str, Any],
    token: str,
) -> dict[str, Any]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("response is not an object")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
