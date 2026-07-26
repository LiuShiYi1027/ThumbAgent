from __future__ import annotations

import tempfile
import time
import unittest
import json
from pathlib import Path

from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.app_removal import AppRemovalApprovalStore
from mobile_agent.domain.app import InstalledApp
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService
from runtime.tests.fakes import FakeProcessRunner, result


class TimeoutRemovalAdapter(FakeDeviceAdapter):
    async def uninstall_app(
        self, device_id: str, app_id: str, keep_data: bool
    ) -> None:
        self.actions.append(("app.uninstall", device_id, app_id, keep_data))
        raise MobileAgentError(
            "ACTION_TIMEOUT",
            ErrorCategory.EXECUTION,
            "test timeout",
            retryable=True,
        )


def _wait(runtime: RuntimeService, task_id: str) -> tuple[dict[str, object], dict[str, object]]:
    deadline = time.monotonic() + 2
    execution: dict[str, object] = {}
    while time.monotonic() < deadline:
        execution = runtime.get_task_execution(task_id)
        if execution["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.01)
    return execution, runtime.get_task(task_id)


class AppRemovalRuntimeTests(unittest.TestCase):
    def test_approval_expires_and_cannot_be_reused_by_another_request(self) -> None:
        now = [1000.0]
        store = AppRemovalApprovalStore(lambda: now[0], ttl_seconds=10)
        app = InstalledApp("com.example.app", "1.0", 1, None, True, False)
        approval = store.create("adb:one", app, False)
        self.assertEqual(
            approval.approval_id,
            store.claim(approval.approval_id, "key-1").approval_id,
        )
        with self.assertRaises(MobileAgentError):
            store.claim(approval.approval_id, "key-2")
        fresh = store.create("adb:one", app, False)
        now[0] = 1011.0
        with self.assertRaises(MobileAgentError) as expired:
            store.claim(fresh.approval_id, "key-3")
        self.assertEqual("APPROVAL_INVALID", expired.exception.code)

    def test_prepare_is_read_only_and_reports_data_deletion_impact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            adapter = FakeDeviceAdapter()
            runtime = RuntimeService(
                adapter, ArtifactStore(Path(directory) / "artifacts")
            )
            status, payload = runtime.prepare_app_removal_sync(
                "fake:android-001", "com.example.fake", keep_data=False
            )

        self.assertEqual(200, status)
        approval = payload["approval"]
        self.assertEqual("com.example.fake", approval["app"]["app_id"])
        self.assertFalse(approval["keep_data"])
        self.assertTrue(approval["application_data_will_be_deleted"])
        self.assertFalse(
            any(action[0] == "app.uninstall" for action in adapter.actions)
        )

    def test_system_app_is_rejected_before_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            adapter = FakeDeviceAdapter()
            runtime = RuntimeService(
                adapter, ArtifactStore(Path(directory) / "artifacts")
            )
            status, payload = runtime.prepare_app_removal_sync(
                "fake:android-001", "com.android.settings"
            )

        self.assertEqual(403, status)
        self.assertEqual("SYSTEM_APP_PROTECTED", payload["error"]["code"])
        self.assertFalse(
            any(action[0] == "app.uninstall" for action in adapter.actions)
        )

    def test_missing_capability_is_rejected_before_package_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            device = Device(
                "fake:limited",
                Platform.ANDROID,
                "Limited",
                "limited",
                "15",
                ConnectionState.ONLINE,
                ("app.inspect@1",),
            )
            adapter = FakeDeviceAdapter([device])
            runtime = RuntimeService(
                adapter, ArtifactStore(Path(directory) / "artifacts")
            )
            status, payload = runtime.prepare_app_removal_sync(
                "fake:limited", "com.example.fake"
            )

        self.assertEqual(503, status)
        self.assertEqual("CAPABILITY_UNAVAILABLE", payload["error"]["code"])
        self.assertEqual([], adapter.actions)

    def test_confirmation_is_required_and_approval_is_single_use(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            adapter = FakeDeviceAdapter()
            store = AppRemovalApprovalStore()
            runtime = RuntimeService(
                adapter,
                ArtifactStore(Path(directory) / "artifacts"),
                app_removal_approval_store=store,
            )
            approval = runtime.prepare_app_removal_sync(
                "fake:android-001", "com.example.fake"
            )[1]["approval"]
            status, payload = runtime.submit_app_removal_task_sync(
                approval["approval_id"], False, "remove-key"
            )

        self.assertEqual(403, status)
        self.assertEqual("CONFIRMATION_REQUIRED", payload["error"]["code"])
        self.assertFalse(
            any(action[0] == "app.uninstall" for action in adapter.actions)
        )

    def test_uninstall_runs_once_and_verifies_package_absence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            adapter = FakeDeviceAdapter()
            runtime = RuntimeService(
                adapter, ArtifactStore(Path(directory) / "artifacts")
            )
            approval = runtime.prepare_app_removal_sync(
                "fake:android-001", "com.example.fake", keep_data=True
            )[1]["approval"]
            submitted = runtime.submit_app_removal_task_sync(
                approval["approval_id"], True, "remove-success", 30
            )[1]["execution"]
            execution, report = _wait(runtime, submitted["task_id"])

        self.assertEqual("succeeded", execution["status"])
        self.assertEqual("succeeded", report["status"])
        self.assertEqual(
            "com.example.fake",
            report["evidence_summary"]["removed_app"]["app_id"],
        )
        self.assertTrue(report["evidence_summary"]["data_retained"])
        self.assertEqual("absent", report["evidence_summary"]["post_removal_state"])
        self.assertEqual(
            1, sum(action[0] == "app.uninstall" for action in adapter.actions)
        )

    def test_contracts_and_manifest_define_high_risk_scoped_removal(self) -> None:
        root = Path(__file__).resolve().parents[2]
        approval = json.loads(
            (root / "contracts/schemas/app-removal-approval.schema.json").read_text()
        )
        result_schema = json.loads(
            (root / "contracts/schemas/app-removal-result.schema.json").read_text()
        )
        manifest = json.loads(
            (
                root / "runtime/mobile_agent/skills/manifests/app.uninstall.json"
            ).read_text()
        )

        self.assertTrue(
            approval["properties"]["confirmation_required"]["const"]
        )
        self.assertEqual("app.uninstall", result_schema["properties"]["skill_id"]["const"])
        self.assertEqual("high", manifest["risk"])
        self.assertEqual(["app.uninstall@1", "app.inspect@1"], manifest["required_capabilities"])

    def test_timeout_is_unknown_outcome_and_is_not_retried(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            adapter = TimeoutRemovalAdapter()
            runtime = RuntimeService(
                adapter, ArtifactStore(Path(directory) / "artifacts")
            )
            approval = runtime.prepare_app_removal_sync(
                "fake:android-001", "com.example.fake"
            )[1]["approval"]
            submitted = runtime.submit_app_removal_task_sync(
                approval["approval_id"], True, "remove-timeout", 30
            )[1]["execution"]
            execution, report = _wait(runtime, submitted["task_id"])

        self.assertEqual("failed", execution["status"])
        self.assertEqual("ACTION_OUTCOME_UNKNOWN", report["error"]["code"])
        self.assertEqual("unknown_outcome", report["error"]["outcome"])
        self.assertEqual(
            1, sum(action[0] == "app.uninstall" for action in adapter.actions)
        )


class AndroidAppRemovalAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_fixed_uninstall_arguments(self) -> None:
        command = ("-s", "serial-1", "uninstall", "-k", "com.example.app")
        process = FakeProcessRunner({command: result(command, "Success\n")})
        runner = AdbRunner(Path("/safe/adb"), process)
        adapter = AndroidDeviceAdapter(runner, install_runner=runner)

        await adapter.uninstall_app(
            "adb:serial-1", "com.example.app", keep_data=True
        )

        self.assertEqual([command], [call[1] for call in process.calls])

    async def test_rejects_invalid_package_before_process_call(self) -> None:
        process = FakeProcessRunner({})
        runner = AdbRunner(Path("/safe/adb"), process)
        adapter = AndroidDeviceAdapter(runner, install_runner=runner)

        with self.assertRaises(MobileAgentError) as raised:
            await adapter.uninstall_app(
                "adb:serial-1", "bad package;id", keep_data=False
            )

        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)
        self.assertEqual([], process.calls)


if __name__ == "__main__":
    unittest.main()
