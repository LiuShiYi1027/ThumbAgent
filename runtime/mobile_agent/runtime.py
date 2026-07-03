"""Application service shared by HTTP, CLI, and future MCP interfaces."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
from typing import Any

from mobile_agent import __version__
from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore, default_artifact_root
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.skills.open_app import OpenAppSkill
from mobile_agent.skills.settings_navigate import SettingsNavigateSkill
from mobile_agent.tools.runtime import ToolRegistry, ToolRuntime


class RuntimeService:
    def __init__(self, adapter: DeviceAdapter, artifacts: ArtifactStore) -> None:
        self._adapter = adapter
        self._artifacts = artifacts
        self._tool_registry = ToolRegistry()
        self._tools = ToolRuntime(adapter, artifacts, self._tool_registry, PolicyEngine())
        self._open_app = OpenAppSkill(self._tools)
        self._settings_navigate = SettingsNavigateSkill(self._tools, self._open_app)

    def health(self) -> dict[str, str]:
        return {"status": "ok", "runtime_version": __version__, "api_version": "v1"}

    async def list_devices(self) -> list[dict[str, Any]]:
        devices = await self._adapter.list_devices()
        return [device.to_dict() for device in devices]

    async def observe(self, device_id: str) -> dict[str, Any]:
        observation = await self._adapter.observe(device_id, self._artifacts)
        return observation.to_dict()

    def list_tools(self) -> list[dict[str, str]]:
        return [definition.to_dict() for definition in self._tool_registry.list()]

    async def invoke_tool(
        self, tool_id: str, device_id: str, arguments: dict[str, Any], confirmed: bool = False
    ) -> dict[str, Any]:
        return (
            await self._tools.execute(tool_id, device_id, arguments, confirmed)
        ).to_dict()

    async def open_app(self, device_id: str, app_id: str) -> dict[str, Any]:
        return (await self._open_app.invoke(device_id, app_id)).to_dict()

    async def navigate_settings(
        self,
        device_id: str,
        target_selector: dict[str, Any],
        expected_selector: dict[str, Any],
        confirmed: bool = False,
    ) -> dict[str, Any]:
        return (
            await self._settings_navigate.invoke(
                device_id, target_selector, expected_selector, confirmed
            )
        ).to_dict()

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

    @staticmethod
    def _error_response(error: MobileAgentError) -> tuple[HTTPStatus, dict[str, Any]]:
        if error.code in {"DEVICE_NOT_FOUND", "TOOL_NOT_FOUND"}:
            status = HTTPStatus.NOT_FOUND
        elif error.code in {"INVALID_ARGUMENT"}:
            status = HTTPStatus.BAD_REQUEST
        elif error.code in {"CONFIRMATION_REQUIRED", "ACTION_REJECTED_BY_POLICY"}:
            status = HTTPStatus.FORBIDDEN
        else:
            status = HTTPStatus.SERVICE_UNAVAILABLE
        return status, {"error": error.to_dict()}


def build_default_runtime() -> RuntimeService:
    """Build the V1 Android runtime using the host's configured ADB."""

    return RuntimeService(
        AndroidDeviceAdapter(AdbRunner()), ArtifactStore(default_artifact_root())
    )
