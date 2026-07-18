"""Platform-neutral Device Adapter port."""

from __future__ import annotations

from typing import Protocol

from mobile_agent.domain.artifact import ArtifactWriter
from mobile_agent.domain.device import Device
from mobile_agent.domain.device_log import DeviceLogLevel
from mobile_agent.domain.observation import Observation
from mobile_agent.domain.performance import DevicePerformanceSnapshot


class DeviceAdapter(Protocol):
    """The minimal adapter contract required by ITER-0001."""

    async def list_devices(self) -> list[Device]:
        """Return devices currently visible to the adapter."""
        ...

    async def observe(self, device_id: str, artifacts: ArtifactWriter) -> Observation:
        """Capture an immutable observation of one device."""
        ...

    async def launch_app(self, device_id: str, app_id: str) -> None: ...

    async def press_back(self, device_id: str) -> None: ...

    async def press_home(self, device_id: str) -> None: ...

    async def tap(self, device_id: str, x: int, y: int) -> None: ...

    async def swipe(
        self, device_id: str, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int
    ) -> None: ...

    async def input_text(self, device_id: str, text: str) -> None: ...

    async def collect_logs(
        self, device_id: str, max_lines: int, minimum_level: DeviceLogLevel
    ) -> bytes:
        """Return one bounded platform log snapshot for an online device."""
        ...

    async def capture_performance(
        self, device_id: str
    ) -> DevicePerformanceSnapshot:
        """Capture one aggregate performance snapshot without process details."""
        ...
