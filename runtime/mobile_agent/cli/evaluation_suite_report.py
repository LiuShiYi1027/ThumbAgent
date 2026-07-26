"""Aggregate stored live Agent task evaluations into one Suite report."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from mobile_agent.cli.task_evaluate import _post_json
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evaluation import AgentEvaluationAggregator, AgentEvaluationSuite


def render_evaluation_summary(summary: dict[str, Any]) -> str:
    """Render a compact human-readable Suite baseline summary."""

    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    lines = [
        "Mobile Agent Evaluation Suite",
        "=============================",
        f"Suite:       {summary.get('suite_id', '-')}",
        f"Runs:        {summary.get('evaluated_run_count', 0)}/{summary.get('expected_run_count', 0)}",
        f"Passed:      {summary.get('passed_run_count', 0)}",
        f"Pass rate:   {_percent(summary.get('pass_rate'))}",
        f"Rounds avg:  {metrics.get('average_round_count', 0)}",
        f"Tools avg:   {metrics.get('average_tool_call_count', 0)}",
        f"Duration:    avg={metrics.get('average_duration_ms', 0)} ms, p50={metrics.get('p50_duration_ms', 0)} ms, p95={metrics.get('p95_duration_ms', 0)} ms",
        f"Provider:    latency={metrics.get('total_provider_latency_ms', 0)} ms, attempts={metrics.get('total_provider_attempt_count', 0)}, retries={metrics.get('total_provider_retry_count', 0)}",
        f"Reliability: no_progress={metrics.get('total_no_progress_count', 0)}, model_unavailable={metrics.get('total_model_unavailable_count', 0)}, policy_violations={metrics.get('total_policy_violation_count', 0)}",
        "",
        "Scenarios",
        "---------",
    ]
    scenario_results = summary.get("scenario_results")
    if isinstance(scenario_results, list):
        for item in scenario_results:
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('scenario_id', '-')}: {item.get('passed_count', 0)}/{item.get('run_count', 0)} ({_percent(item.get('pass_rate'))})"
                )
    _append_counts(lines, "Failure reasons", summary.get("failure_reasons"))
    _append_counts(lines, "Terminal errors", summary.get("terminal_errors"))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate completed Agent tasks without replaying device actions"
    )
    parser.add_argument("--suite", required=True, help="Path to evaluation Suite JSON")
    parser.add_argument(
        "--task",
        action="append",
        default=[],
        metavar="SCENARIO_ID=TASK_ID",
        help="Assign one completed task to a Suite scenario; repeat for every required run",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument(
        "--token",
        default=os.environ.get("MOBILE_AGENT_API_TOKEN", ""),
        help="Local API bearer token; defaults to MOBILE_AGENT_API_TOKEN",
    )
    args = parser.parse_args(argv)
    try:
        suite_payload = json.loads(Path(args.suite).read_text(encoding="utf-8"))
        suite = AgentEvaluationSuite.from_dict(suite_payload)
        assignments = _parse_assignments(args.task)
        _validate_coverage(suite, assignments)
        evaluations = []
        by_id = {scenario.scenario_id: scenario for scenario in suite.scenarios}
        for scenario_id, task_id in assignments:
            payload = _post_json(
                args.base_url,
                f"/v1/tasks/{task_id}/evaluate",
                {"scenario": by_id[scenario_id].to_dict()},
                args.token,
            )
            result = payload.get("evaluation")
            if not isinstance(result, dict):
                raise ValueError("evaluation response is invalid")
            evaluations.append(result)
        summary = AgentEvaluationAggregator().aggregate(suite.to_dict(), evaluations)
    except (
        HTTPError,
        URLError,
        MobileAgentError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        print(f"failed to build evaluation Suite report: {_friendly_error(error)}", file=sys.stderr)
        return 1
    print(render_evaluation_summary(summary), end="")
    return 0 if summary.get("pass_rate") == 1.0 else 2


def _parse_assignments(values: list[str]) -> list[tuple[str, str]]:
    assignments: list[tuple[str, str]] = []
    for value in values:
        scenario_id, separator, task_id = value.partition("=")
        if not separator or not scenario_id or not task_id:
            raise ValueError("--task must use SCENARIO_ID=TASK_ID")
        assignments.append((scenario_id, task_id))
    return assignments


def _validate_coverage(
    suite: AgentEvaluationSuite, assignments: list[tuple[str, str]]
) -> None:
    expected_ids = {scenario.scenario_id for scenario in suite.scenarios}
    counts = {scenario_id: 0 for scenario_id in expected_ids}
    task_ids: set[str] = set()
    for scenario_id, task_id in assignments:
        if scenario_id not in counts:
            raise ValueError(f"unknown scenario_id: {scenario_id}")
        if re.fullmatch(r"task_[a-f0-9]{32}", task_id) is None:
            raise ValueError(f"invalid task_id for {scenario_id}")
        if task_id in task_ids:
            raise ValueError("task_id assignments must be unique")
        counts[scenario_id] += 1
        task_ids.add(task_id)
    if any(count != suite.runs_per_scenario for count in counts.values()):
        raise ValueError("task assignments do not match runs_per_scenario")


def _friendly_error(error: BaseException) -> str:
    if isinstance(error, URLError):
        return (
            "Runtime is not reachable at the configured loopback URL; "
            "start ./scripts/run-mcp-preview.zsh and keep that terminal open"
        )
    return str(error)


def _append_counts(lines: list[str], title: str, value: object) -> None:
    if not isinstance(value, list) or not value:
        return
    lines.extend(["", title, "-" * len(title)])
    for item in value:
        if isinstance(item, dict):
            lines.append(f"- {item.get('name', '-')}: {item.get('count', 0)}")


def _percent(value: object) -> str:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return "0.0%"
    return f"{float(value) * 100:.1f}%"


if __name__ == "__main__":
    raise SystemExit(main())
