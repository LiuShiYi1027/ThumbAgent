from __future__ import annotations

import unittest

from mobile_agent.devices.adapters.android.parser import extract_ui_xml, parse_foreground_app


class ObservationParserTests(unittest.TestCase):
    def test_parses_foreground_app_from_supported_formats(self) -> None:
        self.assertEqual(
            ("com.example", ".MainActivity"),
            parse_foreground_app("mCurrentFocus=Window{abc u0 com.example/.MainActivity}"),
        )
        self.assertEqual(
            ("com.example", "com.example.Home"),
            parse_foreground_app("topResumedActivity=ActivityRecord{1 u0 com.example/com.example.Home t1}"),
        )
        self.assertEqual(("", ""), parse_foreground_app("no focused application"))

    def test_extracts_xml_and_rejects_missing_document(self) -> None:
        xml = b'<?xml version="1.0"?><hierarchy rotation="0"></hierarchy>'
        self.assertEqual(xml, extract_ui_xml(b"noise\n" + xml + b"\nfinished"))
        self.assertEqual(b"", extract_ui_xml(b"UI hierarchy unavailable"))

    def test_foreground_app_prefers_primary_display(self) -> None:
        output = """
        Display: mDisplayId=1 (organized)
          mFocusedApp=ActivityRecord{1 u0 com.example.secondary/.Secondary t1}
        Display: mDisplayId=0 (organized)
          mCurrentFocus=Window{2 u0 NotificationShade}
          mFocusedApp=ActivityRecord{3 u0 com.android.settings/.Settings t2}
        """
        self.assertEqual(
            ("com.android.settings", ".Settings"), parse_foreground_app(output)
        )
