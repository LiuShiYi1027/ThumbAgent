"""Platform-neutral installed application contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class InstalledApp:
    """One installed application as observed from the device package manager."""

    app_id: str
    version_name: str | None = None
    version_code: int | None = None
    installer_app_id: str | None = None
    enabled: bool | None = None
    system_app: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_id": self.app_id,
            "version_name": self.version_name,
            "version_code": self.version_code,
            "installer_app_id": self.installer_app_id,
            "enabled": self.enabled,
            "system_app": self.system_app,
        }


@dataclass(frozen=True, slots=True)
class AppInventory:
    """A bounded installed application listing."""

    device_id: str
    apps: tuple[InstalledApp, ...]
    total_matched: int
    truncated: bool
    prefix: str | None = None
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "device_id": self.device_id,
            "apps": [app.to_dict() for app in self.apps],
            "total_matched": self.total_matched,
            "truncated": self.truncated,
            "prefix": self.prefix,
        }
