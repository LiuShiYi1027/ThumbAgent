"""Android Device Adapter backed by the constrained ADB runner."""

from __future__ import annotations

import asyncio
import struct
import uuid
import re
from pathlib import Path
from datetime import datetime, timezone

from mobile_agent.devices.adapters.android.adb import AdbRunner, AsyncProcessRunner
from mobile_agent.devices.adapters.android.app_parser import (
    parse_package_details,
    parse_package_list,
    parse_package_stopped,
    valid_app_id,
)
from mobile_agent.devices.adapters.android.notification_parser import (
    parse_notification_records,
)
from mobile_agent.devices.adapters.android.parser import (
    AdbDeviceRecord,
    extract_ui_xml,
    parse_adb_devices,
    parse_foreground_app,
)
from mobile_agent.devices.adapters.android.performance_parser import (
    parse_performance_snapshot,
)
from mobile_agent.domain.artifact import ArtifactKind, ArtifactWriter
from mobile_agent.domain.app import InstalledApp
from mobile_agent.domain.app_lifecycle import AppRuntimeState
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.device_log import DeviceLogLevel
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.navigation import NavigationTarget
from mobile_agent.domain.observation import (
    DeviceState,
    ForegroundApp,
    Observation,
    Orientation,
    ScreenObservation,
    UiTreeObservation,
)
from mobile_agent.domain.performance import DevicePerformanceSnapshot


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# The only Android actions app.navigate can reach. Callers never supply these
# strings; they are fixed per NavigationTarget enum and carry no extras.
_NAVIGATION_ACTIONS: dict[NavigationTarget, str] = {
    NavigationTarget.SETTINGS_HOME: "android.settings.SETTINGS",
    NavigationTarget.SETTINGS_WIFI: "android.settings.WIFI_SETTINGS",
    NavigationTarget.SETTINGS_BLUETOOTH: "android.settings.BLUETOOTH_SETTINGS",
    NavigationTarget.SETTINGS_WIRELESS: "android.settings.WIRELESS_SETTINGS",
    NavigationTarget.SETTINGS_DISPLAY: "android.settings.DISPLAY_SETTINGS",
    NavigationTarget.SETTINGS_SOUND: "android.settings.SOUND_SETTINGS",
    NavigationTarget.SETTINGS_STORAGE: "android.settings.INTERNAL_STORAGE_SETTINGS",
    NavigationTarget.SETTINGS_APPS: "android.settings.MANAGE_APPLICATIONS_SETTINGS",
    NavigationTarget.SETTINGS_SECURITY: "android.settings.SECURITY_SETTINGS",
    NavigationTarget.SETTINGS_LOCATION: "android.settings.LOCATION_SOURCE_SETTINGS",
    NavigationTarget.SETTINGS_DATE: "android.settings.DATE_SETTINGS",
    NavigationTarget.SETTINGS_LANGUAGE: "android.settings.LOCALE_SETTINGS",
    NavigationTarget.SETTINGS_ACCESSIBILITY: "android.settings.ACCESSIBILITY_SETTINGS",
    NavigationTarget.SETTINGS_ABOUT: "android.settings.DEVICE_INFO_SETTINGS",
}


