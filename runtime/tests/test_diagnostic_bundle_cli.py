from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from mobile_agent.cli.diagnostic_bundle_collect import main


class _Response:
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(
            {
                "execution": {
                    "task_id": "task_" + "1" * 32,
                    "task_type": "device.diagnostics.bundle",
                    "status": "queued",
                    "device_id": "adb:one",
                    "deadline_seconds": 120,
                }
            }
        ).encode()


class DiagnosticBundleCliTests(unittest.TestCase):
    def test_submits_confirmed_async_bundle_without_printing_content(self) -> None:
        stdout = io.StringIO()
        with patch(
            "mobile_agent.cli.diagnostic_bundle_collect.urlopen",
            return_value=_Response(),
        ), patch("sys.stdout", stdout):
            code = main(
                [
                    "adb:one",
                    "--app-id",
                    "com.example.app",
                    "--confirm",
                    "--token",
                    "test-token",
                ]
            )

        self.assertEqual(0, code)
        self.assertIn("device.diagnostics.bundle", stdout.getvalue())
        self.assertNotIn("screenshot", stdout.getvalue())
