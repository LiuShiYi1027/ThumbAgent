"""Adapter contract tests for the Unicode input helper IME primitives (ITER-0059)."""

from __future__ import annotations

import unittest
from pathlib import Path

from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.domain.errors import MobileAgentError
from runtime.tests.fakes import FakeProcessRunner, result


HELPER_IME = "com.thumbagent.unicodeime/.UnicodeImeService"
DEFAULT_IME = "com.example.ime/.DefaultIme"


def _adapter(responses: dict[tuple[str, ...], object]) -> tuple[AndroidDeviceAdapter, FakeProcessRunner]:
    process = FakeProcessRunner(responses)  # type: ignore[arg-type]
    return AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process)), process


class UnicodeImeAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_current_input_method_uses_fixed_argv(self) -> None:
        adapter, process = _adapter(
            {
                ("-s", "serial-1", "shell", "settings", "get", "secure", "default_input_method"): result(
                    ("-s", "serial-1", "shell", "settings", "get", "secure", "default_input_method"),
                    DEFAULT_IME + "\n",
                ),
            }
        )

        ime = await adapter.current_input_method("adb:serial-1")

        self.assertEqual(DEFAULT_IME, ime)
        self.assertEqual(1, len(process.calls))

    async def test_current_input_method_rejects_empty_report(self) -> None:
        adapter, _ = _adapter(
            {
                ("-s", "serial-1", "shell", "settings", "get", "secure", "default_input_method"): result(
                    ("-s", "serial-1", "shell", "settings", "get", "secure", "default_input_method"),
                    "null\n",
                ),
            }
        )

        with self.assertRaises(MobileAgentError) as ctx:
            await adapter.current_input_method("adb:serial-1")
        self.assertEqual("IME_SWITCH_FAILED", ctx.exception.code)

    async def test_installed_and_enabled_input_methods_use_fixed_argv(self) -> None:
        adapter, _ = _adapter(
            {
                ("-s", "serial-1", "shell", "ime", "list", "-a", "-s"): result(
                    ("-s", "serial-1", "shell", "ime", "list", "-a", "-s"),
                    f"{DEFAULT_IME}\n{HELPER_IME}\n",
                ),
                ("-s", "serial-1", "shell", "ime", "list", "-s"): result(
                    ("-s", "serial-1", "shell", "ime", "list", "-s"),
                    DEFAULT_IME + "\n",
                ),
            }
        )

        installed = await adapter.installed_input_methods("adb:serial-1")
        enabled = await adapter.enabled_input_methods("adb:serial-1")

        self.assertEqual((DEFAULT_IME, HELPER_IME), installed)
        self.assertEqual((DEFAULT_IME,), enabled)

    async def test_enable_and_set_use_fixed_argv(self) -> None:
        adapter, process = _adapter(
            {
                ("-s", "serial-1", "shell", "ime", "enable", HELPER_IME): result(
                    ("-s", "serial-1", "shell", "ime", "enable", HELPER_IME)
                ),
                ("-s", "serial-1", "shell", "ime", "set", HELPER_IME): result(
                    ("-s", "serial-1", "shell", "ime", "set", HELPER_IME)
                ),
            }
        )

        await adapter.enable_input_method("adb:serial-1", HELPER_IME)
        await adapter.set_input_method("adb:serial-1", HELPER_IME)

        self.assertEqual(2, len(process.calls))

    async def test_ime_id_validation_rejects_injection_shapes(self) -> None:
        adapter, process = _adapter({})

        for bad in (
            "",
            "com.example.ime",
            "com.example.ime/.Ime;settings put secure x y",
            "com.example.ime/.Ime$(id)",
            "com.example.ime/.Ime\nmalicious",
            "../escape/.Ime",
        ):
            with self.assertRaises(MobileAgentError) as ctx:
                await adapter.set_input_method("adb:serial-1", bad)
            self.assertEqual("INVALID_ARGUMENT", ctx.exception.code, bad)
        self.assertEqual(0, len(process.calls))

    async def test_ime_set_failure_maps_to_ime_switch_failed(self) -> None:
        # MagicOS 等 ROM 拦截 ime set 时非零退出，映射为已知失败而不是裸 ACTION_FAILED。
        adapter, _ = _adapter(
            {
                ("-s", "serial-1", "shell", "ime", "set", HELPER_IME): result(
                    ("-s", "serial-1", "shell", "ime", "set", HELPER_IME),
                    stderr="SecurityException: not allowed",
                    code=255,
                ),
            }
        )

        with self.assertRaises(MobileAgentError) as ctx:
            await adapter.set_input_method("adb:serial-1", HELPER_IME)
        self.assertEqual("IME_SWITCH_FAILED", ctx.exception.code)
        self.assertTrue(ctx.exception.retryable)

    async def test_enable_failure_maps_to_ime_switch_failed(self) -> None:
        adapter, _ = _adapter(
            {
                ("-s", "serial-1", "shell", "ime", "enable", HELPER_IME): result(
                    ("-s", "serial-1", "shell", "ime", "enable", HELPER_IME),
                    stderr="Error: unknown input method",
                    code=1,
                ),
            }
        )

        with self.assertRaises(MobileAgentError) as ctx:
            await adapter.enable_input_method("adb:serial-1", HELPER_IME)
        self.assertEqual("IME_SWITCH_FAILED", ctx.exception.code)


    async def test_input_text_quotes_utf7_shift_marker_for_remote_shell(self) -> None:
        # ITER-0059 真机回归：adb 把 argv 拼为远端 sh 命令行，'&' 不加引用
        # 会被当作后台操作符导致整条注入失败。
        adapter, process = _adapter(
            {
                ("-s", "serial-1", "shell", "input", "text", "'&T2BZfU4WdUw-'"): result(
                    ("-s", "serial-1", "shell", "input", "text", "'&T2BZfU4WdUw-'")
                ),
            }
        )

        await adapter.input_text("adb:serial-1", "&T2BZfU4WdUw-")

        self.assertEqual(1, len(process.calls))


if __name__ == "__main__":
    unittest.main()
