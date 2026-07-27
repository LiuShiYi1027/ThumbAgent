"""Tool registry and Observe-Act-Verify execution pipeline."""

from __future__ import annotations

import asyncio
import re
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
from mobile_agent.domain.capability import CapabilityCatalog
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
    direct_invocation: bool = True

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "tool_id": self.tool_id,
            "capability": self.capability,
            "risk": self.risk.value,
            "idempotency": self.idempotency.value,
            "direct_invocation": self.direct_invocation,
        }


class ToolRegistry:
    def __init__(self, capabilities: CapabilityCatalog | None = None) -> None:
        catalog = capabilities or CapabilityCatalog()

        def definition(
            tool_id: str, capability: str, direct_invocation: bool = True
        ) -> ToolDefinition:
            metadata = catalog.get(capability)
            return ToolDefinition(
                tool_id,
                capability,
                metadata.risk,
                metadata.idempotency,
                direct_invocation,
            )

        definitions = (
            definition("app.launch", "app.launch@1"),
            definition("navigation.back", "navigation.back@1"),
            definition("navigation.home", "navigation.home@1"),
            definition("input.tap", "input.tap@1"),
            definition("input.swipe", "input.swipe@1"),
            definition("input.text", "input.text@1"),
            definition("input.tap_element", "input.tap@1"),
            definition(
                "device.logs.capture", "logs.collect@1", direct_invocation=False
            ),
            definition(
                "device.performance.capture",
                "performance.snapshot@1",
                direct_invocation=False,
            ),
            definition("app.list", "app.inspect@1", direct_invocation=False),
            definition("app.inspect", "app.inspect@1", direct_invocation=False),
            definition("app.install", "app.install@1", direct_invocation=False),
            definition("app.uninstall", "app.uninstall@1", direct_invocation=False),
            definition(
                "app.state.inspect", "app.state.inspect@1", direct_invocation=False
            ),
            definition("app.stop", "app.stop@1", direct_invocation=False),
            definition(
                "app.data.clear", "app.data.clear@1", direct_invocation=False
            ),
            definition(
                "device.diagnostics.bundle",
                "device.diagnostics.bundle@1",
                direct_invocation=False,
            ),
            ToolDefinition(
                "local.data.cleanup",
                "runtime.local.data.cleanup@1",
                RiskLevel.HIGH,
                Idempotency.UNSAFE,
                direct_invocation=False,
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
        if not definition.direct_invocation:
            skill_id = {
                "device.logs.capture": "device.logs.collect",
                "device.performance.capture": "device.performance.snapshot",
                "app.list": "app.list",
                "app.inspect": "app.inspect",
            }.get(tool_id, "对应的目标级 Skill")
            raise MobileAgentError(
                code="TOOL_REQUIRES_SKILL",
                category=ErrorCategory.VALIDATION,
                message="该底层 Tool 只能通过对应 Skill 调用",
                suggested_action=f"调用 {skill_id} Skill",
            )
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
        if tool_id == "input.swipe":
            direction = arguments.get("direction")
            distance_percent = arguments.get("distance_percent", 0.55)
            duration_ms = arguments.get("duration_ms", 300)
            if direction not in {"up", "down", "left", "right"}:
                self._invalid_argument("direction")
            if (
                not isinstance(distance_percent, int | float)
                or isinstance(distance_percent, bool)
                or distance_percent < 0.1
                or distance_percent > 0.8
            ):
                self._invalid_argument("distance_percent")
            if (
                not isinstance(duration_ms, int)
                or isinstance(duration_ms, bool)
                or duration_ms < 100
                or duration_ms > 2000
            ):
                self._invalid_argument("duration_ms")
            start_x, start_y, end_x, end_y = self._swipe_points(
                before.screen.width, before.screen.height, direction, float(distance_percent)
            )
            await self._adapter.swipe(device_id, start_x, start_y, end_x, end_y, duration_ms)
            return None
        if tool_id == "input.text":
            text = arguments.get("text")
            raw_selector = arguments.get("selector")
            if not isinstance(text, str):
                self._invalid_argument("text")
            self._validate_text_input(text)
            if not isinstance(raw_selector, dict):
                self._invalid_argument("selector")
            selector = UiSelector.from_dict(raw_selector)
            nodes = self._nodes_from_observation(before)
            match = self._locate_editable(nodes, selector, before.screen.width, before.screen.height)
            await self._adapter.tap(device_id, match.tap_x, match.tap_y)
            await self._adapter.input_text(device_id, text)
            return match
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

    async def find_element_with_scroll(
        self,
        device_id: str,
        selector_payload: dict[str, Any],
        direction: str = "up",
        max_scrolls: int = 3,
        timeout_seconds: float = 30.0,
        distance_percent: float = 0.8,
        duration_ms: int = 800,
        settle_seconds: float = 0.8,
        confirmed: bool = False,
    ) -> tuple[Any, UiNode]:
        if max_scrolls < 0 or max_scrolls > 10:
            self._invalid_argument("max_scrolls")
        if timeout_seconds <= 0 or timeout_seconds > 60:
            self._invalid_argument("timeout_seconds")
        if settle_seconds < 0 or settle_seconds > 3:
            self._invalid_argument("settle_seconds")
        selector = UiSelector.from_dict(selector_payload)
        deadline = time.monotonic() + timeout_seconds
        seen_snapshots: set[tuple[str, str, str]] = set()

        for attempt in range(max_scrolls + 1):
            if time.monotonic() >= deadline:
                raise MobileAgentError(
                    code="ACTION_TIMEOUT",
                    category=ErrorCategory.EXECUTION,
                    message="语义滚动查找超时",
                )
            observation = await self._adapter.observe(device_id, self._artifacts)
            matches = self._locator.find_all(self._nodes_from_observation(observation), selector)
            if len(matches) == 1:
                return observation, matches[0]
            if len(matches) > 1:
                raise MobileAgentError(
                    code="TARGET_AMBIGUOUS",
                    category=ErrorCategory.DEVICE,
                    message="目标 UI 元素匹配不唯一",
                    details={"match_count": len(matches), "scroll_attempt": attempt},
                )

            snapshot = self._observation_fingerprint(observation)
            if snapshot in seen_snapshots:
                raise MobileAgentError(
                    code="NO_PROGRESS",
                    category=ErrorCategory.EXECUTION,
                    message="滚动后页面没有产生可观察进展",
                    details={"scroll_attempt": attempt},
                )
            seen_snapshots.add(snapshot)
            if attempt >= max_scrolls:
                raise MobileAgentError(
                    code="TARGET_NOT_FOUND",
                    category=ErrorCategory.DEVICE,
                    message="滚动查找后仍未找到目标 UI 元素",
                    details={"scroll_attempts": attempt},
                )
            await self.execute(
                "input.swipe",
                device_id,
                {
                    "direction": direction,
                    "distance_percent": distance_percent,
                    "duration_ms": duration_ms,
                },
                confirmed=confirmed,
            )
            if settle_seconds:
                await asyncio.sleep(settle_seconds)
        raise AssertionError("unreachable scroll loop exit")

    def _nodes_from_observation(self, observation: Any) -> list[UiNode]:
        path = self._artifacts.resolve(observation.ui_tree.artifact.relative_path)
        return self._parser.parse(path.read_bytes())

    @staticmethod
    def _observation_fingerprint(observation: Any) -> tuple[str, str, str]:
        return (
            observation.foreground_app.app_id,
            observation.foreground_app.activity,
            observation.ui_tree.artifact.sha256,
        )

    @staticmethod
    def _verify(tool_id: str, arguments: dict[str, Any], foreground_app: str) -> VerificationStatus:
        if tool_id == "app.launch":
            return (
                VerificationStatus.VERIFIED
                if foreground_app == arguments.get("app_id")
                else VerificationStatus.NOT_VERIFIED
            )
        return VerificationStatus.INCONCLUSIVE

    @classmethod
    def _swipe_points(
        cls, width: int, height: int, direction: str, distance_percent: float
    ) -> tuple[int, int, int, int]:
        if width < 2 or height < 2:
            cls._invalid_argument("screen size")
        center_x = width // 2
        center_y = height // 2
        safe_left = min(width - 1, max(0, int(width * 0.15)))
        safe_right = max(safe_left + 1, min(width - 1, int(width * 0.85)))
        safe_top = min(height - 1, max(0, int(height * 0.19)))
        safe_bottom = max(safe_top + 1, min(height - 1, int(height * 0.88)))
        if direction in {"up", "down"}:
            distance = max(1, int((height - 1) * distance_percent))
            half = max(1, distance // 2)
            if direction == "up":
                start_y = cls._clamp(center_y + half, safe_top, safe_bottom)
                end_y = cls._clamp(start_y - distance, safe_top, safe_bottom)
            else:
                start_y = cls._clamp(center_y - half, safe_top, safe_bottom)
                end_y = cls._clamp(start_y + distance, safe_top, safe_bottom)
            if start_y == end_y:
                cls._invalid_argument("swipe distance")
            return center_x, start_y, center_x, end_y
        distance = max(1, int((width - 1) * distance_percent))
        half = max(1, distance // 2)
        if direction == "left":
            start_x = cls._clamp(center_x + half, safe_left, safe_right)
            end_x = cls._clamp(start_x - distance, safe_left, safe_right)
        else:
            start_x = cls._clamp(center_x - half, safe_left, safe_right)
            end_x = cls._clamp(start_x + distance, safe_left, safe_right)
        if start_x == end_x:
            cls._invalid_argument("swipe distance")
        return start_x, center_y, end_x, center_y

    def _locate_editable(
        self, nodes: list[UiNode], selector: UiSelector, screen_width: int, screen_height: int
    ) -> UiMatch:
        matches = self._locator.find_all(nodes, selector)
        if not matches:
            raise MobileAgentError(
                code="TARGET_NOT_FOUND",
                category=ErrorCategory.DEVICE,
                message="未找到目标 UI 输入元素",
            )
        if len(matches) > 1:
            raise MobileAgentError(
                code="TARGET_AMBIGUOUS",
                category=ErrorCategory.DEVICE,
                message="目标 UI 输入元素匹配不唯一",
                details={"match_count": len(matches)},
            )
        node = matches[0]
        if not self._is_editable_node(node):
            raise MobileAgentError(
                code="TARGET_NOT_EDITABLE",
                category=ErrorCategory.DEVICE,
                message="目标 UI 元素不是可编辑输入框",
            )
        if self._is_sensitive_input_target(node):
            raise MobileAgentError(
                code="ACTION_REJECTED_BY_POLICY",
                category=ErrorCategory.POLICY,
                message="当前策略禁止向敏感输入框输入文本",
            )
        if not node.enabled or not node.visible:
            raise MobileAgentError(
                code="TARGET_NOT_INTERACTABLE",
                category=ErrorCategory.DEVICE,
                message="目标 UI 输入元素当前不可交互",
            )
        if not node.bounds.within(screen_width, screen_height):
            raise MobileAgentError(
                code="TARGET_OUT_OF_BOUNDS",
                category=ErrorCategory.DEVICE,
                message="目标 UI 输入元素超出屏幕边界",
            )
        tap_x, tap_y = node.bounds.center
        return UiMatch(selector, node, node, tap_x, tap_y)

    @staticmethod
    def _is_editable_node(node: UiNode) -> bool:
        return node.class_name.endswith(".EditText") or node.class_name == "EditText"

    @staticmethod
    def _is_sensitive_input_target(node: UiNode) -> bool:
        haystack = " ".join(
            (node.text, node.resource_id, node.content_description, node.class_name)
        ).lower()
        sensitive_terms = (
            "password",
            "passwd",
            "pwd",
            "验证码",
            "verification",
            "otp",
            "code",
            "pin",
            "支付",
            "pay",
            "card",
            "phone",
            "手机号",
            "账号",
            "account",
            "secret",
            "token",
            "key",
        )
        return any(term in haystack for term in sensitive_terms)

    @classmethod
    def _validate_text_input(cls, text: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", text):
            cls._invalid_argument("text")
        if re.fullmatch(r"\d{4,8}", text) or re.fullmatch(r"\d{11,}", text):
            raise MobileAgentError(
                code="ACTION_REJECTED_BY_POLICY",
                category=ErrorCategory.POLICY,
                message="当前策略禁止输入疑似验证码、手机号或敏感数字",
            )

    @staticmethod
    def _clamp(value: int, minimum: int, maximum: int) -> int:
        return max(minimum, min(value, maximum))

    @staticmethod
    def _invalid_argument(field: str) -> None:
        raise MobileAgentError(
            code="INVALID_ARGUMENT",
            category=ErrorCategory.VALIDATION,
            message=f"无效的动作参数：{field}",
        )
