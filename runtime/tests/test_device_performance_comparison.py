from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.domain.performance_comparison import compare_performance_tasks
from mobile_agent.domain.task import TaskRun, TaskStatus, TaskStep
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService
from mobile_agent.tasks.store import InMemoryTaskStore


BASELINE_ID = "task_11111111111111111111111111111111"
CANDIDATE_ID = "task_22222222222222222222222222222222"


class PerformanceComparisonTests(unittest.TestCase):
    def test_compares_two_points_with_noise_thresholds(self) -> None:
        comparison = compare_performance_tasks(
            _task(BASELINE_ID, "2026-07-15T01:00:00Z", cpu=10, memory=50),
            _task(CANDIDATE_ID, "2026-07-15T01:05:00Z", cpu=13, memory=50.5),
        ).to_dict()

        self.assertEqual(300.0, comparison["interval_seconds"])
        self.assertTrue(comparison["same_device_session"])
        self.assertEqual(
            "increased", comparison["metrics"]["cpu_total_usage_percent"]["trend"]
        )
        self.assertEqual(
            "stable", comparison["metrics"]["memory_used_percent"]["trend"]
        )
        self.assertIn("cpu_total_usage_percent", comparison["summary"]["increased"])
        self.assertTrue(comparison["method"]["single_point_samples"])

    def test_missing_temperature_is_explicitly_unavailable(self) -> None:
        baseline = _task(BASELINE_ID, "2026-07-15T01:00:00Z", temperature=None)
        candidate = _task(CANDIDATE_ID, "2026-07-15T01:01:00Z", temperature=31)

        comparison = compare_performance_tasks(baseline, candidate).to_dict()

        temperature = comparison["metrics"]["battery_temperature_celsius"]
        self.assertIsNone(temperature["delta"])
        self.assertEqual("unavailable", temperature["trend"])

    def test_rejects_different_devices(self) -> None:
        candidate = _task(CANDIDATE_ID, "2026-07-15T01:01:00Z")
        candidate["device_id"] = "fake:other"

        with self.assertRaises(MobileAgentError) as raised:
            compare_performance_tasks(
                _task(BASELINE_ID, "2026-07-15T01:00:00Z"), candidate
            )

        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)
        self.assertEqual("device_mismatch", raised.exception.details["reason"])

    def test_rejects_candidate_that_precedes_baseline(self) -> None:
        with self.assertRaises(MobileAgentError) as raised:
            compare_performance_tasks(
                _task(BASELINE_ID, "2026-07-15T01:02:00Z"),
                _task(CANDIDATE_ID, "2026-07-15T01:01:00Z"),
            )

        self.assertEqual(
            "candidate_precedes_baseline", raised.exception.details["reason"]
        )

    def test_rejects_non_performance_or_failed_task(self) -> None:
        baseline = _task(BASELINE_ID, "2026-07-15T01:00:00Z")
        baseline["task_type"] = "agent.run"

        with self.assertRaises(MobileAgentError) as raised:
            compare_performance_tasks(
                baseline, _task(CANDIDATE_ID, "2026-07-15T01:01:00Z")
            )

        self.assertEqual("baseline_task_type", raised.exception.details["reason"])

    def test_runtime_comparison_is_local_and_does_not_touch_adapter(self) -> None:
        store = InMemoryTaskStore()
        store.save(_task_run(BASELINE_ID, "2026-07-15T01:00:00Z"))
        store.save(_task_run(CANDIDATE_ID, "2026-07-15T01:01:00Z", cpu=15))
        adapter = FakeDeviceAdapter()
        with tempfile.TemporaryDirectory() as directory:
            runtime = RuntimeService(
                adapter, ArtifactStore(Path(directory)), task_store=store
            )

            result = runtime.compare_device_performance(BASELINE_ID, CANDIDATE_ID)

        self.assertEqual("fake:android-001", result["device_id"])
        self.assertEqual([], adapter.actions)

    def test_runtime_rejects_same_task_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory))
            )

            status, payload = runtime.compare_device_performance_sync(
                BASELINE_ID, BASELINE_ID
            )

        self.assertEqual(400, status.value)
        self.assertEqual("INVALID_ARGUMENT", payload["error"]["code"])

    def test_contracts_are_versioned_and_strict(self) -> None:
        root = Path(__file__).resolve().parents[2] / "contracts/schemas"
        input_schema = json.loads(
            (root / "device-performance-comparison-input.schema.json").read_text()
        )
        result_schema = json.loads(
            (root / "device-performance-comparison.schema.json").read_text()
        )

        self.assertFalse(input_schema["additionalProperties"])
        self.assertEqual("1.0.0", result_schema["properties"]["schema_version"]["const"])
        self.assertTrue(
            result_schema["properties"]["method"]["properties"][
                "single_point_samples"
            ]["const"]
        )


def _task(
    task_id: str,
    captured_at: str,
    *,
    cpu: float = 10,
    memory: float = 50,
    temperature: float | None = 30,
) -> dict[str, object]:
    snapshot_suffix = "a" if task_id == BASELINE_ID else "b"
    snapshot = {
        "schema_version": "1.0.0",
        "snapshot_id": f"perf_{snapshot_suffix * 32}",
        "device_id": "fake:android-001",
        "captured_at": captured_at,
        "cpu": {"total_usage_percent": cpu},
        "memory": {
            "total_bytes": 8_000_000_000,
            "free_bytes": 4_000_000_000,
            "used_percent": memory,
        },
        "battery": {
            "level_percent": 80,
            "temperature_celsius": temperature,
            "status": "charging",
            "plugged": "usb",
        },
        "system": {
            "uptime_seconds": 3600,
            "load_average_1m": 1.0,
            "load_average_5m": 0.8,
            "load_average_15m": 0.6,
        },
    }
    return {
        "schema_version": "1.0.0",
        "task_id": task_id,
        "task_type": "device.performance.snapshot",
        "device_id": "fake:android-001",
        "goal": "采集设备聚合性能快照",
        "status": "succeeded",
        "started_at": captured_at,
        "completed_at": captured_at,
        "device_session_id": "session_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "steps": [{"result": {"snapshot": snapshot}}],
        "evidence_summary": {},
        "error": None,
    }


def _task_run(
    task_id: str, captured_at: str, *, cpu: float = 10
) -> TaskRun:
    payload = _task(task_id, captured_at, cpu=cpu)
    step = TaskStep(
        step_id=f"step_{task_id[-32:]}",
        sequence=1,
        kind="diagnostic",
        name="device.performance.snapshot",
        status=TaskStatus.SUCCEEDED,
        started_at=captured_at,
        completed_at=captured_at,
        result=payload["steps"][0]["result"],  # type: ignore[index]
    )
    return TaskRun(
        task_id=task_id,
        task_type="device.performance.snapshot",
        device_id="fake:android-001",
        goal="采集设备聚合性能快照",
        status=TaskStatus.SUCCEEDED,
        started_at=captured_at,
        completed_at=captured_at,
        steps=(step,),
        evidence_summary={},
        device_session_id="session_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )


if __name__ == "__main__":
    unittest.main()
