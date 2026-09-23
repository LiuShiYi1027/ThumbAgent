"""Contract tests for the Unicode text input helper (ITER-0059, ADR-0019)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "contracts" / "schemas"


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text())


class UnicodeInputContractTest(unittest.TestCase):
    def test_result_schema_shape(self) -> None:
        schema = _load_schema("unicode-input-result.schema.json")

        self.assertEqual("input.unicode_text", schema["properties"]["skill_id"]["const"])
        for field in ("field", "text_length", "text_sha256", "ime", "evidence_refs"):
            self.assertIn(field, schema["required"], field)
        # 文本原文不得进入结果，仅记录长度与 SHA-256（沿用 ActionResult 隐私先例）。
        self.assertNotIn("text", schema["properties"])
        self.assertEqual("search", schema["properties"]["submitted"]["const"])
        self.assertNotIn("submitted", schema["required"])
        self.assertEqual(1, schema["properties"]["text_length"]["minimum"])
        self.assertEqual(256, schema["properties"]["text_length"]["maximum"])
        ime = schema["properties"]["ime"]
        self.assertTrue(ime["properties"]["restored"]["const"])
        for field in ("helper_id", "previous_id", "restored"):
            self.assertIn(field, ime["required"], field)

    def test_task_run_schema_accepts_unicode_step(self) -> None:
        schema = _load_schema("task-run.schema.json")

        self.assertIn("input.unicode_text", schema["properties"]["task_type"]["enum"])
        step = schema["properties"]["steps"]["items"]["properties"]
        self.assertIn("input.unicode_text", step["name"]["enum"])
        refs = {entry.get("$ref") for entry in step["result"]["oneOf"]}
        self.assertIn("unicode-input-result.schema.json", refs)

    def test_mcp_tool_input_schema(self) -> None:
        schema = _load_schema("mcp-tool-inputs.schema.json")
        tool = schema["$defs"]["unicode_text_input"]

        self.assertEqual(
            ["device_id", "selector", "text", "confirmed"], tool["required"]
        )
        self.assertEqual("ui-selector.schema.json", tool["properties"]["selector"]["$ref"])
        self.assertEqual(1, tool["properties"]["text"]["minLength"])
        self.assertEqual(256, tool["properties"]["text"]["maxLength"])
        # 高风险动作必须显式确认，不允许默认值。
        self.assertTrue(tool["properties"]["confirmed"]["const"])
        self.assertEqual("search", tool["properties"]["submit"]["const"])
        self.assertNotIn("submit", tool["required"])

    def test_generated_typescript_in_sync(self) -> None:
        generated = (
            ROOT / "contracts" / "generated" / "typescript" / "unicode-input-result.ts"
        )
        self.assertTrue(generated.is_file())
        content = generated.read_text()
        self.assertIn("UnicodeInputResult", content)
        self.assertIn('"input.unicode_text"', content)


if __name__ == "__main__":
    unittest.main()
