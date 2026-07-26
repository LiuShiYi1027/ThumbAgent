from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.devices.adapters.android.app_parser import parse_package_stopped
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.app import InstalledApp
from mobile_agent.domain.app_lifecycle import AppDataClearApprovalStore
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService
from runtime.tests.fakes import FakeProcessRunner, result


def _wait(runtime: RuntimeService, task_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        execution = runtime.get_task_execution(task_id)
        if execution["status"] in {"succeeded", "failed"}:
            return runtime.get_task(task_id)
        time.sleep(0.01)
    raise AssertionError("task did not reach a terminal state")


class TimeoutLifecycleAdapter(FakeDeviceAdapter):
    async def force_stop_app(self, device_id: str, app_id: str) -> None:
        self.actions.append(("app.stop", device_id, app_id))
        raise MobileAgentError(
            "ACTION_TIMEOUT",
            ErrorCategory.EXECUTION,
            "test timeout",
            retryable=True,
        )


class TimeoutDataClearAdapter(FakeDeviceAdapter):
    async def clear_app_data(self, device_id: str, app_id: str) -> None:
        self.actions.append(("app.data.clear", device_id, app_id))
        raise MobileAgentError(
            "ACTION_TIMEOUT",
            ErrorCategory.EXECUTION,
            "test timeout",
            retryable=True,
        )


class AppLifecycleRuntimeTests(unittest.TestCase):
    def _runtime(
        self,
        directory: str,
        adapter: FakeDeviceAdapter | None = None,
        approvals: AppDataClearApprovalStore | None = None,
    ) -> tuple[RuntimeService, FakeDeviceAdapter]:
        device = adapter or FakeDeviceAdapter()
        return (
            RuntimeService(
                device,
                ArtifactStore(Path(directory) / "artifacts"),
                app_data_clear_approval_store=approvals,
            ),
            device,
        )

    def test_state_inspection_is_read_only_and_privacy_minimized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, adapter = self._runtime(directory)
            status, payload = runtime.inspect_app_runtime_state_sync(
                "fake:android-001", "com.example.fake"
            )

        self.assertEqual(200, status)
        self.assertTrue(payload["state"]["foreground"])
        self.assertTrue(payload["state"]["process_present"])
        self.assertNotIn("pid", payload["state"])
        self.assertNotIn("raw", payload["state"])
        self.assertFalse(
            any(action[0] in {"app.stop", "app.data.clear"} for action in adapter.actions)
        )

    def test_launch_stop_and_data_clear_produce_verified_task_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, adapter = self._runtime(directory)
            launch = runtime.submit_app_launch_task_sync(
                "fake:android-001", "com.example.fake", "launch-key"
            )[1]["execution"]
            launch_report = _wait(runtime, launch["task_id"])
            stop = runtime.submit_app_stop_task_sync(
                "fake:android-001",
                "com.example.fake",
                True,
                "stop-key",
            )[1]["execution"]
            stop_report = _wait(runtime, stop["task_id"])
            approval = runtime.prepare_app_data_clear_sync(
                "fake:android-001", "com.example.fake"
            )[1]["approval"]
            clear = runtime.submit_app_data_clear_task_sync(
                approval["approval_id"], True, "clear-key"
            )[1]["execution"]
            clear_report = _wait(runtime, clear["task_id"])

        self.assertEqual("succeeded", launch_report["status"])
        self.assertEqual("launch", launch_report["evidence_summary"]["operation"])
        self.assertTrue(launch_report["evidence_summary"]["state"]["foreground"])
        self.assertEqual("succeeded", stop_report["status"])
        self.assertFalse(stop_report["evidence_summary"]["state"]["process_present"])
        self.assertEqual("succeeded", clear_report["status"])
        self.assertTrue(clear_report["evidence_summary"]["data_cleared"])
        self.assertIn("com.example.fake", adapter._installed_apps)
        self.assertEqual(
            1, sum(action[0] == "app.data.clear" for action in adapter.actions)
        )

    def test_stop_requires_confirmation_and_protects_system_apps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, adapter = self._runtime(directory)
            missing = runtime.submit_app_stop_task_sync(
                "fake:android-001", "com.example.fake", False, "stop-no"
            )
            protected = runtime.submit_app_stop_task_sync(
                "fake:android-001", "com.android.settings", True, "stop-system"
            )
            report = _wait(runtime, protected[1]["execution"]["task_id"])

        self.assertEqual(403, missing[0])
        self.assertEqual("CONFIRMATION_REQUIRED", missing[1]["error"]["code"])
        self.assertEqual("failed", report["status"])
        self.assertEqual("SYSTEM_APP_PROTECTED", report["error"]["code"])
        self.assertFalse(any(action[0] == "app.stop" for action in adapter.actions))

    def test_data_clear_approval_is_scoped_single_use_and_system_safe(self) -> None:
        now = [1000.0]
        store = AppDataClearApprovalStore(lambda: now[0], ttl_seconds=10)
        app = InstalledApp("com.example.fake", "1.0", 1, None, True, False)
        approval = store.create("fake:android-001", app)
        self.assertEqual(
            approval.approval_id,
            store.claim(approval.approval_id, "key-one").approval_id,
        )
        with self.assertRaises(MobileAgentError):
            store.claim(approval.approval_id, "key-two")
        now[0] = 1011
        expired = store.create("fake:android-001", app)
        now[0] = 1022
        with self.assertRaises(MobileAgentError) as raised:
            store.claim(expired.approval_id, "key-three")
        self.assertEqual("APPROVAL_INVALID", raised.exception.code)

        with tempfile.TemporaryDirectory() as directory:
            runtime, adapter = self._runtime(directory)
            status, payload = runtime.prepare_app_data_clear_sync(
                "fake:android-001", "com.android.settings"
            )
        self.assertEqual(403, status)
        self.assertEqual("SYSTEM_APP_PROTECTED", payload["error"]["code"])
        self.assertFalse(any(action[0] == "app.data.clear" for action in adapter.actions))

    def test_timeout_has_unknown_outcome_and_is_not_retried(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            adapter = TimeoutLifecycleAdapter()
            runtime, _ = self._runtime(directory, adapter)
            execution = runtime.submit_app_stop_task_sync(
                "fake:android-001", "com.example.fake", True, "stop-timeout"
            )[1]["execution"]
            report = _wait(runtime, execution["task_id"])

        self.assertEqual("failed", report["status"])
        self.assertEqual("ACTION_OUTCOME_UNKNOWN", report["error"]["code"])
        self.assertEqual("unknown_outcome", report["error"]["outcome"])
        self.assertEqual(1, sum(action[0] == "app.stop" for action in adapter.actions))

    def test_data_clear_timeout_has_unknown_outcome_and_is_not_retried(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            adapter = TimeoutDataClearAdapter()
            runtime, _ = self._runtime(directory, adapter)
            approval = runtime.prepare_app_data_clear_sync(
                "fake:android-001", "com.example.fake"
            )[1]["approval"]
            execution = runtime.submit_app_data_clear_task_sync(
                approval["approval_id"], True, "clear-timeout"
            )[1]["execution"]
            report = _wait(runtime, execution["task_id"])

        self.assertEqual("failed", report["status"])
        self.assertEqual("ACTION_OUTCOME_UNKNOWN", report["error"]["code"])
        self.assertEqual("unknown_outcome", report["error"]["outcome"])
        self.assertEqual(
            1, sum(action[0] == "app.data.clear" for action in adapter.actions)
        )

    def test_contracts_and_manifests_encode_risk_boundaries(self) -> None:
        root = Path(__file__).resolve().parents[2]
        approval = json.loads(
            (root / "contracts/schemas/app-data-clear-approval.schema.json").read_text()
        )
        stop = json.loads(
            (root / "runtime/mobile_agent/skills/manifests/app.stop.json").read_text()
        )
        clear = json.loads(
            (
                root / "runtime/mobile_agent/skills/manifests/app.data.clear.json"
            ).read_text()
        )

        self.assertTrue(approval["properties"]["confirmation_required"]["const"])
        self.assertEqual("medium", stop["risk"])
        self.assertEqual("high", clear["risk"])
        self.assertEqual("package_present_and_runtime_stopped", clear["verification"])


class AndroidAppLifecycleAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_state_uses_fixed_commands_and_returns_no_process_identifier(
        self,
    ) -> None:
        package = ("-s", "serial-1", "shell", "dumpsys", "package", "com.example.app")
        process = ("-s", "serial-1", "shell", "pidof", "com.example.app")
        window = ("-s", "serial-1", "shell", "dumpsys", "window")
        runner = FakeProcessRunner(
            {
                package: result(
                    package,
                    "Package [com.example.app]\n  User 0: installed=true stopped=false\n",
                ),
                process: result(process, "4321\n"),
                window: result(
                    window,
                    "mCurrentFocus=Window{1 u0 com.example.app/.MainActivity}\n",
                ),
            }
        )
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), runner))
        app = InstalledApp("com.example.app", "1.0", 1, None, True, False)

        state = await adapter.inspect_app_runtime_state("adb:serial-1", app)

        self.assertTrue(state.process_present)
        self.assertTrue(state.foreground)
        self.assertFalse(state.stopped)
        self.assertNotIn("4321", json.dumps(state.to_dict()))
        self.assertEqual([package, process, window], [call[1] for call in runner.calls])

    async def test_stop_and_clear_use_fixed_arguments(self) -> None:
        stop = ("-s", "serial-1", "shell", "am", "force-stop", "com.example.app")
        clear = (
            "-s",
            "serial-1",
            "shell",
            "pm",
            "clear",
            "--user",
            "0",
            "com.example.app",
        )
        process = FakeProcessRunner(
            {stop: result(stop), clear: result(clear, "Success\n")}
        )
        runner = AdbRunner(Path("/safe/adb"), process)
        adapter = AndroidDeviceAdapter(runner, install_runner=runner)

        await adapter.force_stop_app("adb:serial-1", "com.example.app")
        await adapter.clear_app_data("adb:serial-1", "com.example.app")

        self.assertEqual([stop, clear], [call[1] for call in process.calls])

    def test_package_stopped_parser_handles_known_and_unknown_states(self) -> None:
        self.assertTrue(parse_package_stopped("User 0: installed=true stopped=true"))
        self.assertFalse(parse_package_stopped("User 0: installed=true stopped=false"))
        self.assertIsNone(parse_package_stopped("Package [com.example.app]"))
