"""Deterministic adapter used by tests and local demos."""

from __future__ import annotations

import struct
import uuid
from datetime import datetime, timezone

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
    return f'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">{body}</hierarchy>'.encode()


class FakeDeviceAdapter:
    """Return caller-provided devices without touching host tools."""

    def __init__(self, devices: list[Device] | None = None) -> None:
        self.foreground_app = "com.example.fake"
        self.foreground_activity = ".MainActivity"
        self.actions: list[tuple[object, ...]] = []
        self._devices = devices or [
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
            _fake_ui_xml(self.foreground_app, self.foreground_activity),
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
