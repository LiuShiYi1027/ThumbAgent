"""Registered, policy-gated Tool for verified Unicode text input (ADR-0019).

编排顺序固定：校验与策略拦截（先于任何设备动作）→ 定位可编辑目标 →
记录当前 IME → 启用/切换 Helper IME → 聚焦并输入 Modified UTF-7 编码文本 →
UI Tree 读回验证（NFC 精确比对）→ 恢复原 IME（强制，失败即 IME_RESTORE_FAILED）。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.domain.device import ConnectionState
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.unicode_input import (
    encode_modified_utf7,
    is_helper_ime,
    normalize_for_verification,
    text_digest,
    validate_unicode_text,
)
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.tools.runtime import ToolRegistry, locate_editable_target
from mobile_agent.ui.locator import UiLocator
from mobile_agent.ui.model import UiMatch, UiSelector
from mobile_agent.ui.parser import UiHierarchyParser


@dataclass(frozen=True, slots=True)
class UnicodeTextInput:
    """Internal output from the registered Tool to its owning Skill."""

    match: UiMatch
    text_length: int
    text_sha256: str
    helper_ime_id: str
    previous_ime_id: str
    evidence_refs: tuple[str, ...]


class UnicodeTextInputTool:
    """Validated, authorized and verified Unicode text input via Helper IME."""

    tool_id = "input.unicode_text"

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
        device_id: str,
        selector_payload: dict[str, Any],
        text: str,
        confirmed: bool,
    ) -> UnicodeTextInput:
        # 校验与敏感拦截先于任何设备动作（ADR-0019）。
        text = validate_unicode_text(text)
        if not isinstance(selector_payload, dict):
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="无效的动作参数：selector",
            )
        selector = UiSelector.from_dict(selector_payload)

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
                message="设备不支持 Unicode 文本输入",
                details={"capability": definition.capability},
            )
        self._policy.authorize(definition.risk, confirmed)

        helper_ime_id = await self._resolve_helper(device_id)
        before = await self._adapter.observe(device_id, self._artifacts)
        nodes = self._parser.parse(
            self._artifacts.resolve(before.ui_tree.artifact.relative_path).read_bytes()
        )
        match = locate_editable_target(
            self._locator, nodes, selector, before.screen.width, before.screen.height
        )

        previous_ime_id = await self._adapter.current_input_method(device_id)
        await self._activate_helper(device_id, helper_ime_id)
        evidence: list[str] = [before.ui_tree.artifact.artifact_id]
        try:
            await self._adapter.tap(device_id, match.tap_x, match.tap_y)
            await self._adapter.input_text(device_id, encode_modified_utf7(text))
            await self._verify_readback(device_id, selector, text, evidence)
        finally:
            await self._restore_input_method(device_id, previous_ime_id)

        return UnicodeTextInput(
            match=match,
            text_length=len(text),
            text_sha256=text_digest(text),
            helper_ime_id=helper_ime_id,
            previous_ime_id=previous_ime_id,
            evidence_refs=tuple(evidence),
        )

    async def _resolve_helper(self, device_id: str) -> str:
        installed = await self._adapter.installed_input_methods(device_id)
        for ime_id in installed:
            if is_helper_ime(ime_id):
                return ime_id
        raise MobileAgentError(
            code="IME_HELPER_NOT_INSTALLED",
            category=ErrorCategory.DEVICE,
            message="Unicode 输入 Helper IME 未安装",
            retryable=False,
            suggested_action="经 app.install 两阶段授权安装 helpers/unicode-ime 登记的 Helper APK",
        )

    async def _activate_helper(self, device_id: str, helper_ime_id: str) -> None:
        enabled = await self._adapter.enabled_input_methods(device_id)
        if not any(is_helper_ime(ime_id) for ime_id in enabled):
            await self._adapter.enable_input_method(device_id, helper_ime_id)
        await self._adapter.set_input_method(device_id, helper_ime_id)
        # ime set 返回成功不代表切换生效（ROM 可能静默忽略），必须读回确认。
        current = await self._adapter.current_input_method(device_id)
        if not is_helper_ime(current):
            raise MobileAgentError(
                code="IME_SWITCH_FAILED",
                category=ErrorCategory.DEVICE,
                message="Helper IME 切换未生效，可能被系统策略拦截",
                retryable=False,
                suggested_action="在系统设置中手动启用 Helper IME，或降级为人工输入",
            )

    async def _verify_readback(
        self,
        device_id: str,
        selector: UiSelector,
        text: str,
        evidence: list[str],
    ) -> None:
        after = await self._adapter.observe(device_id, self._artifacts)
        if after.ui_tree.artifact.artifact_id not in evidence:
            evidence.append(after.ui_tree.artifact.artifact_id)
        nodes = self._parser.parse(
            self._artifacts.resolve(after.ui_tree.artifact.relative_path).read_bytes()
        )
        matches = self._locator.find_all(nodes, selector)
        expected = normalize_for_verification(text)
        actual = (
            normalize_for_verification(matches[0].text) if len(matches) == 1 else None
        )
        if actual != expected:
            raise MobileAgentError(
                code="TEXT_INPUT_NOT_VERIFIED",
                category=ErrorCategory.DEVICE,
                message="输入内容读回验证不一致",
                retryable=False,
                details={
                    "match_count": len(matches),
                    "expected_sha256": hashlib.sha256(expected.encode("utf-8")).hexdigest(),
                    "actual_sha256": (
                        hashlib.sha256(actual.encode("utf-8")).hexdigest()
                        if actual is not None
                        else None
                    ),
                },
            )

    async def _restore_input_method(self, device_id: str, previous_ime_id: str) -> None:
        try:
            await self._adapter.set_input_method(device_id, previous_ime_id)
            current = await self._adapter.current_input_method(device_id)
            if current != previous_ime_id:
                raise MobileAgentError(
                    code="IME_RESTORE_FAILED",
                    category=ErrorCategory.DEVICE,
                    message="原输入法恢复未生效",
                    retryable=False,
                )
        except MobileAgentError as failure:
            # 恢复失败必须显著上报：设备可能停留在 Helper IME（ADR-0019）。
            if failure.code == "IME_RESTORE_FAILED":
                raise
            raise MobileAgentError(
                code="IME_RESTORE_FAILED",
                category=ErrorCategory.DEVICE,
                message="恢复原输入法失败，设备可能仍停留在 Helper IME",
                retryable=False,
                suggested_action="立即在系统设置中手动检查并恢复默认输入法",
            ) from failure
