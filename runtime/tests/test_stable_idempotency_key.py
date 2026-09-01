"""Regression tests for stable, content-derived Idempotency-Key values (M13)."""

from __future__ import annotations

import io
import json
import threading
import unittest
from typing import Any
from unittest.mock import patch
from urllib.request import Request

from mobile_agent.api.idempotency import stable_idempotency_key
from mobile_agent.api.server import _idempotency_key
from mobile_agent.cli import (
    device_logs_collect,
    device_performance_snapshot,
    diagnostic_bundle_collect,
    local_data_cleanup,
)
from mobile_agent.domain.task import TaskRun, TaskStatus
from mobile_agent.mcp.api_client import RuntimeApiClient
from mobile_agent.tasks.execution import AsyncTaskExecutor, InMemoryTaskExecutionStore


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()


class _Transport:
    def __init__(self, payload: dict[str, Any], status: int = 200) -> None:
        self.payload = payload
        self.status = status
        self.calls: list[tuple[str, str, dict[str, str], bytes, float]] = []

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout: float,
    ) -> tuple[int, bytes]:
        self.calls.append((method, url, headers, body or b"", timeout))
        return self.status, json.dumps(self.payload).encode()


def _cli_submitted_keys(module: Any, argv: list[str]) -> list[str | None]:
    """Run one async CLI main twice with identical argv and capture the keys."""

    requests: list[Request] = []
    payload = {
        "execution": {
            "task_id": "task_1",
            "task_type": "x",
            "status": "queued",
            "device_id": "adb:001",
            "deadline_seconds": 60,
        }
    }

    def fake_urlopen(request: Request, timeout: float = 0) -> _Response:
        requests.append(request)
        return _Response(payload)

    with patch.object(module, "urlopen", fake_urlopen), patch(
        "sys.stdout", io.StringIO()
    ):
        for _ in range(2):
            if module.main(list(argv)) != 0:
                raise AssertionError(f"{module.__name__} exited non-zero")
    return [request.get_header("Idempotency-key") for request in requests]


