from __future__ import annotations

import struct
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.action import RiskLevel
from mobile_agent.domain.apk import ApkInspector, ApkInstallApprovalStore
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.runtime import RuntimeService
from runtime.tests.fakes import FakeProcessRunner, result


class TimeoutInstallAdapter(FakeDeviceAdapter):
    async def install_apk(
        self, device_id: str, apk_path: Path, replace_existing: bool
    ) -> None:
        self.actions.append(("app.install", device_id, apk_path.name, replace_existing))
        raise MobileAgentError(
            "ACTION_TIMEOUT", category=ErrorCategory.EXECUTION,
            message="test timeout", retryable=True,
        )


def _binary_manifest(app_id: str) -> bytes:
    values = ("manifest", "package", app_id)
    encoded = [bytes((len(value), len(value))) + value.encode() + b"\0" for value in values]
    offsets: list[int] = []
    cursor = 0
    for value in encoded:
        offsets.append(cursor)
        cursor += len(value)
    strings_start = 28 + len(values) * 4
    pool_size = strings_start + cursor
    pool = (
        struct.pack("<HHI", 0x0001, 28, pool_size)
        + struct.pack("<IIIII", len(values), 0, 0x100, strings_start, 0)
        + b"".join(struct.pack("<I", value) for value in offsets)
        + b"".join(encoded)
    )
    attribute = struct.pack("<IIIHBBI", 0xFFFFFFFF, 1, 2, 8, 0, 3, 2)
    extension = struct.pack("<IIHHHHHH", 0xFFFFFFFF, 0, 20, 20, 1, 0, 0, 0)
    start = struct.pack("<HHIII", 0x0102, 16, 56, 1, 0xFFFFFFFF) + extension + attribute
    total = 8 + len(pool) + len(start)
    return struct.pack("<HHI", 0x0003, 8, total) + pool + start


def _write_apk(root: Path, name: str = "sample.apk", app_id: str = "com.example.installed") -> Path:
    path = root / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("AndroidManifest.xml", _binary_manifest(app_id))
    return path


class ApkPreflightTests(unittest.TestCase):
    def test_inspects_manifest_hash_and_rejects_escape_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            apk = _write_apk(root)
            package = ApkInspector(root).inspect(str(apk))
            self.assertEqual("com.example.installed", package.app_id)
            self.assertEqual(64, len(package.sha256))

            escaped = _write_apk(Path(outside), "escaped.apk")
            with self.assertRaises(MobileAgentError) as escape:
                ApkInspector(root).inspect(str(escaped))
            self.assertEqual("APK_INVALID", escape.exception.code)

            link = root / "link.apk"
            link.symlink_to(apk)
            with self.assertRaises(MobileAgentError) as symlink:
                ApkInspector(root).inspect(str(link))
            self.assertEqual("APK_INVALID", symlink.exception.code)

    def test_approval_is_expiring_single_use_and_idempotent_for_same_key(self) -> None:
        now = [1000.0]
        with tempfile.TemporaryDirectory() as directory:
            package = ApkInspector(Path(directory)).inspect(str(_write_apk(Path(directory))))
            store = ApkInstallApprovalStore(lambda: now[0], ttl_seconds=10)
            approval = store.create("adb:one", package, False)
            self.assertEqual(approval.approval_id, store.claim(approval.approval_id, "key-1").approval_id)
            self.assertEqual(approval.approval_id, store.claim(approval.approval_id, "key-1").approval_id)
            with self.assertRaises(MobileAgentError):
                store.claim(approval.approval_id, "key-2")
            fresh = store.create("adb:one", package, False)
            now[0] = 1011.0
            with self.assertRaises(MobileAgentError) as expired:
                store.claim(fresh.approval_id, "key-3")
            self.assertEqual("APPROVAL_INVALID", expired.exception.code)

    def test_high_risk_policy_requires_internal_scoped_authorization(self) -> None:
        policy = PolicyEngine()
        with self.assertRaises(MobileAgentError):
            policy.authorize(RiskLevel.HIGH, confirmed=True)
        policy.authorize(RiskLevel.HIGH, confirmed=True, high_risk_authorized=True)


