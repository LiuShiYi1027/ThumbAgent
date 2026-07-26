"""Render a compact human-readable task report."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def render_task_report(task: dict[str, Any], events: list[dict[str, Any]]) -> str:
    """Render a TaskRun and its compact events as a terminal-friendly report."""

    lines = [
        "Mobile Agent Task Report",
        "========================",
        f"Task:   {task.get('task_id', '-')}",
        f"Type:   {task.get('task_type', '-')}",
        f"Status: {task.get('status', '-')}",
        f"Device: {task.get('device_id', '-')}",
        f"Device session: {task.get('device_session_id', '-')}",
        f"Goal:   {task.get('goal', '-')}",
        f"Completion: {task.get('completion_source', '-')}",
        f"Deadline: {task.get('deadline_seconds', '-')} seconds",
        f"Time:   {task.get('started_at', '-')} -> {task.get('completed_at', '-')}",
        "",
        "Steps",
        "-----",
    ]
    acceptance = task.get("goal_acceptance")
    if isinstance(acceptance, dict):
        lines.insert(
            8,
            "Acceptance: "
            + json.dumps(acceptance, ensure_ascii=False, separators=(",", ":")),
        )
    goal_spec = task.get("goal_spec")
    if isinstance(goal_spec, dict):
        lines.insert(
            8,
            "GoalSpec: "
            + json.dumps(goal_spec, ensure_ascii=False, separators=(",", ":")),
        )
    steps = task.get("steps", [])
    if isinstance(steps, list) and steps:
        for step in steps:
            if not isinstance(step, dict):
                continue
            lines.append(
                f"{step.get('sequence', '?')}. {step.get('name', '-')} "
                f"[{step.get('status', '-')}]"
            )
            decision = _step_decision(step)
            if decision:
                lines.append(f"   decision: {decision}")
            error = step.get("error")
            if isinstance(error, dict) and error:
                lines.append(f"   error: {error.get('code', '-')}")
    else:
        lines.append("(no steps)")
    lines.extend(["", "Evidence", "--------"])
    lines.extend(_evidence_lines(task))
    lines.extend(["", "Events", "------"])
    if events:
        for event in events:
            lines.append(_event_line(event))
    else:
        lines.append("(no events)")
    error = task.get("error")
    if isinstance(error, dict) and error:
        lines.extend(["", "Failure", "-------", f"Code: {error.get('code', '-')}"])
        message = error.get("message")
        if isinstance(message, str) and message:
            lines.append(f"Message: {message}")
        diagnostics = _safe_error_diagnostics(error.get("details"))
        if diagnostics:
            lines.append(f"Diagnostics: {diagnostics}")
        suggested = error.get("suggested_action")
        if isinstance(suggested, str) and suggested:
            lines.append(f"Suggested action: {suggested}")
    return "\n".join(lines) + "\n"


def _safe_error_diagnostics(details: object) -> str:
    if not isinstance(details, dict):
        return ""
    scalar_keys = (
        "failure_kind",
        "failure_phase",
        "http_status",
        "timeout_seconds",
        "elapsed_ms",
        "total_elapsed_ms",
        "provider_attempt_count",
        "provider_retry_count",
        "match_count",
        "tap_y",
        "safe_top",
        "safe_bottom",
        "tool_id",
        "selector_error",
        "selector_error_field",
        "repair_count",
        "owner_id",
        "session_id",
        "lease_expired",
    )
    list_keys = (
        "argument_keys",
        "missing_argument_keys",
        "unknown_argument_keys",
        "selector_keys",
        "selector_unknown_keys",
    )
    parts: list[str] = []
    for key in scalar_keys:
        value = details.get(key)
        if isinstance(value, str | int | float | bool):
            parts.append(f"{key}={value}")
    for key in list_keys:
        value = details.get(key)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            parts.append(f"{key}={json.dumps(value, ensure_ascii=False, separators=(',', ':'))}")
    return ", ".join(parts)


def _evidence_lines(task: dict[str, Any]) -> list[str]:
    summary = task.get("evidence_summary")
    if not isinstance(summary, dict) or not summary:
        return ["(no evidence summary)"]
    lines: list[str] = []
    foreground = summary.get("final_foreground_app")
    if isinstance(foreground, dict):
        lines.append(
            "Foreground: "
            f"{foreground.get('app_id', '-')} / {foreground.get('activity', '-')}"
        )
    node = summary.get("verified_node")
    if isinstance(node, dict):
        text = node.get("text") if isinstance(node.get("text"), str) else ""
        resource_id = node.get("resource_id") if isinstance(node.get("resource_id"), str) else ""
        lines.append(f"Verified node: {text or '-'} ({resource_id or '-'})")
    skill_call_id = summary.get("skill_call_id")
    if isinstance(skill_call_id, str) and skill_call_id:
        lines.append(f"Skill call: {skill_call_id}")
    tap_action_id = summary.get("tap_action_id")
    if isinstance(tap_action_id, str) and tap_action_id:
        lines.append(f"Tap action: {tap_action_id}")
    artifact_refs = summary.get("artifact_refs")
    if isinstance(artifact_refs, list) and all(
        isinstance(item, str) for item in artifact_refs
    ):
        lines.append(f"Artifacts: {', '.join(artifact_refs)}")
    captured_bytes = summary.get("captured_bytes")
    if isinstance(captured_bytes, int) and not isinstance(captured_bytes, bool):
        lines.append(f"Captured bytes: {captured_bytes}")
    redaction_count = summary.get("redaction_count")
    if isinstance(redaction_count, int) and not isinstance(redaction_count, bool):
        lines.append(f"Redactions: {redaction_count}")
    if isinstance(summary.get("truncated"), bool):
        lines.append(f"Truncated: {summary['truncated']}")
    performance_keys = (
        ("CPU total", "cpu_total_usage_percent", "%"),
        ("Memory used", "memory_used_percent", "%"),
        ("Battery", "battery_level_percent", "%"),
        ("Battery temperature", "battery_temperature_celsius", " C"),
    )
    for label, key, suffix in performance_keys:
        value = summary.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool):
            lines.append(f"{label}: {value}{suffix}")
    operation = summary.get("operation")
    app = summary.get("app")
    state = summary.get("state")
    if isinstance(operation, str):
        lines.append(f"Application operation: {operation}")
    if isinstance(app, dict) and isinstance(app.get("app_id"), str):
        lines.append(
            f"Application: {app['app_id']} "
            f"({app.get('version_name') or '-'} / {app.get('version_code') or '-'})"
        )
    if isinstance(state, dict):
        lines.append(
            "Application state: "
            f"foreground={state.get('foreground', '-')} "
            f"process_present={state.get('process_present', '-')} "
            f"stopped={state.get('stopped', '-')}"
        )
    if isinstance(summary.get("data_cleared"), bool):
        lines.append(f"Application data cleared: {summary['data_cleared']}")
    bundle = summary.get("bundle_artifact")
    if isinstance(bundle, dict):
        lines.append(
            "Diagnostic bundle: "
            f"{bundle.get('artifact_id', '-')} / "
            f"{bundle.get('size_bytes', '-')} bytes / "
            f"{bundle.get('relative_path', '-')}"
        )
    bundle_logs = summary.get("log_summary")
    if isinstance(bundle_logs, dict):
        lines.append(
            "Diagnostic logs: "
            f"{bundle_logs.get('captured_bytes', '-')} bytes / "
            f"redactions={bundle_logs.get('redaction_count', '-')} / "
            f"truncated={bundle_logs.get('truncated', '-')}"
        )
    bundle_performance = summary.get("performance_summary")
    if isinstance(bundle_performance, dict):
        cpu = bundle_performance.get("cpu")
        memory = bundle_performance.get("memory")
        if isinstance(cpu, dict) and isinstance(memory, dict):
            lines.append(
                "Diagnostic performance: "
                f"CPU={cpu.get('total_usage_percent', '-')}% / "
                f"memory={memory.get('used_percent', '-')}%"
            )
    return lines or ["(no evidence summary)"]


def _step_decision(step: dict[str, Any]) -> str:
    result = step.get("result")
    if not isinstance(result, dict):
        return ""
    decision = result.get("decision")
    if not isinstance(decision, dict):
        return ""
    skill_id = decision.get("skill_id")
    tool_id = decision.get("tool_id")
    decision_type = decision.get("decision_type")
    reason = decision.get("reason")
    source = decision.get("source")
    confidence = decision.get("confidence")
    repair_count = decision.get("repair_count")
    provider_retry_count = decision.get("provider_retry_count")
    provider_latency_ms = decision.get("provider_latency_ms")
    provider_attempt_count = decision.get("provider_attempt_count")
    parts = []
    if isinstance(skill_id, str) and skill_id:
        parts.append(skill_id)
    elif isinstance(tool_id, str) and tool_id:
        parts.append(tool_id)
    elif isinstance(decision_type, str) and decision_type:
        parts.append(decision_type)
    if isinstance(source, str) and source:
        parts.append(f"source={source}")
    if isinstance(confidence, int | float) and not isinstance(confidence, bool):
        parts.append(f"confidence={confidence:.2f}")
    if isinstance(repair_count, int) and not isinstance(repair_count, bool) and repair_count > 0:
        parts.append(f"repair_count={repair_count}")
    if (
        isinstance(provider_retry_count, int)
        and not isinstance(provider_retry_count, bool)
        and provider_retry_count > 0
    ):
        parts.append(f"provider_retry_count={provider_retry_count}")
    if (
        isinstance(provider_attempt_count, int)
        and not isinstance(provider_attempt_count, bool)
        and provider_attempt_count > 0
    ):
        parts.append(f"provider_attempt_count={provider_attempt_count}")
    if (
        isinstance(provider_latency_ms, int)
        and not isinstance(provider_latency_ms, bool)
        and provider_latency_ms >= 0
        and isinstance(provider_attempt_count, int)
        and not isinstance(provider_attempt_count, bool)
        and provider_attempt_count > 0
    ):
        parts.append(f"provider_latency_ms={provider_latency_ms}")
    if isinstance(reason, str) and reason:
        parts.append(reason)
    return " · ".join(parts)


def _event_line(event: dict[str, Any]) -> str:
    payload = event.get("payload")
    suffix = ""
    if isinstance(payload, dict):
        status = payload.get("status")
        error_code = payload.get("error_code")
        if isinstance(status, str) and status:
            suffix = f" status={status}"
        if isinstance(error_code, str) and error_code:
            suffix = f"{suffix} error={error_code}"
    return (
        f"{event.get('sequence', '?')}. {event.get('event_type', '-')} "
        f"@ {event.get('occurred_at', '-')}{suffix}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a Mobile Agent task report")
    parser.add_argument("task_id", help="Task id returned by the local Runtime")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--token", default="", help="Optional local API bearer token")
    args = parser.parse_args(argv)
    try:
        task = _fetch_json(args.base_url, f"/v1/tasks/{args.task_id}", args.token)["task"]
        events = _fetch_json(args.base_url, f"/v1/tasks/{args.task_id}/events", args.token)[
            "events"
        ]
    except (KeyError, TypeError, ValueError, HTTPError, URLError) as error:
        print(f"failed to load task report: {error}", file=sys.stderr)
        return 1
    if not isinstance(task, dict) or not isinstance(events, list):
        print("failed to load task report: invalid response shape", file=sys.stderr)
        return 1
    print(render_task_report(task, events), end="")
    return 0


def _fetch_json(base_url: str, path: str, token: str) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{base_url.rstrip('/')}{path}", headers=headers, method="GET")
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("response is not an object")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
