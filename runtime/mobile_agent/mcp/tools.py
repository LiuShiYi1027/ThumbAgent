"""Contract-backed MCP tool catalog and input validation."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class McpToolDefinition:
    """One stable goal-level MCP tool exposed to trusted local clients."""

    name: str
    title: str
    description: str
    schema_key: str
    read_only: bool
    idempotent: bool
    destructive: bool = False

    def to_dict(self, schemas: dict[str, dict[str, Any]]) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputSchema": schemas[self.schema_key],
            "annotations": {
                "title": self.title,
                "readOnlyHint": self.read_only,
                "destructiveHint": self.destructive,
                "idempotentHint": self.idempotent,
                "openWorldHint": False,
            },
            "execution": {"taskSupport": "forbidden"},
        }


TOOLS = (
    McpToolDefinition(
        "mobile_runtime_readiness",
        "Mobile Runtime readiness",
        "Read local Runtime, Android gateway, device, Session and Lease readiness. Performs no device observation or action.",
        "empty",
        True,
        True,
    ),
    McpToolDefinition(
        "mobile_list_devices",
        "List mobile devices",
        "List devices discovered by the local Runtime and their normalized device_id values.",
        "empty",
        True,
        True,
    ),
    McpToolDefinition(
        "mobile_get_local_storage",
        "Get local Artifact storage",
        "Read aggregate counts, bytes and expired Artifact totals below the Mobile Agent data directory. Reads no Artifact content.",
        "local_storage",
        True,
        True,
    ),
    McpToolDefinition(
        "mobile_prepare_local_data_cleanup",
        "Prepare local Artifact cleanup",
        "Build a bounded read-only preview of expired Mobile Agent Artifacts and return a short-lived scoped approval. Deletes nothing.",
        "local_cleanup_prepare",
        True,
        False,
    ),
    McpToolDefinition(
        "mobile_cleanup_local_data",
        "Clean approved local Artifacts",
        "Permanently delete the exact expired Artifact set in a short-lived approval. The MCP host must show count, bytes, cutoff and truncation, then obtain a new explicit confirmation. Do not automatically retry failures.",
        "local_cleanup_submit",
        False,
        False,
        True,
    ),
    McpToolDefinition(
        "mobile_inspect_device",
        "Inspect mobile device",
        "Inspect one device's capabilities, risk, confirmation requirements and current availability without observing its screen.",
        "device",
        True,
        True,
    ),
    McpToolDefinition(
        "mobile_list_apps",
        "List installed applications",
        "List a bounded set of installed application identifiers. Does not launch, install, remove, or modify applications.",
        "app_list",
        True,
        True,
    ),
    McpToolDefinition(
        "mobile_inspect_app",
        "Inspect installed application",
        "Read privacy-minimized version, installer and enabled metadata for one installed application.",
        "app_inspect",
        True,
        True,
    ),
    McpToolDefinition(
        "mobile_inspect_app_state",
        "Inspect application runtime state",
        "Read bounded foreground, process-presence and stopped state for one installed application. Returns no process identifiers or raw system output.",
        "app_state",
        True,
        True,
    ),
    McpToolDefinition(
        "mobile_launch_app",
        "Launch application",
        "Submit a deterministic application launch and verify that the requested package reaches the foreground. Returns a task_id.",
        "app_launch",
        False,
        False,
    ),
    McpToolDefinition(
        "mobile_stop_app",
        "Stop application",
        "Submit a Medium-risk force-stop for one non-system application. The MCP host must obtain explicit user confirmation before confirmed=true.",
        "app_stop",
        False,
        False,
    ),
    McpToolDefinition(
        "mobile_prepare_app_data_clear",
        "Prepare application data clear",
        "Inspect one installed non-system application and return a short-lived deletion impact summary. Performs no mutation.",
        "app_data_clear_prepare",
        True,
        False,
    ),
    McpToolDefinition(
        "mobile_clear_app_data",
        "Clear approved application data",
        "Submit a High-risk application data clear using a short-lived approval_id. The MCP host must show the exact impact summary and obtain new explicit user confirmation before confirmed=true. Do not automatically retry failed or unknown-outcome work.",
        "app_data_clear_submit",
        False,
        False,
        True,
    ),
    McpToolDefinition(
        "mobile_prepare_apk_install",
        "Prepare local APK installation",
        "Read and validate one APK inside the Runtime-authorized APK directory. Returns a short-lived scoped approval summary and performs no installation.",
        "apk_install_prepare",
        True,
        False,
    ),
    McpToolDefinition(
        "mobile_install_apk",
        "Install approved local APK",
        "Submit a High-risk APK installation using a short-lived approval_id. The MCP host must show the exact approval summary and obtain explicit user confirmation before confirmed=true.",
        "apk_install_submit",
        False,
        False,
        True,
    ),
    McpToolDefinition(
        "mobile_prepare_app_uninstall",
        "Prepare application uninstall",
        "Read and validate one installed non-system application. Returns a short-lived summary including data deletion impact and performs no uninstall.",
        "app_uninstall_prepare",
        True,
        False,
    ),
    McpToolDefinition(
        "mobile_uninstall_app",
        "Uninstall approved application",
        "Submit a High-risk application uninstall using a short-lived approval_id. The MCP host must show the exact data impact summary and obtain new explicit user confirmation before confirmed=true. Do not automatically retry a failed or unknown-outcome uninstall.",
        "app_uninstall_submit",
        False,
        False,
        True,
    ),
    McpToolDefinition(
        "mobile_run_agent",
        "Run mobile Agent task",
        "Submit one dynamic Observe-Plan-Act task. The MCP host must show the goal and obtain explicit user confirmation before confirmed=true. Returns immediately with task_id; poll that task to a terminal state and report its final TaskRun. Do not automatically submit a replacement task after terminal failure without new user confirmation.",
        "agent_run",
        False,
        False,
    ),
    McpToolDefinition(
        "mobile_list_tasks",
        "List Mobile Agent tasks",
        "List recent persisted task summaries for reports and follow-up queries.",
        "task_list",
        True,
        True,
    ),
    McpToolDefinition(
        "mobile_get_task_execution",
        "Get task execution",
        "Get queued/running/terminal execution state for an asynchronous Mobile Agent task.",
        "task",
        True,
        True,
    ),
    McpToolDefinition(
        "mobile_get_task_report",
        "Get task report",
        "Get the completed auditable TaskRun report, including structured steps, evidence references and errors.",
        "task",
        True,
        True,
    ),
    McpToolDefinition(
        "mobile_cancel_task",
        "Cancel mobile task",
        "Request cooperative cancellation at the next safe task boundary. This does not undo completed device actions.",
        "task",
        False,
        True,
    ),
    McpToolDefinition(
        "mobile_collect_device_logs",
        "Collect bounded device logs",
        "Submit bounded, redacted Android log capture. The MCP host must obtain explicit user confirmation before confirmed=true. Returns task_id, never log text.",
        "logs_collect",
        False,
        False,
    ),
    McpToolDefinition(
        "mobile_capture_device_performance",
        "Capture device performance",
        "Submit a privacy-minimized aggregate CPU, memory, battery and load snapshot. Returns task_id and never raw dumpsys output.",
        "performance_snapshot",
        False,
        False,
    ),
    McpToolDefinition(
        "mobile_compare_device_performance",
        "Compare device performance",
        "Compare two successful aggregate performance tasks from the same device. Two-point trends do not prove causality or regression.",
        "performance_comparison",
        True,
        True,
    ),
    McpToolDefinition(
        "mobile_collect_diagnostic_bundle",
        "Collect diagnostic evidence bundle",
        "Submit one bounded local capture containing screenshot, UI tree, redacted logs, aggregate performance and optional app state. The MCP host must explain the captured evidence and obtain explicit user confirmation before confirmed=true. Returns task_id and never inline evidence content.",
        "diagnostic_bundle",
        False,
        False,
    ),
)


def load_input_schemas() -> dict[str, dict[str, Any]]:
    """Load MCP input schemas from the repository Contract truth source."""

    configured = os.environ.get("MOBILE_AGENT_CONTRACT_DIR")
    root = Path(configured) if configured else Path(__file__).resolve().parents[3] / "contracts/schemas"
    document = json.loads((root / "mcp-tool-inputs.schema.json").read_text(encoding="utf-8"))
    definitions = document.get("$defs")
    if not isinstance(definitions, dict):
        raise RuntimeError("MCP tool input contract has no $defs")
    schemas: dict[str, dict[str, Any]] = {}
    for name, schema in definitions.items():
        if isinstance(name, str) and isinstance(schema, dict):
            schemas[name] = dict(schema)
    missing = {tool.schema_key for tool in TOOLS} - schemas.keys()
    if missing:
        raise RuntimeError("MCP tool input contract is incomplete")
    return schemas


def validate_arguments(schema: dict[str, Any], arguments: object) -> list[str]:
    """Validate the supported strict object subset used by MCP input Contracts."""

    if not isinstance(arguments, dict):
        return ["arguments"]
    errors: list[str] = []
    properties = schema.get("properties", {})
    properties = properties if isinstance(properties, dict) else {}
    required = schema.get("required", [])
    required = required if isinstance(required, list) else []
    for key in required:
        if isinstance(key, str) and key not in arguments:
            errors.append(key)
    if schema.get("additionalProperties") is False:
        errors.extend(key for key in arguments if key not in properties)
    for key, value in arguments.items():
        rule = properties.get(key)
        if not isinstance(rule, dict):
            continue
        if not _valid_value(rule, value):
            errors.append(key)
    return sorted(set(errors))


def _valid_value(rule: dict[str, Any], value: object) -> bool:
    if "const" in rule and value != rule["const"]:
        return False
    choices = rule.get("enum")
    if isinstance(choices, list) and value not in choices:
        return False
    expected = rule.get("type")
    if expected == "string":
        if not isinstance(value, str):
            return False
        minimum = rule.get("minLength")
        maximum = rule.get("maxLength")
        pattern = rule.get("pattern")
        if isinstance(minimum, int) and len(value) < minimum:
            return False
        if isinstance(maximum, int) and len(value) > maximum:
            return False
        if isinstance(pattern, str) and re.fullmatch(pattern, value) is None:
            return False
    elif expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return False
    elif expected == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
    elif expected == "boolean" and not isinstance(value, bool):
        return False
    if expected in {"integer", "number"}:
        minimum = rule.get("minimum")
        maximum = rule.get("maximum")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        numeric_value = float(value)
        if isinstance(minimum, (int, float)) and numeric_value < float(minimum):
            return False
        if isinstance(maximum, (int, float)) and numeric_value > float(maximum):
            return False
    return True
