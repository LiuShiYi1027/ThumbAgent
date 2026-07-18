"""Registered, policy-gated Tool for bounded device log snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.domain.artifact import Artifact, ArtifactKind
from mobile_agent.domain.device import ConnectionState
from mobile_agent.domain.device_log import DeviceLogLevel
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.evidence.log_redaction import redact_device_log
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.tools.runtime import ToolRegistry


MAX_LOG_ARTIFACT_BYTES = 1_048_576


@dataclass(frozen=True, slots=True)
class CapturedDeviceLog:
    """Internal output from the registered Tool to its owning Skill."""

    artifact: Artifact
    captured_bytes: int
    truncated: bool
    redaction_count: int


class DeviceLogCaptureTool:
    """Validate, authorize, capture, redact and persist a finite device log snapshot."""

    tool_id = "device.logs.capture"

    def __init__(
        self,
        adapter: DeviceAdapter,
        artifacts: ArtifactStore,
        registry: ToolRegistry,
        policy: PolicyEngine,
    ) -> None:
        self._adapter = adapter
        self._artifacts = artifacts
        self._registry = registry
        self._policy = policy

    async def execute(
        self,
        device_id: str,
        max_lines: int,
        minimum_level: DeviceLogLevel | str,
        confirmed: bool,
    ) -> CapturedDeviceLog:
        max_lines, level = self.validate_request(max_lines, minimum_level)
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
                code="DEVICE_NOT_FOUND",
                category=ErrorCategory.DEVICE,
                message="设备不存在",
            )
        if device.connection is not ConnectionState.ONLINE:
            raise MobileAgentError(
                code="DEVICE_OFFLINE",
                category=ErrorCategory.DEVICE,
                message="设备当前不可交互",
                retryable=True,
            )
        if definition.capability not in device.capabilities:
            raise MobileAgentError(
                code="CAPABILITY_UNAVAILABLE",
                category=ErrorCategory.CAPABILITY,
                message="设备不支持日志采集",
                details={"capability": definition.capability},
            )
        self._policy.authorize(definition.risk, confirmed)

        raw = await self._adapter.collect_logs(device_id, max_lines, level)
        redacted, redaction_count = redact_device_log(raw)
        truncated = len(redacted) > MAX_LOG_ARTIFACT_BYTES
        if truncated:
            redacted = redacted[:MAX_LOG_ARTIFACT_BYTES]
            redacted = redacted.decode("utf-8", errors="ignore").encode("utf-8")
        if not redacted:
            raise MobileAgentError(
                code="LOG_CAPTURE_EMPTY",
                category=ErrorCategory.DEVICE,
                message="设备没有返回可保存的日志",
                retryable=True,
            )
        artifact = self._artifacts.write(
            ArtifactKind.DEVICE_LOG,
            "text/plain",
            redacted,
            ".log",
        )
        return CapturedDeviceLog(
            artifact=artifact,
            captured_bytes=artifact.size_bytes,
            truncated=truncated,
            redaction_count=redaction_count,
        )

    @staticmethod
    def validate_request(
        max_lines: int, minimum_level: DeviceLogLevel | str
    ) -> tuple[int, DeviceLogLevel]:
        """Validate public request fields before any device discovery or lease."""

        if (
            not isinstance(max_lines, int)
            or isinstance(max_lines, bool)
            or max_lines < 1
            or max_lines > 2000
        ):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="日志行数必须在 1 到 2000 之间",
            )
        try:
            level = (
                minimum_level
                if isinstance(minimum_level, DeviceLogLevel)
                else DeviceLogLevel(minimum_level)
            )
        except (TypeError, ValueError) as error:
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="日志级别无效",
            ) from error
        return max_lines, level