class StableIdempotencyKeyTests(unittest.TestCase):
    def test_same_parameters_derive_same_key(self) -> None:
        params = {"device_id": "adb:001", "confirmed": True, "max_lines": 100}
        first = stable_idempotency_key("mcp", "/v1/tasks/app.launch/async", params)
        second = stable_idempotency_key(
            "mcp",
            "/v1/tasks/app.launch/async",
            {"max_lines": 100, "confirmed": True, "device_id": "adb:001"},
        )

        self.assertEqual(first, second)
        self.assertRegex(first, r"^mcp-[a-f0-9]{32}$")

    def test_different_parameters_or_endpoints_derive_different_keys(self) -> None:
        base = stable_idempotency_key(
            "cli", "/v1/tasks/device.logs.collect/async", {"device_id": "adb:001"}
        )

        self.assertNotEqual(
            base,
            stable_idempotency_key(
                "cli",
                "/v1/tasks/device.logs.collect/async",
                {"device_id": "adb:002"},
            ),
        )
        self.assertNotEqual(
            base,
            stable_idempotency_key(
                "cli", "/v1/tasks/device.performance.snapshot/async",
                {"device_id": "adb:001"},
            ),
        )
        self.assertNotEqual(
            base,
            stable_idempotency_key(
                "mcp", "/v1/tasks/device.logs.collect/async", {"device_id": "adb:001"}
            ),
        )

    def test_derived_key_passes_server_validator(self) -> None:
        key = stable_idempotency_key(
            "mcp",
            "/v1/tasks/agent.run/async",
            {"device_id": "adb:001", "goal": "打开设置", "confirmed": True},
        )

        self.assertEqual(key, _idempotency_key(key))

    def test_mcp_client_reuses_stable_key_for_identical_submission(self) -> None:
        transport = _Transport({"execution": {"task_id": "task_1"}})
        client = RuntimeApiClient("http://127.0.0.1:8765", "token", transport)
        arguments = {"device_id": "adb:001", "app_id": "com.example.app"}

        client.launch_app(dict(arguments))
        client.launch_app(dict(arguments))
        client.launch_app({"device_id": "adb:001", "app_id": "com.other.app"})

        keys = [call[2]["Idempotency-Key"] for call in transport.calls]
        self.assertEqual(keys[0], keys[1])
        self.assertNotEqual(keys[0], keys[2])
        self.assertRegex(keys[0], r"^mcp-[a-f0-9]{32}$")

    def test_device_logs_cli_reuses_stable_key_for_identical_command(self) -> None:
        argv = ["adb:001", "--confirm", "--token", "token", "--async-task"]
        keys = _cli_submitted_keys(device_logs_collect, argv)
        changed = _cli_submitted_keys(
            device_logs_collect, argv + ["--max-lines", "100"]
        )

        self.assertEqual(keys[0], keys[1])
        self.assertNotEqual(keys[0], changed[0])
        self.assertRegex(keys[0] or "", r"^cli-[a-f0-9]{32}$")

    def test_performance_cli_reuses_stable_key_for_identical_command(self) -> None:
        argv = ["adb:001", "--token", "token", "--async-task"]
        keys = _cli_submitted_keys(device_performance_snapshot, argv)
        changed = _cli_submitted_keys(
            device_performance_snapshot, argv + ["--deadline-seconds", "30"]
        )

        self.assertEqual(keys[0], keys[1])
        self.assertNotEqual(keys[0], changed[0])
        self.assertRegex(keys[0] or "", r"^cli-[a-f0-9]{32}$")

    def test_diagnostic_cli_reuses_stable_key_for_identical_command(self) -> None:
        argv = ["adb:001", "--confirm", "--token", "token"]
        keys = _cli_submitted_keys(diagnostic_bundle_collect, argv)
        changed = _cli_submitted_keys(
            diagnostic_bundle_collect, argv + ["--app-id", "com.example.app"]
        )

        self.assertEqual(keys[0], keys[1])
        self.assertNotEqual(keys[0], changed[0])
        self.assertRegex(keys[0] or "", r"^cli-[a-f0-9]{32}$")

    def test_cleanup_cli_reuses_stable_key_for_identical_command(self) -> None:
        argv = ["approval_" + "1" * 32, "--confirm", "--token", "token"]
        keys = _cli_submitted_keys(local_data_cleanup, argv)
        changed = _cli_submitted_keys(
            local_data_cleanup, ["approval_" + "2" * 32, "--confirm", "--token", "token"]
        )

        self.assertEqual(keys[0], keys[1])
        self.assertNotEqual(keys[0], changed[0])
        self.assertRegex(keys[0] or "", r"^cli-[a-f0-9]{32}$")

    def test_stable_key_hits_task_engine_dedup(self) -> None:
        store = InMemoryTaskExecutionStore()
        executor = AsyncTaskExecutor(store)
        completed = threading.Event()

        def run_factory(
            task_id: str,
            on_step: Any,
            cancelled: Any,
            exceeded: Any,
        ) -> Any:
            async def run() -> TaskRun:
                now = "2026-09-01T00:00:00Z"
                return TaskRun(
                    task_id=task_id,
                    task_type="device.logs.collect",
                    device_id="adb:001",
                    goal="collect",
                    status=TaskStatus.SUCCEEDED,
                    started_at=now,
                    completed_at=now,
                    steps=(),
                    evidence_summary={},
                    deadline_seconds=60.0,
                )

            return run()

        key = stable_idempotency_key(
            "mcp",
            "/v1/tasks/device.logs.collect/async",
            {
                "device_id": "adb:001",
                "max_lines": 100,
                "minimum_level": "info",
                "confirmed": True,
                "deadline_seconds": 60,
            },
        )
        first = executor.submit(
            "adb:001",
            "collect",
            run_factory,
            lambda task: completed.set(),
            key,
            "fingerprint",
            60.0,
            task_type="device.logs.collect",
        )
        second = executor.submit(
            "adb:001",
            "collect",
            run_factory,
            lambda task: completed.set(),
            key,
            "fingerprint",
            60.0,
            task_type="device.logs.collect",
        )

        self.assertEqual(first.task_id, second.task_id)
        self.assertTrue(completed.wait(2), "deduplicated task did not finish")


if __name__ == "__main__":
    unittest.main()
