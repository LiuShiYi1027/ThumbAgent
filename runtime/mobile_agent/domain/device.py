"""Platform-neutral device contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


DEVICE_SCHEMA_VERSION = "1.0.0"


class Platform(str, Enum):
    ANDROID = "android"
    IOS = "ios"
    HARMONYOS = "harmonyos"


class ConnectionState(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNAUTHORIZED = "unauthorized"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Device:
    """A mobile device visible to the runtime."""

    device_id: str
    platform: Platform
    name: str
    model: str
    os_version: str
    connection: ConnectionState
    capabilities: tuple[str, ...] = ()
    schema_version: str = DEVICE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("device_id must not be empty")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("capabilities must be unique")

    def to_dict(self) -> dict[str, Any]:
        """Serialize using the public Device Contract."""

        return {
            "schema_version": self.schema_version,
            "device_id": self.device_id,
            "platform": self.platform.value,
            "name": self.name,
            "model": self.model,
            "os_version": self.os_version,
            "connection": self.connection.value,
            "capabilities": list(self.capabilities),
        }

