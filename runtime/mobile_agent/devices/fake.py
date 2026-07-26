"""Deterministic adapter used by tests and local demos."""

from __future__ import annotations

import struct
import uuid
from pathlib import Path
from datetime import datetime, timezone

from mobile_agent.domain.artifact import ArtifactKind, ArtifactWriter
from mobile_agent.domain.app import InstalledApp
from mobile_agent.domain.app_lifecycle import AppRuntimeState
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.device_log import DeviceLogLevel
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
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


def _fake_png(width: int = 2, height: int = 3) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", width, height) + b"fake"


def _fake_ui_xml(app_id: str, activity: str) -> bytes:
    if app_id == "com.android.settings" and activity == ".MainActivity":
        body = (
            '<node text="" resource-id="settings_list" class="android.view.View" '
            'package="com.android.settings" clickable="true" enabled="true" '
            'visible-to-user="true" bounds="[0,0][2,3]">'
            '<node text="Display" resource-id="settings_display" '
            'class="android.widget.TextView" package="com.android.settings" '
            'clickable="false" enabled="true" visible-to-user="true" bounds="[0,0][2,1]"/>'
            "</node>"
        )
    elif app_id == "com.android.settings" and activity == ".DisplaySettings":
        body = (
            '<node text="Display settings" resource-id="settings_title" '
            'class="android.widget.TextView" package="com.android.settings" '
            'clickable="false" enabled="true" visible-to-user="true" bounds="[0,0][2,1]"/>'
        )
    else:
        body = (
            '<node text="Fake home" resource-id="fake_home" class="android.view.View" '
            'package="com.example.fake" clickable="false" enabled="true" '
            'visible-to-user="true" bounds="[0,0][2,3]"/>'
        )
    if app_id == "com.example.form":
        body = (
            '<node text="" resource-id="search_box" class="android.widget.EditText" '
            'package="com.example.form" clickable="true" enabled="true" '
            'visible-to-user="true" bounds="[0,0][2,1]"/>'
        )
    return f'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">{body}</hierarchy>'.encode()


