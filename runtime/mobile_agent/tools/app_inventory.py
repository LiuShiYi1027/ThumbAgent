"""Registered, policy-gated tools for installed application metadata."""

from __future__ import annotations

import re

from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.domain.app import AppInventory, InstalledApp
from mobile_agent.domain.device import ConnectionState
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.tools.runtime import ToolRegistry


_APP_ID = re.compile(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+")


class AppInventoryTool:
    """Expose bounded package-manager reads through the shared policy boundary."""

    def __init__(
        self,
        adapter: DeviceAdapter,
        registry: ToolRegistry,
        policy: PolicyEngine,
    ) -> None:
        self._adapter = adapter
        self._registry = registry
        self._policy = policy

    async def list(
        self, device_id: str, limit: int = 200, prefix: str | None = None
    ) -> AppInventory:
        limit, prefix = self.validate_list_request(limit, prefix)
        await self._authorize("app.list", device_id)
        app_ids = await self._adapter.list_installed_apps(device_id)
        matched = tuple(
            app_id for app_id in app_ids if prefix is None or app_id.startswith(prefix)
        )
        return AppInventory(
            device_id=device_id,
            apps=tuple(InstalledApp(app_id) for app_id in matched[:limit]),
            total_matched=len(matched),
            truncated=len(matched) > limit,
            prefix=prefix,
        )

    async def inspect(self, device_id: str, app_id: str) -> InstalledApp:
        app_id = self.validate_app_id(app_id)
        await self._authorize("app.inspect", device_id)
        return await self._adapter.inspect_installed_app(device_id, app_id)

    async def _authorize(self, tool_id: str, device_id: str) -> None:
        definition = self._registry.get(tool_id)
        device = next(
            (item for item in await self._adapter.list_devices() if item.device_id == device_id),
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
                message="设备不支持应用清单检查",
                details={"capability": definition.capability},
            )
        self._policy.authorize(definition.risk)

    @staticmethod
    def validate_list_request(
        limit: int, prefix: str | None
    ) -> tuple[int, str | None]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="应用清单 limit 必须在 1 到 500 之间",
            )
        if prefix is not None and (
            not isinstance(prefix, str)
            or not 1 <= len(prefix) <= 128
            or re.fullmatch(r"[A-Za-z0-9_.]+", prefix) is None
        ):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="应用标识前缀无效",
            )
        return limit, prefix

    @staticmethod
    def validate_app_id(app_id: str) -> str:
        if not isinstance(app_id, str) or _APP_ID.fullmatch(app_id) is None:
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="无效的应用标识",
            )
        return app_id
