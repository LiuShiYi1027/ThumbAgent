"""Platform-neutral Device Adapter port."""

from __future__ import annotations

from typing import Protocol

from mobile_agent.domain.artifact import ArtifactWriter
from mobile_agent.domain.device import Device
from mobile_agent.domain.observation import Observation


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