class AndroidDeviceAdapter:
    """Discover Android devices and normalize them into Device Contracts."""

    def __init__(self, runner: AdbRunner, install_runner: AdbRunner | None = None) -> None:
        self._runner = runner
        self._install_runner = install_runner or AdbRunner(
            runner.executable, AsyncProcessRunner(timeout_seconds=180.0)
        )

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
                "input.swipe@1",
                "input.text@1",
                "logs.collect@1",
                "performance.snapshot@1",
                "app.inspect@1",
                "app.install@1",
                "app.uninstall@1",
                "app.state.inspect@1",
                "app.stop@1",
                "app.data.clear@1",
                "device.diagnostics.bundle@1",
                "app.navigate@1",
                "notifications.read@1",
                "input.unicode@1",
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
        screenshot_data = await self._capture_screenshot(serial)
        width, height = self._png_dimensions(screenshot_data)
        screenshot = artifacts.write(
            ArtifactKind.SCREENSHOT, "image/png", screenshot_data, ".png"
        )

        ui_time = _now()
        ui_xml = await self._capture_ui_tree(serial)
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

    async def _capture_ui_tree(self, serial: str) -> bytes:
        for attempt in range(2):
            result = await self._runner.run(
                "-s", serial, "exec-out", "uiautomator", "dump", "/dev/tty"
            )
            ui_xml = extract_ui_xml(result.stdout)
            if ui_xml:
                return ui_xml
            if attempt == 0:
                await asyncio.sleep(0.2)
        raise MobileAgentError(
            code="OBSERVATION_FAILED",
            category=ErrorCategory.DEVICE,
            message="无法读取设备 UI hierarchy",
            retryable=True,
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

    async def _capture_screenshot(self, serial: str) -> bytes:
        result = await self._runner.run("-s", serial, "exec-out", "screencap", "-p")
        signature = b"\x89PNG\r\n\x1a\n"
        if result.stdout.startswith(signature):
            return result.stdout
        offset = result.stdout.find(signature)
        prefix = result.stdout[:offset] if offset >= 0 else result.stdout
        if offset < 0 or b"Multiple displays were found" not in prefix:
            return result.stdout
        displays = await self._runner.run(
            "-s", serial, "shell", "dumpsys", "SurfaceFlinger", "--display-id"
        )
        match = re.search(r"Display\s+(\d+)\s+\(HWC display 0\)", displays.stdout_text)
        if match is None:
            raise MobileAgentError(
                code="OBSERVATION_FAILED",
                category=ErrorCategory.DEVICE,
                message="无法确定设备内置主屏 display ID",
                retryable=True,
            )
        recaptured = await self._runner.run(
            "-s", serial, "exec-out", "screencap", "-d", match.group(1), "-p"
        )
        return recaptured.stdout

    async def launch_app(self, device_id: str, app_id: str) -> None:
        serial = self._serial_from_device_id(device_id)
        if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", app_id):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="无效的应用标识",
            )
        if app_id == "com.android.settings":
            result = await self._runner.run(
                "-s",
                serial,
                "shell",
                "am",
                "start",
                "-W",
                "-a",
                "android.settings.SETTINGS",
                "-f",
                "0x14000000",
            )
        else:
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
        self._require_success(result.returncode, "无法启动应用", result.stderr_text)

    async def navigate_to(self, device_id: str, target: NavigationTarget) -> None:
        """Open one registered system settings page using a fixed action."""

        if not isinstance(target, NavigationTarget):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="导航目标必须是登记的 NavigationTarget 枚举",
            )
        action = _NAVIGATION_ACTIONS.get(target)
        if action is None:
            raise MobileAgentError(
                code="CAPABILITY_UNAVAILABLE",
                category=ErrorCategory.CAPABILITY,
                message="当前平台不支持该导航目标",
                details={"target": target.value},
            )
        serial = self._serial_from_device_id(device_id)
        argv = (
            "-s",
            serial,
            "shell",
            "am",
            "start",
            "-W",
            "-a",
            action,
            "-f",
            "0x14000000",
        )
        result = await self._runner.run(*argv)
        if result.returncode != 0:
            # MagicOS 等 ROM 拒绝 shell 冷启动 Settings Action（error 102），
            # 但允许 monkey LAUNCHER 预热进程；预热后有界重试一次原动作。
            # 这不是盲重试：预热是确定性的状态变更，动作 argv 不变。
            await self._warm_up_settings(serial)
            result = await self._runner.run(*argv)
        self._require_success(result.returncode, "无法打开目标系统页面", result.stderr_text)

    async def _warm_up_settings(self, serial: str) -> None:
        """Bring the Settings process alive via the launcher-category entry."""

        result = await self._runner.run(
            "-s",
            serial,
            "shell",
            "monkey",
            "-p",
            "com.android.settings",
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        )
        self._require_success(result.returncode, "无法预热系统设置应用", result.stderr_text)

    async def read_notifications(
        self, device_id: str
    ) -> list[tuple[str, str | None, int | None]]:
        """Read one notification snapshot, parse it and discard the raw dump.

        Bounding and privacy minimization for public output happen in the
        owning Tool; the Adapter already drops every field except package,
        platform-exposed title and post timestamp.
        """

        serial = self._serial_from_device_id(device_id)
        result = await self._runner.run(
            "-s", serial, "shell", "dumpsys", "notification"
        )
        if result.returncode != 0:
            raise MobileAgentError(
                code="NOTIFICATIONS_READ_FAILED",
                category=ErrorCategory.DEVICE,
                message="设备通知读取失败",
                retryable=True,
                suggested_action="确认设备在线、调试授权有效后重试",
            )
        records = parse_notification_records(result.stdout_text)
        if records is None:
            raise MobileAgentError(
                code="NOTIFICATIONS_READ_FAILED",
                category=ErrorCategory.DEVICE,
                message="设备通知输出格式无法识别",
                suggested_action="记录设备型号与系统版本并更新解析样本",
            )
        if not records:
            raise MobileAgentError(
                code="NOTIFICATIONS_READ_EMPTY",
                category=ErrorCategory.DEVICE,
                message="设备当前没有活动通知",
            )
        return records

    async def press_back(self, device_id: str) -> None:
        await self._key_event(device_id, "4")

    async def press_home(self, device_id: str) -> None:
        await self._key_event(device_id, "3")

    async def tap(self, device_id: str, x: int, y: int) -> None:
        serial = self._serial_from_device_id(device_id)
        result = await self._runner.run(
            "-s", serial, "shell", "input", "touchscreen", "tap", str(x), str(y)
        )
        self._require_success(result.returncode, "设备点击失败", result.stderr_text)

    async def swipe(
        self, device_id: str, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int
    ) -> None:
        serial = self._serial_from_device_id(device_id)
        result = await self._runner.run(
            "-s",
            serial,
            "shell",
            "input",
            "swipe",
            str(start_x),
            str(start_y),
            str(end_x),
            str(end_y),
            str(duration_ms),
        )
        self._require_success(result.returncode, "设备滑动失败", result.stderr_text)

    async def input_text(self, device_id: str, text: str) -> None:
        serial = self._serial_from_device_id(device_id)
        result = await self._runner.run("-s", serial, "shell", "input", "text", text)
        self._require_success(result.returncode, "设备文本输入失败", result.stderr_text)

    async def current_input_method(self, device_id: str) -> str:
        """Return the current default IME component id for one online device."""

        serial = self._serial_from_device_id(device_id)
        result = await self._runner.run(
            "-s", serial, "shell", "settings", "get", "secure", "default_input_method"
        )
        if result.returncode != 0:
            raise MobileAgentError(
                code="IME_SWITCH_FAILED",
                category=ErrorCategory.DEVICE,
                message="无法读取设备当前输入法",
                retryable=True,
            )
        ime_id = result.stdout_text.strip()
        if not ime_id or ime_id == "null":
            raise MobileAgentError(
                code="IME_SWITCH_FAILED",
                category=ErrorCategory.DEVICE,
                message="设备未报告当前默认输入法",
                retryable=True,
            )
        return ime_id

    async def installed_input_methods(self, device_id: str) -> tuple[str, ...]:
        """Return all installed IME component ids, including disabled ones."""

        return await self._list_input_methods(device_id, all_methods=True)

    async def enabled_input_methods(self, device_id: str) -> tuple[str, ...]:
        """Return currently enabled IME component ids."""

        return await self._list_input_methods(device_id, all_methods=False)

    async def _list_input_methods(self, device_id: str, all_methods: bool) -> tuple[str, ...]:
        serial = self._serial_from_device_id(device_id)
        argv = ["-s", serial, "shell", "ime", "list"]
        if all_methods:
            argv.append("-a")
        argv.append("-s")
        result = await self._runner.run(*argv)
        if result.returncode != 0:
            raise MobileAgentError(
                code="IME_SWITCH_FAILED",
                category=ErrorCategory.DEVICE,
                message="无法枚举设备输入法",
                retryable=True,
            )
        return tuple(
            line.strip() for line in result.stdout_text.splitlines() if line.strip()
        )

    async def enable_input_method(self, device_id: str, ime_id: str) -> None:
        """Enable one installed IME so it can become the default."""

        serial = self._serial_from_device_id(device_id)
        validated = self._validate_ime_id(ime_id)
        result = await self._runner.run("-s", serial, "shell", "ime", "enable", validated)
        self._require_ime_success(result.returncode, "无法启用目标输入法", result.stderr_text)

    async def set_input_method(self, device_id: str, ime_id: str) -> None:
        """Switch the default IME; also used to restore the previous one."""

        serial = self._serial_from_device_id(device_id)
        validated = self._validate_ime_id(ime_id)
        result = await self._runner.run("-s", serial, "shell", "ime", "set", validated)
        self._require_ime_success(result.returncode, "无法切换设备输入法", result.stderr_text)

    @staticmethod
    def _validate_ime_id(ime_id: str) -> str:
        """Accept only a component-style IME id; reject everything else."""

        if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+/[.A-Za-z0-9_$]+", ime_id):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="无效的输入法组件标识",
            )
        return ime_id

    @staticmethod
    def _require_ime_success(returncode: int, message: str, stderr: str = "") -> None:
        if returncode != 0:
            # MagicOS 等 ROM 可能拦截 ime set；统一映射为已知失败，由上层降级。
            raise MobileAgentError(
                code="IME_SWITCH_FAILED",
                category=ErrorCategory.DEVICE,
                message=message,
                retryable=True,
                suggested_action="确认 Helper IME 已安装且未被系统策略拦截；失败时降级为人工输入",
            )

    async def collect_logs(
        self, device_id: str, max_lines: int, minimum_level: DeviceLogLevel
    ) -> bytes:
        """Capture a finite logcat snapshot using only validated, constructed arguments."""

        if (
            not isinstance(max_lines, int)
            or isinstance(max_lines, bool)
            or max_lines < 1
            or max_lines > 2000
        ):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="日志行数必须在 1 到 2000 之间",
            )
        if not isinstance(minimum_level, DeviceLogLevel):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="日志级别无效",
            )
        priority = {
            DeviceLogLevel.VERBOSE: "V",
            DeviceLogLevel.DEBUG: "D",
            DeviceLogLevel.INFO: "I",
            DeviceLogLevel.WARN: "W",
            DeviceLogLevel.ERROR: "E",
            DeviceLogLevel.FATAL: "F",
        }[minimum_level]
        serial = self._serial_from_device_id(device_id)
        result = await self._runner.run(
            "-s",
            serial,
            "logcat",
            "-d",
            "-t",
            str(max_lines),
            "-v",
            "threadtime",
            f"*:{priority}",
        )
        if result.returncode != 0:
            raise MobileAgentError(
                code="LOG_CAPTURE_FAILED",
                category=ErrorCategory.DEVICE,
                message="设备日志采集失败",
                retryable=True,
                suggested_action="确认设备在线、调试授权有效后重试",
            )
        if not result.stdout:
            raise MobileAgentError(
                code="LOG_CAPTURE_EMPTY",
                category=ErrorCategory.DEVICE,
                message="设备没有返回符合条件的日志",
                retryable=True,
                suggested_action="降低最低日志级别或稍后重试",
            )
        return result.stdout

    async def capture_performance(
        self, device_id: str
    ) -> DevicePerformanceSnapshot:
        """Read fixed aggregate diagnostics and discard all process-level output."""

        serial = self._serial_from_device_id(device_id)
        commands = (
            ("shell", "dumpsys", "cpuinfo"),
            ("shell", "dumpsys", "meminfo"),
            ("shell", "dumpsys", "battery"),
            ("shell", "cat", "/proc/uptime"),
            ("shell", "cat", "/proc/loadavg"),
        )
        results = []
        for command in commands:
            result = await self._runner.run("-s", serial, *command)
            if result.returncode != 0:
                raise MobileAgentError(
                    code="PERFORMANCE_SNAPSHOT_FAILED",
                    category=ErrorCategory.DEVICE,
                    message="设备聚合性能采集失败",
                    retryable=True,
                    suggested_action="确认设备在线、调试授权有效后重试",
                )
            results.append(result.stdout_text)
        return parse_performance_snapshot(device_id, *results)

    async def list_installed_apps(self, device_id: str) -> tuple[str, ...]:
        """List package identifiers using a fixed package-manager command."""

        serial = self._serial_from_device_id(device_id)
        result = await self._runner.run(
            "-s", serial, "shell", "pm", "list", "packages", "--user", "0"
        )
        if result.returncode != 0:
            raise MobileAgentError(
                code="APP_INVENTORY_FAILED",
                category=ErrorCategory.DEVICE,
                message="无法读取设备应用清单",
                retryable=True,
            )
        return parse_package_list(result.stdout_text)

    async def inspect_installed_app(self, device_id: str, app_id: str) -> InstalledApp:
        """Inspect one validated package without exposing raw dumpsys output."""

        if not valid_app_id(app_id):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="无效的应用标识",
            )
        serial = self._serial_from_device_id(device_id)
        result = await self._runner.run(
            "-s", serial, "shell", "dumpsys", "package", app_id
        )
        if result.returncode != 0:
            raise MobileAgentError(
                code="APP_INVENTORY_FAILED",
                category=ErrorCategory.DEVICE,
                message="无法读取应用详情",
                retryable=True,
            )
        if f"Package [{app_id}]" not in result.stdout_text:
            raise MobileAgentError(
                code="APP_NOT_FOUND",
                category=ErrorCategory.DEVICE,
                message="设备上未安装该应用",
            )
        return parse_package_details(app_id, result.stdout_text)

    async def install_apk(
        self, device_id: str, apk_path: Path, replace_existing: bool
    ) -> None:
        """Install one already inspected APK with a fixed argument shape."""

        serial = self._serial_from_device_id(device_id)
        arguments = ["-s", serial, "install"]
        if replace_existing:
            arguments.append("-r")
        arguments.append(str(apk_path))
        result = await self._install_runner.run(*arguments)
        if result.returncode != 0:
            raise MobileAgentError(
                code="APK_INSTALL_FAILED",
                category=ErrorCategory.DEVICE,
                message="设备拒绝安装 APK",
                suggested_action="检查 APK 签名、版本兼容性、设备空间和系统安装策略",
            )

    async def uninstall_app(
        self, device_id: str, app_id: str, keep_data: bool
    ) -> None:
        """Uninstall one validated package with a fixed argument shape."""

        if not valid_app_id(app_id):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="无效的应用标识",
            )
        serial = self._serial_from_device_id(device_id)
        arguments = ["-s", serial, "uninstall"]
        if keep_data:
            arguments.append("-k")
        arguments.append(app_id)
        result = await self._install_runner.run(*arguments)
        if result.returncode != 0:
            raise MobileAgentError(
                code="APP_UNINSTALL_FAILED",
                category=ErrorCategory.DEVICE,
                message="设备拒绝卸载应用",
                suggested_action="检查应用是否受设备管理策略保护，并只读确认当前安装状态",
            )

    async def inspect_app_runtime_state(
        self, device_id: str, app: InstalledApp
    ) -> AppRuntimeState:
        """Read bounded lifecycle state using fixed package/process/window commands."""

        if not valid_app_id(app.app_id):
            raise MobileAgentError(
                "INVALID_ARGUMENT", ErrorCategory.VALIDATION, "无效的应用标识"
            )
        serial = self._serial_from_device_id(device_id)
        package_result = await self._runner.run(
            "-s", serial, "shell", "dumpsys", "package", app.app_id
        )
        if (
            package_result.returncode != 0
            or f"Package [{app.app_id}]" not in package_result.stdout_text
        ):
            raise MobileAgentError(
                "APP_NOT_FOUND", ErrorCategory.DEVICE, "设备上未安装该应用"
            )
        process_result = await self._runner.run(
            "-s", serial, "shell", "pidof", app.app_id
        )
        if process_result.returncode not in {0, 1}:
            raise MobileAgentError(
                "APP_STATE_INSPECTION_FAILED",
                ErrorCategory.DEVICE,
                "无法读取应用进程状态",
                retryable=True,
            )
        window_result = await self._runner.run(
            "-s", serial, "shell", "dumpsys", "window"
        )
        if window_result.returncode != 0:
            raise MobileAgentError(
                "APP_STATE_INSPECTION_FAILED",
                ErrorCategory.DEVICE,
                "无法读取前台应用状态",
                retryable=True,
            )
        foreground_app, _ = parse_foreground_app(window_result.stdout_text)
        return AppRuntimeState(
            device_id,
            app,
            process_result.returncode == 0 and bool(process_result.stdout_text.strip()),
            foreground_app == app.app_id,
            parse_package_stopped(package_result.stdout_text),
            _now(),
        )

    async def force_stop_app(self, device_id: str, app_id: str) -> None:
        """Force-stop one validated package using a fixed command."""

        if not valid_app_id(app_id):
            raise MobileAgentError(
                "INVALID_ARGUMENT", ErrorCategory.VALIDATION, "无效的应用标识"
            )
        serial = self._serial_from_device_id(device_id)
        result = await self._runner.run(
            "-s", serial, "shell", "am", "force-stop", app_id
        )
        if result.returncode != 0:
            raise MobileAgentError(
                "APP_STOP_FAILED",
                ErrorCategory.DEVICE,
                "设备拒绝停止应用",
                suggested_action="检查设备管理策略并只读确认应用当前状态",
            )

    async def clear_app_data(self, device_id: str, app_id: str) -> None:
        """Clear one validated package using fixed package-manager arguments."""

        if not valid_app_id(app_id):
            raise MobileAgentError(
                "INVALID_ARGUMENT", ErrorCategory.VALIDATION, "无效的应用标识"
            )
        serial = self._serial_from_device_id(device_id)
        result = await self._install_runner.run(
            "-s", serial, "shell", "pm", "clear", "--user", "0", app_id
        )
        if result.returncode != 0 or result.stdout_text.strip() != "Success":
            raise MobileAgentError(
                "APP_DATA_CLEAR_FAILED",
                ErrorCategory.DEVICE,
                "设备拒绝清除应用数据",
                suggested_action="检查设备管理策略，并只读确认应用和运行状态",
            )

    async def _key_event(self, device_id: str, key_code: str) -> None:
        serial = self._serial_from_device_id(device_id)
        result = await self._runner.run("-s", serial, "shell", "input", "keyevent", key_code)
        self._require_success(result.returncode, "设备按键失败", result.stderr_text)

    @staticmethod
    def _require_success(returncode: int, message: str, stderr: str = "") -> None:
        if returncode != 0:
            if "SecurityException" in stderr and "INJECT_EVENTS" in stderr:
                raise MobileAgentError(
                    code="DEVICE_UNAUTHORIZED",
                    category=ErrorCategory.DEVICE,
                    message="设备当前未授权 ADB 注入输入事件",
                    retryable=False,
                    suggested_action="检查设备系统限制、开发者选项或更换允许 ADB 输入注入的测试设备",
                    details={"reason": "input_event_injection_denied"},
                )
            raise MobileAgentError(
                code="ACTION_FAILED",
                category=ErrorCategory.EXECUTION,
                message=message,
                retryable=True,
            )