class ApkInstallRuntimeTests(unittest.TestCase):
    def test_install_timeout_is_unknown_and_not_retried(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "apks"
            root.mkdir()
            apk = _write_apk(root)
            adapter = TimeoutInstallAdapter()
            runtime = RuntimeService(
                adapter, ArtifactStore(Path(directory) / "artifacts"), apk_root=root
            )
            approval = runtime.prepare_apk_install_sync(
                "fake:android-001", str(apk), "com.example.installed"
            )[1]["approval"]
            submitted = runtime.submit_apk_install_task_sync(
                approval["approval_id"], True, "timeout-key", 30
            )[1]["execution"]
            deadline = time.monotonic() + 2
            execution = {}
            while time.monotonic() < deadline:
                execution = runtime.get_task_execution(submitted["task_id"])
                if execution["status"] in {"succeeded", "failed"}:
                    break
                time.sleep(0.01)
            report = runtime.get_task(submitted["task_id"])

        self.assertEqual("failed", execution["status"])
        self.assertEqual("ACTION_OUTCOME_UNKNOWN", report["error"]["code"])
        self.assertEqual("unknown_outcome", report["error"]["outcome"])
        self.assertEqual(1, sum(action[0] == "app.install" for action in adapter.actions))

    def test_prepare_rejects_missing_capability_before_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "apks"
            root.mkdir()
            apk = _write_apk(root)
            device = Device(
                "fake:limited", Platform.ANDROID, "Limited", "limited", "15",
                ConnectionState.ONLINE, ("app.inspect@1",),
            )
            adapter = FakeDeviceAdapter([device])
            runtime = RuntimeService(
                adapter, ArtifactStore(Path(directory) / "artifacts"), apk_root=root
            )
            status, payload = runtime.prepare_apk_install_sync(
                "fake:limited", str(apk), "com.example.installed"
            )
        self.assertEqual("CAPABILITY_UNAVAILABLE", payload["error"]["code"])
        self.assertFalse(any(action[0] == "app.install" for action in adapter.actions))

    def test_prepare_rejects_manifest_mismatch_before_device_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "apks"
            root.mkdir()
            apk = _write_apk(root, app_id="com.example.actual")
            adapter = FakeDeviceAdapter()
            runtime = RuntimeService(
                adapter, ArtifactStore(Path(directory) / "artifacts"), apk_root=root
            )
            status, payload = runtime.prepare_apk_install_sync(
                "fake:android-001", str(apk), "com.example.expected"
            )
        self.assertEqual(400, status.value)
        self.assertEqual("APK_PACKAGE_MISMATCH", payload["error"]["code"])
        self.assertEqual([], adapter.actions)

    def test_prepare_submit_and_verify_async_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "apks"
            root.mkdir()
            apk = _write_apk(root)
            adapter = FakeDeviceAdapter()
            runtime = RuntimeService(
                adapter, ArtifactStore(Path(directory) / "artifacts"), apk_root=root
            )
            approval = runtime.prepare_apk_install_sync(
                "fake:android-001", str(apk), "com.example.installed"
            )[1]["approval"]
            status, submitted = runtime.submit_apk_install_task_sync(
                approval["approval_id"], True, "install-key", 30
            )
            task_id = submitted["execution"]["task_id"]
            deadline = time.monotonic() + 2
            execution = {}
            while time.monotonic() < deadline:
                execution = runtime.get_task_execution(task_id)
                if execution["status"] in {"succeeded", "failed"}:
                    break
                time.sleep(0.01)
            report = runtime.get_task(task_id)

        self.assertEqual(202, status.value)
        self.assertEqual("succeeded", execution["status"])
        self.assertEqual("com.example.installed", report["evidence_summary"]["app"]["app_id"])
        self.assertEqual(64, len(report["evidence_summary"]["apk_sha256"]))
        self.assertIn(("app.install", "fake:android-001", "sample.apk", False), adapter.actions)

    def test_file_change_after_approval_is_rejected_before_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "apks"
            root.mkdir()
            apk = _write_apk(root)
            adapter = FakeDeviceAdapter()
            runtime = RuntimeService(
                adapter, ArtifactStore(Path(directory) / "artifacts"), apk_root=root
            )
            approval = runtime.prepare_apk_install_sync(
                "fake:android-001", str(apk), "com.example.installed"
            )[1]["approval"]
            _write_apk(root, app_id="com.example.changed")
            submitted = runtime.submit_apk_install_task_sync(
                approval["approval_id"], True, "changed-key", 30
            )[1]["execution"]
            deadline = time.monotonic() + 2
            execution = {}
            while time.monotonic() < deadline:
                execution = runtime.get_task_execution(submitted["task_id"])
                if execution["status"] in {"succeeded", "failed"}:
                    break
                time.sleep(0.01)
            report = runtime.get_task(submitted["task_id"])

        self.assertEqual("failed", execution["status"])
        self.assertEqual("APPROVAL_INVALID", report["error"]["code"])
        self.assertFalse(any(action[0] == "app.install" for action in adapter.actions))

    def test_submit_requires_confirmation_before_claiming_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "apks"
            root.mkdir()
            apk = _write_apk(root)
            store = ApkInstallApprovalStore()
            runtime = RuntimeService(
                FakeDeviceAdapter(), ArtifactStore(Path(directory) / "artifacts"),
                apk_root=root, apk_approval_store=store,
            )
            approval = runtime.prepare_apk_install_sync(
                "fake:android-001", str(apk), "com.example.installed"
            )[1]["approval"]
            status, payload = runtime.submit_apk_install_task_sync(
                approval["approval_id"], False, "unconfirmed-key", 30
            )
            claimed = store.claim(approval["approval_id"], "confirmed-key")
        self.assertEqual(403, status.value)
        self.assertEqual("CONFIRMATION_REQUIRED", payload["error"]["code"])
        self.assertEqual(approval["approval_id"], claimed.approval_id)


class AndroidApkInstallAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_install_uses_fixed_replace_arguments(self) -> None:
        command = ("-s", "serial-1", "install", "-r", "/approved/sample.apk")
        process = FakeProcessRunner({command: result(command, "Success\n")})
        runner = AdbRunner(Path("/safe/adb"), process)
        adapter = AndroidDeviceAdapter(runner, runner)
        await adapter.install_apk("adb:serial-1", Path("/approved/sample.apk"), True)
        self.assertEqual([command], [call[1] for call in process.calls])


if __name__ == "__main__":
    unittest.main()