class FakeDeviceAdapter:
    """Return caller-provided devices without touching host tools."""

    def __init__(self, devices: list[Device] | None = None) -> None:
        self.foreground_app = "com.example.fake"
        self.foreground_activity = ".MainActivity"
        self.actions: list[tuple[object, ...]] = []
        self.custom_ui_xml: bytes | None = None
        self.install_target_app_id = "com.example.installed"
        self._installed_apps = {"com.android.settings", "com.example.fake"}
        self._running_apps = {"com.example.fake"}
        self._stopped_apps: set[str] = set()
        self._devices = devices if devices is not None else [
            Device(
                device_id="fake:android-001",
                platform=Platform.ANDROID,
                name="Fake Android Device",
                model="fake_android",
                os_version="15",
                connection=ConnectionState.ONLINE,
                capabilities=(
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
                ),
            )
        ]

    async def list_devices(self) -> list[Device]:
        return list(self._devices)

    async def observe(self, device_id: str, artifacts: ArtifactWriter) -> Observation:
        if not any(device.device_id == device_id for device in self._devices):
            raise MobileAgentError(
                code="DEVICE_NOT_FOUND",
                category=ErrorCategory.DEVICE,
                message="设备不存在",
            )
        screenshot_time = _now()
        screenshot = artifacts.write(
            ArtifactKind.SCREENSHOT, "image/png", _fake_png(), ".png"
        )

        ui_time = _now()
        ui_tree = artifacts.write(
            ArtifactKind.UI_TREE,
            "application/xml",
            self.custom_ui_xml
            if self.custom_ui_xml is not None
            else _fake_ui_xml(self.foreground_app, self.foreground_activity),
            ".xml",
        )
        app_time = _now()
        return Observation(
            observation_id=f"obs_{uuid.uuid4().hex}",
            device_id=device_id,
            captured_at=_now(),
            foreground_app=ForegroundApp(
                self.foreground_app, self.foreground_activity, app_time
            ),
            screen=ScreenObservation(
                2, 3, Orientation.PORTRAIT, screenshot_time, screenshot
            ),
            ui_tree=UiTreeObservation(ui_time, ui_tree),
            device_state=DeviceState.INTERACTIVE,
        )

    async def launch_app(self, device_id: str, app_id: str) -> None:
        self.foreground_app = app_id
        self.foreground_activity = ".MainActivity"
        self.actions.append(("app.launch", device_id, app_id))
        self._running_apps.add(app_id)
        self._stopped_apps.discard(app_id)

    async def press_back(self, device_id: str) -> None:
        self.actions.append(("navigation.back", device_id))

    async def press_home(self, device_id: str) -> None:
        self.foreground_app = "com.example.launcher"
        self.foreground_activity = ".Launcher"
        self.actions.append(("navigation.home", device_id))

    async def tap(self, device_id: str, x: int, y: int) -> None:
        self.actions.append(("input.tap", device_id, x, y))
        if (
            self.foreground_app == "com.android.settings"
            and self.foreground_activity == ".MainActivity"
            and (x, y) == (1, 1)
        ):
            self.foreground_activity = ".DisplaySettings"

    async def swipe(
        self, device_id: str, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int
    ) -> None:
        self.actions.append(("input.swipe", device_id, start_x, start_y, end_x, end_y, duration_ms))

    async def input_text(self, device_id: str, text: str) -> None:
        self.actions.append(("input.text", device_id, text))

    async def collect_logs(
        self, device_id: str, max_lines: int, minimum_level: DeviceLogLevel
    ) -> bytes:
        self.actions.append(("device.logs.capture", device_id, max_lines, minimum_level.value))
        return (
            b"07-15 10:00:00.000  100  100 I MobileAgent: connected user@example.com\n"
            b"07-15 10:00:00.001  100  100 I MobileAgent: ready\n"
        )

    async def capture_performance(
        self, device_id: str
    ) -> DevicePerformanceSnapshot:
        self.actions.append(("device.performance.capture", device_id))
        return DevicePerformanceSnapshot(
            snapshot_id=f"perf_{uuid.uuid4().hex}",
            device_id=device_id,
            captured_at=_now(),
            cpu_total_usage_percent=12.5,
            memory_total_bytes=8_000_000_000,
            memory_free_bytes=3_000_000_000,
            battery_level_percent=80.0,
            battery_temperature_celsius=31.0,
            battery_status="charging",
            battery_plugged="usb",
            uptime_seconds=3600.0,
            load_average_1m=1.0,
            load_average_5m=0.8,
            load_average_15m=0.6,
        )

    async def list_installed_apps(self, device_id: str) -> tuple[str, ...]:
        self.actions.append(("app.list", device_id))
        return tuple(sorted(self._installed_apps))

    async def inspect_installed_app(self, device_id: str, app_id: str) -> InstalledApp:
        self.actions.append(("app.inspect", device_id, app_id))
        if app_id not in self._installed_apps:
            raise MobileAgentError(
                code="APP_NOT_FOUND",
                category=ErrorCategory.DEVICE,
                message="设备上未安装该应用",
            )
        return InstalledApp(
            app_id, "1.0", 1, "com.android.vending", True,
            app_id.startswith("com.android."),
        )

    async def install_apk(
        self, device_id: str, apk_path: Path, replace_existing: bool
    ) -> None:
        self.actions.append(("app.install", device_id, apk_path.name, replace_existing))
        self._installed_apps.add(self.install_target_app_id)
        self._stopped_apps.add(self.install_target_app_id)

    async def uninstall_app(
        self, device_id: str, app_id: str, keep_data: bool
    ) -> None:
        self.actions.append(("app.uninstall", device_id, app_id, keep_data))
        self._installed_apps.discard(app_id)
        self._running_apps.discard(app_id)
        self._stopped_apps.discard(app_id)

    async def inspect_app_runtime_state(
        self, device_id: str, app: InstalledApp
    ) -> AppRuntimeState:
        self.actions.append(("app.state.inspect", device_id, app.app_id))
        if app.app_id not in self._installed_apps:
            raise MobileAgentError(
                "APP_NOT_FOUND", ErrorCategory.DEVICE, "设备上未安装该应用"
            )
        return AppRuntimeState(
            device_id,
            app,
            app.app_id in self._running_apps,
            self.foreground_app == app.app_id,
            app.app_id in self._stopped_apps,
            _now(),
        )

    async def force_stop_app(self, device_id: str, app_id: str) -> None:
        self.actions.append(("app.stop", device_id, app_id))
        self._running_apps.discard(app_id)
        self._stopped_apps.add(app_id)
        if self.foreground_app == app_id:
            self.foreground_app = "com.example.launcher"
            self.foreground_activity = ".Launcher"

    async def clear_app_data(self, device_id: str, app_id: str) -> None:
        self.actions.append(("app.data.clear", device_id, app_id))
        self._running_apps.discard(app_id)
        self._stopped_apps.add(app_id)
        if self.foreground_app == app_id:
            self.foreground_app = "com.example.launcher"
            self.foreground_activity = ".Launcher"
