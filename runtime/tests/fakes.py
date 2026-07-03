"""Shared deterministic process fakes."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from mobile_agent.devices.adapters.android.adb import CommandResult


class FakeProcessRunner:
    def __init__(self, responses: dict[tuple[str, ...], CommandResult]) -> None:
        self.responses = responses
        self.calls: list[tuple[Path, tuple[str, ...]]] = []

    async def run(self, executable: Path, args: Sequence[str]) -> CommandResult:
        key = tuple(args)
        self.calls.append((executable, key))
        if key not in self.responses:
            raise AssertionError(f"Unexpected process call: {key!r}")
        return self.responses[key]


def result(
    args: tuple[str, ...], stdout: str | bytes = "", stderr: str | bytes = "", code: int = 0
) -> CommandResult:
    stdout_bytes = stdout.encode() if isinstance(stdout, str) else stdout
    stderr_bytes = stderr.encode() if isinstance(stderr, str) else stderr
    return CommandResult(args, code, stdout_bytes, stderr_bytes)
