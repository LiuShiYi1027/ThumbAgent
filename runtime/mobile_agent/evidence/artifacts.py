"""Atomic, local-only artifact persistence."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mobile_agent.domain.artifact import Artifact, ArtifactKind
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError

class ArtifactStore:
    """Persist artifacts below a configured root using generated names."""

    _ALLOWED = {
        (ArtifactKind.SCREENSHOT, "image/png", ".png"),
        (ArtifactKind.UI_TREE, "application/xml", ".xml"),
        (ArtifactKind.DEVICE_LOG, "text/plain", ".log"),
        (ArtifactKind.DEVICE_PERFORMANCE, "application/json", ".json"),
        (ArtifactKind.DIAGNOSTIC_BUNDLE, "application/zip", ".zip"),
    }

    def __init__(self, root: Path) -> None:
        self._root = root.expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def write(
        self, kind: ArtifactKind, content_type: str, data: bytes, extension: str
    ) -> Artifact:
        if (kind, content_type, extension) not in self._ALLOWED:
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="不支持的 Artifact 类型",
            )
        if not data:
            raise MobileAgentError(
                code="ARTIFACT_EMPTY",
                category=ErrorCategory.STORAGE,
                message="不能保存空证据",
            )
        now = datetime.now(timezone.utc)
        artifact_id = f"artifact_{uuid.uuid4().hex}"
        directory = self._root / now.strftime("%Y/%m/%d")
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{artifact_id}{extension}"
        try:
            with tempfile.NamedTemporaryFile(dir=directory, prefix=".tmp-", delete=False) as temp:
                temp.write(data)
                temp.flush()
                os.fsync(temp.fileno())
                temporary_path = Path(temp.name)
            os.replace(temporary_path, destination)
        except OSError as error:
            if "temporary_path" in locals():
                temporary_path.unlink(missing_ok=True)
            raise MobileAgentError(
                code="STORAGE_ERROR",
                category=ErrorCategory.STORAGE,
                message="无法保存本地证据",
            ) from error
        relative_path = destination.relative_to(self._root).as_posix()
        return Artifact(
            artifact_id=artifact_id,
            kind=kind,
            content_type=content_type,
            relative_path=relative_path,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            created_at=now.isoformat().replace("+00:00", "Z"),
        )

    def resolve(self, relative_path: str) -> Path:
        candidate = (self._root / relative_path).resolve()
        if not candidate.is_relative_to(self._root):
            raise MobileAgentError(
                code="INVALID_ARTIFACT_PATH",
                category=ErrorCategory.STORAGE,
                message="Artifact 路径越界",
            )
        return candidate


def default_artifact_root() -> Path:
    configured = os.environ.get("MOBILE_AGENT_DATA_DIR")
    if configured:
        return Path(configured) / "artifacts"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/MobileAgent/artifacts"
    xdg_data = os.environ.get("XDG_DATA_HOME")
    return Path(xdg_data) / "mobile-agent/artifacts" if xdg_data else Path.home() / ".local/share/mobile-agent/artifacts"
