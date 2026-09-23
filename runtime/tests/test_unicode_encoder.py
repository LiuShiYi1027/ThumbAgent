"""Unit tests for the Modified UTF-7 encoder and unicode text validation."""

from __future__ import annotations

import unittest

from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.domain.unicode_input import (
    HELPER_IME_ID,
    HELPER_PACKAGE,
    encode_modified_utf7,
    is_helper_ime,
    normalize_for_verification,
    text_digest,
    validate_ime_submit,
    validate_unicode_text,
)
from runtime.tests.utf7ref import reference_decode_modified_utf7


class ModifiedUtf7EncoderTests(unittest.TestCase):
    @staticmethod
    def _roundtrip(text: str) -> str:
        return reference_decode_modified_utf7(encode_modified_utf7(text))

    def test_roundtrip_chinese(self) -> None:
        self.assertEqual("你好世界", self._roundtrip("你好世界"))

    def test_roundtrip_mixed_ascii_cjk(self) -> None:
        self.assertEqual("hello 你好 world", self._roundtrip("hello 你好 world"))

    def test_roundtrip_emoji_and_astral(self) -> None:
        self.assertEqual("加油💪🏽 OK", self._roundtrip("加油💪🏽 OK"))

    def test_roundtrip_ampersand_and_percent(self) -> None:
        self.assertEqual("a&b 100%", self._roundtrip("a&b 100%"))

    def test_roundtrip_punctuation(self) -> None:
        self.assertEqual("价格：¥100（含税）", self._roundtrip("价格：¥100（含税）"))

    def test_output_is_wire_safe_ascii(self) -> None:
        for text in ("你好 世界", "café & tea", "100% 完成", "search 关键词"):
            encoded = encode_modified_utf7(text)
            self.assertTrue(encoded.isascii(), encoded)
            # 空格与 % 不直接出现在线上文本中，规避 input text 的设备端解析歧义。
            self.assertNotIn(" ", encoded)
            self.assertNotIn("%", encoded)

    def test_direct_chars_pass_through(self) -> None:
        self.assertEqual("abcXYZ019._-!?", encode_modified_utf7("abcXYZ019._-!?"))

    def test_ampersand_encodes_as_shift_escape(self) -> None:
        self.assertEqual("a&-b", encode_modified_utf7("a&b"))

    def test_base64_uses_modified_alphabet(self) -> None:
        # 构造会产生 '/' 的 UTF-16BE 字节序列，确认被替换为 ','。
        encoded = encode_modified_utf7("￿")  # U+FFFF -> ff ff -> //8- in standard base64
        self.assertNotIn("/", encoded)
        self.assertEqual("￿", self._roundtrip("￿"))

    def test_helper_id_matching_accepts_full_and_short_forms(self) -> None:
        self.assertTrue(is_helper_ime(HELPER_IME_ID))
        self.assertTrue(
            is_helper_ime(f"{HELPER_PACKAGE}/{HELPER_PACKAGE}.UnicodeImeService")
        )
        self.assertFalse(is_helper_ime("com.example.ime/.DefaultIme"))
        self.assertFalse(is_helper_ime("com.thumbagent.unicodeimex/.Fake"))


class UnicodeTextValidationTests(unittest.TestCase):
    def test_accepts_unicode_text(self) -> None:
        self.assertEqual("你好，世界", validate_unicode_text("你好，世界"))

    def test_rejects_non_string_and_empty(self) -> None:
        for bad in (None, 123, "", ["x"]):
            with self.assertRaises(MobileAgentError) as ctx:
                validate_unicode_text(bad)
            self.assertEqual("INVALID_ARGUMENT", ctx.exception.code, repr(bad))

    def test_rejects_overlong_text(self) -> None:
        with self.assertRaises(MobileAgentError) as ctx:
            validate_unicode_text("汉" * 257)
        self.assertEqual("INVALID_ARGUMENT", ctx.exception.code)
        self.assertEqual("汉" * 256, validate_unicode_text("汉" * 256))

    def test_rejects_control_characters(self) -> None:
        for bad in ("你好\n世界", "tab\t字符", "回车\r", "null\x00"):
            with self.assertRaises(MobileAgentError) as ctx:
                validate_unicode_text(bad)
            self.assertEqual("INVALID_ARGUMENT", ctx.exception.code, repr(bad))

    def test_rejects_sensitive_digit_shapes(self) -> None:
        for bad in ("1234", "123456", "12345678", "13800138000"):
            with self.assertRaises(MobileAgentError) as ctx:
                validate_unicode_text(bad)
            self.assertEqual("ACTION_REJECTED_BY_POLICY", ctx.exception.code, bad)

    def test_rejects_ascii_fast_path_text(self) -> None:
        with self.assertRaises(MobileAgentError) as ctx:
            validate_unicode_text("helloWorld.1")
        self.assertEqual("INVALID_ARGUMENT", ctx.exception.code)
        self.assertIn("input.text", ctx.exception.suggested_action or "")

    def test_ascii_with_space_is_unicode_path(self) -> None:
        # 含空格的 ASCII 走 unicode 通道（input.text 不支持空格）。
        self.assertEqual("hello world", validate_unicode_text("hello world"))

    def test_ime_submit_accepts_search_or_none(self) -> None:
        self.assertIsNone(validate_ime_submit(None))
        self.assertEqual("search", validate_ime_submit("search"))
        for bad in ("go", "done", "", 1):
            with self.assertRaises(MobileAgentError) as ctx:
                validate_ime_submit(bad)
            self.assertEqual("INVALID_ARGUMENT", ctx.exception.code, repr(bad))


class VerificationHelpersTests(unittest.TestCase):
    def test_nfc_normalization_merges_combining_forms(self) -> None:
        composed = "é"
        decomposed = "é"
        self.assertEqual(
            normalize_for_verification(composed), normalize_for_verification(decomposed)
        )
        self.assertEqual(text_digest(composed), text_digest(decomposed))

    def test_digest_is_stable_hex(self) -> None:
        digest = text_digest("你好")
        self.assertEqual(64, len(digest))
        self.assertEqual(digest, text_digest("你好"))


if __name__ == "__main__":
    unittest.main()
