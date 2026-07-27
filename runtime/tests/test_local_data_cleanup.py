from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.artifact import ArtifactKind
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.domain.local_data import LocalDataCleanupApprovalStore
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.runtime import RuntimeService
from mobile_agent.tools.local_data import LocalDataTool


NOW = 1_800_000_000.0


def _wait(runtime: RuntimeService, task_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        execution = runtime.get_task_execution(task_id)
        if execution["status"] in {"succeeded", "failed", "cancelled"}:
            return runtime.get_task(task_id)
        time.sleep(0.01)
    raise AssertionError("cleanup task did not reach a terminal state")


def _runtime(directory: str) -> tuple[RuntimeService, ArtifactStore]:
    store = ArtifactStore(Path(directory) / "artifacts")
    return (
        RuntimeService(
            FakeDeviceAdapter(),
            store,
            artifact_retention_days=7,
            wall_clock=lambda: NOW,
        ),
        store,
    )


def _artifact(
    store: ArtifactStore, age_days: int, payload: bytes
) -> tuple[str, Path]:
    artifact = store.write(
        ArtifactKind.DEVICE_LOG, "text/plain", payload, ".log"
    )
    path = store.resolve(artifact.relative_path)
    timestamp = NOW - age_days * 86400
    os.utime(path, (timestamp, timestamp))
    return artifact.artifact_id, path


class LocalDataCleanupTests(unittest.TestCase):
    def test_summary_is_read_only_bounded_and_ignores_unknown_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, store = _runtime(directory)
            _artifact(store, 10, b"old")
            _artifact(store, 1, b"newer")
            (store.root / "notes.txt").write_text("not an artifact")

            summary = runtime.local_storage_summary()

        self.assertEqual(2, summary["total_count"])
        self.assertEqual(8, summary["total_bytes"])
        self.assertEqual(1, summary["expired_count"])
        self.assertEqual(3, summary["expired_bytes"])
        self.assertEqual(2, summary["by_kind"]["device_log"]["count"])

    def test_prepare_has_no_delete_and_confirmation_precedes_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, store = _runtime(directory)
            _, old_path = _artifact(store, 10, b"old")
            approval = runtime.prepare_local_data_cleanup()

            status, payload = runtime.submit_local_data_cleanup_task_sync(
                approval["approval_id"], False, "cleanup-no"
            )

            self.assertEqual(403, status)
            self.assertEqual("CONFIRMATION_REQUIRED", payload["error"]["code"])
            self.assertTrue(old_path.exists())
            accepted = runtime.submit_local_data_cleanup_task_sync(
                approval["approval_id"], True, "cleanup-yes"
            )[1]["execution"]
            report = _wait(runtime, accepted["task_id"])

        self.assertEqual("succeeded", report["status"])

    def test_cleanup_deletes_only_exact_expired_set_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, store = _runtime(directory)
            old_id, old_path = _artifact(store, 10, b"old")
            _, new_path = _artifact(store, 1, b"new")
            approval = runtime.prepare_local_data_cleanup(7, 500)

            first = runtime.submit_local_data_cleanup_task(
                approval["approval_id"], True, "cleanup-same", 30
            )
            second = runtime.submit_local_data_cleanup_task(
                approval["approval_id"], True, "cleanup-same", 30
            )
            report = _wait(runtime, first["task_id"])
            self.assertFalse(old_path.exists())
            self.assertTrue(new_path.exists())

        self.assertEqual(first["task_id"], second["task_id"])
        self.assertEqual(1, report["evidence_summary"]["deleted_count"])
        self.assertEqual(
            [old_id], report["evidence_summary"]["deleted_artifact_ids"]
        )
        self.assertEqual("artifacts_absent", report["evidence_summary"]["verification"])
        self.assertIsNone(report.get("device_session_id"))

    def test_changed_candidate_is_rejected_without_deleting_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, store = _runtime(directory)
            _, old_path = _artifact(store, 10, b"old")
            approval = runtime.prepare_local_data_cleanup()
            old_path.write_bytes(b"changed")
            os.utime(old_path, (NOW - 10 * 86400, NOW - 10 * 86400))
            execution = runtime.submit_local_data_cleanup_task(
                approval["approval_id"], True, "cleanup-changed"
            )
            report = _wait(runtime, execution["task_id"])
            self.assertTrue(old_path.exists())

        self.assertEqual("failed", report["status"])
        self.assertEqual(
            "LOCAL_DATA_CLEANUP_SCOPE_CHANGED", report["error"]["code"]
        )

    def test_partial_failure_reports_completed_deletions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, store = _runtime(directory)
            first_id, first_path = _artifact(store, 11, b"first")
            _, second_path = _artifact(store, 10, b"second")
            approval = runtime.prepare_local_data_cleanup()
            second_path.write_bytes(b"changed")
            os.utime(
                second_path,
                (NOW - 10 * 86400, NOW - 10 * 86400),
            )
            execution = runtime.submit_local_data_cleanup_task(
                approval["approval_id"], True, "cleanup-partial"
            )
            report = _wait(runtime, execution["task_id"])
            self.assertFalse(first_path.exists())
            self.assertTrue(second_path.exists())

        self.assertEqual("failed", report["status"])
        self.assertEqual(
            [first_id], report["evidence_summary"]["deleted_artifact_ids"]
        )
        self.assertEqual(1, report["evidence_summary"]["deleted_count"])

    def test_historical_task_marks_cleaned_artifact_expired(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, store = _runtime(directory)
            execution = runtime.submit_device_logs_task_sync(
                "fake:android-001",
                100,
                "info",
                True,
                "logs-for-retention",
                30,
            )[1]["execution"]
            original = _wait(runtime, execution["task_id"])
            artifact = original["steps"][0]["result"]["artifact"]
            self.assertEqual("available", artifact["availability"])
            path = store.resolve(artifact["relative_path"])
            old = NOW - 10 * 86400
            os.utime(path, (old, old))
            approval = runtime.prepare_local_data_cleanup()
            cleanup = runtime.submit_local_data_cleanup_task(
                approval["approval_id"], True, "cleanup-history"
            )
            _wait(runtime, cleanup["task_id"])

            updated = runtime.get_task(execution["task_id"])

        self.assertEqual(
            "expired",
            updated["steps"][0]["result"]["artifact"]["availability"],
        )

    def test_single_cleanup_is_bounded_and_reports_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, store = _runtime(directory)
            _artifact(store, 10, b"one")
            _artifact(store, 11, b"two")

            approval = runtime.prepare_local_data_cleanup(7, 1)

        self.assertEqual(1, approval["candidate_count"])
        self.assertTrue(approval["truncated"])

    def test_prepare_ignores_hardlinked_and_oversized_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, store = _runtime(directory)
            _, linked_path = _artifact(store, 10, b"linked")
            os.link(linked_path, store.root / "artifact_hardlink.log")
            _, oversized_path = _artifact(store, 10, b"large")
            oversized_path.write_bytes(b"")
            oversized_path.touch()
            os.truncate(oversized_path, 64 * 1024 * 1024 + 1)
            old = NOW - 10 * 86400
            os.utime(oversized_path, (old, old))

            approval = runtime.prepare_local_data_cleanup()

        self.assertEqual(0, approval["candidate_count"])

    def test_cancellation_boundary_stops_before_next_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory) / "artifacts")
            _, first_path = _artifact(store, 11, b"first")
            _, second_path = _artifact(store, 10, b"second")
            tool = LocalDataTool(store, PolicyEngine(), lambda: NOW)
            cutoff, candidates, truncated = tool.prepare(7, 500)
            approval = LocalDataCleanupApprovalStore(
                lambda: NOW
            ).create(7, cutoff, candidates, truncated)
            checks = 0

            def cancelled() -> bool:
                nonlocal checks
                checks += 1
                return checks > 1

            deleted, _ = tool.cleanup(
                approval, True, cancellation_requested=cancelled
            )

            self.assertEqual(1, len(deleted))
            self.assertFalse(first_path.exists())
            self.assertTrue(second_path.exists())

    def test_contracts_and_manifest_define_scoped_high_risk_delete(self) -> None:
        root = Path(__file__).resolve().parents[2]
        approval = json.loads(
            (
                root
                / "contracts/schemas/local-data-cleanup-approval.schema.json"
            ).read_text()
        )
        manifest = json.loads(
            (
                root
                / "runtime/mobile_agent/skills/manifests/local.data.cleanup.json"
            ).read_text()
        )

        self.assertTrue(
            approval["properties"][
                "local_artifacts_will_be_permanently_deleted"
            ]["const"]
        )
        self.assertEqual("high", manifest["risk"])
        self.assertEqual(["local.data.cleanup"], manifest["tool_allowlist"])
