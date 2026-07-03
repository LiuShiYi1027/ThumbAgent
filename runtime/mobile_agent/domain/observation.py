"""Platform-neutral immutable Observation contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from mobile_agent.domain.artifact import Artifact


OBSERVATION_SCHEMA_VERSION = "1.0.0"


class Orientation(str, Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    SQUARE = "square"


class DeviceState(str, Enum):
    INTERACTIVE = "interactive"
    LOCKED = "locked"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ForegroundApp:
    app_id: str
    activity: str
    captured_at: str

    def to_dict(self) -> dict[str, str]:
        return {
            "app_id": self.app_id,
            "activity": self.activity,
            "captured_at": self.captured_at,
        }


@dataclass(frozen=True, slots=True)
class ScreenObservation:
    width: int
    height: int
    orientation: Orientation
    captured_at: str
    screenshot: Artifact

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("screen dimensions must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "orientation": self.orientation.value,
            "captured_at": self.captured_at,
            "screenshot": self.screenshot.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class UiTreeObservation:
    captured_at: str
    artifact: Artifact

    def to_dict(self) -> dict[str, Any]:
        return {"captured_at": self.captured_at, "artifact": self.artifact.to_dict()}


@dataclass(frozen=True, slots=True)
class Observation:
    observation_id: str
    device_id: str
    captured_at: str
    foreground_app: ForegroundApp
    screen: ScreenObservation
    ui_tree: UiTreeObservation
    device_state: DeviceState = DeviceState.UNKNOWN
    schema_version: str = OBSERVATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "observation_id": self.observation_id,
            "device_id": self.device_id,
            "captured_at": self.captured_at,
            "foreground_app": self.foreground_app.to_dict(),
            "screen": self.screen.to_dict(),
            "ui_tree": self.ui_tree.to_dict(),
            "device_state": self.device_state.value,
        }
