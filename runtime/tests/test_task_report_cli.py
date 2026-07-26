from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mobile_agent.cli.task_report import render_task_report
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService


TARGET = {
    "strategy": "text",
    "value": "Display",
    "resolve_clickable_ancestor": True,
}
EXPECTED = {"strategy": "text", "value": "Display settings"}


class TaskReportCliTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.runtime = RuntimeService(
            FakeDeviceAdapter(), ArtifactStore(Path(self.directory.name))
        )

    async def test_renders_confirmed_goal_spec(self) -> None:
        task = await self.runtime.run_settings_scroll_navigation_task(
            "fake:android-001",
            TARGET,
            EXPECTED,
            confirmed=True,
            goal="进入显示设置页面",
        )
        payload = dict(task)
        payload["goal_spec"] = {
            "schema_version": "1.0.0",
            "source_goal": "进入显示设置页面",
            "execution_goal": "打开设置，找到显示入口并进入显示设置页面",
            "assumptions": [],
            "confidence": 0.9,
            "compiler_id": "test.llm",
            "source": "llm",
            "confirmation_required": True,
        }

        report = render_task_report(payload, [])

        self.assertIn("GoalSpec:", report)
        self.assertIn("打开设置，找到显示入口", report)

    async def test_renders_successful_task_report_for_humans(self) -> None:
        task = await self.runtime.run_settings_scroll_navigation_task(
            "fake:android-001",
            TARGET,
            EXPECTED,
            confirmed=True,
            goal="进入显示设置页面",
        )
        events = self.runtime.list_task_events(task["task_id"])

        report = render_task_report(task, events)

        self.assertIn("Mobile Agent Task Report", report)
        self.assertIn("Status: succeeded", report)
        self.assertIn("Goal:   进入显示设置页面", report)
        self.assertIn("1. settings.scroll_navigate [succeeded]", report)
        self.assertIn("Foreground: com.android.settings / .DisplaySettings", report)
        self.assertIn("Verified node: Display settings (settings_title)", report)
        self.assertIn("task.completed", report)
        self.assertNotIn("ui_tree", report)
        self.assertNotIn("screenshot", report)

    def test_renders_device_log_artifact_evidence_without_content(self) -> None:
        task = {
            "task_id": "task_test",
            "task_type": "device.logs.collect",
            "status": "succeeded",
            "device_id": "fake:android-001",
            "goal": "采集设备日志",
            "started_at": "2026-07-15T00:00:00Z",
            "completed_at": "2026-07-15T00:00:01Z",
            "steps": [],
            "evidence_summary": {
                "skill_call_id": "skillcall_test",
                "artifact_refs": ["artifact_test"],
                "captured_bytes": 1024,
                "redaction_count": 3,
                "truncated": False,
            },
            "error": None,
        }

        report = render_task_report(task, [])

        self.assertIn("Artifacts: artifact_test", report)
        self.assertIn("Captured bytes: 1024", report)
        self.assertIn("Redactions: 3", report)
        self.assertNotIn("logcat line", report)

    def test_renders_performance_aggregate_evidence(self) -> None:
        task = {
            "task_id": "task_perf",
            "task_type": "device.performance.snapshot",
            "status": "succeeded",
            "device_id": "fake:android-001",
            "goal": "采集设备聚合性能快照",
            "started_at": "2026-07-15T00:00:00Z",
            "completed_at": "2026-07-15T00:00:01Z",
            "steps": [],
            "evidence_summary": {
                "artifact_refs": ["artifact_perf"],
                "cpu_total_usage_percent": 10.5,
                "memory_used_percent": 60.0,
                "battery_level_percent": 80.0,
                "battery_temperature_celsius": 31.0,
            },
            "error": None,
        }

        report = render_task_report(task, [])

        self.assertIn("CPU total: 10.5%", report)
        self.assertIn("Memory used: 60.0%", report)
        self.assertIn("Battery temperature: 31.0 C", report)

    def test_renders_application_lifecycle_evidence(self) -> None:
        task = {
            "task_id": "task_app",
            "task_type": "app.data.clear",
            "status": "succeeded",
            "device_id": "fake:android-001",
            "goal": "清除应用数据",
            "started_at": "2026-07-26T00:00:00Z",
            "completed_at": "2026-07-26T00:00:01Z",
            "steps": [],
            "evidence_summary": {
                "operation": "clear_data",
                "app": {
                    "app_id": "com.example.app",
                    "version_name": "1.0",
                    "version_code": 1,
                },
                "state": {
                    "foreground": False,
                    "process_present": False,
                    "stopped": True,
                },
                "data_cleared": True,
            },
            "error": None,
        }

        report = render_task_report(task, [])

        self.assertIn("Application operation: clear_data", report)
        self.assertIn("Application: com.example.app (1.0 / 1)", report)
        self.assertIn("foreground=False process_present=False stopped=True", report)
        self.assertIn("Application data cleared: True", report)

    def test_renders_diagnostic_bundle_metadata_without_content(self) -> None:
        task = {
            "task_id": "task_bundle",
            "task_type": "device.diagnostics.bundle",
            "status": "succeeded",
            "device_id": "fake:android-001",
            "goal": "采集诊断包",
            "started_at": "2026-07-26T00:00:00Z",
            "completed_at": "2026-07-26T00:00:01Z",
            "steps": [],
            "evidence_summary": {
                "bundle_artifact": {
                    "artifact_id": "artifact_bundle",
                    "size_bytes": 4096,
                    "relative_path": "2026/07/26/artifact_bundle.zip",
                }
            },
            "error": None,
        }

        report = render_task_report(task, [])

        self.assertIn(
            "Diagnostic bundle: artifact_bundle / 4096 bytes / "
            "2026/07/26/artifact_bundle.zip",
            report,
        )

    async def test_renders_failure_reason_without_full_payload_noise(self) -> None:
        task = await self.runtime.run_settings_scroll_navigation_task(
            "fake:android-001",
            TARGET,
            EXPECTED,
            confirmed=False,
        )
        events = self.runtime.list_task_events(task["task_id"])

        report = render_task_report(task, events)

        self.assertIn("Status: failed", report)
        self.assertIn("error: CONFIRMATION_REQUIRED", report)
        self.assertIn("Code: CONFIRMATION_REQUIRED", report)
        self.assertIn("error=CONFIRMATION_REQUIRED", report)

    async def test_renders_agent_decision_summary(self) -> None:
        task = await self.runtime.run_agent_task(
            "fake:android-001",
            "open display settings",
            confirmed=True,
        )
        events = self.runtime.list_task_events(task["task_id"])

        report = render_task_report(task, events)

        self.assertIn("Type:   agent.run", report)
        self.assertIn("1. agent.round [succeeded]", report)
        self.assertIn("decision: app.launch", report)
        self.assertIn("decision: input.tap_element", report)
        self.assertIn("decision: finish", report)
        self.assertIn("source=rule", report)
        self.assertIn("confidence=1.00", report)

        task["steps"][0]["result"]["decision"]["repair_count"] = 1
        task["steps"][0]["result"]["decision"]["provider_retry_count"] = 1
        task["steps"][0]["result"]["decision"]["provider_attempt_count"] = 2
        task["steps"][0]["result"]["decision"]["provider_latency_ms"] = 1234
        repaired_report = render_task_report(task, events)
        self.assertIn("repair_count=1", repaired_report)
        self.assertIn("provider_retry_count=1", repaired_report)
        self.assertIn("provider_attempt_count=2", repaired_report)
        self.assertIn("provider_latency_ms=1234", repaired_report)

    def test_renders_only_whitelisted_error_diagnostics(self) -> None:
        task = {
            "task_id": "task_test",
            "task_type": "agent.run",
            "status": "failed",
            "device_id": "fake:android-001",
            "goal": "进入显示和亮度页面",
            "started_at": "2026-07-13T00:00:00Z",
            "completed_at": "2026-07-13T00:00:01Z",
            "steps": [],
            "error": {
                "code": "MODEL_OUTPUT_INVALID",
                "message": "input.tap_element selector 无效",
                "details": {
                    "failure_phase": "response_headers",
                    "elapsed_ms": 60001,
                    "total_elapsed_ms": 120005,
                    "provider_attempt_count": 2,
                    "selector_error_field": "unknown_fields",
                    "selector_unknown_keys": ["unexpected"],
                    "secret_response": "must-not-appear",
                },
            },
        }

        report = render_task_report(task, [])

        self.assertIn("selector_error_field=unknown_fields", report)
        self.assertIn("failure_phase=response_headers", report)
        self.assertIn("total_elapsed_ms=120005", report)
        self.assertIn('selector_unknown_keys=["unexpected"]', report)
        self.assertNotIn("must-not-appear", report)

    def test_renders_runtime_owned_completion(self) -> None:
        task = {
            "task_id": "task_test",
            "task_type": "agent.run",
            "status": "succeeded",
            "device_id": "fake:android-001",
            "goal": "进入显示页面",
            "goal_acceptance": {
                "foreground_app_id": "com.android.settings",
                "foreground_activity": ".DisplaySettings",
            },
            "completion_source": "runtime_acceptance",
            "started_at": "2026-07-13T00:00:00Z",
            "completed_at": "2026-07-13T00:00:01Z",
            "steps": [],
        }

        report = render_task_report(task, [])

        self.assertIn("Completion: runtime_acceptance", report)
        self.assertIn('"foreground_activity":".DisplaySettings"', report)
