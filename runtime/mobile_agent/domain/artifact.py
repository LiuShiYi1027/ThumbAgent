"""Artifact value objects shared by domain and persistence ports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


ARTIFACT_SCHEMA_VERSION = "1.0.0"


class ArtifactKind(str, Enum):
    SCREENSHOT = "screenshot"
    UI_TREE = "ui_tree"
    DEVICE_LOG = "device_log"
    DEVICE_PERFORMANCE = "device_performance"


@dataclass(frozen=True, slots=True)
class Artifact:
    artifact_id: str
    kind: ArtifactKind
    content_type: str
    relative_path: str
    size_bytes: int
    sha256: str
    created_at: str
    schema_version: str = ARTIFACT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_id": self.artifact_id,
            "kind": self.kind.value,
            "content_type": self.content_type,
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "created_at": self.created_at,
        }


class ArtifactWriter(Protocol):
    def write(
        self, kind: ArtifactKind, content_type: str, data: bytes, extension: str
    ) -> Artifact: ...
