"""High-risk APK installation Tool gated by a claimed scoped Approval."""

from __future__ import annotations

from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.domain.apk import ApkInspector, ApkInstallApproval
from mobile_agent.domain.app import InstalledApp
from mobile_agent.domain.device import ConnectionState
from mobile_agent.domain.errors import ErrorCategory, ErrorOutcome, MobileAgentError
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.tools.runtime import ToolRegistry


class ApkInstallTool:
    tool_id = "app.install"

    def __init__(
        self,
        adapter: DeviceAdapter,
        registry: ToolRegistry,
        policy: PolicyEngine,
        inspector: ApkInspector,
    ) -> None:
        self._adapter = adapter
        self._registry = registry
        self._policy = policy
        self._inspector = inspector

    async def execute(
        self, approval: ApkInstallApproval, confirmed: bool
    ) -> InstalledApp:
        definition = self._registry.get(self.tool_id)
        device = next(
            (item for item in await self._adapter.list_devices() if item.device_id == approval.device_id),
            None,
        )
        if device is None:
            raise MobileAgentError("DEVICE_NOT_FOUND", ErrorCategory.DEVICE, "设备不存在")
        if device.connection is not ConnectionState.ONLINE:
            raise MobileAgentError("DEVICE_OFFLINE", ErrorCategory.DEVICE, "设备当前不可交互", retryable=True)
        if definition.capability not in device.capabilities:
            raise MobileAgentError(
                "CAPABILITY_UNAVAILABLE", ErrorCategory.CAPABILITY, "设备不支持 APK 安装",
                details={"capability": definition.capability},
            )
        current = self._inspector.inspect(str(approval.package.path))
        if (
            current.sha256 != approval.package.sha256
            or current.app_id != approval.package.app_id
            or current.size_bytes != approval.package.size_bytes
        ):
            raise MobileAgentError(
                "APPROVAL_INVALID", ErrorCategory.POLICY,
                "APK 文件在用户确认后发生变化，原 Approval 已失效",
            )
        self._policy.authorize(
            definition.risk, confirmed, high_risk_authorized=True
        )
        try:
            await self._adapter.install_apk(
                approval.device_id, approval.package.path, approval.replace_existing
            )
        except MobileAgentError as error:
            if error.code == "ACTION_TIMEOUT":
                raise MobileAgentError(
                    "ACTION_OUTCOME_UNKNOWN",
                    ErrorCategory.EXECUTION,
                    "APK 安装等待超时，设备结果未知",
                    outcome=ErrorOutcome.UNKNOWN_OUTCOME,
                    suggested_action="只读检查目标应用状态，不要自动重试安装",
                ) from error
            raise
        try:
            return await self._adapter.inspect_installed_app(
                approval.device_id, approval.package.app_id
            )
        except MobileAgentError as error:
            raise MobileAgentError(
                "APK_INSTALL_NOT_VERIFIED",
                ErrorCategory.DEVICE,
                "APK 命令完成，但安装后未能验证目标应用",
                suggested_action="检查设备安装策略和应用清单后再决定是否重试",
            ) from error
