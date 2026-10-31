"""Run the standard Android baseline on an isolated, reproducible Emulator.

The script never wipes a personal AVD. It creates or reuses ThumbAgent_API_36,
only wipes that dedicated AVD when starting it, and only stops an Emulator
process started by this invocation. It is an explicit device_e2e entry point;
default unit/contract tests never invoke it.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, BinaryIO

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime"))

from mobile_agent.api.idempotency import stable_idempotency_key
from mobile_agent.api.server import RuntimeRequestHandler
from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = ROOT / "e2e-output" / "emulator-baseline"
AVD_NAME = "ThumbAgent_API_36"
SYSTEM_IMAGE = "system-images;android-36;google_apis;arm64-v8a"
DEVICE_TEMPLATE = "pixel_7"
SETTINGS_APP = "com.android.settings"
STABILITY_PATH = "/v1/tasks/skill.dsl.run/async"
TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled", "timed_out"})


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _run(
    args: Sequence[str | Path], *, timeout: float = 30, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run one fixed executable/argument vector without a shell."""

    return subprocess.run(
        [str(argument) for argument in args],
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


@dataclass(frozen=True, slots=True)
class AndroidSdk:
    """Resolved local Android tools required by the baseline."""

    root: Path
    adb: Path
    emulator: Path
    avdmanager: Path

    @classmethod
    def discover(cls) -> "AndroidSdk":
        configured = os.environ.get("ANDROID_HOME") or os.environ.get(
            "ANDROID_SDK_ROOT", ""
        )
        default = (
            Path.home() / "Library/Android/sdk"
            if sys.platform == "darwin"
            else Path.home() / "Android/Sdk"
        )
        root = Path(configured).expanduser() if configured else default
        adb = root / "platform-tools/adb"
        emulator = root / "emulator/emulator"
        avdmanager = root / "cmdline-tools/latest/bin/avdmanager"
        missing = [path for path in (adb, emulator, avdmanager) if not path.is_file()]
        if missing:
            raise RuntimeError(f"Android SDK 工具缺失: {', '.join(map(str, missing))}")
        image = root / "system-images/android-36/google_apis/arm64-v8a/package.xml"
        if not image.is_file():
            raise RuntimeError(
                "缺少 API 36 ARM64 系统镜像；请先运行: "
                f"{root / 'cmdline-tools/latest/bin/sdkmanager'} '{SYSTEM_IMAGE}'"
            )
        return cls(root, adb, emulator, avdmanager)

    def adb_command(self, *args: str, timeout: float = 30) -> subprocess.CompletedProcess[str]:
        return _run((self.adb, *args), timeout=timeout)

    def online_devices(self) -> set[str]:
        result = self.adb_command("devices")
        if result.returncode != 0:
            raise RuntimeError(f"adb devices 失败: {result.stderr.strip()}")
        return {
            fields[0]
            for line in result.stdout.splitlines()[1:]
            if len(fields := line.split()) >= 2 and fields[1] == "device"
        }


def _ensure_dedicated_avd(sdk: AndroidSdk) -> None:
    avd_home = Path(os.environ.get("ANDROID_AVD_HOME", Path.home() / ".android/avd"))
    if (avd_home / f"{AVD_NAME}.ini").is_file():
        return
    result = _run(
        (
            sdk.avdmanager,
            "create",
            "avd",
            "--name",
            AVD_NAME,
            "--package",
            SYSTEM_IMAGE,
            "--device",
            DEVICE_TEMPLATE,
        ),
        timeout=120,
        input_text="no\n",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"创建测试 AVD 失败: {(result.stderr or result.stdout).strip()}"
        )


def _find_running_avd(sdk: AndroidSdk) -> str | None:
    for serial in sorted(sdk.online_devices()):
        if not serial.startswith("emulator-"):
            continue
        result = sdk.adb_command("-s", serial, "emu", "avd", "name", timeout=10)
        if result.returncode == 0 and result.stdout.splitlines():
            if result.stdout.splitlines()[0].strip() == AVD_NAME:
                return serial
    return None


def _free_emulator_port() -> int:
    for port in range(5554, 5685, 2):
        sockets: list[socket.socket] = []
        try:
            for candidate in (port, port + 1):
                listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                listener.bind(("127.0.0.1", candidate))
                sockets.append(listener)
        except OSError:
            continue
        finally:
            for listener in sockets:
                listener.close()
        return port
    raise RuntimeError("没有可用的 Emulator console/adb 端口对")


@dataclass(slots=True)
class EmulatorSession:
    """One reused or script-owned Emulator process and its cleanup state."""

    sdk: AndroidSdk
    serial: str
    log_path: Path
    process: subprocess.Popen[bytes] | None = None
    log_handle: BinaryIO | None = None

    @property
    def started_by_script(self) -> bool:
        return self.process is not None

    @property
    def device_id(self) -> str:
        return f"adb:{self.serial}"

    @classmethod
    def start(cls, sdk: AndroidSdk, log_path: Path) -> "EmulatorSession":
        running_serial = _find_running_avd(sdk)
        if running_serial is not None:
            log_path.write_text(
                f"Reusing running {AVD_NAME} at {running_serial}; no wipe or stop.\n",
                encoding="utf-8",
            )
            return cls(sdk=sdk, serial=running_serial, log_path=log_path)

        port = _free_emulator_port()
        serial = f"emulator-{port}"
        log_handle = log_path.open("wb")
        try:
            process = subprocess.Popen(
                [
                    str(sdk.emulator),
                    "-avd",
                    AVD_NAME,
                    "-port",
                    str(port),
                    "-wipe-data",
                    "-no-snapshot-save",
                    "-no-window",
                    "-no-audio",
                    "-no-boot-anim",
                ],
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
            )
        except Exception:
            log_handle.close()
            raise
        session = cls(sdk, serial, log_path, process, log_handle)
        try:
            session._wait_until_booted()
        except Exception:
            session.close()
            raise
        return session

    def _wait_until_booted(self) -> None:
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            assert self.process is not None
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"Emulator 启动后提前退出，exit={self.process.returncode}；见 {self.log_path}"
                )
            result = self.sdk.adb_command(
                "-s", self.serial, "shell", "getprop", "sys.boot_completed", timeout=10
            )
            if result.returncode == 0 and result.stdout.strip() == "1":
                return
            time.sleep(2)
        raise RuntimeError(f"等待 Emulator 启动超时；见 {self.log_path}")

    def close(self) -> dict[str, Any]:
        """Stop only a process owned by this session; leave reused devices alone."""

        if self.process is None:
            return {
                "started_by_script": False,
                "stop_requested": False,
                "serial_online_after": self.serial in self.sdk.online_devices(),
            }
        try:
            result = self.sdk.adb_command(
                "-s", self.serial, "emu", "kill", timeout=15
            )
        except subprocess.TimeoutExpired:
            result = None
        try:
            exit_code = self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                exit_code = self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                exit_code = self.process.wait(timeout=10)
        finally:
            if self.log_handle is not None:
                self.log_handle.close()
        online_after = self.serial in self.sdk.online_devices()
        return {
            "started_by_script": True,
            "stop_requested": True,
            "adb_emu_kill_returncode": result.returncode if result is not None else None,
            "process_exit_code": exit_code,
            "serial_online_after": online_after,
        }


