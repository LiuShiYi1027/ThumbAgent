from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from mobile_agent.cli.local_data_cleanup import main as cleanup_main
from mobile_agent.cli.local_data_cleanup_prepare import main as prepare_main
from mobile_agent.cli.local_storage import main as storage_main


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()


class LocalDataCliTests(unittest.TestCase):
    def test_renders_storage_and_read_only_prepare(self) -> None:
        stdout = io.StringIO()
        storage = _Response(
            {
                "storage": {
                    "total_count": 4,
                    "total_bytes": 100,
                    "expired_count": 2,
                    "expired_bytes": 50,
                    "retention_days": 7,
                    "oldest_created_at": None,
                    "newest_created_at": None,
                }
            }
        )
        with patch(
            "mobile_agent.cli.local_storage.urlopen", return_value=storage
        ), patch("sys.stdout", stdout):
            self.assertEqual(0, storage_main([]))
        self.assertIn("Artifacts: 4 / 100 bytes", stdout.getvalue())

        stdout = io.StringIO()
        prepared = _Response(
            {
                "approval": {
                    "approval_id": "approval_" + "1" * 32,
                    "candidate_count": 2,
                    "candidate_bytes": 50,
                    "cutoff_at": "2026-07-20T00:00:00Z",
                    "truncated": False,
                    "expires_at": "2026-07-27T00:10:00Z",
                }
            }
        )
        with patch(
            "mobile_agent.cli.local_data_cleanup_prepare.urlopen",
            return_value=prepared,
        ), patch("sys.stdout", stdout):
            self.assertEqual(0, prepare_main(["--token", "token"]))
        self.assertIn("No files were deleted.", stdout.getvalue())

    def test_submit_requires_confirm_and_renders_async_task(self) -> None:
        stdout = io.StringIO()
        response = _Response(
            {
                "execution": {
                    "task_id": "task_" + "1" * 32,
                    "task_type": "local.data.cleanup",
                    "status": "queued",
                    "device_id": "local:runtime",
                    "deadline_seconds": 120,
                }
            }
        )
        with patch(
            "mobile_agent.cli.local_data_cleanup.urlopen",
            return_value=response,
        ), patch("sys.stdout", stdout):
            self.assertEqual(
                0,
                cleanup_main(
                    [
                        "approval_" + "1" * 32,
                        "--confirm",
                        "--token",
                        "token",
                    ]
                ),
            )
        self.assertIn("local.data.cleanup", stdout.getvalue())
