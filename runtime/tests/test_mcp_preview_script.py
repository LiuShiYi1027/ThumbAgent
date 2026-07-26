from __future__ import annotations

import unittest
from pathlib import Path


class McpPreviewScriptTests(unittest.TestCase):
    def test_registration_fingerprint_tracks_tool_catalog_sources(self) -> None:
        root = Path(__file__).resolve().parents[2]
        script = (root / "scripts/run-mcp-preview.zsh").read_text(
            encoding="utf-8"
        )

        for relative_path in (
            "runtime/mobile_agent/mcp/api_client.py",
            "runtime/mobile_agent/mcp/server.py",
            "runtime/mobile_agent/mcp/tools.py",
            "contracts/schemas/mcp-tool-inputs.schema.json",
        ):
            self.assertIn(relative_path, script)
        self.assertIn("path.read_bytes()", script)
