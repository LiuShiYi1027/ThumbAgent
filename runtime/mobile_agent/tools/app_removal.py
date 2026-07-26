"""High-risk application removal Tool gated by a scoped Approval."""

from __future__ import annotations

from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.domain.app_removal import AppRemovalApproval
from mobile_agent.domain.device import ConnectionState
from mobile_agent.domain.errors import ErrorCategory, ErrorOutcome, MobileAgentError
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.tools.runtime import ToolRegistry


class AppRemovalTool:
    tool_id = "app.uninstall"

    def __init__(
        self, adapter: DeviceAdapter, registry: ToolRegistry, policy: PolicyEngine
    ) -> None:
        self._adapter = adapter
        self._registry = registry
        self._policy = policy

    async def execute(
        self, approval: AppRemovalApproval, confirmed: bool
    ) -> None:
        definition = self._registry.get(self.tool_id)
        device = next(
            (
                item
                for item in await self._adapter.list_devices()
                if item.device_id == approval.device_id
            ),
            None,
        )
        if device is None:
            raise MobileAgentError("DEVICE_NOT_FOUND", ErrorCategory.DEVICE, "设备不存在")
        if device.connection is not ConnectionState.ONLINE:
            raise MobileAgentError(
                "DEVICE_OFFLINE",
                ErrorCategory.DEVICE,
                "设备当前不可交互",
                retryable=True,
            )
        if definition.capability not in device.capabilities:
            raise MobileAgentError(
                "CAPABILITY_UNAVAILABLE",
                ErrorCategory.CAPABILITY,
                "设备不支持应用卸载",
                details={"capability": definition.capability},
            )
        current = await self._adapter.inspect_installed_app(
            approval.device_id, approval.app.app_id
        )
        if current.system_app is not False or (
            current.version_code != approval.app.version_code
            or current.version_name != approval.app.version_name
        ):
            raise MobileAgentError(
                "APPROVAL_INVALID",
                ErrorCategory.POLICY,
                "应用状态在用户确认后发生变化，原 Approval 已失效",
            )
        self._policy.authorize(
            definition.risk, confirmed, high_risk_authorized=True
        )
        try:
            await self._adapter.uninstall_app(
                approval.device_id, approval.app.app_id, approval.keep_data
            )
        except MobileAgentError as error:
            if error.code == "ACTION_TIMEOUT":
                raise MobileAgentError(
                    "ACTION_OUTCOME_UNKNOWN",
                    ErrorCategory.EXECUTION,
                    "应用卸载等待超时，设备结果未知",
                    outcome=ErrorOutcome.UNKNOWN_OUTCOME,
                    suggested_action="只读检查目标应用状态，不要自动重试卸载",
                ) from error
            raise
        installed = await self._adapter.list_installed_apps(approval.device_id)
        if approval.app.app_id in installed:
            raise MobileAgentError(
                "APP_UNINSTALL_NOT_VERIFIED",
                ErrorCategory.DEVICE,
                "卸载命令完成，但目标应用仍在设备应用清单中",
                suggested_action="检查设备管理策略后再决定是否重新预检",
            )
