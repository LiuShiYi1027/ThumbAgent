"""Registered, policy-gated Tool for verified Unicode text input (ADR-0019).

编排顺序固定：校验与策略拦截（先于任何设备动作）→ 定位可编辑目标 →
记录当前 IME → 启用/切换 Helper IME → 聚焦并输入 Modified UTF-7 编码文本 →
UI Tree 读回验证（追加语义：字段原文 + 目标文本，NFC 精确比对）→
恢复原 IME（强制，失败即 IME_RESTORE_FAILED）。
"""

from __future__ import annotations

import asyncio
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

# 聚焦后到注入前的 settle：覆盖 Helper IME 冷启动与输入连接建立延迟。
_INPUT_SETTLE_SECONDS = 0.5
# 注入整体丢失后的单次重试间隔。
_INPUT_RETRY_SETTLE_SECONDS = 1.0


def _nothing_landed(failure: MobileAgentError, before_text: str) -> bool:
    """读回摘要仍等于输入前原文摘要 = 注入整体丢失（区别于字段被篡改）。

    错误 details 按隐私先例只带 SHA-256，不带文本原文，因此用摘要比对判定。
    """
    actual = (failure.details or {}).get("actual_sha256")
    if not isinstance(actual, str):
        return False
    before_digest = hashlib.sha256(
        normalize_for_verification(before_text).encode("utf-8")
    ).hexdigest()
    return actual == before_digest


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
        # commitText 是追加语义：验证期望 = 输入前字段文本 + 目标文本（NFC 精确比对）。
        # 空字段的 text 是 hint 占位，必须用 effective_text 剔除（真机实测假阴性）。
        before_text = match.target_node.effective_text

        previous_ime_id = await self._adapter.current_input_method(device_id)
        await self._activate_helper(device_id, helper_ime_id)
        evidence: list[str] = [before.ui_tree.artifact.artifact_id]
        try:
            await self._adapter.tap(device_id, match.tap_x, match.tap_y)
            # 真机实测：Helper IME 冷启动 / 输入连接建立有延迟，聚焦后立即注入
            # 字符会被静默丢弃（无任何报错），读回才发现。先做一个固定短 settle。
            await asyncio.sleep(_INPUT_SETTLE_SECONDS)
            await self._adapter.input_text(device_id, encode_modified_utf7(text))
            try:
                await self._verify_readback(
                    device_id, selector, before_text + text, evidence
                )
            except MobileAgentError as failure:
                if (
                    failure.code != "TEXT_INPUT_NOT_VERIFIED"
                    or not _nothing_landed(failure, before_text)
                ):
                    raise
                # 读回仍是原文 = 注入整体丢失（而非被篡改），settle 后有界重试一次。
                await asyncio.sleep(_INPUT_RETRY_SETTLE_SECONDS)
                await self._adapter.input_text(device_id, encode_modified_utf7(text))
                await self._verify_readback(
                    device_id, selector, before_text + text, evidence
                )
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
        # MagicOS 实测：安装完成后包扫描有短暂竞态，ime list 立即可见但
        # ime enable 可能滞后；未找到时按固定间隔有界重试一次再判定。
        for attempt in range(2):
            installed = await self._adapter.installed_input_methods(device_id)
            for ime_id in installed:
                if is_helper_ime(ime_id):
                    return ime_id
            if attempt == 0:
                await asyncio.sleep(1.0)
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
        expected_text: str,
        evidence: list[str],
    ) -> None:
        after = await self._adapter.observe(device_id, self._artifacts)
        if after.ui_tree.artifact.artifact_id not in evidence:
            evidence.append(after.ui_tree.artifact.artifact_id)
        nodes = self._parser.parse(
            self._artifacts.resolve(after.ui_tree.artifact.relative_path).read_bytes()
        )
        matches = self._locator.find_all(nodes, selector)
        expected = normalize_for_verification(expected_text)
        actual = (
            normalize_for_verification(matches[0].effective_text)
            if len(matches) == 1
            else None
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