def _http_json(
    base_url: str,
    path: str,
    token: str,
    *,
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    method = "GET"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    request = urllib.request.Request(
        base_url + path, data=data, headers=headers, method=method
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


async def _stability_baseline(
    runtime: RuntimeService, device_id: str, output_dir: Path
) -> dict[str, Any]:
    """Submit the two-iteration stability task through the real REST adapter."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), RuntimeRequestHandler)
    token = secrets.token_hex(16)
    server.runtime = runtime
    server.api_token = token
    server.allowed_origins = frozenset()
    server.server_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    payload = {
        "device_id": device_id,
        "skill_id": "app.stability_test",
        "skill_version": "1.1.0",
        "inputs": {
            "app_id": SETTINGS_APP,
            "duration_seconds": 120,
            "max_actions": 2,
        },
        "confirmed": True,
        "deadline_seconds": 180,
    }
    key = stable_idempotency_key("emulator-e2e", STABILITY_PATH, payload)
    try:
        submitted = await asyncio.to_thread(
            _http_json,
            base_url,
            STABILITY_PATH,
            token,
            payload=payload,
            idempotency_key=key,
        )
        task_id = submitted["execution"]["task_id"]
        deadline = time.monotonic() + 200
        while True:
            execution_payload = await asyncio.to_thread(
                _http_json, base_url, f"/v1/task-executions/{task_id}", token
            )
            execution = execution_payload["execution"]
            if execution["status"] in TERMINAL_STATUSES:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError(f"稳定性任务轮询超时: {task_id}")
            await asyncio.sleep(1)
        task_payload = await asyncio.to_thread(
            _http_json, base_url, f"/v1/tasks/{task_id}", token
        )
        events_payload = await asyncio.to_thread(
            _http_json, base_url, f"/v1/task-executions/{task_id}/events", token
        )
    finally:
        await asyncio.to_thread(server.shutdown)
        server.server_close()
        thread.join(timeout=2)

    task = task_payload["task"]
    _write_json(output_dir / "stability-task.json", task)
    _write_json(output_dir / "stability-events.json", events_payload["events"])
    records = task["evidence_summary"]["step_records"]
    counts: dict[str, int] = {}
    for record in records:
        step_id = record["step_id"]
        counts[step_id] = counts.get(step_id, 0) + 1
    expected = {
        "launch_target_app": 1,
        "swipe_up": 2,
        "swipe_down": 2,
        "navigate_back": 2,
        "sample_performance": 2,
        "stress_traverse": 1,
        "collect_logs": 1,
        "relaunch_target_app": 1,
    }
    assert task["status"] == "succeeded", task.get("error")
    assert counts == expected, counts
    assert len(task["evidence_summary"]["sampling_series"]) == 2
    assert "crash_check" in task["evidence_summary"]
    return {
        "task_id": task_id,
        "status": task["status"],
        "execution_status": execution["status"],
        "step_counts": counts,
        "sampling_points": 2,
        "crash_check_present": True,
    }


async def _run_baseline(
    sdk: AndroidSdk, session: EmulatorSession, output_dir: Path
) -> list[dict[str, Any]]:
    artifacts = ArtifactStore(output_dir / "artifacts")
    runtime = RuntimeService(
        AndroidDeviceAdapter(AdbRunner(executable=sdk.adb)), artifacts
    )
    device_id = session.device_id
    scenarios: list[dict[str, Any]] = []

    devices = await runtime.list_devices()
    selected = next((device for device in devices if device["device_id"] == device_id), None)
    assert selected is not None, f"目标设备未被发现: {device_id}"
    readiness = await runtime.readiness()
    device_readiness = next(
        (
            item
            for item in readiness["devices"]
            if item["device"]["device_id"] == device_id
        ),
        None,
    )
    assert device_readiness is not None and device_readiness["status"] == "ready"
    scenarios.append(
        {
            "scenario": "device_readiness",
            "status": "passed",
            "device": selected,
            "readiness": device_readiness["status"],
        }
    )

    opened = await runtime.open_app(device_id, SETTINGS_APP)
    assert opened["success"] is True and opened["status"] == "succeeded", opened
    scenarios.append({"scenario": "open_settings", "status": "passed"})

    navigated = await runtime.navigate_app(device_id, "settings.display")
    assert navigated["success"] is True and navigated["status"] == "succeeded", navigated
    assert "display" in navigated["foreground_app"]["activity"].lower()
    scenarios.append(
        {
            "scenario": "display_navigation",
            "status": "passed",
            "activity": navigated["foreground_app"]["activity"],
        }
    )

    observation = await runtime.observe(device_id)
    assert observation["foreground_app"]["app_id"] == SETTINGS_APP
    assert "display" in observation["foreground_app"]["activity"].lower()
    screenshot = observation["screen"]["screenshot"]
    ui_tree = observation["ui_tree"]["artifact"]
    assert artifacts.resolve(screenshot["relative_path"]).is_file()
    assert artifacts.resolve(ui_tree["relative_path"]).is_file()
    _write_json(output_dir / "observation.json", observation)
    scenarios.append(
        {
            "scenario": "display_observation",
            "status": "passed",
            "screenshot_artifact_id": screenshot["artifact_id"],
            "ui_tree_artifact_id": ui_tree["artifact_id"],
        }
    )

    stability = await _stability_baseline(runtime, device_id, output_dir)
    scenarios.append({"scenario": "stability_budget", "status": "passed", **stability})

    final_observation = await runtime.observe(device_id)
    assert final_observation["foreground_app"]["app_id"] == SETTINGS_APP
    scenarios.append(
        {
            "scenario": "final_foreground",
            "status": "passed",
            "foreground_app": final_observation["foreground_app"],
        }
    )
    return scenarios


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = OUTPUT_ROOT / stamp
    output_dir.mkdir(parents=True, exist_ok=False)
    summary: dict[str, Any] = {
        "schema_version": "1.0.0",
        "suite": "android-emulator-baseline",
        "started_at": stamp,
        "avd": AVD_NAME,
        "system_image": SYSTEM_IMAGE,
        "status": "failed",
        "scenarios": [],
    }
    session: EmulatorSession | None = None
    try:
        sdk = AndroidSdk.discover()
        _ensure_dedicated_avd(sdk)
        session = EmulatorSession.start(sdk, output_dir / "emulator.log")
        summary["emulator"] = {
            "serial": session.serial,
            "started_by_script": session.started_by_script,
        }
        summary["scenarios"] = asyncio.run(
            _run_baseline(sdk, session, output_dir)
        )
        summary["status"] = "passed"
    except Exception as error:
        summary["error"] = {"type": type(error).__name__, "message": str(error)}
        (output_dir / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
        traceback.print_exc()
    finally:
        if session is not None:
            try:
                summary["cleanup"] = session.close()
                if session.started_by_script and summary["cleanup"]["serial_online_after"]:
                    summary["status"] = "failed"
                    summary["error"] = {
                        "type": "CleanupError",
                        "message": f"Emulator 仍在线: {session.serial}",
                    }
            except Exception as error:
                summary["status"] = "failed"
                summary["cleanup_error"] = {
                    "type": type(error).__name__,
                    "message": str(error),
                }
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        _write_json(output_dir / "summary.json", summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Emulator baseline: {summary['status']}；产物: {output_dir}")
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
