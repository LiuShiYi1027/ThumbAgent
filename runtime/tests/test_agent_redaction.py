from __future__ import annotations

import unittest

from mobile_agent.agent.redaction import redact_ui_text


class AgentRedactionTests(unittest.TestCase):
    def test_redacts_common_identifiers_without_hiding_normal_settings_values(self) -> None:
        cases = {
            "联系 13812345678": "联系 [REDACTED_PHONE]",
            "账号 150******20": "账号 [REDACTED_PHONE]",
            "邮箱 person@example.com": "邮箱 [REDACTED_EMAIL]",
            "编号 6222021234567890": "编号 [REDACTED_IDENTIFIER]",
            "亮度 60%": "亮度 60%",
        }

        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(expected, redact_ui_text(source))
