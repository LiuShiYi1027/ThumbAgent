"""Policy-gated application lifecycle tools."""

from __future__ import annotations

from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.domain.app import InstalledApp
from mobile_agent.domain.app_lifecycle import AppDataClearApproval, AppRuntimeState
from mobile_agent.domain.device import ConnectionState
from mobile_agent.domain.errors import ErrorCategory, ErrorOutcome, MobileAgentError
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.tools.runtime import ToolRegistry


class AppLifecycleTool:
    """Inspect and mutate one installed application's bounded lifecycle state."""

    def __init__(
        self, adapter: DeviceAdapter, registry: ToolRegistry, policy: PolicyEngine
    ) -> None:
        self._adapter = adapter
        self._registry = registry
        self._policy = policy

    async def inspect(
        self, device_id: str, app_id: str
    ) -> tuple[InstalledApp, AppRuntimeState]:
        definition = self._registry.get("app.state.inspect")
        await self._require_device(device_id, definition.capability)
        self._policy.authorize(definition.risk)
        app = await self._adapter.inspect_installed_app(device_id, app_id)
        return app, await self._adapter.inspect_app_runtime_state(device_id, app)

    async def stop(
        self, device_id: str, app_id: str, confirmed: bool
    ) -> tuple[InstalledApp, AppRuntimeState]:
        definition = self._registry.get("app.stop")
        await self._require_device(device_id, definition.capability)
        app = await self._adapter.inspect_installed_app(device_id, app_id)
        _require_non_system(app, "停止")
        self._policy.authorize(definition.risk, confirmed)
        try:
            await self._adapter.force_stop_app(device_id, app_id)
        except MobileAgentError as error:
            _map_unknown(error, "应用停止等待超时，设备结果未知")
            raise
        state = await self._adapter.inspect_app_runtime_state(device_id, app)
        if state.foreground or state.process_present:
            raise MobileAgentError(
                "APP_STOP_NOT_VERIFIED",
                ErrorCategory.DEVICE,
                "停止命令完成，但应用仍在前台或进程仍存在",
                suggested_action="只读检查应用状态后再决定是否重新停止",
            )
        return app, state

    async def clear_data(
        self, approval: AppDataClearApproval, confirmed: bool
    ) -> tuple[InstalledApp, AppRuntimeState]:
        definition = self._registry.get("app.data.clear")
        await self._require_device(approval.device_id, definition.capability)
        current = await self._adapter.inspect_installed_app(
            approval.device_id, approval.app.app_id
        )
        _require_non_system(current, "清除数据")
        if (
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
            await self._adapter.clear_app_data(
                approval.device_id, approval.app.app_id
            )
        except MobileAgentError as error:
            _map_unknown(error, "清除应用数据等待超时，设备结果未知")
            raise
        installed = await self._adapter.inspect_installed_app(
            approval.device_id, approval.app.app_id
        )
        state = await self._adapter.inspect_app_runtime_state(
            approval.device_id, installed
        )
        if state.foreground or state.process_present:
            raise MobileAgentError(
                "APP_DATA_CLEAR_NOT_VERIFIED",
                ErrorCategory.DEVICE,
                "平台报告数据已清除，但应用运行状态未复位",
                suggested_action="只读检查应用状态，不要自动重试清除数据",
            )
        return installed, state

    async def _require_device(self, device_id: str, capability: str) -> None:
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
                "DEVICE_OFFLINE",
                ErrorCategory.DEVICE,
                "设备当前不可交互",
                retryable=True,
            )
        if capability not in device.capabilities:
            raise MobileAgentError(
                "CAPABILITY_UNAVAILABLE",
                ErrorCategory.CAPABILITY,
                "设备不支持该应用生命周期能力",
                details={"capability": capability},
            )


def _require_non_system(app: InstalledApp, action: str) -> None:
    if app.system_app is not False:
        raise MobileAgentError(
            "SYSTEM_APP_PROTECTED",
            ErrorCategory.POLICY,
            f"系统应用或系统属性未知的应用不允许{action}",
            suggested_action="仅选择明确识别为非系统应用的测试包",
        )


def _map_unknown(error: MobileAgentError, message: str) -> None:
    if error.code == "ACTION_TIMEOUT":
        raise MobileAgentError(
            "ACTION_OUTCOME_UNKNOWN",
            ErrorCategory.EXECUTION,
            message,
            outcome=ErrorOutcome.UNKNOWN_OUTCOME,
            suggested_action="只读检查应用状态，不要自动重试设备写动作",
        ) from error
