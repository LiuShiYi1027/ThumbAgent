"""Tool registry and Observe-Act-Verify execution pipeline."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.domain.action import (
    ActionResult,
    ActionStatus,
    Idempotency,
    RiskLevel,
    VerificationStatus,
)
from mobile_agent.domain.device import ConnectionState
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.ui.locator import UiLocator
from mobile_agent.ui.model import UiMatch, UiNode, UiSelector
from mobile_agent.ui.parser import UiHierarchyParser


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    tool_id: str
    capability: str
    risk: RiskLevel
    idempotency: Idempotency

    def to_dict(self) -> dict[str, str]:
        return {
            "tool_id": self.tool_id,
            "capability": self.capability,
            "risk": self.risk.value,
            "idempotency": self.idempotency.value,
        }


class ToolRegistry:
    def __init__(self) -> None:
        definitions = (
            ToolDefinition("app.launch", "app.launch@1", RiskLevel.LOW, Idempotency.CONDITIONAL),
            ToolDefinition("navigation.back", "navigation.back@1", RiskLevel.LOW, Idempotency.UNSAFE),
            ToolDefinition("navigation.home", "navigation.home@1", RiskLevel.LOW, Idempotency.SAFE),
            ToolDefinition("input.tap", "input.tap@1", RiskLevel.MEDIUM, Idempotency.UNSAFE),
            ToolDefinition(
                "input.tap_element", "input.tap@1", RiskLevel.MEDIUM, Idempotency.UNSAFE
            ),
        )
        self._definitions = {definition.tool_id: definition for definition in definitions}

    def list(self) -> list[ToolDefinition]:
        return list(self._definitions.values())

    def get(self, tool_id: str) -> ToolDefinition:
        definition = self._definitions.get(tool_id)
        if definition is None:
            raise MobileAgentError(
                code="TOOL_NOT_FOUND",
                category=ErrorCategory.VALIDATION,
                message="未注册的 Tool",
            )
        return definition


class ToolRuntime:
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
        self._parser = UiHierarchyParser()
        self._locator = UiLocator()

    async def execute(
        self,
        tool_id: str,
        device_id: str,
        arguments: dict[str, Any],
        confirmed: bool = False,
    ) -> ActionResult:
        definition = self._registry.get(tool_id)
        device = next(
            (item for item in await self._adapter.list_devices() if item.device_id == device_id), None
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
            )
        if definition.capability not in device.capabilities:
            raise MobileAgentError(
                code="CAPABILITY_UNAVAILABLE",
                category=ErrorCategory.CAPABILITY,
                message="设备不支持该动作",
                details={"capability": definition.capability},
            )
        self._policy.authorize(definition.risk, confirmed)

        started_at = _now()
        before = await self._adapter.observe(device_id, self._artifacts)
        ui_match = await self._dispatch(tool_id, device_id, arguments, before)
        after = await self._adapter.observe(device_id, self._artifacts)
        verification = self._verify(tool_id, arguments, after.foreground_app.app_id)
        status = (
            ActionStatus.SUCCEEDED
            if verification is not VerificationStatus.NOT_VERIFIED
            else ActionStatus.FAILED
        )
        return ActionResult(
            action_id=f"action_{uuid.uuid4().hex}",
            tool_id=tool_id,
            device_id=device_id,
            status=status,
            verification=verification,
            started_at=started_at,
            completed_at=_now(),
            before=before,
            after=after,
            ui_match=ui_match,
        )

    async def _dispatch(
        self, tool_id: str, device_id: str, arguments: dict[str, Any], before: Any
    ) -> UiMatch | None:
        if tool_id == "app.launch":
            app_id = arguments.get("app_id")
            if not isinstance(app_id, str) or not app_id:
                self._invalid_argument("app_id")
            await self._adapter.launch_app(device_id, app_id)
            return None
        if tool_id == "navigation.back":
            await self._adapter.press_back(device_id)
            return None
        if tool_id == "navigation.home":
            await self._adapter.press_home(device_id)
            return None
        if tool_id == "input.tap":
            x, y = arguments.get("x"), arguments.get("y")
            if not isinstance(x, int) or isinstance(x, bool) or not isinstance(y, int) or isinstance(y, bool):
                self._invalid_argument("x/y")
            if x < 0 or y < 0 or x >= before.screen.width or y >= before.screen.height:
                self._invalid_argument("x/y bounds")
            await self._adapter.tap(device_id, x, y)
            return None
        if tool_id == "input.tap_element":
            raw_selector = arguments.get("selector")
            if not isinstance(raw_selector, dict):
                self._invalid_argument("selector")
            selector = UiSelector.from_dict(raw_selector)
            nodes = self._nodes_from_observation(before)
            match = self._locator.locate(
                nodes, selector, before.screen.width, before.screen.height
            )
            await self._adapter.tap(device_id, match.tap_x, match.tap_y)
            return match
        raise AssertionError(f"registered tool lacks dispatcher: {tool_id}")

    async def wait_for_element(
        self,
        device_id: str,
        selector_payload: dict[str, Any],
        timeout_seconds: float = 5.0,
        poll_interval: float = 0.5,
    ) -> tuple[Any, UiNode]:
        if timeout_seconds <= 0 or timeout_seconds > 30 or poll_interval <= 0:
            self._invalid_argument("wait timeout")
        selector = UiSelector.from_dict(selector_payload)
        deadline = time.monotonic() + timeout_seconds
        while True:
            observation = await self._adapter.observe(device_id, self._artifacts)
            matches = self._locator.find_all(self._nodes_from_observation(observation), selector)
            if len(matches) == 1:
                return observation, matches[0]
            if len(matches) > 1:
                raise MobileAgentError(
                    code="TARGET_AMBIGUOUS",
                    category=ErrorCategory.DEVICE,
                    message="目标 UI 元素匹配不唯一",
                    details={"match_count": len(matches)},
                )
            if time.monotonic() >= deadline:
                raise MobileAgentError(
                    code="TARGET_NOT_FOUND",
                    category=ErrorCategory.DEVICE,
                    message="等待目标 UI 元素超时",
                )
            await asyncio.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))

    def _nodes_from_observation(self, observation: Any) -> list[UiNode]:
        path = self._artifacts.resolve(observation.ui_tree.artifact.relative_path)
        return self._parser.parse(path.read_bytes())

    @staticmethod
    def _verify(tool_id: str, arguments: dict[str, Any], foreground_app: str) -> VerificationStatus:
        if tool_id == "app.launch":
            return (
                VerificationStatus.VERIFIED
                if foreground_app == arguments.get("app_id")
                else VerificationStatus.NOT_VERIFIED
            )
        return VerificationStatus.INCONCLUSIVE

    @staticmethod
    def _invalid_argument(field: str) -> None:
        raise MobileAgentError(
            code="INVALID_ARGUMENT",
            category=ErrorCategory.VALIDATION,
            message=f"无效的动作参数：{field}",
        )
