"""Device Adapter used when a required local transport is unavailable."""

from __future__ import annotations

from typing import NoReturn
from pathlib import Path

from mobile_agent.domain.artifact import ArtifactWriter
from mobile_agent.domain.app import InstalledApp
from mobile_agent.domain.device import Device
from mobile_agent.domain.device_log import DeviceLogLevel
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.domain.observation import Observation
from mobile_agent.domain.performance import DevicePerformanceSnapshot


class UnavailableDeviceAdapter:
    """Keep Runtime interfaces available while rejecting all device access."""

    def __init__(self, error: MobileAgentError) -> None:
        self._error = error

    def _raise(self) -> NoReturn:
        raise self._error

    async def list_devices(self) -> list[Device]:
        self._raise()

    async def observe(self, device_id: str, artifacts: ArtifactWriter) -> Observation:
        self._raise()

    async def launch_app(self, device_id: str, app_id: str) -> None:
        self._raise()

    async def press_back(self, device_id: str) -> None:
        self._raise()

    async def press_home(self, device_id: str) -> None:
        self._raise()

    async def tap(self, device_id: str, x: int, y: int) -> None:
        self._raise()

    async def swipe(
        self,
        device_id: str,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int,
    ) -> None:
        self._raise()

    async def input_text(self, device_id: str, text: str) -> None:
        self._raise()

    async def collect_logs(
        self, device_id: str, max_lines: int, minimum_level: DeviceLogLevel
    ) -> bytes:
        self._raise()

    async def capture_performance(
        self, device_id: str
    ) -> DevicePerformanceSnapshot:
        self._raise()

    async def list_installed_apps(self, device_id: str) -> tuple[str, ...]:
        self._raise()

    async def inspect_installed_app(self, device_id: str, app_id: str) -> InstalledApp:
        self._raise()

    async def install_apk(
        self, device_id: str, apk_path: Path, replace_existing: bool
    ) -> None:
        self._raise()

    async def uninstall_app(
        self, device_id: str, app_id: str, keep_data: bool
    ) -> None:
        self._raise()
