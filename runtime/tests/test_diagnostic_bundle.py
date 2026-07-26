from __future__ import annotations

import hashlib
import json
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService


def _wait(runtime: RuntimeService, task_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        execution = runtime.get_task_execution(task_id)
        if execution["status"] in {"succeeded", "failed"}:
            return runtime.get_task(task_id)
        time.sleep(0.01)
    raise AssertionError("task did not reach a terminal state")


class DiagnosticBundleTests(unittest.TestCase):
    def test_requires_confirmation_before_any_device_or_artifact_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            adapter = FakeDeviceAdapter()
            store = ArtifactStore(Path(directory) / "artifacts")
            runtime = RuntimeService(adapter, store)

            status, payload = runtime.submit_diagnostic_bundle_task_sync(
                "fake:android-001",
                "com.example.fake",
                confirmed=False,
                idempotency_key="bundle-no",
            )

            self.assertEqual(403, status)
            self.assertEqual("CONFIRMATION_REQUIRED", payload["error"]["code"])
            self.assertEqual([], adapter.actions)
            self.assertEqual([], list(store.root.rglob("*")))

    def test_collects_fixed_local_bundle_and_verified_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            adapter = FakeDeviceAdapter()
            store = ArtifactStore(Path(directory) / "artifacts")
            runtime = RuntimeService(adapter, store)
            execution = runtime.submit_diagnostic_bundle_task_sync(
                "fake:android-001",
                "com.example.fake",
                200,
                "info",
                True,
                "bundle-success",
                30,
            )[1]["execution"]
            report = _wait(runtime, execution["task_id"])
            summary = report["evidence_summary"]
            bundle = summary["bundle_artifact"]
            bundle_path = store.resolve(bundle["relative_path"])

            with zipfile.ZipFile(bundle_path) as archive:
                self.assertEqual(
                    {
                        "manifest.json",
                        "screenshot.png",
                        "ui-tree.xml",
                        "device.log",
                        "performance.json",
                    },
                    set(archive.namelist()),
                )
                manifest = json.loads(archive.read("manifest.json"))
                for entry in manifest["entries"]:
                    data = archive.read(entry["name"])
                    self.assertEqual(entry["size_bytes"], len(data))
                    self.assertEqual(
                        entry["sha256"], hashlib.sha256(data).hexdigest()
                    )

        self.assertEqual("succeeded", report["status"])
        self.assertEqual("diagnostic_bundle", bundle["kind"])
        self.assertEqual("application/zip", bundle["content_type"])
        self.assertEqual(5, len(summary["artifact_refs"]))
        self.assertEqual(
            "com.example.fake", summary["app_state"]["app"]["app_id"]
        )
        self.assertEqual("info", summary["log_summary"]["minimum_level"])
        self.assertGreater(summary["log_summary"]["captured_bytes"], 0)
        self.assertIn("cpu", summary["performance_summary"])
        self.assertNotIn("pid", json.dumps(report))
        self.assertNotIn("user@example.com", json.dumps(report))

    def test_missing_bundle_capability_rejects_before_device_read(self) -> None:
        device = Device(
            "fake:limited",
            Platform.ANDROID,
            "Limited",
            "limited",
            "15",
            ConnectionState.ONLINE,
            ("screen.observe@1", "logs.collect@1", "performance.snapshot@1"),
        )
        with tempfile.TemporaryDirectory() as directory:
            adapter = FakeDeviceAdapter([device])
            runtime = RuntimeService(
                adapter, ArtifactStore(Path(directory) / "artifacts")
            )
            execution = runtime.submit_diagnostic_bundle_task_sync(
                "fake:limited",
                confirmed=True,
                idempotency_key="bundle-limited",
            )[1]["execution"]
            report = _wait(runtime, execution["task_id"])

        self.assertEqual("failed", report["status"])
        self.assertEqual("CAPABILITY_UNAVAILABLE", report["error"]["code"])
        self.assertEqual([], adapter.actions)

    def test_failure_preserves_completed_artifact_references(self) -> None:
        class PerformanceFailureAdapter(FakeDeviceAdapter):
            async def capture_performance(self, device_id: str) -> object:
                self.actions.append(("device.performance.capture", device_id))
                raise MobileAgentError(
                    "PERFORMANCE_SNAPSHOT_FAILED",
                    ErrorCategory.DEVICE,
                    "test failure",
                )

        with tempfile.TemporaryDirectory() as directory:
            adapter = PerformanceFailureAdapter()
            runtime = RuntimeService(
                adapter, ArtifactStore(Path(directory) / "artifacts")
            )
            execution = runtime.submit_diagnostic_bundle_task_sync(
                "fake:android-001",
                confirmed=True,
                idempotency_key="bundle-partial",
            )[1]["execution"]
            report = _wait(runtime, execution["task_id"])

        self.assertEqual("failed", report["status"])
        self.assertEqual("PERFORMANCE_SNAPSHOT_FAILED", report["error"]["code"])
        self.assertEqual(3, len(report["evidence_summary"]["artifact_refs"]))

    def test_invalid_log_request_is_rejected_before_submission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            adapter = FakeDeviceAdapter()
            runtime = RuntimeService(
                adapter, ArtifactStore(Path(directory) / "artifacts")
            )
            status, payload = runtime.submit_diagnostic_bundle_task_sync(
                "fake:android-001",
                max_log_lines=0,
                confirmed=True,
                idempotency_key="bundle-invalid",
            )

        self.assertEqual(400, status)
        self.assertEqual("INVALID_ARGUMENT", payload["error"]["code"])
        self.assertEqual([], adapter.actions)

    def test_contracts_and_manifest_define_medium_local_capture(self) -> None:
        root = Path(__file__).resolve().parents[2]
        request = json.loads(
            (
                root / "contracts/schemas/diagnostic-bundle-request.schema.json"
            ).read_text()
        )
        manifest = json.loads(
            (
                root
                / "runtime/mobile_agent/skills/manifests/device.diagnostics.bundle.json"
            ).read_text()
        )
        self.assertTrue(request["properties"]["confirmed"]["const"])
        self.assertEqual("medium", manifest["risk"])
        self.assertEqual(
            "zip_manifest_and_source_hashes_verified", manifest["verification"]
        )
