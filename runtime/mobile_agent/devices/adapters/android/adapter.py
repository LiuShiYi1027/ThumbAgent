"""Android Device Adapter backed by the constrained ADB runner."""

from __future__ import annotations

import asyncio
import struct
import uuid
import re
from datetime import datetime, timezone

from mobile_agent.devices.adapters.android.adb import AdbRunner
from mobile_agent.devices.adapters.android.parser import (
    AdbDeviceRecord,
    extract_ui_xml,
    parse_adb_devices,
    parse_foreground_app,
)
from mobile_agent.domain.artifact import ArtifactKind, ArtifactWriter
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.observation import (
    DeviceState,
    ForegroundApp,
    Observation,
    Orientation,
    ScreenObservation,
    UiTreeObservation,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AndroidDeviceAdapter:
    """Discover Android devices and normalize them into Device Contracts."""

    def __init__(self, runner: AdbRunner) -> None:
        self._runner = runner

    async def list_devices(self) -> list[Device]:
        result = await self._runner.run("devices", "-l")
        if result.returncode != 0:
            raise MobileAgentError(
                code="DEVICE_DISCOVERY_FAILED",
                category=ErrorCategory.DEVICE,
                message="无法读取 Android 设备列表",
                retryable=True,
                details={"adb_exit_code": result.returncode},
            )
        records = parse_adb_devices(result.stdout_text)
        return list(await asyncio.gather(*(self._to_device(record) for record in records)))

    async def _to_device(self, record: AdbDeviceRecord) -> Device:
        model = record.properties.get("model", "")
        name = record.properties.get("device", "") or model or record.serial
        os_version = ""
        capabilities: tuple[str, ...] = ()
        if record.connection is ConnectionState.ONLINE:
            capabilities = (
                "device.inspect@1",
                "screen.observe@1",
                "app.launch@1",
                "navigation.back@1",
                "navigation.home@1",
                "input.tap@1",
            )
            os_version = await self._read_os_version(record.serial)
        return Device(
            device_id=f"adb:{record.serial}",
            platform=Platform.ANDROID,
            name=name,
            model=model,
            os_version=os_version,
            connection=record.connection,
            capabilities=capabilities,
        )

    async def _read_os_version(self, serial: str) -> str:
        result = await self._runner.run(
            "-s", serial, "shell", "getprop", "ro.build.version.release"
        )
        if result.returncode != 0:
            return ""
        return result.stdout_text.strip()[:64]

    async def observe(self, device_id: str, artifacts: ArtifactWriter) -> Observation:
        serial = self._serial_from_device_id(device_id)
        devices = await self.list_devices()
        device = next((item for item in devices if item.device_id == device_id), None)
        if device is None:
            raise MobileAgentError(
                code="DEVICE_NOT_FOUND",
                category=ErrorCategory.DEVICE,
                message="设备不存在",
            )
        if device.connection is not ConnectionState.ONLINE:
            raise MobileAgentError(
                code="DEVICE_OFFLINE",
                category=ErrorCategory.DEVICE,
                message="设备当前不可交互",
                retryable=True,
                details={"connection": device.connection.value},
            )

        app_time = _now()
        app_result = await self._runner.run("-s", serial, "shell", "dumpsys", "window")
        app_id, activity = parse_foreground_app(app_result.stdout_text)

        screenshot_time = _now()
        screenshot_result = await self._runner.run("-s", serial, "exec-out", "screencap", "-p")
        screenshot_data = screenshot_result.stdout
        width, height = self._png_dimensions(screenshot_data)
        screenshot = artifacts.write(
            ArtifactKind.SCREENSHOT, "image/png", screenshot_data, ".png"
        )

        ui_time = _now()
        ui_result = await self._runner.run(
            "-s", serial, "exec-out", "uiautomator", "dump", "/dev/tty"
        )
        ui_xml = extract_ui_xml(ui_result.stdout)
        if not ui_xml:
            raise MobileAgentError(
                code="OBSERVATION_FAILED",
                category=ErrorCategory.DEVICE,
                message="无法读取设备 UI hierarchy",
                retryable=True,
            )
        ui_tree = artifacts.write(
            ArtifactKind.UI_TREE, "application/xml", ui_xml, ".xml"
        )

        orientation = (
            Orientation.PORTRAIT
            if height > width
            else Orientation.LANDSCAPE
            if width > height
            else Orientation.SQUARE
        )
        return Observation(
            observation_id=f"obs_{uuid.uuid4().hex}",
            device_id=device_id,
            captured_at=_now(),
            foreground_app=ForegroundApp(app_id, activity, app_time),
            screen=ScreenObservation(width, height, orientation, screenshot_time, screenshot),
            ui_tree=UiTreeObservation(ui_time, ui_tree),
            device_state=DeviceState.UNKNOWN,
        )

    @staticmethod
    def _serial_from_device_id(device_id: str) -> str:
        prefix = "adb:"
        if not device_id.startswith(prefix) or len(device_id) == len(prefix):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="无效的 Android device_id",
            )
        serial = device_id[len(prefix) :]
        if any(character in serial for character in "\x00\r\n"):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="无效的 Android device_id",
            )
        return serial

    @staticmethod
    def _png_dimensions(data: bytes) -> tuple[int, int]:
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise MobileAgentError(
                code="OBSERVATION_FAILED",
                category=ErrorCategory.DEVICE,
                message="设备截图不是有效 PNG",
                retryable=True,
            )
        width, height = struct.unpack(">II", data[16:24])
        if width <= 0 or height <= 0:
            raise MobileAgentError(
                code="OBSERVATION_FAILED",
                category=ErrorCategory.DEVICE,
                message="设备截图尺寸无效",
            )
        return width, height

    async def launch_app(self, device_id: str, app_id: str) -> None:
        serial = self._serial_from_device_id(device_id)
        if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", app_id):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="无效的应用标识",
            )
        result = await self._runner.run(
            "-s",
            serial,
            "shell",
            "monkey",
            "-p",
            app_id,
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        )
        self._require_success(result.returncode, "无法启动应用")

    async def press_back(self, device_id: str) -> None:
        await self._key_event(device_id, "4")

    async def press_home(self, device_id: str) -> None:
        await self._key_event(device_id, "3")

    async def tap(self, device_id: str, x: int, y: int) -> None:
        serial = self._serial_from_device_id(device_id)
        result = await self._runner.run("-s", serial, "shell", "input", "tap", str(x), str(y))
        self._require_success(result.returncode, "设备点击失败")

    async def _key_event(self, device_id: str, key_code: str) -> None:
        serial = self._serial_from_device_id(device_id)
        result = await self._runner.run("-s", serial, "shell", "input", "keyevent", key_code)
        self._require_success(result.returncode, "设备按键失败")

    @staticmethod
    def _require_success(returncode: int, message: str) -> None:
        if returncode != 0:
            raise MobileAgentError(
                code="ACTION_FAILED",
                category=ErrorCategory.EXECUTION,
                message=message,
                retryable=True,
            )
