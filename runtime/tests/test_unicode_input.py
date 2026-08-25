"""Skill matrix tests for input.unicode_text (ITER-0059, ADR-0019)."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.domain.unicode_input import (
    HELPER_IME_ID,
    HELPER_PACKAGE,
    encode_modified_utf7,
    text_digest,
)
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService
from runtime.tests.utf7ref import reference_decode_modified_utf7

DEFAULT_IME = "com.example.ime/.DefaultIme"
HELPER_FULL = f"{HELPER_PACKAGE}/{HELPER_PACKAGE}.UnicodeImeService"
DEVICE_ID = "fake:android-001"
SELECTOR = {"strategy": "resource_id", "value": "search_box"}


def _form_xml(text: str, resource_id: str = "search_box") -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
        f'<node text="{text}" resource-id="{resource_id}" class="android.widget.EditText" '
        'package="com.example.form" clickable="true" enabled="true" '
        'visible-to-user="true" bounds="[0,0][2,1]"/></hierarchy>'
    ).encode()


def _configure_ready(
    adapter: FakeDeviceAdapter, field_text: str = ""
) -> FakeDeviceAdapter:
    """动态 fake 路径：前台为 com.example.form，读回文本随 input_text 追加更新。"""
    adapter.foreground_app = "com.example.form"
    adapter.foreground_activity = ".MainActivity"
    adapter.field_text = field_text
    adapter.installed_imes = (DEFAULT_IME, HELPER_FULL)
    adapter.enabled_imes = [DEFAULT_IME]
    adapter.current_ime = DEFAULT_IME
    return adapter


def _ready_adapter(field_text: str = "") -> FakeDeviceAdapter:
    return _configure_ready(FakeDeviceAdapter(), field_text)


class HelperSetFailingAdapter(FakeDeviceAdapter):
    """Simulate a ROM that rejects switching to the Helper IME."""

    async def set_input_method(self, device_id: str, ime_id: str) -> None:
        from mobile_agent.domain.errors import ErrorCategory

        self.actions.append(("input.ime.set", device_id, ime_id))
        if "unicodeime" in ime_id:
            raise MobileAgentError(
                code="IME_SWITCH_FAILED",
                category=ErrorCategory.DEVICE,
                message="无法切换设备输入法",
                retryable=True,
            )
        self.current_ime = ime_id


class RestoreFailingAdapter(FakeDeviceAdapter):
    """Simulate restore failure: only switching back to the previous IME fails."""

    async def set_input_method(self, device_id: str, ime_id: str) -> None:
        from mobile_agent.domain.errors import ErrorCategory

        self.actions.append(("input.ime.set", device_id, ime_id))
        if "unicodeime" not in ime_id:
            raise MobileAgentError(
                code="IME_SWITCH_FAILED",
                category=ErrorCategory.DEVICE,
                message="无法切换设备输入法",
                retryable=True,
            )
        self.current_ime = ime_id


class TamperingAdapter(FakeDeviceAdapter):
    """Simulate the field being mutated between input and read-back."""

    async def input_text(self, device_id: str, text: str) -> None:
        await super().input_text(device_id, text)
        self.field_text += "X"


class UnicodeTextInputSkillTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.artifacts = ArtifactStore(Path(self.directory.name))

    def _runtime(self, adapter: FakeDeviceAdapter) -> RuntimeService:
        return RuntimeService(adapter, self.artifacts)

    async def test_success_switches_inputs_verifies_and_restores(self) -> None:
        adapter = _ready_adapter()
        runtime = self._runtime(adapter)

        result = await runtime.unicode_text_input(
            DEVICE_ID, SELECTOR, "你好世界", confirmed=True
        )

        self.assertTrue(result["success"])
        self.assertEqual("input.unicode_text", result["skill_id"])
        self.assertEqual("verified", result["verification"])
        self.assertEqual(4, result["text_length"])
        self.assertEqual(text_digest("你好世界"), result["text_sha256"])
        self.assertNotIn("你好世界", str(result))
        self.assertEqual(HELPER_FULL, result["ime"]["helper_id"])
        self.assertEqual(DEFAULT_IME, result["ime"]["previous_id"])
        self.assertTrue(result["ime"]["restored"])
        self.assertEqual("com.example.form", result["field"]["package"])
        self.assertEqual("search_box", result["field"]["resource_id"])
        self.assertEqual(
            {"strategy": "resource_id", "value": "search_box", "match": "exact"},
            result["field"]["selector"],
        )
        self.assertGreaterEqual(len(result["evidence_refs"]), 1)

        # 线路上送的是纯 ASCII 编码文本，且解码后与目标一致。
        typed = [a for a in adapter.actions if a[0] == "input.text"]
        self.assertEqual(1, len(typed))
        wire_text = typed[0][2]
        self.assertTrue(str(wire_text).isascii())
        self.assertEqual("你好世界", reference_decode_modified_utf7(str(wire_text)))

        # 动作顺序：探测 → 启用 → 切换 → 输入 → 恢复原 IME（恢复后还有读回确认）。
        kinds = [a[0] for a in adapter.actions]
        self.assertLess(kinds.index("input.ime.installed"), kinds.index("input.ime.enable"))
        set_actions = [a for a in adapter.actions if a[0] == "input.ime.set"]
        self.assertEqual(("input.ime.set", DEVICE_ID, DEFAULT_IME), set_actions[-1])
        self.assertEqual(DEFAULT_IME, adapter.current_ime)

    async def test_autocomplete_text_view_is_accepted_as_editable(self) -> None:
        """AutoCompleteTextView（EditText 平台子类，MagicOS 搜索框实际形态）可输入。"""
        adapter = _ready_adapter()
        adapter.field_class = "android.widget.AutoCompleteTextView"
        runtime = self._runtime(adapter)

        result = await runtime.unicode_text_input(
            DEVICE_ID, SELECTOR, "你好世界", confirmed=True
        )

        self.assertTrue(result["success"])

    async def test_append_semantics_preserves_existing_field_text(self) -> None:
        """commitText 是追加语义：字段已有内容时验证期望为 原文 + 目标文本。"""
        adapter = _ready_adapter("前缀")
        runtime = self._runtime(adapter)

        result = await runtime.unicode_text_input(
            DEVICE_ID, SELECTOR, "你好", confirmed=True
        )

        self.assertTrue(result["success"])
        self.assertEqual("前缀你好", adapter.field_text)

    async def test_empty_field_with_hint_is_treated_as_empty(self) -> None:
        """真机回归：空输入框的 uiautomator text 等于 hint（如“搜索设置项”），
        追加语义验证不得把 hint 当原文，否则读回必然假阴性。"""
        adapter = _ready_adapter()
        adapter.field_hint = "搜索设置项"
        runtime = self._runtime(adapter)

        result = await runtime.unicode_text_input(
            DEVICE_ID, SELECTOR, "你好", confirmed=True
        )

        self.assertTrue(result["success"])
        self.assertEqual("你好", adapter.field_text)

    async def test_hinted_field_with_real_text_appends_normally(self) -> None:
        """字段有 hint 且已有真实内容时，hint 不生效，仍按真实原文追加验证。"""
        adapter = _ready_adapter("前缀")
        adapter.field_hint = "搜索设置项"
        runtime = self._runtime(adapter)

        result = await runtime.unicode_text_input(
            DEVICE_ID, SELECTOR, "你好", confirmed=True
        )

        self.assertTrue(result["success"])
        self.assertEqual("前缀你好", adapter.field_text)

    async def test_spaced_and_isolated_chars_on_hinted_field(self) -> None:
        """真机回归：空格与孤立单字符（短 UTF-7 载荷块场景）在带 hint 的空字段上可验证。"""
        adapter = _ready_adapter()
        adapter.field_hint = "搜索"
        runtime = self._runtime(adapter)

        result = await runtime.unicode_text_input(
            DEVICE_ID, SELECTOR, "A你 B", confirmed=True
        )

        self.assertTrue(result["success"])
        self.assertEqual("A你 B", adapter.field_text)

    async def test_already_enabled_helper_skips_enable(self) -> None:
        adapter = _ready_adapter()
        adapter.enabled_imes = [DEFAULT_IME, HELPER_FULL]
        runtime = self._runtime(adapter)

        await runtime.unicode_text_input(DEVICE_ID, SELECTOR, "你好", confirmed=True)

        kinds = [a[0] for a in adapter.actions]
        self.assertNotIn("input.ime.enable", kinds)

    async def test_helper_not_installed_fails_before_any_switch(self) -> None:
        adapter = FakeDeviceAdapter()
        adapter.custom_ui_xml = _form_xml("你好")
        runtime = self._runtime(adapter)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.unicode_text_input(DEVICE_ID, SELECTOR, "你好", confirmed=True)

        self.assertEqual("IME_HELPER_NOT_INSTALLED", raised.exception.code)
        kinds = [a[0] for a in adapter.actions]
        self.assertNotIn("input.ime.set", kinds)
        self.assertNotIn("input.text", kinds)

    async def test_switch_failure_maps_to_ime_switch_failed_without_input(self) -> None:
        failing = _configure_ready(HelperSetFailingAdapter())
        runtime = self._runtime(failing)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.unicode_text_input(DEVICE_ID, SELECTOR, "你好", confirmed=True)

        self.assertEqual("IME_SWITCH_FAILED", raised.exception.code)
        kinds = [a[0] for a in failing.actions]
        self.assertNotIn("input.text", kinds)

    async def test_readback_mismatch_fails_and_restores(self) -> None:
        adapter = _configure_ready(TamperingAdapter())
        runtime = self._runtime(adapter)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.unicode_text_input(DEVICE_ID, SELECTOR, "你好世界", confirmed=True)

        self.assertEqual("TEXT_INPUT_NOT_VERIFIED", raised.exception.code)
        self.assertFalse(raised.exception.retryable)
        # 验证失败也必须恢复原 IME。
        set_actions = [a for a in adapter.actions if a[0] == "input.ime.set"]
        self.assertEqual(("input.ime.set", DEVICE_ID, DEFAULT_IME), set_actions[-1])
        self.assertEqual(DEFAULT_IME, adapter.current_ime)

    async def test_restore_failure_is_reported_prominently(self) -> None:
        adapter = _configure_ready(RestoreFailingAdapter())
        runtime = self._runtime(adapter)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.unicode_text_input(DEVICE_ID, SELECTOR, "你好", confirmed=True)

        self.assertEqual("IME_RESTORE_FAILED", raised.exception.code)
        self.assertFalse(raised.exception.retryable)

    async def test_sensitive_digit_shapes_rejected_before_device_io(self) -> None:
        adapter = _ready_adapter("123456")
        runtime = self._runtime(adapter)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.unicode_text_input(DEVICE_ID, SELECTOR, "123456", confirmed=True)

        self.assertEqual("ACTION_REJECTED_BY_POLICY", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_ascii_fast_path_text_is_redirected(self) -> None:
        adapter = _ready_adapter("helloWorld.1")
        runtime = self._runtime(adapter)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.unicode_text_input(
                DEVICE_ID, SELECTOR, "helloWorld.1", confirmed=True
            )

        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_control_characters_rejected_before_device_io(self) -> None:
        adapter = _ready_adapter("x")
        runtime = self._runtime(adapter)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.unicode_text_input(
                DEVICE_ID, SELECTOR, "你好\n世界", confirmed=True
            )

        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_sensitive_field_rejected_by_policy(self) -> None:
        adapter = FakeDeviceAdapter()
        adapter.custom_ui_xml = _form_xml("", resource_id="password_input")
        adapter.installed_imes = (DEFAULT_IME, HELPER_FULL)
        runtime = self._runtime(adapter)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.unicode_text_input(
                DEVICE_ID,
                {"strategy": "resource_id", "value": "password_input"},
                "你好",
                confirmed=True,
            )

        self.assertEqual("ACTION_REJECTED_BY_POLICY", raised.exception.code)
        kinds = [a[0] for a in adapter.actions]
        self.assertNotIn("input.ime.set", kinds)
        self.assertNotIn("input.text", kinds)

    async def test_policy_requires_explicit_confirmation(self) -> None:
        adapter = _ready_adapter("你好")
        runtime = self._runtime(adapter)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.unicode_text_input(
                DEVICE_ID, SELECTOR, "你好", confirmed=False
            )

        self.assertEqual("CONFIRMATION_REQUIRED", raised.exception.code)
        self.assertEqual([], adapter.actions)

    async def test_missing_capability_is_rejected(self) -> None:
        device = Device(
            device_id="fake:no-unicode",
            platform=Platform.ANDROID,
            name="No unicode",
            model="fake",
            os_version="15",
            connection=ConnectionState.ONLINE,
            capabilities=("device.inspect@1",),
        )
        adapter = _ready_adapter("你好")
        adapter._devices = [device]
        runtime = self._runtime(adapter)

        with self.assertRaises(MobileAgentError) as raised:
            await runtime.unicode_text_input(
                device.device_id, SELECTOR, "你好", confirmed=True
            )

        self.assertEqual("CAPABILITY_UNAVAILABLE", raised.exception.code)

    async def test_encode_helper_matches_wire_format(self) -> None:
        encoded = encode_modified_utf7("搜索 关键词")
        self.assertTrue(encoded.isascii())
        self.assertNotIn(" ", encoded)
        self.assertEqual("搜索 关键词", reference_decode_modified_utf7(encoded))


if __name__ == "__main__":
    unittest.main()
