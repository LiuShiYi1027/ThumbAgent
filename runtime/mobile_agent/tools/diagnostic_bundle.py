"""Policy-gated collection and local packaging of diagnostic evidence."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.domain.app_lifecycle import AppRuntimeState
from mobile_agent.domain.artifact import Artifact, ArtifactKind
from mobile_agent.domain.device import ConnectionState
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.tools.app_lifecycle import AppLifecycleTool
from mobile_agent.tools.log_capture import DeviceLogCaptureTool
from mobile_agent.tools.performance_capture import DevicePerformanceCaptureTool
from mobile_agent.tools.runtime import ToolRegistry


MAX_SOURCE_BYTES = 24 * 1024 * 1024
MAX_BUNDLE_BYTES = 24 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class DiagnosticBundleTool:
    """Collect existing trusted diagnostics and write one integrity manifest ZIP."""

    tool_id = "device.diagnostics.bundle"

    def __init__(
        self,
        adapter: DeviceAdapter,
        artifacts: ArtifactStore,
        registry: ToolRegistry,
        policy: PolicyEngine,
        logs: DeviceLogCaptureTool,
        performance: DevicePerformanceCaptureTool,
        lifecycle: AppLifecycleTool,
    ) -> None:
        self._adapter = adapter
        self._artifacts = artifacts
        self._registry = registry
        self._policy = policy
        self._logs = logs
        self._performance = performance
        self._lifecycle = lifecycle

    async def execute(
        self,
        device_id: str,
        app_id: str | None,
        max_log_lines: int,
        minimum_log_level: str,
        confirmed: bool,
    ) -> tuple[
        dict[str, Any],
        AppRuntimeState | None,
        dict[str, Any],
        dict[str, Any],
        tuple[Artifact, ...],
        Artifact,
    ]:
        definition = self._registry.get(self.tool_id)
        device = next(
            (
                item
                for item in await self._adapter.list_devices()
                if item.device_id == device_id
            ),
            None,
        )
        if device is None:
            raise MobileAgentError(
                "DEVICE_NOT_FOUND", ErrorCategory.DEVICE, "设备不存在"
            )
        if device.connection is not ConnectionState.ONLINE:
            raise MobileAgentError(
                "DEVICE_OFFLINE", ErrorCategory.DEVICE, "设备当前不可交互"
            )
        if definition.capability not in device.capabilities:
            raise MobileAgentError(
                "CAPABILITY_UNAVAILABLE",
                ErrorCategory.CAPABILITY,
                "设备不支持诊断包采集",
                details={"capability": definition.capability},
            )
        self._policy.authorize(definition.risk, confirmed)
        max_log_lines, level = DeviceLogCaptureTool.validate_request(
            max_log_lines, minimum_log_level
        )

        completed: list[Artifact] = []
        observation = await self._adapter.observe(device_id, self._artifacts)
        completed.extend(
            (observation.screen.screenshot, observation.ui_tree.artifact)
        )
        try:
            logs = await self._logs.execute(
                device_id, max_log_lines, level, confirmed
            )
            completed.append(logs.artifact)
            performance = await self._performance.execute(device_id)
            completed.append(performance.artifact)
            app_state = (
                (await self._lifecycle.inspect(device_id, app_id))[1]
                if app_id is not None
                else None
            )
        except MobileAgentError as error:
            raise _with_completed_artifacts(error, completed) from error
        sources = tuple(completed)
        foreground = observation.foreground_app.to_dict()
        log_summary = {
            "minimum_level": level.value,
            "captured_bytes": logs.captured_bytes,
            "truncated": logs.truncated,
            "redaction_count": logs.redaction_count,
        }
        performance_summary = performance.snapshot.to_dict()
        try:
            bundle = self._build_bundle(
                device_id, foreground, app_state, sources
            )
        except MobileAgentError as error:
            raise _with_completed_artifacts(error, completed) from error
        return (
            foreground,
            app_state,
            log_summary,
            performance_summary,
            sources,
            bundle,
        )

    def _build_bundle(
        self,
        device_id: str,
        foreground_app: dict[str, Any],
        app_state: AppRuntimeState | None,
        artifacts: tuple[Artifact, ...],
    ) -> Artifact:
        names = ("screenshot.png", "ui-tree.xml", "device.log", "performance.json")
        contents: list[bytes] = []
        entries: list[dict[str, Any]] = []
        total = 0
        for name, artifact in zip(names, artifacts, strict=True):
            data = self._artifacts.resolve(artifact.relative_path).read_bytes()
            if (
                len(data) != artifact.size_bytes
                or hashlib.sha256(data).hexdigest() != artifact.sha256
            ):
                raise MobileAgentError(
                    "DIAGNOSTIC_SOURCE_INVALID",
                    ErrorCategory.STORAGE,
                    "诊断源证据完整性校验失败",
                    details={"artifact_id": artifact.artifact_id},
                )
            total += len(data)
            if total > MAX_SOURCE_BYTES:
                raise MobileAgentError(
                    "DIAGNOSTIC_BUNDLE_TOO_LARGE",
                    ErrorCategory.STORAGE,
                    "诊断源证据超过本地大小限制",
                )
            contents.append(data)
            entries.append(
                {
                    "name": name,
                    "artifact_id": artifact.artifact_id,
                    "kind": artifact.kind.value,
                    "size_bytes": artifact.size_bytes,
                    "sha256": artifact.sha256,
                }
            )
        manifest = {
            "schema_version": "1.0.0",
            "device_id": device_id,
            "captured_at": _now(),
            "foreground_app": foreground_app,
            "app_state": app_state.to_dict() if app_state else None,
            "entries": entries,
        }
        output = io.BytesIO()
        with zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            for name, data in zip(names, contents, strict=True):
                archive.writestr(name, data)
            archive.writestr(
                "manifest.json",
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8"),
            )
        payload = output.getvalue()
        if len(payload) > MAX_BUNDLE_BYTES:
            raise MobileAgentError(
                "DIAGNOSTIC_BUNDLE_TOO_LARGE",
                ErrorCategory.STORAGE,
                "诊断包超过本地大小限制",
            )
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if set(archive.namelist()) != {*names, "manifest.json"}:
                raise MobileAgentError(
                    "DIAGNOSTIC_BUNDLE_NOT_VERIFIED",
                    ErrorCategory.STORAGE,
                    "诊断包内容验证失败",
                )
        return self._artifacts.write(
            ArtifactKind.DIAGNOSTIC_BUNDLE,
            "application/zip",
            payload,
            ".zip",
        )


def _with_completed_artifacts(
    error: MobileAgentError, artifacts: list[Artifact]
) -> MobileAgentError:
    details = dict(error.details)
    details["artifact_refs"] = [
        artifact.artifact_id for artifact in artifacts
    ]
    return MobileAgentError(
        error.code,
        error.category,
        error.message,
        error.retryable,
        error.outcome,
        error.suggested_action,
        details,
    )
