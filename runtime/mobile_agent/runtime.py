"""Application service shared by HTTP, CLI, and future MCP interfaces."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

from mobile_agent import __version__
from mobile_agent.agent import AgentRunner, Planner, RuleBasedPlanner, UnavailablePlanner
from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.devices.lease import DeviceLeaseManager
from mobile_agent.devices.session import SessionTrackingDeviceAdapter
from mobile_agent.devices.unavailable import UnavailableDeviceAdapter
from mobile_agent.domain.device import ConnectionState, Device
from mobile_agent.domain.apk import ApkInspector, ApkInstallApprovalStore
from mobile_agent.domain.app_removal import AppRemovalApprovalStore
from mobile_agent.domain.app_lifecycle import AppDataClearApprovalStore
from mobile_agent.domain.local_data import (
    LocalDataCleanupApprovalStore,
    validate_cleanup_limit,
    validate_retention_days,
)
from mobile_agent.domain.capability import (
    CapabilityAvailability,
    CapabilityCatalog,
    CapabilityDescriptor,
    DeviceInspection,
)
from mobile_agent.domain.task import TaskRun, TaskStatus
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.readiness import (
    DeviceAvailability,
    DeviceAvailabilityStatus,
    GatewayReadiness,
    GatewayStatus,
    ReadinessIssue,
    ReadinessStatus,
    RuntimeReadiness,
)
from mobile_agent.domain.performance_comparison import compare_performance_tasks
from mobile_agent.evaluation import AgentEvaluator, AgentGoalAcceptance
from mobile_agent.evidence.artifacts import ArtifactStore, default_artifact_root
from mobile_agent.goals import (
    AgentGoalSpec,
    GoalCompiler,
    PassThroughGoalCompiler,
    UnavailableGoalCompiler,
)
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.providers import (
    EnvironmentSecretResolver,
    ModelProviderSettings,
    OpenAICompatiblePlanner,
)
from mobile_agent.providers import build_planner_from_settings
from mobile_agent.providers import load_model_provider_settings
from mobile_agent.providers import model_provider_status as redacted_model_provider_status
from mobile_agent.skills.open_app import OpenAppSkill
from mobile_agent.skills.app_inventory import AppInspectSkill, AppListSkill
from mobile_agent.skills.apk_install import ApkInstallSkill
from mobile_agent.skills.app_removal import AppRemovalSkill
from mobile_agent.skills.app_lifecycle import (
    AppDataClearSkill,
    AppLaunchSkill,
    AppStateInspectSkill,
    AppStopSkill,
)
from mobile_agent.skills.device_logs import DeviceLogsCollectSkill
from mobile_agent.skills.device_performance import DevicePerformanceSnapshotSkill
from mobile_agent.skills.diagnostic_bundle import DiagnosticBundleSkill
from mobile_agent.skills.local_data import LocalDataCleanupSkill
from mobile_agent.skills.settings_navigate import SettingsNavigateSkill, SettingsScrollNavigateSkill
from mobile_agent.storage.sqlite import SQLiteTaskStore
from mobile_agent.storage.execution import SQLiteTaskExecutionStore
from mobile_agent.tasks.execution import (
    AsyncTaskExecutor,
    InMemoryTaskExecutionStore,
    TaskExecutionStore,
)
from mobile_agent.tasks.runner import TaskRunner
from mobile_agent.tasks.device_logs import DeviceLogsTaskRunner
from mobile_agent.tasks.device_performance import DevicePerformanceTaskRunner
from mobile_agent.tasks.diagnostic_bundle import DiagnosticBundleTaskRunner
from mobile_agent.tasks.local_data import LocalDataCleanupTaskRunner
from mobile_agent.tasks.apk_install import ApkInstallTaskRunner
from mobile_agent.tasks.app_removal import AppRemovalTaskRunner
from mobile_agent.tasks.app_lifecycle import AppLifecycleTaskRunner
from mobile_agent.tasks.store import InMemoryTaskStore, TaskStore
from mobile_agent.tools.runtime import ToolRegistry, ToolRuntime
from mobile_agent.tools.log_capture import DeviceLogCaptureTool
from mobile_agent.tools.performance_capture import DevicePerformanceCaptureTool
from mobile_agent.tools.app_inventory import AppInventoryTool
from mobile_agent.tools.apk_install import ApkInstallTool
from mobile_agent.tools.app_removal import AppRemovalTool
from mobile_agent.tools.app_lifecycle import AppLifecycleTool
from mobile_agent.tools.diagnostic_bundle import DiagnosticBundleTool
from mobile_agent.tools.local_data import LocalDataTool


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RuntimeService:
    def __init__(
        self,
        adapter: DeviceAdapter,
        artifacts: ArtifactStore,
        task_store: TaskStore | None = None,
        model_provider_settings: ModelProviderSettings | None = None,
        planner: Planner | None = None,
        model_provider_runtime_status: str | None = None,
        model_provider_error: MobileAgentError | None = None,
        goal_compiler: GoalCompiler | None = None,
        task_execution_store: TaskExecutionStore | None = None,
        device_lease_manager: DeviceLeaseManager | None = None,
        monotonic_clock: Callable[[], float] = time.monotonic,
        device_gateway_error: MobileAgentError | None = None,
        gateway_platform: str = "android",
        gateway_transport: str = "adapter",
        apk_root: Path | None = None,
        apk_approval_store: ApkInstallApprovalStore | None = None,
        app_removal_approval_store: AppRemovalApprovalStore | None = None,
        app_data_clear_approval_store: AppDataClearApprovalStore | None = None,
        local_data_cleanup_approval_store: LocalDataCleanupApprovalStore | None = None,
        artifact_retention_days: int = 7,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self._adapter = (
            adapter
            if isinstance(adapter, SessionTrackingDeviceAdapter)
            else SessionTrackingDeviceAdapter(adapter)
        )
        self._artifacts = artifacts
        self._capabilities = CapabilityCatalog()
        self._tool_registry = ToolRegistry(self._capabilities)
        self._policy = PolicyEngine()
        self._tools = ToolRuntime(
            self._adapter, artifacts, self._tool_registry, self._policy
        )
        self._device_log_tool = DeviceLogCaptureTool(
            self._adapter, artifacts, self._tool_registry, self._policy
        )
        self._device_logs = DeviceLogsCollectSkill(self._device_log_tool)
        self._device_logs_task_runner = DeviceLogsTaskRunner(self._device_logs)
        self._device_performance_tool = DevicePerformanceCaptureTool(
            self._adapter, artifacts, self._tool_registry, self._policy
        )
        self._device_performance = DevicePerformanceSnapshotSkill(
            self._device_performance_tool
        )
        self._device_performance_task_runner = DevicePerformanceTaskRunner(
            self._device_performance
        )
        self._app_inventory_tool = AppInventoryTool(
            self._adapter, self._tool_registry, self._policy
        )
        self._app_list = AppListSkill(self._app_inventory_tool)
        self._app_inspect = AppInspectSkill(self._app_inventory_tool)
        self._apk_inspector = ApkInspector(apk_root or artifacts.root.parent / "apks")
        self._apk_approvals = apk_approval_store or ApkInstallApprovalStore()
        self._apk_install_tool = ApkInstallTool(
            self._adapter, self._tool_registry, self._policy, self._apk_inspector
        )
        self._apk_install = ApkInstallSkill(self._apk_install_tool)
        self._apk_install_task_runner = ApkInstallTaskRunner(self._apk_install)
        self._app_removal_approvals = (
            app_removal_approval_store or AppRemovalApprovalStore()
        )
        self._app_removal_tool = AppRemovalTool(
            self._adapter, self._tool_registry, self._policy
        )
        self._app_removal = AppRemovalSkill(self._app_removal_tool)
        self._app_removal_task_runner = AppRemovalTaskRunner(self._app_removal)
        self._open_app = OpenAppSkill(self._tools)
        self._app_lifecycle_tool = AppLifecycleTool(
            self._adapter, self._tool_registry, self._policy
        )
        self._app_state = AppStateInspectSkill(self._app_lifecycle_tool)
        self._app_launch = AppLaunchSkill(
            self._open_app, self._app_lifecycle_tool
        )
        self._app_stop = AppStopSkill(self._app_lifecycle_tool)
        self._app_data_clear_approvals = (
            app_data_clear_approval_store or AppDataClearApprovalStore()
        )
        self._app_data_clear = AppDataClearSkill(self._app_lifecycle_tool)
        self._app_lifecycle_task_runner = AppLifecycleTaskRunner(
            self._app_launch, self._app_stop, self._app_data_clear
        )
        self._diagnostic_bundle_tool = DiagnosticBundleTool(
            self._adapter,
            artifacts,
            self._tool_registry,
            self._policy,
            self._device_log_tool,
            self._device_performance_tool,
            self._app_lifecycle_tool,
        )
        self._diagnostic_bundle = DiagnosticBundleSkill(
            self._diagnostic_bundle_tool
        )
        self._diagnostic_bundle_task_runner = DiagnosticBundleTaskRunner(
            self._diagnostic_bundle
        )
        self._artifact_retention_days = validate_retention_days(
            artifact_retention_days
        )
        self._local_data_tool = LocalDataTool(artifacts, self._policy, wall_clock)
        self._local_data_cleanup_approvals = (
            local_data_cleanup_approval_store
            or LocalDataCleanupApprovalStore(wall_clock)
        )
        self._local_data_cleanup = LocalDataCleanupSkill(self._local_data_tool)
        self._local_data_cleanup_task_runner = LocalDataCleanupTaskRunner(
            self._local_data_cleanup
        )
        self._settings_navigate = SettingsNavigateSkill(self._tools, self._open_app)
        self._settings_scroll_navigate = SettingsScrollNavigateSkill(self._tools, self._open_app)
        self._tasks = TaskRunner(self._settings_scroll_navigate)
        self._agent_runner = AgentRunner(
            self._adapter,
            artifacts,
            planner or RuleBasedPlanner(),
            self._tools,
            self._settings_scroll_navigate,
        )
        self._task_store = task_store or InMemoryTaskStore()
        self._agent_evaluator = AgentEvaluator()
        self._goal_compiler = goal_compiler or PassThroughGoalCompiler()
        self._monotonic = monotonic_clock
        self._task_executor = AsyncTaskExecutor(
            task_execution_store or InMemoryTaskExecutionStore(), monotonic_clock
        )
        self._device_leases = device_lease_manager or DeviceLeaseManager()
        self._model_provider_settings = model_provider_settings or ModelProviderSettings()
        self._model_provider_runtime_status = (
            model_provider_runtime_status
            or ("configured" if self._model_provider_settings.enabled else "disabled")
        )
        self._model_provider_error = model_provider_error
        self._device_gateway_error = device_gateway_error
        self._gateway_platform = gateway_platform
        self._gateway_transport = gateway_transport

    def health(self) -> dict[str, str]:
        return {"status": "ok", "runtime_version": __version__, "api_version": "v1"}

    def model_provider_status(self) -> dict[str, object]:
        """Return redacted planner model provider status for local clients."""

        status = dict(redacted_model_provider_status(self._model_provider_settings))
        status["status"] = self._model_provider_runtime_status
        if self._model_provider_error is not None:
            error = self._model_provider_error.to_dict()
            status["error"] = {
                "code": error["code"],
                "message": error["message"],
            }
        return status

    def local_storage_summary(
        self, retention_days: int | None = None
    ) -> dict[str, Any]:
        """Return local Artifact counts and bytes without reading file content."""

        days = (
            self._artifact_retention_days
            if retention_days is None
            else validate_retention_days(retention_days)
        )
        return self._local_data_tool.summarize(days).to_dict()

    def prepare_local_data_cleanup(
        self,
        retention_days: int | None = None,
        max_artifacts: int = 500,
    ) -> dict[str, Any]:
        """Create a read-only exact cleanup preview and short-lived Approval."""

        days = (
            self._artifact_retention_days
            if retention_days is None
            else validate_retention_days(retention_days)
        )
        max_artifacts = validate_cleanup_limit(max_artifacts)
        cutoff, candidates, truncated = self._local_data_tool.prepare(
            days, max_artifacts
        )
        return self._local_data_cleanup_approvals.create(
            days, cutoff, candidates, truncated
        ).to_public_dict()

    def submit_local_data_cleanup_task(
        self,
        approval_id: str,
        confirmed: bool,
        idempotency_key: str,
        deadline_seconds: float = 120.0,
    ) -> dict[str, Any]:
        """Claim one scoped Approval and enqueue permanent local deletion."""

        if not confirmed:
            raise MobileAgentError(
                "CONFIRMATION_REQUIRED",
                ErrorCategory.POLICY,
                "清理本地证据需要用户对永久删除影响进行明确确认",
            )
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise MobileAgentError(
                "INVALID_ARGUMENT",
                ErrorCategory.VALIDATION,
                "本地数据清理必须提供 Idempotency-Key",
            )
        deadline_seconds = self._validated_deadline(deadline_seconds)
        approval = self._local_data_cleanup_approvals.claim(
            approval_id, idempotency_key
        )
        goal = "清理已批准的过期本地 Artifact"

        async def run_factory(
            task_id: str, on_step: Any, is_cancelled: Any, deadline_exceeded: Any
        ) -> TaskRun:
            return await self._local_data_cleanup_task_runner.run(
                task_id,
                approval,
                confirmed,
                deadline_seconds,
                on_step,
                is_cancelled,
                deadline_exceeded,
            )

        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "task_type": "local.data.cleanup",
                    "approval_id": approval.approval_id,
                    "retention_days": approval.retention_days,
                    "cutoff_at": approval.cutoff_at,
                    "artifact_ids": [
                        item.artifact_id for item in approval.candidates
                    ],
                    "deadline_seconds": deadline_seconds,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return self._task_executor.submit(
            LocalDataCleanupTaskRunner.target_id,
            goal,
            run_factory,
            self._task_store.save,
            idempotency_key,
            fingerprint,
            deadline_seconds,
            task_type="local.data.cleanup",
        ).to_dict()

    async def list_devices(self) -> list[dict[str, Any]]:
        devices = await self._adapter.list_devices()
        return [device.to_dict() for device in devices]

    async def readiness(self) -> dict[str, Any]:
        """Return a side-effect-free Runtime and device availability snapshot."""

        gateway_error = self._device_gateway_error
        devices: list[Device] = []
        if gateway_error is None:
            try:
                devices = await self._adapter.list_devices()
            except MobileAgentError as error:
                gateway_error = error
        if gateway_error is not None:
            issue = ReadinessIssue.from_error(gateway_error)
            return RuntimeReadiness(
                generated_at=_utc_now(),
                status=ReadinessStatus.BLOCKED,
                gateway=GatewayReadiness(
                    self._gateway_platform,
                    self._gateway_transport,
                    GatewayStatus.UNAVAILABLE,
                    issue,
                ),
                devices=(),
                issues=(issue,),
            ).to_dict()

        availability = tuple(self._device_availability(device) for device in devices)
        ready_count = sum(
            item.status is DeviceAvailabilityStatus.READY for item in availability
        )
        busy_count = sum(
            item.status is DeviceAvailabilityStatus.BUSY for item in availability
        )
        issues: tuple[ReadinessIssue, ...] = ()
        if not devices:
            issues = (
                ReadinessIssue(
                    "DEVICE_NOT_FOUND",
                    "未发现已连接的移动设备",
                    "连接设备、启用开发者模式和 USB 调试后刷新诊断",
                ),
            )
        status = (
            ReadinessStatus.READY
            if ready_count > 0
            else ReadinessStatus.ATTENTION
            if busy_count > 0
            else ReadinessStatus.BLOCKED
        )
        return RuntimeReadiness(
            generated_at=_utc_now(),
            status=status,
            gateway=GatewayReadiness(
                self._gateway_platform,
                self._gateway_transport,
                GatewayStatus.AVAILABLE,
            ),
            devices=availability,
            issues=issues,
        ).to_dict()

    def _device_availability(self, device: Device) -> DeviceAvailability:
        lease = self._device_leases.current(device.device_id)
        if device.connection is ConnectionState.ONLINE and device.session_id is not None:
            if lease is None:
                return DeviceAvailability(device, DeviceAvailabilityStatus.READY)
            return DeviceAvailability(
                device,
                DeviceAvailabilityStatus.BUSY,
                lease_owner_id=lease.owner_id,
                lease_session_id=lease.session_id,
                lease_expired=self._monotonic() >= lease.expires_at_monotonic,
                issues=(
                    ReadinessIssue(
                        "DEVICE_LOCKED",
                        "设备正由另一个任务使用",
                        "等待当前任务结束或取消后刷新诊断",
                    ),
                ),
            )
        if device.connection is ConnectionState.UNAUTHORIZED:
            status = DeviceAvailabilityStatus.UNAUTHORIZED
            issue = ReadinessIssue(
                "DEVICE_UNAUTHORIZED",
                "设备尚未授权当前电脑进行调试",
                "解锁设备并确认 USB 调试授权弹窗后刷新诊断",
            )
        elif device.connection is ConnectionState.OFFLINE:
            status = DeviceAvailabilityStatus.OFFLINE
            issue = ReadinessIssue(
                "DEVICE_OFFLINE",
                "设备当前离线",
                "重新连接设备或重启设备调试连接后刷新诊断",
            )
        else:
            status = DeviceAvailabilityStatus.UNKNOWN
            issue = ReadinessIssue(
                "DEVICE_OFFLINE",
                "设备连接状态未知",
                "检查设备连接、授权和平台工具后刷新诊断",
            )
        return DeviceAvailability(device, status, issues=(issue,))

    async def observe(self, device_id: str) -> dict[str, Any]:
        observation = await self._adapter.observe(device_id, self._artifacts)
        return observation.to_dict()

    async def inspect_device(self, device_id: str) -> dict[str, Any]:
        """Describe current capabilities without observing or mutating the device."""

        devices = await self._adapter.list_devices()
        device = next((item for item in devices if item.device_id == device_id), None)
        if device is None:
            raise MobileAgentError(
                code="DEVICE_NOT_FOUND",
                category=ErrorCategory.DEVICE,
                message="设备不存在",
            )
        availability = self._device_availability(device)
        advertised = frozenset(device.capabilities)
        descriptors = tuple(
            CapabilityDescriptor(
                definition=definition,
                availability=self._capability_availability(
                    definition.capability, advertised, availability.status
                ),
                tools=tuple(
                    tool.tool_id
                    for tool in self._tool_registry.list()
                    if tool.capability == definition.capability
                ),
                platform=self._gateway_platform,
                transport=self._gateway_transport,
            )
            for definition in self._capabilities.list()
        )
        return DeviceInspection(
            generated_at=_utc_now(),
            availability=availability,
            capabilities=descriptors,
        ).to_dict()

    async def list_installed_apps(
        self, device_id: str, limit: int = 200, prefix: str | None = None
    ) -> dict[str, Any]:
        """Return a bounded, privacy-minimized application inventory."""

        limit, prefix = AppInventoryTool.validate_list_request(limit, prefix)
        session_id = await self._adapter.require_online_session(device_id)
        with self._device_leases.hold(
            device_id, f"skill_{uuid.uuid4().hex}", 30.0, session_id
        ), self._adapter.bind_session(device_id, session_id):
            return (await self._app_list.list(device_id, limit, prefix)).to_dict()

    async def inspect_installed_app(
        self, device_id: str, app_id: str
    ) -> dict[str, Any]:
        """Return structured metadata for one installed application."""

        app_id = AppInventoryTool.validate_app_id(app_id)
        session_id = await self._adapter.require_online_session(device_id)
        with self._device_leases.hold(
            device_id, f"skill_{uuid.uuid4().hex}", 30.0, session_id
        ), self._adapter.bind_session(device_id, session_id):
            return (await self._app_inspect.invoke(device_id, app_id)).to_dict()

    async def prepare_apk_install(
        self,
        device_id: str,
        apk_path: str,
        expected_app_id: str,
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        """Preflight a local APK and create a short-lived scoped Approval."""

        expected_app_id = AppInventoryTool.validate_app_id(expected_app_id)
        if not isinstance(replace_existing, bool):
            raise MobileAgentError("INVALID_ARGUMENT", ErrorCategory.VALIDATION, "replace_existing 无效")
        package = self._apk_inspector.inspect(apk_path)
        if package.app_id != expected_app_id:
            raise MobileAgentError(
                "APK_PACKAGE_MISMATCH", ErrorCategory.VALIDATION,
                "APK Manifest package 与预期应用标识不一致",
                details={"manifest_app_id": package.app_id},
            )
        session_id = await self._adapter.require_online_session(device_id)
        with self._device_leases.hold(
            device_id, f"prepare_{uuid.uuid4().hex}", 30.0, session_id
        ), self._adapter.bind_session(device_id, session_id):
            devices = await self._adapter.list_devices()
            device = next((item for item in devices if item.device_id == device_id), None)
            if device is None or "app.install@1" not in device.capabilities:
                raise MobileAgentError(
                    "CAPABILITY_UNAVAILABLE", ErrorCategory.CAPABILITY,
                    "设备不支持 APK 安装", details={"capability": "app.install@1"},
                )
            installed = package.app_id in await self._adapter.list_installed_apps(device_id)
        if installed and not replace_existing:
            raise MobileAgentError(
                "APP_ALREADY_INSTALLED", ErrorCategory.VALIDATION,
                "目标应用已安装；如需升级必须显式允许替换",
            )
        if replace_existing and not installed:
            raise MobileAgentError(
                "APP_NOT_FOUND", ErrorCategory.VALIDATION,
                "设备上没有可替换的目标应用",
            )
        return self._apk_approvals.create(
            device_id, package, replace_existing
        ).to_public_dict()

    def submit_apk_install_task(
        self,
        approval_id: str,
        confirmed: bool,
        idempotency_key: str,
        deadline_seconds: float = 300.0,
    ) -> dict[str, Any]:
        """Claim one scoped Approval and enqueue the High-risk installation."""

        if not confirmed:
            raise MobileAgentError(
                "CONFIRMATION_REQUIRED", ErrorCategory.POLICY,
                "APK 安装需要用户对影响摘要进行明确确认",
            )
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise MobileAgentError(
                "INVALID_ARGUMENT", ErrorCategory.VALIDATION,
                "APK 安装必须提供 Idempotency-Key",
            )
        deadline_seconds = self._validated_deadline(deadline_seconds)
        approval = self._apk_approvals.claim(approval_id, idempotency_key)
        goal = f"安装已批准的本地 APK：{approval.package.app_id}"

        async def run_factory(
            task_id: str, on_step: Any, is_cancelled: Any, deadline_exceeded: Any
        ) -> TaskRun:
            try:
                session_id = await self._adapter.require_online_session(approval.device_id)
                with self._device_leases.hold(
                    approval.device_id, task_id, deadline_seconds + 30.0, session_id
                ), self._adapter.bind_session(approval.device_id, session_id):
                    self._task_executor.bind_device_session(task_id, session_id)
                    task = await self._apk_install_task_runner.run(
                        task_id, approval, confirmed, deadline_seconds,
                        on_step, is_cancelled, deadline_exceeded,
                    )
                    return replace(task, device_session_id=session_id)
            except MobileAgentError as error:
                now = _utc_now()
                return TaskRun(
                    task_id, "app.install", approval.device_id, goal,
                    TaskStatus.FAILED, now, now, (), {}, error.to_dict(),
                    deadline_seconds=deadline_seconds,
                )

        fingerprint = hashlib.sha256(json.dumps({
            "task_type": "app.install", "approval_id": approval.approval_id,
            "device_id": approval.device_id, "sha256": approval.package.sha256,
            "replace_existing": approval.replace_existing,
            "deadline_seconds": deadline_seconds,
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return self._task_executor.submit(
            approval.device_id, goal, run_factory, self._task_store.save,
            idempotency_key, fingerprint, deadline_seconds, task_type="app.install",
        ).to_dict()

    async def prepare_app_removal(
        self, device_id: str, app_id: str, keep_data: bool = False
    ) -> dict[str, Any]:
        """Inspect one non-system app and create a scoped removal Approval."""

        app_id = AppInventoryTool.validate_app_id(app_id)
        if not isinstance(keep_data, bool):
            raise MobileAgentError(
                "INVALID_ARGUMENT", ErrorCategory.VALIDATION, "keep_data 无效"
            )
        session_id = await self._adapter.require_online_session(device_id)
        with self._device_leases.hold(
            device_id, f"prepare_{uuid.uuid4().hex}", 30.0, session_id
        ), self._adapter.bind_session(device_id, session_id):
            device = next(
                (
                    item
                    for item in await self._adapter.list_devices()
                    if item.device_id == device_id
                ),
                None,
            )
            if device is None or "app.uninstall@1" not in device.capabilities:
                raise MobileAgentError(
                    "CAPABILITY_UNAVAILABLE",
                    ErrorCategory.CAPABILITY,
                    "设备不支持应用卸载",
                    details={"capability": "app.uninstall@1"},
                )
            app = await self._adapter.inspect_installed_app(device_id, app_id)
        if app.system_app is not False:
            raise MobileAgentError(
                "SYSTEM_APP_PROTECTED",
                ErrorCategory.POLICY,
                "系统应用或系统属性未知的应用不允许卸载",
                suggested_action="仅选择明确识别为非系统应用的测试包",
            )
        return self._app_removal_approvals.create(
            device_id, app, keep_data
        ).to_public_dict()

    def submit_app_removal_task(
        self,
        approval_id: str,
        confirmed: bool,
        idempotency_key: str,
        deadline_seconds: float = 180.0,
    ) -> dict[str, Any]:
        """Claim one scoped Approval and enqueue High-risk app removal."""

        if not confirmed:
            raise MobileAgentError(
                "CONFIRMATION_REQUIRED",
                ErrorCategory.POLICY,
                "应用卸载需要用户对数据删除影响进行明确确认",
            )
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise MobileAgentError(
                "INVALID_ARGUMENT",
                ErrorCategory.VALIDATION,
                "应用卸载必须提供 Idempotency-Key",
            )
        deadline_seconds = self._validated_deadline(deadline_seconds)
        approval = self._app_removal_approvals.claim(
            approval_id, idempotency_key
        )
        goal = f"卸载已批准的应用：{approval.app.app_id}"

        async def run_factory(
            task_id: str, on_step: Any, is_cancelled: Any, deadline_exceeded: Any
        ) -> TaskRun:
            try:
                session_id = await self._adapter.require_online_session(
                    approval.device_id
                )
                with self._device_leases.hold(
                    approval.device_id,
                    task_id,
                    deadline_seconds + 30.0,
                    session_id,
                ), self._adapter.bind_session(approval.device_id, session_id):
                    self._task_executor.bind_device_session(task_id, session_id)
                    task = await self._app_removal_task_runner.run(
                        task_id,
                        approval,
                        confirmed,
                        deadline_seconds,
                        on_step,
                        is_cancelled,
                        deadline_exceeded,
                    )
                    return replace(task, device_session_id=session_id)
            except MobileAgentError as error:
                now = _utc_now()
                return TaskRun(
                    task_id,
                    "app.uninstall",
                    approval.device_id,
                    goal,
                    TaskStatus.FAILED,
                    now,
                    now,
                    (),
                    {},
                    error.to_dict(),
                    deadline_seconds=deadline_seconds,
                )

        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "task_type": "app.uninstall",
                    "approval_id": approval.approval_id,
                    "device_id": approval.device_id,
                    "app_id": approval.app.app_id,
                    "version_code": approval.app.version_code,
                    "keep_data": approval.keep_data,
                    "deadline_seconds": deadline_seconds,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return self._task_executor.submit(
            approval.device_id,
            goal,
            run_factory,
            self._task_store.save,
            idempotency_key,
            fingerprint,
            deadline_seconds,
            task_type="app.uninstall",
        ).to_dict()

    async def inspect_app_runtime_state(
        self, device_id: str, app_id: str
    ) -> dict[str, Any]:
        """Return bounded application lifecycle state under Session and Lease."""

        app_id = AppInventoryTool.validate_app_id(app_id)
        session_id = await self._adapter.require_online_session(device_id)
        with self._device_leases.hold(
            device_id, f"skill_{uuid.uuid4().hex}", 30.0, session_id
        ), self._adapter.bind_session(device_id, session_id):
            return (await self._app_state.invoke(device_id, app_id)).to_dict()

    async def prepare_app_data_clear(
        self, device_id: str, app_id: str
    ) -> dict[str, Any]:
        """Inspect a non-system app and create a scoped data-clear Approval."""

        app_id = AppInventoryTool.validate_app_id(app_id)
        session_id = await self._adapter.require_online_session(device_id)
        with self._device_leases.hold(
            device_id, f"prepare_{uuid.uuid4().hex}", 30.0, session_id
        ), self._adapter.bind_session(device_id, session_id):
            device = next(
                (
                    item
                    for item in await self._adapter.list_devices()
                    if item.device_id == device_id
                ),
                None,
            )
            if device is None or "app.data.clear@1" not in device.capabilities:
                raise MobileAgentError(
                    "CAPABILITY_UNAVAILABLE",
                    ErrorCategory.CAPABILITY,
                    "设备不支持清除应用数据",
                    details={"capability": "app.data.clear@1"},
                )
            app = await self._adapter.inspect_installed_app(device_id, app_id)
        if app.system_app is not False:
            raise MobileAgentError(
                "SYSTEM_APP_PROTECTED",
                ErrorCategory.POLICY,
                "系统应用或系统属性未知的应用不允许清除数据",
                suggested_action="仅选择明确识别为非系统应用的测试包",
            )
        return self._app_data_clear_approvals.create(
            device_id, app
        ).to_public_dict()

    def submit_app_launch_task(
        self,
        device_id: str,
        app_id: str,
        idempotency_key: str,
        deadline_seconds: float = 60.0,
    ) -> dict[str, Any]:
        """Enqueue a deterministic application launch and foreground verification."""

        app_id = AppInventoryTool.validate_app_id(app_id)
        return self._submit_app_lifecycle_task(
            "app.launch",
            device_id,
            f"启动应用并验证前台：{app_id}",
            idempotency_key,
            deadline_seconds,
            {"app_id": app_id},
            lambda task_id, on_step, cancelled, exceeded: (
                self._app_lifecycle_task_runner.run_launch(
                    task_id,
                    device_id,
                    app_id,
                    deadline_seconds,
                    on_step,
                    cancelled,
                    exceeded,
                )
            ),
        )

    def submit_app_stop_task(
        self,
        device_id: str,
        app_id: str,
        confirmed: bool,
        idempotency_key: str,
        deadline_seconds: float = 60.0,
    ) -> dict[str, Any]:
        """Enqueue one explicitly confirmed non-system application stop."""

        app_id = AppInventoryTool.validate_app_id(app_id)
        if not confirmed:
            raise MobileAgentError(
                "CONFIRMATION_REQUIRED",
                ErrorCategory.POLICY,
                "停止应用需要用户明确确认",
            )
        return self._submit_app_lifecycle_task(
            "app.stop",
            device_id,
            f"停止非系统应用并验证：{app_id}",
            idempotency_key,
            deadline_seconds,
            {"app_id": app_id, "confirmed": True},
            lambda task_id, on_step, cancelled, exceeded: (
                self._app_lifecycle_task_runner.run_stop(
                    task_id,
                    device_id,
                    app_id,
                    confirmed,
                    deadline_seconds,
                    on_step,
                    cancelled,
                    exceeded,
                )
            ),
        )

    def submit_app_data_clear_task(
        self,
        approval_id: str,
        confirmed: bool,
        idempotency_key: str,
        deadline_seconds: float = 180.0,
    ) -> dict[str, Any]:
        """Claim a scoped Approval and enqueue High-risk application data clear."""

        if not confirmed:
            raise MobileAgentError(
                "CONFIRMATION_REQUIRED",
                ErrorCategory.POLICY,
                "清除应用数据需要用户对删除影响进行明确确认",
            )
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise MobileAgentError(
                "INVALID_ARGUMENT",
                ErrorCategory.VALIDATION,
                "清除应用数据必须提供 Idempotency-Key",
            )
        approval = self._app_data_clear_approvals.claim(
            approval_id, idempotency_key
        )
        return self._submit_app_lifecycle_task(
            "app.data.clear",
            approval.device_id,
            f"清除已批准应用的数据：{approval.app.app_id}",
            idempotency_key,
            deadline_seconds,
            {
                "approval_id": approval.approval_id,
                "app_id": approval.app.app_id,
                "version_code": approval.app.version_code,
            },
            lambda task_id, on_step, cancelled, exceeded: (
                self._app_lifecycle_task_runner.run_clear_data(
                    task_id,
                    approval,
                    confirmed,
                    deadline_seconds,
                    on_step,
                    cancelled,
                    exceeded,
                )
            ),
        )

    def _submit_app_lifecycle_task(
        self,
        task_type: str,
        device_id: str,
        goal: str,
        idempotency_key: str,
        deadline_seconds: float,
        fingerprint_fields: dict[str, Any],
        invoke: Callable[
            [str, Any, Any, Any], Awaitable[TaskRun]
        ],
    ) -> dict[str, Any]:
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise MobileAgentError(
                "INVALID_ARGUMENT",
                ErrorCategory.VALIDATION,
                "应用生命周期任务必须提供 Idempotency-Key",
            )
        deadline_seconds = self._validated_deadline(deadline_seconds)

        async def run_factory(
            task_id: str, on_step: Any, is_cancelled: Any, deadline_exceeded: Any
        ) -> TaskRun:
            try:
                session_id = await self._adapter.require_online_session(device_id)
                with self._device_leases.hold(
                    device_id,
                    task_id,
                    deadline_seconds + 30.0,
                    session_id,
                ), self._adapter.bind_session(device_id, session_id):
                    self._task_executor.bind_device_session(task_id, session_id)
                    task = await invoke(
                        task_id, on_step, is_cancelled, deadline_exceeded
                    )
                    return replace(task, device_session_id=session_id)
            except MobileAgentError as error:
                now = _utc_now()
                return TaskRun(
                    task_id,
                    task_type,
                    device_id,
                    goal,
                    TaskStatus.FAILED,
                    now,
                    now,
                    (),
                    {},
                    error.to_dict(),
                    deadline_seconds=deadline_seconds,
                )

        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "task_type": task_type,
                    "device_id": device_id,
                    "deadline_seconds": deadline_seconds,
                    **fingerprint_fields,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return self._task_executor.submit(
            device_id,
            goal,
            run_factory,
            self._task_store.save,
            idempotency_key,
            fingerprint,
            deadline_seconds,
            task_type=task_type,
        ).to_dict()

    @staticmethod
    def _capability_availability(
        capability: str,
        advertised: frozenset[str],
        device_status: DeviceAvailabilityStatus,
    ) -> CapabilityAvailability:
        if device_status is DeviceAvailabilityStatus.READY:
            return (
                CapabilityAvailability.AVAILABLE
                if capability in advertised
                else CapabilityAvailability.UNSUPPORTED
            )
        if device_status is DeviceAvailabilityStatus.BUSY:
            return (
                CapabilityAvailability.TEMPORARILY_UNAVAILABLE
                if capability in advertised
                else CapabilityAvailability.UNSUPPORTED
            )
        return CapabilityAvailability.UNKNOWN

    def list_tools(self) -> list[dict[str, str | bool]]:
        return [definition.to_dict() for definition in self._tool_registry.list()]

    async def invoke_tool(
        self, tool_id: str, device_id: str, arguments: dict[str, Any], confirmed: bool = False
    ) -> dict[str, Any]:
        session_id = await self._adapter.require_online_session(device_id)
        with self._device_leases.hold(
            device_id,
            f"tool_{uuid.uuid4().hex}",
            120.0,
            session_id,
        ), self._adapter.bind_session(device_id, session_id):
            return (
                await self._tools.execute(tool_id, device_id, arguments, confirmed)
            ).to_dict()

    async def open_app(self, device_id: str, app_id: str) -> dict[str, Any]:
        session_id = await self._adapter.require_online_session(device_id)
        with self._device_leases.hold(
            device_id,
            f"skill_{uuid.uuid4().hex}",
            120.0,
            session_id,
        ), self._adapter.bind_session(device_id, session_id):
            return (await self._open_app.invoke(device_id, app_id)).to_dict()

    async def collect_device_logs(
        self,
        device_id: str,
        max_lines: int = 500,
        minimum_level: str = "info",
        confirmed: bool = False,
    ) -> dict[str, Any]:
        """Collect one bounded log snapshot under a device lease and session binding."""

        DeviceLogCaptureTool.validate_request(max_lines, minimum_level)
        session_id = await self._adapter.require_online_session(device_id)
        with self._device_leases.hold(
            device_id,
            f"skill_{uuid.uuid4().hex}",
            60.0,
            session_id,
        ), self._adapter.bind_session(device_id, session_id):
            return (
                await self._device_logs.invoke(
                    device_id, max_lines, minimum_level, confirmed
                )
            ).to_dict()

    async def capture_device_performance(self, device_id: str) -> dict[str, Any]:
        """Capture one aggregate performance snapshot under Session and Lease."""

        session_id = await self._adapter.require_online_session(device_id)
        with self._device_leases.hold(
            device_id,
            f"skill_{uuid.uuid4().hex}",
            90.0,
            session_id,
        ), self._adapter.bind_session(device_id, session_id):
            return (await self._device_performance.invoke(device_id)).to_dict()

    async def navigate_settings(
        self,
        device_id: str,
        target_selector: dict[str, Any],
        expected_selector: dict[str, Any],
        confirmed: bool = False,
    ) -> dict[str, Any]:
        session_id = await self._adapter.require_online_session(device_id)
        with self._device_leases.hold(
            device_id,
            f"skill_{uuid.uuid4().hex}",
            180.0,
            session_id,
        ), self._adapter.bind_session(device_id, session_id):
            return (
                await self._settings_navigate.invoke(
                    device_id, target_selector, expected_selector, confirmed
                )
            ).to_dict()

    async def scroll_navigate_settings(
        self,
        device_id: str,
        target_selector: dict[str, Any],
        expected_selector: dict[str, Any],
        direction: str = "up",
        max_scrolls: int = 3,
        confirmed: bool = False,
        distance_percent: float = 0.8,
        duration_ms: int = 800,
        settle_seconds: float = 0.8,
    ) -> dict[str, Any]:
        session_id = await self._adapter.require_online_session(device_id)
        with self._device_leases.hold(
            device_id,
            f"skill_{uuid.uuid4().hex}",
            180.0,
            session_id,
        ), self._adapter.bind_session(device_id, session_id):
            return (
                await self._settings_scroll_navigate.invoke(
                    device_id,
                    target_selector,
                    expected_selector,
                    direction,
                    max_scrolls,
                    confirmed,
                    distance_percent,
                    duration_ms,
                    settle_seconds,
                )
            ).to_dict()

    async def run_settings_scroll_navigation_task(
        self,
        device_id: str,
        target_selector: dict[str, Any],
        expected_selector: dict[str, Any],
        direction: str = "up",
        max_scrolls: int = 3,
        confirmed: bool = False,
        distance_percent: float = 0.8,
        duration_ms: int = 800,
        settle_seconds: float = 0.8,
        goal: str | None = None,
    ) -> dict[str, Any]:
        session_id = await self._adapter.require_online_session(device_id)
        with self._device_leases.hold(
            device_id,
            f"task_{uuid.uuid4().hex}",
            180.0,
            session_id,
        ), self._adapter.bind_session(device_id, session_id):
            task = await self._tasks.run_settings_scroll_navigation(
                device_id,
                target_selector,
                expected_selector,
                direction,
                max_scrolls,
                confirmed,
                distance_percent,
                duration_ms,
                settle_seconds,
                goal,
            )
            task = replace(task, device_session_id=session_id)
        self._task_store.save(task)
        return task.to_dict()

    async def run_agent_task(
        self,
        device_id: str,
        goal: str,
        confirmed: bool = False,
        max_rounds: int = 6,
        acceptance: object | None = None,
        goal_spec: object | None = None,
        goal_spec_confirmed: bool = False,
        deadline_seconds: float = 600.0,
    ) -> dict[str, Any]:
        deadline_seconds = self._validated_deadline(deadline_seconds)
        normalized_goal, parsed_acceptance, parsed_spec = self._prepare_agent_task(
            goal, acceptance, goal_spec, goal_spec_confirmed
        )
        task_id = f"task_{uuid.uuid4().hex}"
        deadline_monotonic = self._monotonic() + deadline_seconds
        session_id = await self._adapter.require_online_session(device_id)
        with self._device_leases.hold(
            device_id, task_id, deadline_seconds + 30.0, session_id
        ), self._adapter.bind_session(device_id, session_id):
            task = await self._agent_runner.run(
                device_id,
                normalized_goal,
                confirmed,
                max_rounds,
                parsed_acceptance,
                parsed_spec.execution_goal if parsed_spec is not None else None,
                parsed_spec.to_dict() if parsed_spec is not None else None,
                task_id,
                None,
                None,
                lambda: self._monotonic() >= deadline_monotonic,
                deadline_seconds,
            )
            task = replace(task, device_session_id=session_id)
        self._task_store.save(task)
        return task.to_dict()

    def _prepare_agent_task(
        self,
        goal: str,
        acceptance: object | None,
        goal_spec: object | None,
        goal_spec_confirmed: bool,
    ) -> tuple[str, AgentGoalAcceptance | None, AgentGoalSpec | None]:
        """Validate task input before any model or device side effect."""

        parsed_spec = AgentGoalSpec.from_dict(goal_spec) if goal_spec is not None else None
        normalized_goal = goal.strip()
        if parsed_spec is not None and parsed_spec.source_goal != normalized_goal:
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="GoalSpec source_goal 与请求 goal 不一致",
            )
        if (
            parsed_spec is not None
            and parsed_spec.confirmation_required
            and not goal_spec_confirmed
        ):
            raise MobileAgentError(
                code="CONFIRMATION_REQUIRED",
                category=ErrorCategory.POLICY,
                message="模型生成的 GoalSpec 需要用户确认后才能执行",
            )
        if (
            parsed_spec is not None
            and parsed_spec.acceptance is not None
            and acceptance is not None
        ):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="goal_spec 与请求不能同时定义 acceptance",
            )
        parsed_acceptance = (
            AgentGoalAcceptance.from_dict(acceptance)
            if acceptance is not None
            else (parsed_spec.acceptance if parsed_spec is not None else None)
        )
        return normalized_goal, parsed_acceptance, parsed_spec

    def submit_agent_task(
        self,
        device_id: str,
        goal: str,
        confirmed: bool = False,
        max_rounds: int = 6,
        acceptance: object | None = None,
        goal_spec: object | None = None,
        goal_spec_confirmed: bool = False,
        idempotency_key: str | None = None,
        deadline_seconds: float = 600.0,
    ) -> dict[str, Any]:
        """Validate and enqueue one Agent task without blocking the caller."""

        deadline_seconds = self._validated_deadline(deadline_seconds)
        normalized_goal, parsed_acceptance, parsed_spec = self._prepare_agent_task(
            goal, acceptance, goal_spec, goal_spec_confirmed
        )

        async def run_factory(
            task_id: str,
            on_step: Any,
            is_cancelled: Any,
            deadline_exceeded: Any,
        ) -> Any:
            try:
                session_id = await self._adapter.require_online_session(device_id)
                with self._device_leases.hold(
                    device_id, task_id, deadline_seconds + 30.0, session_id
                ), self._adapter.bind_session(device_id, session_id):
                    self._task_executor.bind_device_session(task_id, session_id)
                    task = await self._agent_runner.run(
                        device_id,
                        normalized_goal,
                        confirmed,
                        max_rounds,
                        parsed_acceptance,
                        parsed_spec.execution_goal if parsed_spec is not None else None,
                        parsed_spec.to_dict() if parsed_spec is not None else None,
                        task_id,
                        on_step,
                        is_cancelled,
                        deadline_exceeded,
                        deadline_seconds,
                    )
                    return replace(task, device_session_id=session_id)
            except MobileAgentError as error:
                return self._agent_preflight_error_task(
                    task_id,
                    device_id,
                    normalized_goal,
                    error,
                    deadline_seconds,
                    parsed_spec,
                    parsed_acceptance,
                )

        execution = self._task_executor.submit(
            device_id,
            normalized_goal,
            run_factory,
            self._task_store.save,
            idempotency_key,
            self._agent_request_fingerprint(
                device_id,
                normalized_goal,
                confirmed,
                max_rounds,
                parsed_acceptance,
                parsed_spec,
                deadline_seconds,
            ),
            deadline_seconds,
        )
        return execution.to_dict()

    def submit_device_logs_task(
        self,
        device_id: str,
        max_lines: int = 500,
        minimum_level: str = "info",
        confirmed: bool = False,
        idempotency_key: str | None = None,
        deadline_seconds: float = 60.0,
    ) -> dict[str, Any]:
        """Validate and enqueue one bounded diagnostic log task."""

        max_lines, level = DeviceLogCaptureTool.validate_request(
            max_lines, minimum_level
        )
        deadline_seconds = self._validated_deadline(deadline_seconds)
        definition = self._tool_registry.get(DeviceLogCaptureTool.tool_id)
        self._policy.authorize(definition.risk, confirmed)
        goal = f"采集最近 {max_lines} 行 {level.value} 及以上设备日志"

        async def run_factory(
            task_id: str,
            on_step: Any,
            is_cancelled: Any,
            deadline_exceeded: Any,
        ) -> TaskRun:
            try:
                session_id = await self._adapter.require_online_session(device_id)
                with self._device_leases.hold(
                    device_id, task_id, deadline_seconds + 30.0, session_id
                ), self._adapter.bind_session(device_id, session_id):
                    self._task_executor.bind_device_session(task_id, session_id)
                    task = await self._device_logs_task_runner.run(
                        task_id,
                        device_id,
                        max_lines,
                        level.value,
                        confirmed,
                        deadline_seconds,
                        on_step,
                        is_cancelled,
                        deadline_exceeded,
                    )
                    return replace(task, device_session_id=session_id)
            except MobileAgentError as error:
                now = _utc_now()
                return TaskRun(
                    task_id=task_id,
                    task_type="device.logs.collect",
                    device_id=device_id,
                    goal=goal,
                    status=TaskStatus.FAILED,
                    started_at=now,
                    completed_at=now,
                    steps=(),
                    evidence_summary={},
                    error=error.to_dict(),
                    deadline_seconds=deadline_seconds,
                )

        execution = self._task_executor.submit(
            device_id,
            goal,
            run_factory,
            self._task_store.save,
            idempotency_key,
            self._device_logs_request_fingerprint(
                device_id,
                max_lines,
                level.value,
                confirmed,
                deadline_seconds,
            ),
            deadline_seconds,
            task_type="device.logs.collect",
        )
        return execution.to_dict()

    def submit_device_performance_task(
        self,
        device_id: str,
        idempotency_key: str | None = None,
        deadline_seconds: float = 90.0,
    ) -> dict[str, Any]:
        """Enqueue one explicitly registered aggregate performance task."""

        deadline_seconds = self._validated_deadline(deadline_seconds)
        goal = "采集设备聚合性能快照"

        async def run_factory(
            task_id: str,
            on_step: Any,
            is_cancelled: Any,
            deadline_exceeded: Any,
        ) -> TaskRun:
            try:
                session_id = await self._adapter.require_online_session(device_id)
                with self._device_leases.hold(
                    device_id, task_id, deadline_seconds + 30.0, session_id
                ), self._adapter.bind_session(device_id, session_id):
                    self._task_executor.bind_device_session(task_id, session_id)
                    task = await self._device_performance_task_runner.run(
                        task_id,
                        device_id,
                        deadline_seconds,
                        on_step,
                        is_cancelled,
                        deadline_exceeded,
                    )
                    return replace(task, device_session_id=session_id)
            except MobileAgentError as error:
                now = _utc_now()
                return TaskRun(
                    task_id=task_id,
                    task_type="device.performance.snapshot",
                    device_id=device_id,
                    goal=goal,
                    status=TaskStatus.FAILED,
                    started_at=now,
                    completed_at=now,
                    steps=(),
                    evidence_summary={},
                    error=error.to_dict(),
                    deadline_seconds=deadline_seconds,
                )

        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "task_type": "device.performance.snapshot",
                    "device_id": device_id,
                    "deadline_seconds": deadline_seconds,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        execution = self._task_executor.submit(
            device_id,
            goal,
            run_factory,
            self._task_store.save,
            idempotency_key,
            fingerprint,
            deadline_seconds,
            task_type="device.performance.snapshot",
        )
        return execution.to_dict()

    def submit_diagnostic_bundle_task(
        self,
        device_id: str,
        app_id: str | None = None,
        max_log_lines: int = 500,
        minimum_log_level: str = "info",
        confirmed: bool = False,
        idempotency_key: str | None = None,
        deadline_seconds: float = 120.0,
    ) -> dict[str, Any]:
        """Enqueue one confirmed, bounded, local-only diagnostic bundle."""

        if app_id is not None:
            app_id = AppInventoryTool.validate_app_id(app_id)
        max_log_lines, level = DeviceLogCaptureTool.validate_request(
            max_log_lines, minimum_log_level
        )
        deadline_seconds = self._validated_deadline(deadline_seconds)
        definition = self._tool_registry.get("device.diagnostics.bundle")
        self._policy.authorize(definition.risk, confirmed)
        goal = "采集本地工程诊断包"

        async def run_factory(
            task_id: str,
            on_step: Any,
            is_cancelled: Any,
            deadline_exceeded: Any,
        ) -> TaskRun:
            try:
                session_id = await self._adapter.require_online_session(device_id)
                with self._device_leases.hold(
                    device_id, task_id, deadline_seconds + 30.0, session_id
                ), self._adapter.bind_session(device_id, session_id):
                    self._task_executor.bind_device_session(task_id, session_id)
                    task = await self._diagnostic_bundle_task_runner.run(
                        task_id,
                        device_id,
                        app_id,
                        max_log_lines,
                        level.value,
                        confirmed,
                        deadline_seconds,
                        on_step,
                        is_cancelled,
                        deadline_exceeded,
                    )
                    return replace(task, device_session_id=session_id)
            except MobileAgentError as error:
                now = _utc_now()
                return TaskRun(
                    task_id=task_id,
                    task_type="device.diagnostics.bundle",
                    device_id=device_id,
                    goal=goal,
                    status=TaskStatus.FAILED,
                    started_at=now,
                    completed_at=now,
                    steps=(),
                    evidence_summary={},
                    error=error.to_dict(),
                    deadline_seconds=deadline_seconds,
                )

        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "task_type": "device.diagnostics.bundle",
                    "device_id": device_id,
                    "app_id": app_id,
                    "max_log_lines": max_log_lines,
                    "minimum_log_level": level.value,
                    "confirmed": confirmed,
                    "deadline_seconds": deadline_seconds,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return self._task_executor.submit(
            device_id,
            goal,
            run_factory,
            self._task_store.save,
            idempotency_key,
            fingerprint,
            deadline_seconds,
            task_type="device.diagnostics.bundle",
        ).to_dict()

    @staticmethod
    def _device_logs_request_fingerprint(
        device_id: str,
        max_lines: int,
        minimum_level: str,
        confirmed: bool,
        deadline_seconds: float,
    ) -> str:
        payload = {
            "task_type": "device.logs.collect",
            "device_id": device_id,
            "max_lines": max_lines,
            "minimum_level": minimum_level,
            "confirmed": confirmed,
            "deadline_seconds": deadline_seconds,
        }
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _agent_request_fingerprint(
        device_id: str,
        goal: str,
        confirmed: bool,
        max_rounds: int,
        acceptance: AgentGoalAcceptance | None,
        goal_spec: AgentGoalSpec | None,
        deadline_seconds: float,
    ) -> str:
        payload = {
            "device_id": device_id,
            "goal": goal,
            "confirmed": confirmed,
            "max_rounds": max_rounds,
            "acceptance": acceptance.to_dict() if acceptance is not None else None,
            "goal_spec": goal_spec.to_dict() if goal_spec is not None else None,
            "deadline_seconds": deadline_seconds,
        }
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _validated_deadline(value: float) -> float:
        if (
            not isinstance(value, int | float)
            or isinstance(value, bool)
            or value < 1
            or value > 1800
        ):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="deadline_seconds 必须在 1 到 1800 之间",
            )
        return float(value)

    @staticmethod
    def _agent_preflight_error_task(
        task_id: str,
        device_id: str,
        goal: str,
        error: MobileAgentError,
        deadline_seconds: float,
        goal_spec: AgentGoalSpec | None,
        acceptance: AgentGoalAcceptance | None,
    ) -> TaskRun:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return TaskRun(
            task_id=task_id,
            task_type="agent.run",
            device_id=device_id,
            goal=goal,
            status=TaskStatus.FAILED,
            started_at=now,
            completed_at=now,
            steps=(),
            evidence_summary={"rounds_completed": 0},
            error=error.to_dict(),
            goal_spec=goal_spec.to_dict() if goal_spec is not None else None,
            goal_acceptance=acceptance.to_dict() if acceptance is not None else None,
            deadline_seconds=deadline_seconds,
        )

    def get_task_execution(self, task_id: str) -> dict[str, Any]:
        """Return the latest asynchronous execution snapshot."""

        return self._task_executor.get(task_id).to_dict()

    def list_task_execution_events(self, task_id: str) -> list[dict[str, Any]]:
        """Return durable live events for an asynchronous execution."""

        return [dict(event) for event in self._task_executor.list_events(task_id)]

    def cancel_task_execution(self, task_id: str) -> dict[str, Any]:
        """Request cooperative cancellation for queued or running work."""

        return self._task_executor.cancel(task_id).to_dict()

    def pause_task_execution(self, task_id: str) -> dict[str, Any]:
        """Request a cooperative pause for manual takeover at a safe boundary."""

        return self._task_executor.pause(task_id).to_dict()

    def resume_task_execution(self, task_id: str) -> dict[str, Any]:
        """Resume a paused execution; the agent re-observes before its next action."""

        return self._task_executor.resume(task_id).to_dict()

    def compile_goal(self, goal: str) -> dict[str, Any]:
        """Compile a goal without observing or mutating a device."""

        return self._goal_compiler.compile(goal).to_dict()

    def get_task(self, task_id: str) -> dict[str, Any]:
        task = dict(self._task_store.get_task_dict(task_id))
        deleted = self._task_store.list_deleted_artifact_ids()
        return self._annotate_artifact_availability(task, deleted)

    def _annotate_artifact_availability(
        self, value: Any, deleted: set[str]
    ) -> Any:
        if isinstance(value, list):
            return [
                self._annotate_artifact_availability(item, deleted)
                for item in value
            ]
        if not isinstance(value, dict):
            return value
        result = {
            key: self._annotate_artifact_availability(item, deleted)
            for key, item in value.items()
        }
        artifact_id = value.get("artifact_id")
        relative_path = value.get("relative_path")
        if (
            isinstance(artifact_id, str)
            and artifact_id.startswith("artifact_")
            and isinstance(relative_path, str)
        ):
            try:
                available = self._artifacts.resolve(relative_path).is_file()
            except MobileAgentError:
                available = False
            result["availability"] = (
                "available"
                if available
                else "expired"
                if artifact_id in deleted
                else "missing"
            )
        return result

    def list_task_events(self, task_id: str) -> list[dict[str, Any]]:
        return [dict(event) for event in self._task_store.list_event_dicts(task_id)]

    def list_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        return [dict(task) for task in self._task_store.list_task_summaries(limit)]

    def evaluate_agent_task(
        self, task_id: str, scenario: object
    ) -> dict[str, Any]:
        """Evaluate a stored live Agent task against independent acceptance criteria."""

        task = dict(self._task_store.get_task_dict(task_id))
        return self._agent_evaluator.evaluate(task, scenario)

    def compare_device_performance(
        self, baseline_task_id: str, candidate_task_id: str
    ) -> dict[str, Any]:
        """Compare two stored aggregate snapshots without device access."""

        if baseline_task_id == candidate_task_id:
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="基线任务和候选任务不能相同",
                details={"reason": "same_task"},
            )
        baseline = dict(self._task_store.get_task_dict(baseline_task_id))
        candidate = dict(self._task_store.get_task_dict(candidate_task_id))
        return compare_performance_tasks(baseline, candidate).to_dict()

    def list_devices_sync(self) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            return HTTPStatus.OK, {"devices": asyncio.run(self.list_devices())}
        except MobileAgentError as error:
            status = (
                HTTPStatus.SERVICE_UNAVAILABLE
                if error.code in {"ADB_NOT_FOUND", "DEVICE_DISCOVERY_FAILED"}
                else HTTPStatus.UNPROCESSABLE_ENTITY
            )
            return status, {"error": error.to_dict()}

    def readiness_sync(self) -> tuple[HTTPStatus, dict[str, Any]]:
        """Return readiness as a renderable snapshot even when blocked."""

        return HTTPStatus.OK, {"readiness": asyncio.run(self.readiness())}

    def observe_sync(self, device_id: str) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            return HTTPStatus.OK, {"observation": asyncio.run(self.observe(device_id))}
        except MobileAgentError as error:
            if error.code == "DEVICE_NOT_FOUND":
                status = HTTPStatus.NOT_FOUND
            elif error.code in {"INVALID_ARGUMENT"}:
                status = HTTPStatus.BAD_REQUEST
            else:
                status = HTTPStatus.SERVICE_UNAVAILABLE
            return status, {"error": error.to_dict()}

    def inspect_device_sync(
        self, device_id: str
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            return HTTPStatus.OK, {
                "inspection": asyncio.run(self.inspect_device(device_id))
            }
        except MobileAgentError as error:
            return self._error_response(error)

    def list_installed_apps_sync(
        self, device_id: str, limit: int = 200, prefix: str | None = None
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            inventory = asyncio.run(self.list_installed_apps(device_id, limit, prefix))
            return HTTPStatus.OK, {"inventory": inventory}
        except MobileAgentError as error:
            return self._error_response(error)

    def local_storage_summary_sync(
        self, retention_days: int | None = None
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            return HTTPStatus.OK, {
                "storage": self.local_storage_summary(retention_days)
            }
        except MobileAgentError as error:
            return self._error_response(error)

    def artifact_screenshot_content_sync(
        self, artifact_id: str
    ) -> tuple[HTTPStatus, bytes | dict[str, Any]]:
        """Read one stored screenshot artifact as bounded PNG bytes.

        与 JSON 端点不同，成功时返回原始字节；该端点只服务截图 Artifact，
        由 API 层在调用前完成 Bearer token 认证。
        """
        try:
            return HTTPStatus.OK, self._artifacts.screenshot_content(artifact_id)
        except MobileAgentError as error:
            status, payload = self._error_response(error)
            return status, payload

    def prepare_local_data_cleanup_sync(
        self, retention_days: int | None = None, max_artifacts: int = 500
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            return HTTPStatus.OK, {
                "approval": self.prepare_local_data_cleanup(
                    retention_days, max_artifacts
                )
            }
        except MobileAgentError as error:
            return self._error_response(error)

    def submit_local_data_cleanup_task_sync(
        self,
        approval_id: str,
        confirmed: bool,
        idempotency_key: str,
        deadline_seconds: float = 120.0,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            execution = self.submit_local_data_cleanup_task(
                approval_id, confirmed, idempotency_key, deadline_seconds
            )
            return HTTPStatus.ACCEPTED, {"execution": execution}
        except MobileAgentError as error:
            return self._error_response(error)

    def inspect_installed_app_sync(
        self, device_id: str, app_id: str
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            app = asyncio.run(self.inspect_installed_app(device_id, app_id))
            return HTTPStatus.OK, {"app": app}
        except MobileAgentError as error:
            return self._error_response(error)

    def prepare_apk_install_sync(
        self, device_id: str, apk_path: str, expected_app_id: str,
        replace_existing: bool = False,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            approval = asyncio.run(self.prepare_apk_install(
                device_id, apk_path, expected_app_id, replace_existing
            ))
            return HTTPStatus.OK, {"approval": approval}
        except MobileAgentError as error:
            return self._error_response(error)

    def submit_apk_install_task_sync(
        self, approval_id: str, confirmed: bool, idempotency_key: str,
        deadline_seconds: float = 300.0,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            execution = self.submit_apk_install_task(
                approval_id, confirmed, idempotency_key, deadline_seconds
            )
            return HTTPStatus.ACCEPTED, {"execution": execution}
        except MobileAgentError as error:
            return self._error_response(error)

    def prepare_app_removal_sync(
        self, device_id: str, app_id: str, keep_data: bool = False
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            approval = asyncio.run(
                self.prepare_app_removal(device_id, app_id, keep_data)
            )
            return HTTPStatus.OK, {"approval": approval}
        except MobileAgentError as error:
            return self._error_response(error)

    def submit_app_removal_task_sync(
        self,
        approval_id: str,
        confirmed: bool,
        idempotency_key: str,
        deadline_seconds: float = 180.0,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            execution = self.submit_app_removal_task(
                approval_id, confirmed, idempotency_key, deadline_seconds
            )
            return HTTPStatus.ACCEPTED, {"execution": execution}
        except MobileAgentError as error:
            return self._error_response(error)

    def inspect_app_runtime_state_sync(
        self, device_id: str, app_id: str
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        """Synchronous interface wrapper for bounded application state."""

        try:
            state = asyncio.run(self.inspect_app_runtime_state(device_id, app_id))
            return HTTPStatus.OK, {"state": state}
        except MobileAgentError as error:
            return self._error_response(error)

    def prepare_app_data_clear_sync(
        self, device_id: str, app_id: str
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        """Synchronous interface wrapper for application data-clear preflight."""

        try:
            approval = asyncio.run(self.prepare_app_data_clear(device_id, app_id))
            return HTTPStatus.OK, {"approval": approval}
        except MobileAgentError as error:
            return self._error_response(error)

    def submit_app_launch_task_sync(
        self,
        device_id: str,
        app_id: str,
        idempotency_key: str,
        deadline_seconds: float = 60.0,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        """Synchronous interface wrapper for deterministic app launch."""

        try:
            execution = self.submit_app_launch_task(
                device_id, app_id, idempotency_key, deadline_seconds
            )
            return HTTPStatus.ACCEPTED, {"execution": execution}
        except MobileAgentError as error:
            return self._error_response(error)

    def submit_app_stop_task_sync(
        self,
        device_id: str,
        app_id: str,
        confirmed: bool,
        idempotency_key: str,
        deadline_seconds: float = 60.0,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        """Synchronous interface wrapper for explicitly confirmed app stop."""

        try:
            execution = self.submit_app_stop_task(
                device_id,
                app_id,
                confirmed,
                idempotency_key,
                deadline_seconds,
            )
            return HTTPStatus.ACCEPTED, {"execution": execution}
        except MobileAgentError as error:
            return self._error_response(error)

    def submit_app_data_clear_task_sync(
        self,
        approval_id: str,
        confirmed: bool,
        idempotency_key: str,
        deadline_seconds: float = 180.0,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        """Synchronous interface wrapper for approved application data clear."""

        try:
            execution = self.submit_app_data_clear_task(
                approval_id, confirmed, idempotency_key, deadline_seconds
            )
            return HTTPStatus.ACCEPTED, {"execution": execution}
        except MobileAgentError as error:
            return self._error_response(error)

    def invoke_tool_sync(
        self, tool_id: str, device_id: str, arguments: dict[str, Any], confirmed: bool = False
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            result = asyncio.run(self.invoke_tool(tool_id, device_id, arguments, confirmed))
            return HTTPStatus.OK, {"action": result}
        except MobileAgentError as error:
            return self._error_response(error)

    def open_app_sync(self, device_id: str, app_id: str) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            return HTTPStatus.OK, {"result": asyncio.run(self.open_app(device_id, app_id))}
        except MobileAgentError as error:
            return self._error_response(error)

    def collect_device_logs_sync(
        self,
        device_id: str,
        max_lines: int = 500,
        minimum_level: str = "info",
        confirmed: bool = False,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        """Synchronous interface wrapper for the device log Skill."""

        try:
            result = asyncio.run(
                self.collect_device_logs(
                    device_id, max_lines, minimum_level, confirmed
                )
            )
            return HTTPStatus.OK, {"result": result}
        except MobileAgentError as error:
            return self._error_response(error)

    def capture_device_performance_sync(
        self, device_id: str
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        """Synchronous interface wrapper for aggregate performance sampling."""

        try:
            result = asyncio.run(self.capture_device_performance(device_id))
            return HTTPStatus.OK, {"result": result}
        except MobileAgentError as error:
            return self._error_response(error)

    def navigate_settings_sync(
        self,
        device_id: str,
        target_selector: dict[str, Any],
        expected_selector: dict[str, Any],
        confirmed: bool = False,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            result = asyncio.run(
                self.navigate_settings(
                    device_id, target_selector, expected_selector, confirmed
                )
            )
            return HTTPStatus.OK, {"result": result}
        except MobileAgentError as error:
            return self._error_response(error)

    def scroll_navigate_settings_sync(
        self,
        device_id: str,
        target_selector: dict[str, Any],
        expected_selector: dict[str, Any],
        direction: str = "up",
        max_scrolls: int = 3,
        confirmed: bool = False,
        distance_percent: float = 0.8,
        duration_ms: int = 800,
        settle_seconds: float = 0.8,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            result = asyncio.run(
                self.scroll_navigate_settings(
                    device_id,
                    target_selector,
                    expected_selector,
                    direction,
                    max_scrolls,
                    confirmed,
                    distance_percent,
                    duration_ms,
                    settle_seconds,
                )
            )
            return HTTPStatus.OK, {"result": result}
        except MobileAgentError as error:
            return self._error_response(error)

    def run_settings_scroll_navigation_task_sync(
        self,
        device_id: str,
        target_selector: dict[str, Any],
        expected_selector: dict[str, Any],
        direction: str = "up",
        max_scrolls: int = 3,
        confirmed: bool = False,
        distance_percent: float = 0.8,
        duration_ms: int = 800,
        settle_seconds: float = 0.8,
        goal: str | None = None,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        result = asyncio.run(
            self.run_settings_scroll_navigation_task(
                device_id,
                target_selector,
                expected_selector,
                direction,
                max_scrolls,
                confirmed,
                distance_percent,
                duration_ms,
                settle_seconds,
                goal,
            )
        )
        return HTTPStatus.OK, {"task": result}

    def run_agent_task_sync(
        self,
        device_id: str,
        goal: str,
        confirmed: bool = False,
        max_rounds: int = 6,
        acceptance: object | None = None,
        goal_spec: object | None = None,
        goal_spec_confirmed: bool = False,
        deadline_seconds: float = 600.0,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            result = asyncio.run(
                self.run_agent_task(
                    device_id,
                    goal,
                    confirmed,
                    max_rounds,
                    acceptance,
                    goal_spec,
                    goal_spec_confirmed,
                    deadline_seconds,
                )
            )
            return HTTPStatus.OK, {"task": result}
        except MobileAgentError as error:
            return self._error_response(error)

    def submit_agent_task_sync(
        self,
        device_id: str,
        goal: str,
        confirmed: bool = False,
        max_rounds: int = 6,
        acceptance: object | None = None,
        goal_spec: object | None = None,
        goal_spec_confirmed: bool = False,
        idempotency_key: str | None = None,
        deadline_seconds: float = 600.0,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            execution = self.submit_agent_task(
                device_id,
                goal,
                confirmed,
                max_rounds,
                acceptance,
                goal_spec,
                goal_spec_confirmed,
                idempotency_key,
                deadline_seconds,
            )
            return HTTPStatus.ACCEPTED, {"execution": execution}
        except MobileAgentError as error:
            return self._error_response(error)

    def submit_device_logs_task_sync(
        self,
        device_id: str,
        max_lines: int = 500,
        minimum_level: str = "info",
        confirmed: bool = False,
        idempotency_key: str | None = None,
        deadline_seconds: float = 60.0,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        """Synchronous submission wrapper for asynchronous diagnostic logs."""

        try:
            execution = self.submit_device_logs_task(
                device_id,
                max_lines,
                minimum_level,
                confirmed,
                idempotency_key,
                deadline_seconds,
            )
            return HTTPStatus.ACCEPTED, {"execution": execution}
        except MobileAgentError as error:
            return self._error_response(error)

    def submit_device_performance_task_sync(
        self,
        device_id: str,
        idempotency_key: str | None = None,
        deadline_seconds: float = 90.0,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        """Submission wrapper for asynchronous aggregate performance sampling."""

        try:
            execution = self.submit_device_performance_task(
                device_id, idempotency_key, deadline_seconds
            )
            return HTTPStatus.ACCEPTED, {"execution": execution}
        except MobileAgentError as error:
            return self._error_response(error)

    def submit_diagnostic_bundle_task_sync(
        self,
        device_id: str,
        app_id: str | None = None,
        max_log_lines: int = 500,
        minimum_log_level: str = "info",
        confirmed: bool = False,
        idempotency_key: str | None = None,
        deadline_seconds: float = 120.0,
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        """Submission wrapper for one local diagnostic evidence bundle."""

        try:
            execution = self.submit_diagnostic_bundle_task(
                device_id,
                app_id,
                max_log_lines,
                minimum_log_level,
                confirmed,
                idempotency_key,
                deadline_seconds,
            )
            return HTTPStatus.ACCEPTED, {"execution": execution}
        except MobileAgentError as error:
            return self._error_response(error)

    def get_task_execution_sync(
        self, task_id: str
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            return HTTPStatus.OK, {"execution": self.get_task_execution(task_id)}
        except MobileAgentError as error:
            return self._error_response(error)

    def list_task_execution_events_sync(
        self, task_id: str
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            return HTTPStatus.OK, {
                "events": self.list_task_execution_events(task_id)
            }
        except MobileAgentError as error:
            return self._error_response(error)

    def cancel_task_execution_sync(
        self, task_id: str
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            return HTTPStatus.ACCEPTED, {
                "execution": self.cancel_task_execution(task_id)
            }
        except MobileAgentError as error:
            return self._error_response(error)

    def pause_task_execution_sync(
        self, task_id: str
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            return HTTPStatus.ACCEPTED, {
                "execution": self.pause_task_execution(task_id)
            }
        except MobileAgentError as error:
            return self._error_response(error)

    def resume_task_execution_sync(
        self, task_id: str
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            return HTTPStatus.ACCEPTED, {
                "execution": self.resume_task_execution(task_id)
            }
        except MobileAgentError as error:
            return self._error_response(error)

    def compile_goal_sync(self, goal: str) -> tuple[HTTPStatus, dict[str, Any]]:
        """Synchronously compile one reviewable goal draft."""

        try:
            return HTTPStatus.OK, {"goal_spec": self.compile_goal(goal)}
        except MobileAgentError as error:
            return self._error_response(error)

    def get_task_sync(self, task_id: str) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            return HTTPStatus.OK, {"task": self.get_task(task_id)}
        except MobileAgentError as error:
            return self._error_response(error)

    def list_task_events_sync(self, task_id: str) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            return HTTPStatus.OK, {"events": self.list_task_events(task_id)}
        except MobileAgentError as error:
            return self._error_response(error)

    def list_tasks_sync(self, limit: int = 20) -> tuple[HTTPStatus, dict[str, Any]]:
        try:
            return HTTPStatus.OK, {"tasks": self.list_tasks(limit)}
        except MobileAgentError as error:
            return self._error_response(error)

    def evaluate_agent_task_sync(
        self, task_id: str, scenario: object
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        """Synchronously evaluate one stored Agent task for local interfaces."""

        try:
            return HTTPStatus.OK, {
                "evaluation": self.evaluate_agent_task(task_id, scenario)
            }
        except MobileAgentError as error:
            return self._error_response(error)

    def compare_device_performance_sync(
        self, baseline_task_id: str, candidate_task_id: str
    ) -> tuple[HTTPStatus, dict[str, Any]]:
        """Synchronous wrapper for local performance comparison clients."""

        try:
            return HTTPStatus.OK, {
                "comparison": self.compare_device_performance(
                    baseline_task_id, candidate_task_id
                )
            }
        except MobileAgentError as error:
            return self._error_response(error)

    def model_provider_status_sync(self) -> tuple[HTTPStatus, dict[str, Any]]:
        return HTTPStatus.OK, {"model_provider": self.model_provider_status()}

    @staticmethod
    def _error_response(error: MobileAgentError) -> tuple[HTTPStatus, dict[str, Any]]:
        if error.code in {
            "DEVICE_NOT_FOUND",
            "APP_NOT_FOUND",
            "TOOL_NOT_FOUND",
            "TASK_NOT_FOUND",
            "ARTIFACT_NOT_FOUND",
        }:
            status = HTTPStatus.NOT_FOUND
        elif error.code in {
            "INVALID_ARGUMENT", "APK_INVALID", "APK_PACKAGE_MISMATCH",
            "APP_ALREADY_INSTALLED",
        }:
            status = HTTPStatus.BAD_REQUEST
        elif error.code in {
            "CONFIRMATION_REQUIRED",
            "ACTION_REJECTED_BY_POLICY",
            "APPROVAL_INVALID",
            "SYSTEM_APP_PROTECTED",
        }:
            status = HTTPStatus.FORBIDDEN
        elif error.code in {
            "TASK_STATE_CONFLICT",
            "IDEMPOTENCY_CONFLICT",
            "DEVICE_LOCKED",
        }:
            status = HTTPStatus.CONFLICT
        elif error.code in {"MODEL_OUTPUT_INVALID", "TOOL_REQUIRES_SKILL"}:
            status = HTTPStatus.UNPROCESSABLE_ENTITY
        else:
            status = HTTPStatus.SERVICE_UNAVAILABLE
        return status, {"error": error.to_dict()}


def build_default_runtime() -> RuntimeService:
    """Build the V1 Android runtime using the host's configured ADB."""

    artifact_root = default_artifact_root()
    model_provider_settings = load_model_provider_settings(
        artifact_root.parent / "model-provider.json"
    )
    planner, runtime_status, model_error = build_runtime_planner(model_provider_settings)
    if isinstance(planner, OpenAICompatiblePlanner):
        goal_compiler: GoalCompiler = planner
    elif model_error is not None:
        goal_compiler = UnavailableGoalCompiler(model_error)
    else:
        goal_compiler = PassThroughGoalCompiler()
    device_gateway_error: MobileAgentError | None = None
    try:
        adapter: DeviceAdapter = AndroidDeviceAdapter(AdbRunner())
    except MobileAgentError as error:
        if error.code != "ADB_NOT_FOUND":
            raise
        device_gateway_error = MobileAgentError(
            code=error.code,
            category=error.category,
            message=error.message,
            retryable=error.retryable,
            outcome=error.outcome,
            suggested_action=(
                f"{error.suggested_action}，然后重启 Mobile Agent Runtime"
            ),
            details=error.details,
        )
        adapter = UnavailableDeviceAdapter(device_gateway_error)
    return RuntimeService(
        adapter,
        ArtifactStore(artifact_root),
        task_store=SQLiteTaskStore(artifact_root.parent / "mobile-agent.db"),
        model_provider_settings=model_provider_settings,
        planner=planner,
        model_provider_runtime_status=runtime_status,
        model_provider_error=model_error,
        goal_compiler=goal_compiler,
        task_execution_store=SQLiteTaskExecutionStore(
            artifact_root.parent / "mobile-agent.db"
        ),
        device_gateway_error=device_gateway_error,
        gateway_platform="android",
        gateway_transport="adb",
    )


def build_runtime_planner(
    settings: ModelProviderSettings,
) -> tuple[Planner, str, MobileAgentError | None]:
    """Build the Runtime planner while preserving explicit model-unavailable state."""

    if not settings.enabled:
        return RuleBasedPlanner(), "disabled", None
    try:
        return (
            build_planner_from_settings(
                settings,
                secret_resolver=EnvironmentSecretResolver(),
            ),
            "active",
            None,
        )
    except MobileAgentError as error:
        return UnavailablePlanner(error), "unavailable", error
