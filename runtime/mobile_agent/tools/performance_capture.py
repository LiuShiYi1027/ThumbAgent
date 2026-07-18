"""Registered Tool for privacy-minimized aggregate performance snapshots."""

from __future__ import annotations

import json
from dataclasses import dataclass

from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.domain.artifact import Artifact, ArtifactKind
from mobile_agent.domain.device import ConnectionState
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.performance import DevicePerformanceSnapshot
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.tools.runtime import ToolRegistry


@dataclass(frozen=True, slots=True)
class CapturedPerformanceSnapshot:
    """Internal Tool output passed to the deterministic Skill."""

    snapshot: DevicePerformanceSnapshot
    artifact: Artifact


class DevicePerformanceCaptureTool:
    """Authorize aggregate sampling and persist only normalized JSON metrics."""

    tool_id = "device.performance.capture"

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

    async def execute(self, device_id: str) -> CapturedPerformanceSnapshot:
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
                message="设备不支持性能快照",
                details={"capability": definition.capability},
            )
        self._policy.authorize(definition.risk)
        snapshot = await self._adapter.capture_performance(device_id)
        encoded = (
            json.dumps(
                snapshot.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        artifact = self._artifacts.write(
            ArtifactKind.DEVICE_PERFORMANCE,
            "application/json",
            encoded,
            ".json",
        )
        return CapturedPerformanceSnapshot(snapshot, artifact)
