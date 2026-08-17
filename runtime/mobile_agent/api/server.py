"""Minimal local HTTP interface for the runtime foundation iteration."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evidence.artifacts import default_artifact_root
from mobile_agent.runtime import RuntimeService, build_default_runtime
from mobile_agent.runtime_lock import RuntimeInstanceLock
from mobile_agent.web import TASK_UI_HTML


class RuntimeRequestHandler(BaseHTTPRequestHandler):
    """Expose the initial health and device discovery endpoints on loopback."""

    runtime_factory: Callable[[], RuntimeService] = staticmethod(build_default_runtime)
    server_version = "MobileAgentRuntime/0.1"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        if path in {"/ui", "/ui/"}:
            token = getattr(self.server, "api_token", "")
            self._write_html(
                HTTPStatus.OK,
                TASK_UI_HTML.replace(
                    "__MOBILE_AGENT_API_TOKEN__",
                    json.dumps(str(token)),
                ),
            )
            return
        if path == "/v1/health":
            self._write_json(HTTPStatus.OK, self._runtime().health())
            return
        if path == "/v1/readiness":
            status, payload = self._runtime().readiness_sync()
            self._write_json(status, payload)
            return
        if path == "/v1/devices":
            try:
                status, payload = self._runtime().list_devices_sync()
            except MobileAgentError as error:
                status, payload = HTTPStatus.SERVICE_UNAVAILABLE, {"error": error.to_dict()}
            self._write_json(status, payload)
            return
        if path == "/v1/tools":
            self._write_json(HTTPStatus.OK, {"tools": self._runtime().list_tools()})
            return
        if path == "/v1/model-provider/status":
            status, payload = self._runtime().model_provider_status_sync()
            self._write_json(status, payload)
            return
        if path == "/v1/storage":
            try:
                query = parse_qs(parsed_path.query, keep_blank_values=True)
                if set(query) - {"retention_days"}:
                    raise ValueError("unknown query")
                retention_days = _query_int(
                    parsed_path.query,
                    "retention_days",
                    7,
                    maximum=365,
                )
            except ValueError:
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": {"code": "INVALID_ARGUMENT", "message": "请求参数无效"}},
                )
                return
            status, payload = self._runtime().local_storage_summary_sync(
                retention_days
            )
            self._write_json(status, payload)
            return
        inspection_match = re.fullmatch(r"/v1/devices/([^/]+)/inspection", path)
        if inspection_match:
            status, payload = self._runtime().inspect_device_sync(
                unquote(inspection_match.group(1))
            )
            self._write_json(status, payload)
            return
        apps_match = re.fullmatch(r"/v1/devices/([^/]+)/apps", path)
        if apps_match:
            try:
                query = parse_qs(parsed_path.query, keep_blank_values=True)
                if set(query) - {"limit", "prefix"}:
                    raise ValueError("unknown query")
                limit = _query_int(parsed_path.query, "limit", 200, maximum=500)
                prefix_values = query.get("prefix", [])
                if len(prefix_values) > 1:
                    raise ValueError("prefix")
                prefix = prefix_values[0] if prefix_values else None
            except ValueError:
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": {"code": "INVALID_ARGUMENT", "message": "请求参数无效"}},
                )
                return
            status, payload = self._runtime().list_installed_apps_sync(
                unquote(apps_match.group(1)), limit, prefix
            )
            self._write_json(status, payload)
            return
        app_state_match = re.fullmatch(
            r"/v1/devices/([^/]+)/apps/([^/]+)/state", path
        )
        if app_state_match:
            status, payload = self._runtime().inspect_app_runtime_state_sync(
                unquote(app_state_match.group(1)),
                unquote(app_state_match.group(2)),
            )
            self._write_json(status, payload)
            return
        app_match = re.fullmatch(r"/v1/devices/([^/]+)/apps/([^/]+)", path)
        if app_match:
            status, payload = self._runtime().inspect_installed_app_sync(
                unquote(app_match.group(1)), unquote(app_match.group(2))
            )
            self._write_json(status, payload)
            return
        if path == "/v1/tasks":
            try:
                limit = _query_int(parsed_path.query, "limit", 20)
            except ValueError:
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": {"code": "INVALID_ARGUMENT", "message": "请求参数无效"}},
                )
                return
            status, payload = self._runtime().list_tasks_sync(limit)
            self._write_json(status, payload)
            return
        execution_event_match = re.fullmatch(
            r"/v1/task-executions/(task_[a-f0-9]{32})/events", path
        )
        if execution_event_match:
            status, payload = self._runtime().list_task_execution_events_sync(
                execution_event_match.group(1)
            )
            self._write_json(status, payload)
            return
        execution_match = re.fullmatch(
            r"/v1/task-executions/(task_[a-f0-9]{32})", path
        )
        if execution_match:
            status, payload = self._runtime().get_task_execution_sync(
                execution_match.group(1)
            )
            self._write_json(status, payload)
            return
        event_match = re.fullmatch(r"/v1/tasks/(task_[a-f0-9]{32})/events", path)
        if event_match:
            status, payload = self._runtime().list_task_events_sync(event_match.group(1))
            self._write_json(status, payload)
            return
        task_match = re.fullmatch(r"/v1/tasks/(task_[a-f0-9]{32})", path)
        if task_match:
            status, payload = self._runtime().get_task_sync(task_match.group(1))
            self._write_json(status, payload)
            return
        self._write_json(
            HTTPStatus.NOT_FOUND,
            {
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "category": "validation",
                    "message": "请求的本地资源不存在",
                    "retryable": False,
                    "outcome": "rejected",
                }
            },
        )

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._authorize_post():
            return
        match = re.fullmatch(r"/v1/devices/([^/]+)/observe", self.path)
        if match:
            try:
                status, payload = self._runtime().observe_sync(match.group(1))
            except MobileAgentError as error:
                status, payload = HTTPStatus.SERVICE_UNAVAILABLE, {"error": error.to_dict()}
            self._write_json(status, payload)
            return

        tool_match = re.fullmatch(r"/v1/tools/([a-z.]+)/invoke", self.path)
        skill_match = re.fullmatch(r"/v1/skills/app\.open/invoke", self.path)
        device_logs_match = re.fullmatch(
            r"/v1/skills/device\.logs\.collect/invoke", self.path
        )
        device_performance_match = re.fullmatch(
            r"/v1/skills/device\.performance\.snapshot/invoke", self.path
        )
        navigation_match = re.fullmatch(r"/v1/skills/settings\.navigate/invoke", self.path)
        scroll_navigation_match = re.fullmatch(
            r"/v1/skills/settings\.scroll_navigate/invoke", self.path
        )
        task_run_match = re.fullmatch(r"/v1/tasks/settings\.scroll_navigate/run", self.path)
        agent_run_match = re.fullmatch(r"/v1/tasks/agent\.run", self.path)
        async_agent_run_match = re.fullmatch(
            r"/v1/tasks/agent\.run/async", self.path
        )
        async_device_logs_match = re.fullmatch(
            r"/v1/tasks/device\.logs\.collect/async", self.path
        )
        async_device_performance_match = re.fullmatch(
            r"/v1/tasks/device\.performance\.snapshot/async", self.path
        )
        async_diagnostic_bundle_match = re.fullmatch(
            r"/v1/tasks/device\.diagnostics\.bundle/async", self.path
        )
        apk_prepare_match = re.fullmatch(r"/v1/apps/install/prepare", self.path)
        async_apk_install_match = re.fullmatch(
            r"/v1/tasks/app\.install/async", self.path
        )
        app_removal_prepare_match = re.fullmatch(
            r"/v1/apps/uninstall/prepare", self.path
        )
        async_app_removal_match = re.fullmatch(
            r"/v1/tasks/app\.uninstall/async", self.path
        )
        async_app_launch_match = re.fullmatch(
            r"/v1/tasks/app\.launch/async", self.path
        )
        async_app_stop_match = re.fullmatch(
            r"/v1/tasks/app\.stop/async", self.path
        )
        app_data_clear_prepare_match = re.fullmatch(
            r"/v1/apps/data/clear/prepare", self.path
        )
        async_app_data_clear_match = re.fullmatch(
            r"/v1/tasks/app\.data\.clear/async", self.path
        )
        local_cleanup_prepare_match = re.fullmatch(
            r"/v1/storage/cleanup/prepare", self.path
        )
        async_local_cleanup_match = re.fullmatch(
            r"/v1/tasks/local\.data\.cleanup/async", self.path
        )
        execution_cancel_match = re.fullmatch(
            r"/v1/task-executions/(task_[a-f0-9]{32})/cancel", self.path
        )
        goal_compile_match = re.fullmatch(r"/v1/goals/compile", self.path)
        evaluation_match = re.fullmatch(
            r"/v1/tasks/(task_[a-f0-9]{32})/evaluate", self.path
        )
        performance_comparison_match = re.fullmatch(
            r"/v1/performance-comparisons", self.path
        )
        try:
            body = self._read_json()
            if performance_comparison_match:
                if set(body) != {"baseline_task_id", "candidate_task_id"}:
                    raise ValueError("performance comparison fields")
                baseline_task_id = body.get("baseline_task_id")
                candidate_task_id = body.get("candidate_task_id")
                task_id_pattern = r"task_[a-f0-9]{32}"
                if (
                    not isinstance(baseline_task_id, str)
                    or not isinstance(candidate_task_id, str)
                    or re.fullmatch(task_id_pattern, baseline_task_id) is None
                    or re.fullmatch(task_id_pattern, candidate_task_id) is None
                ):
                    raise ValueError("performance comparison task ids")
                status, payload = self._runtime().compare_device_performance_sync(
                    baseline_task_id, candidate_task_id
                )
                self._write_json(status, payload)
                return
            if evaluation_match:
                if set(body) != {"scenario"}:
                    raise ValueError("scenario")
                status, payload = self._runtime().evaluate_agent_task_sync(
                    evaluation_match.group(1), body.get("scenario")
                )
                self._write_json(status, payload)
                return
            if goal_compile_match:
                if set(body) != {"goal"} or not isinstance(body.get("goal"), str):
                    raise ValueError("goal")
                status, payload = self._runtime().compile_goal_sync(body["goal"])
                self._write_json(status, payload)
                return
            if local_cleanup_prepare_match:
                if set(body) - {"retention_days", "max_artifacts"}:
                    raise ValueError("local cleanup prepare fields")
                retention_days = body.get("retention_days", 7)
                max_artifacts = body.get("max_artifacts", 500)
                if (
                    isinstance(retention_days, bool)
                    or not isinstance(retention_days, int)
                    or isinstance(max_artifacts, bool)
                    or not isinstance(max_artifacts, int)
                ):
                    raise ValueError("local cleanup prepare")
                status, payload = (
                    self._runtime().prepare_local_data_cleanup_sync(
                        retention_days, max_artifacts
                    )
                )
                self._write_json(status, payload)
                return
            if async_local_cleanup_match:
                if set(body) - {"approval_id", "confirmed", "deadline_seconds"}:
                    raise ValueError("local cleanup fields")
                approval_id = body.get("approval_id")
                confirmed = body.get("confirmed", False)
                deadline_seconds = _body_float(
                    body, "deadline_seconds", 120.0, 1.0, 1800.0
                )
                if not isinstance(approval_id, str) or not isinstance(confirmed, bool):
                    raise ValueError("local cleanup")
                idempotency_key = _idempotency_key(
                    self.headers.get("Idempotency-Key")
                )
                if idempotency_key is None:
                    raise ValueError("Idempotency-Key")
                status, payload = (
                    self._runtime().submit_local_data_cleanup_task_sync(
                        approval_id,
                        confirmed,
                        idempotency_key,
                        deadline_seconds,
                    )
                )
                self._write_json(status, payload)
                return
            if apk_prepare_match:
                if set(body) - {"device_id", "apk_path", "expected_app_id", "replace_existing"}:
                    raise ValueError("apk prepare fields")
                device_id = body.get("device_id")
                apk_path = body.get("apk_path")
                expected_app_id = body.get("expected_app_id")
                replace_existing = body.get("replace_existing", False)
                if (
                    not isinstance(device_id, str)
                    or not isinstance(apk_path, str)
                    or not isinstance(expected_app_id, str)
                    or not isinstance(replace_existing, bool)
                ):
                    raise ValueError("apk prepare")
                status, payload = self._runtime().prepare_apk_install_sync(
                    device_id, apk_path, expected_app_id, replace_existing
                )
                self._write_json(status, payload)
                return
            if async_apk_install_match:
                if set(body) - {"approval_id", "confirmed", "deadline_seconds"}:
                    raise ValueError("apk install fields")
                approval_id = body.get("approval_id")
                confirmed = body.get("confirmed", False)
                deadline_seconds = _body_float(
                    body, "deadline_seconds", 300.0, 1.0, 1800.0
                )
                if not isinstance(approval_id, str) or not isinstance(confirmed, bool):
                    raise ValueError("apk install")
                idempotency_key = _idempotency_key(self.headers.get("Idempotency-Key"))
                if idempotency_key is None:
                    raise ValueError("Idempotency-Key")
                status, payload = self._runtime().submit_apk_install_task_sync(
                    approval_id, confirmed, idempotency_key, deadline_seconds
                )
                self._write_json(status, payload)
                return
            if app_removal_prepare_match:
                if set(body) - {"device_id", "app_id", "keep_data"}:
                    raise ValueError("app removal prepare fields")
                device_id = body.get("device_id")
                app_id = body.get("app_id")
                keep_data = body.get("keep_data", False)
                if (
                    not isinstance(device_id, str)
                    or not isinstance(app_id, str)
                    or not isinstance(keep_data, bool)
                ):
                    raise ValueError("app removal prepare")
                status, payload = self._runtime().prepare_app_removal_sync(
                    device_id, app_id, keep_data
                )
                self._write_json(status, payload)
                return
            if async_app_removal_match:
                if set(body) - {"approval_id", "confirmed", "deadline_seconds"}:
                    raise ValueError("app removal fields")
                approval_id = body.get("approval_id")
                confirmed = body.get("confirmed", False)
                deadline_seconds = _body_float(
                    body, "deadline_seconds", 180.0, 1.0, 1800.0
                )
                if not isinstance(approval_id, str) or not isinstance(confirmed, bool):
                    raise ValueError("app removal")
                idempotency_key = _idempotency_key(
                    self.headers.get("Idempotency-Key")
                )
                if idempotency_key is None:
                    raise ValueError("Idempotency-Key")
                status, payload = self._runtime().submit_app_removal_task_sync(
                    approval_id, confirmed, idempotency_key, deadline_seconds
                )
                self._write_json(status, payload)
                return
            if app_data_clear_prepare_match:
                if set(body) != {"device_id", "app_id"}:
                    raise ValueError("app data clear prepare fields")
                device_id = body.get("device_id")
                app_id = body.get("app_id")
                if not isinstance(device_id, str) or not isinstance(app_id, str):
                    raise ValueError("app data clear prepare")
                status, payload = self._runtime().prepare_app_data_clear_sync(
                    device_id, app_id
                )
                self._write_json(status, payload)
                return
            if async_app_data_clear_match:
                if set(body) - {"approval_id", "confirmed", "deadline_seconds"}:
                    raise ValueError("app data clear fields")
                approval_id = body.get("approval_id")
                confirmed = body.get("confirmed", False)
                deadline_seconds = _body_float(
                    body, "deadline_seconds", 180.0, 1.0, 1800.0
                )
                if not isinstance(approval_id, str) or not isinstance(confirmed, bool):
                    raise ValueError("app data clear")
                idempotency_key = _idempotency_key(
                    self.headers.get("Idempotency-Key")
                )
                if idempotency_key is None:
                    raise ValueError("Idempotency-Key")
                status, payload = self._runtime().submit_app_data_clear_task_sync(
                    approval_id, confirmed, idempotency_key, deadline_seconds
                )
                self._write_json(status, payload)
                return
            if execution_cancel_match:
                if body:
                    raise ValueError("empty body")
                status, payload = self._runtime().cancel_task_execution_sync(
                    execution_cancel_match.group(1)
                )
                self._write_json(status, payload)
                return
            device_id = body.get("device_id")
            if not isinstance(device_id, str):
                raise ValueError("device_id")
            if async_app_launch_match:
                if set(body) - {"device_id", "app_id", "deadline_seconds"}:
                    raise ValueError("app launch fields")
                app_id = body.get("app_id")
                deadline_seconds = _body_float(
                    body, "deadline_seconds", 60.0, 1.0, 1800.0
                )
                if not isinstance(app_id, str):
                    raise ValueError("app launch")
                idempotency_key = _idempotency_key(
                    self.headers.get("Idempotency-Key")
                )
                if idempotency_key is None:
                    raise ValueError("Idempotency-Key")
                status, payload = self._runtime().submit_app_launch_task_sync(
                    device_id, app_id, idempotency_key, deadline_seconds
                )
            elif async_app_stop_match:
                if set(body) - {
                    "device_id",
                    "app_id",
                    "confirmed",
                    "deadline_seconds",
                }:
                    raise ValueError("app stop fields")
                app_id = body.get("app_id")
                confirmed = body.get("confirmed", False)
                deadline_seconds = _body_float(
                    body, "deadline_seconds", 60.0, 1.0, 1800.0
                )
                if not isinstance(app_id, str) or not isinstance(confirmed, bool):
                    raise ValueError("app stop")
                idempotency_key = _idempotency_key(
                    self.headers.get("Idempotency-Key")
                )
                if idempotency_key is None:
                    raise ValueError("Idempotency-Key")
                status, payload = self._runtime().submit_app_stop_task_sync(
                    device_id,
                    app_id,
                    confirmed,
                    idempotency_key,
                    deadline_seconds,
                )
            elif tool_match:
                arguments = body.get("arguments", {})
                confirmed = body.get("confirmed", False)
                if not isinstance(arguments, dict) or not isinstance(confirmed, bool):
                    raise ValueError("arguments/confirmed")
                status, payload = self._runtime().invoke_tool_sync(
                    tool_match.group(1), device_id, arguments, confirmed
                )
            elif skill_match:
                app_id = body.get("app_id")
                if not isinstance(app_id, str):
                    raise ValueError("app_id")
                status, payload = self._runtime().open_app_sync(device_id, app_id)
            elif device_logs_match:
                if not set(body).issubset(
                    {"device_id", "max_lines", "minimum_level", "confirmed"}
                ):
                    raise ValueError("device logs fields")
                max_lines = body.get("max_lines", 500)
                minimum_level = body.get("minimum_level", "info")
                confirmed = body.get("confirmed", False)
                if (
                    not isinstance(max_lines, int)
                    or isinstance(max_lines, bool)
                    or max_lines < 1
                    or max_lines > 2000
                    or not isinstance(minimum_level, str)
                    or minimum_level
                    not in {"verbose", "debug", "info", "warn", "error", "fatal"}
                    or not isinstance(confirmed, bool)
                ):
                    raise ValueError("device logs arguments")
                status, payload = self._runtime().collect_device_logs_sync(
                    device_id, max_lines, minimum_level, confirmed
                )
            elif async_device_logs_match:
                if not set(body).issubset(
                    {
                        "device_id",
                        "max_lines",
                        "minimum_level",
                        "confirmed",
                        "deadline_seconds",
                    }
                ):
                    raise ValueError("async device logs fields")
                max_lines = body.get("max_lines", 500)
                minimum_level = body.get("minimum_level", "info")
                confirmed = body.get("confirmed", False)
                deadline_seconds = _body_float(
                    body, "deadline_seconds", 60.0, 1.0, 1800.0
                )
                if (
                    not isinstance(max_lines, int)
                    or isinstance(max_lines, bool)
                    or max_lines < 1
                    or max_lines > 2000
                    or not isinstance(minimum_level, str)
                    or minimum_level
                    not in {"verbose", "debug", "info", "warn", "error", "fatal"}
                    or not isinstance(confirmed, bool)
                ):
                    raise ValueError("async device logs arguments")
                status, payload = self._runtime().submit_device_logs_task_sync(
                    device_id,
                    max_lines,
                    minimum_level,
                    confirmed,
                    _idempotency_key(self.headers.get("Idempotency-Key")),
                    deadline_seconds,
                )
            elif device_performance_match:
                if set(body) != {"device_id"}:
                    raise ValueError("device performance fields")
                status, payload = self._runtime().capture_device_performance_sync(
                    device_id
                )
            elif async_device_performance_match:
                if not set(body).issubset({"device_id", "deadline_seconds"}):
                    raise ValueError("async device performance fields")
                deadline_seconds = _body_float(
                    body, "deadline_seconds", 90.0, 1.0, 1800.0
                )
                status, payload = (
                    self._runtime().submit_device_performance_task_sync(
                        device_id,
                        _idempotency_key(self.headers.get("Idempotency-Key")),
                        deadline_seconds,
                    )
                )
            elif async_diagnostic_bundle_match:
                if not set(body).issubset(
                    {
                        "device_id",
                        "app_id",
                        "max_log_lines",
                        "minimum_log_level",
                        "confirmed",
                        "deadline_seconds",
                    }
                ):
                    raise ValueError("diagnostic bundle fields")
                app_id = body.get("app_id")
                max_log_lines = body.get("max_log_lines", 500)
                minimum_log_level = body.get("minimum_log_level", "info")
                confirmed = body.get("confirmed", False)
                deadline_seconds = _body_float(
                    body, "deadline_seconds", 120.0, 1.0, 1800.0
                )
                if (
                    (app_id is not None and not isinstance(app_id, str))
                    or not isinstance(max_log_lines, int)
                    or isinstance(max_log_lines, bool)
                    or not isinstance(minimum_log_level, str)
                    or not isinstance(confirmed, bool)
                ):
                    raise ValueError("diagnostic bundle arguments")
                status, payload = self._runtime().submit_diagnostic_bundle_task_sync(
                    device_id,
                    app_id,
                    max_log_lines,
                    minimum_log_level,
                    confirmed,
                    _idempotency_key(self.headers.get("Idempotency-Key")),
                    deadline_seconds,
                )
            elif navigation_match:
                target = body.get("target_selector")
                expected = body.get("expected_selector")
                confirmed = body.get("confirmed", False)
                if not isinstance(target, dict) or not isinstance(expected, dict):
                    raise ValueError("selectors")
                if not isinstance(confirmed, bool):
                    raise ValueError("confirmed")
                status, payload = self._runtime().navigate_settings_sync(
                    device_id, target, expected, confirmed
                )
            elif scroll_navigation_match:
                target = body.get("target_selector")
                expected = body.get("expected_selector")
                direction = body.get("direction", "up")
                max_scrolls = body.get("max_scrolls", 3)
                confirmed = body.get("confirmed", False)
                distance_percent = _body_float(body, "distance_percent", 0.8, 0.1, 0.8)
                duration_ms = _body_int(body, "duration_ms", 800, 100, 2000)
                settle_seconds = _body_float(body, "settle_seconds", 0.8, 0.0, 3.0)
                if not isinstance(target, dict) or not isinstance(expected, dict):
                    raise ValueError("selectors")
                if direction not in {"up", "down", "left", "right"}:
                    raise ValueError("direction")
                if (
                    not isinstance(max_scrolls, int)
                    or isinstance(max_scrolls, bool)
                    or not isinstance(confirmed, bool)
                ):
                    raise ValueError("max_scrolls/confirmed")
                status, payload = self._runtime().scroll_navigate_settings_sync(
                    device_id,
                    target,
                    expected,
                    direction,
                    max_scrolls,
                    confirmed,
                    distance_percent,
                    duration_ms,
                    settle_seconds,
                )
            elif task_run_match:
                target = body.get("target_selector")
                expected = body.get("expected_selector")
                direction = body.get("direction", "up")
                max_scrolls = body.get("max_scrolls", 3)
                confirmed = body.get("confirmed", False)
                distance_percent = _body_float(body, "distance_percent", 0.8, 0.1, 0.8)
                duration_ms = _body_int(body, "duration_ms", 800, 100, 2000)
                settle_seconds = _body_float(body, "settle_seconds", 0.8, 0.0, 3.0)
                goal = body.get("goal")
                if not isinstance(target, dict) or not isinstance(expected, dict):
                    raise ValueError("selectors")
                if direction not in {"up", "down", "left", "right"}:
                    raise ValueError("direction")
                if (
                    not isinstance(max_scrolls, int)
                    or isinstance(max_scrolls, bool)
                    or not isinstance(confirmed, bool)
                ):
                    raise ValueError("max_scrolls/confirmed")
                if goal is not None and not isinstance(goal, str):
                    raise ValueError("goal")
                status, payload = self._runtime().run_settings_scroll_navigation_task_sync(
                    device_id,
                    target,
                    expected,
                    direction,
                    max_scrolls,
                    confirmed,
                    distance_percent,
                    duration_ms,
                    settle_seconds,
                    goal,
                )
            elif agent_run_match or async_agent_run_match:
                goal = body.get("goal")
                confirmed = body.get("confirmed", False)
                max_rounds = body.get("max_rounds", 6)
                acceptance = body.get("acceptance")
                goal_spec = body.get("goal_spec")
                goal_spec_confirmed = body.get("goal_spec_confirmed", False)
                deadline_seconds = _body_float(
                    body, "deadline_seconds", 600.0, 1.0, 1800.0
                )
                if not isinstance(goal, str) or not goal.strip():
                    raise ValueError("goal")
                if not isinstance(confirmed, bool):
                    raise ValueError("confirmed")
                if (
                    not isinstance(max_rounds, int)
                    or isinstance(max_rounds, bool)
                    or max_rounds < 1
                    or max_rounds > 12
                ):
                    raise ValueError("max_rounds")
                if acceptance is not None and not isinstance(acceptance, dict):
                    raise ValueError("acceptance")
                if goal_spec is not None and not isinstance(goal_spec, dict):
                    raise ValueError("goal_spec")
                if not isinstance(goal_spec_confirmed, bool):
                    raise ValueError("goal_spec_confirmed")
                if async_agent_run_match:
                    idempotency_key = _idempotency_key(self.headers.get("Idempotency-Key"))
                    status, payload = self._runtime().submit_agent_task_sync(
                        device_id,
                        goal,
                        confirmed,
                        max_rounds,
                        acceptance,
                        goal_spec,
                        goal_spec_confirmed,
                        idempotency_key,
                        deadline_seconds,
                    )
                else:
                    status, payload = self._runtime().run_agent_task_sync(
                        device_id,
                        goal,
                        confirmed,
                        max_rounds,
                        acceptance,
                        goal_spec,
                        goal_spec_confirmed,
                        deadline_seconds,
                    )
            else:
                status, payload = HTTPStatus.NOT_FOUND, {
                    "error": {"code": "RESOURCE_NOT_FOUND", "message": "资源不存在"}
                }
        except (ValueError, json.JSONDecodeError):
            status, payload = HTTPStatus.BAD_REQUEST, {
                "error": {"code": "INVALID_ARGUMENT", "message": "请求参数无效"}
            }
        except MobileAgentError as error:
            status, payload = HTTPStatus.SERVICE_UNAVAILABLE, {"error": error.to_dict()}
        self._write_json(status, payload)

    def _runtime(self) -> RuntimeService:
        runtime = getattr(self.server, "runtime", None)
        if isinstance(runtime, RuntimeService):
            return runtime
        return self.runtime_factory()

    def _authorize_post(self) -> bool:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self._write_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                {"error": {"code": "INVALID_CONTENT_TYPE", "message": "需要 application/json"}},
            )
            return False
        expected = getattr(self.server, "api_token", "")
        authorization = self.headers.get("Authorization", "")
        supplied = authorization[7:] if authorization.startswith("Bearer ") else ""
        if not expected or not secrets.compare_digest(supplied, expected):
            self._write_json(
                HTTPStatus.UNAUTHORIZED,
                {"error": {"code": "UNAUTHORIZED", "message": "缺少有效的本地 API 令牌"}},
            )
            return False
        origin = self.headers.get("Origin")
        allowed_origins = getattr(self.server, "allowed_origins", frozenset())
        if origin is not None and origin not in allowed_origins:
            parsed = urlparse(origin)
            if not self._is_same_loopback_origin(parsed):
                self._write_json(
                    HTTPStatus.FORBIDDEN,
                    {"error": {"code": "ORIGIN_REJECTED", "message": "请求来源未获授权"}},
                )
                return False
        return True

    def _is_same_loopback_origin(self, parsed: Any) -> bool:
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
            return False
        return parsed.port == getattr(self.server, "server_port", None)

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        length = int(raw_length)
        if length <= 0 or length > 65_536:
            raise ValueError("content length")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("json object")
        return payload

    def log_message(self, format: str, *args: Any) -> None:
        """Avoid leaking request details through default stderr logging."""

    def _write_json(self, status: HTTPStatus, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _write_html(self, status: HTTPStatus, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def create_server(
    host: str = "127.0.0.1", port: int = 8765, api_token: str | None = None
) -> ThreadingHTTPServer:
    """Create a loopback-only HTTP server."""

    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("The V1 runtime may only listen on loopback")
    server = ThreadingHTTPServer((host, port), RuntimeRequestHandler)
    server.api_token = api_token or secrets.token_urlsafe(32)  # type: ignore[attr-defined]
    server.allowed_origins = frozenset({"tauri://localhost"})  # type: ignore[attr-defined]
    server.runtime = RuntimeRequestHandler.runtime_factory()  # type: ignore[attr-defined]
    return server


def _write_runtime_token(token: str) -> Path:
    root = _runtime_data_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / "runtime-token"
    path.write_text(token, encoding="utf-8")
    path.chmod(0o600)
    return path


def _runtime_data_root() -> Path:
    """Resolve the shared ownership boundary for Runtime state."""

    data_dir = os.environ.get("MOBILE_AGENT_DATA_DIR")
    return Path(data_dir) if data_dir else default_artifact_root().parent


def _query_int(query: str, name: str, default: int, maximum: int = 100) -> int:
    values = parse_qs(query).get(name)
    if not values:
        return default
    if len(values) != 1:
        raise ValueError(name)
    try:
        value = int(values[0])
    except ValueError as error:
        raise ValueError(name) from error
    if value < 1 or value > maximum:
        raise ValueError(name)
    return value


def _body_int(
    body: dict[str, Any],
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = body.get(name, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum or value > maximum:
        raise ValueError(name)
    return value


def _body_float(
    body: dict[str, Any],
    name: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    value = body.get(name, default)
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or value < minimum
        or value > maximum
    ):
        raise ValueError(name)
    return float(value)


def _idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value):
        raise ValueError("Idempotency-Key")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Mobile Agent local runtime")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    configured_token = os.environ.get("MOBILE_AGENT_API_TOKEN")
    token = configured_token or secrets.token_urlsafe(32)
    try:
        with RuntimeInstanceLock(_runtime_data_root() / "runtime.lock"):
            token_file = None if configured_token else _write_runtime_token(token)
            server = None
            try:
                server = create_server(args.host, args.port, token)
                print(f"Mobile Agent runtime listening on http://{args.host}:{server.server_port}")
                if token_file is not None:
                    print(f"Local API token written to {token_file}")
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                if server is not None:
                    server.server_close()
                if token_file is not None:
                    token_file.unlink(missing_ok=True)
    except MobileAgentError as error:
        if error.code != "RUNTIME_ALREADY_RUNNING":
            raise
        parser.exit(2, f"Mobile Agent Runtime 启动失败：{error.message}\n")


if __name__ == "__main__":
    main()
