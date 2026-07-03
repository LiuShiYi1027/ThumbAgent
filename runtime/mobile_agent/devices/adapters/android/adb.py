"""A constrained, cancellable ADB process runner."""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError


@dataclass(frozen=True, slots=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: bytes
    stderr: bytes

    @property
    def stdout_text(self) -> str:
        return self.stdout.decode("utf-8", errors="replace")

    @property
    def stderr_text(self) -> str:
        return self.stderr.decode("utf-8", errors="replace")


class ProcessRunner(Protocol):
    async def run(self, executable: Path, args: Sequence[str]) -> CommandResult: ...


class AsyncProcessRunner:
    """Execute a fixed binary without a shell and with bounded output."""

    def __init__(self, timeout_seconds: float = 15.0, max_output_bytes: int = 33_554_432) -> None:
        if timeout_seconds <= 0 or max_output_bytes <= 0:
            raise ValueError("timeout and output limit must be positive")
        self._timeout = timeout_seconds
        self._max_output = max_output_bytes

    async def run(self, executable: Path, args: Sequence[str]) -> CommandResult:
        process = await asyncio.create_subprocess_exec(
            str(executable),
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                self._communicate_limited(process), timeout=self._timeout
            )
        except asyncio.TimeoutError as error:
            await self._stop(process)
            raise MobileAgentError(
                code="ACTION_TIMEOUT",
                category=ErrorCategory.EXECUTION,
                message="ADB 命令执行超时",
                retryable=True,
                suggested_action="检查设备连接后重试",
            ) from error
        except asyncio.CancelledError:
            await self._stop(process)
            raise
        except MobileAgentError:
            await self._stop(process)
            raise
        return CommandResult(tuple(args), process.returncode or 0, stdout, stderr)

    async def _communicate_limited(
        self, process: asyncio.subprocess.Process
    ) -> tuple[bytes, bytes]:
        assert process.stdout is not None
        assert process.stderr is not None
        stdout_task = asyncio.create_task(self._read_limited(process.stdout))
        stderr_task = asyncio.create_task(self._read_limited(process.stderr))
        try:
            stdout, stderr = await asyncio.gather(stdout_task, stderr_task)
            await process.wait()
            return stdout, stderr
        except Exception:
            stdout_task.cancel()
            stderr_task.cancel()
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            raise

    async def _read_limited(self, stream: asyncio.StreamReader) -> bytes:
        output = bytearray()
        while chunk := await stream.read(65_536):
            output.extend(chunk)
            if len(output) > self._max_output:
                raise MobileAgentError(
                    code="PROCESS_OUTPUT_LIMIT_EXCEEDED",
                    category=ErrorCategory.EXECUTION,
                    message="ADB 命令输出超过安全限制",
                )
        return bytes(output)

    @staticmethod
    async def _stop(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()


class AdbRunner:
    """The sole Android gateway for invoking approved ADB argument lists."""

    def __init__(
        self,
        executable: Path | None = None,
        process_runner: ProcessRunner | None = None,
    ) -> None:
        self._executable = executable or self._resolve_adb()
        self._process_runner = process_runner or AsyncProcessRunner()

    @property
    def executable(self) -> Path:
        return self._executable

    async def run(self, *args: str) -> CommandResult:
        self._validate_args(args)
        return await self._process_runner.run(self._executable, args)

    @staticmethod
    def _resolve_adb() -> Path:
        resolved = shutil.which("adb")
        if not resolved:
            raise MobileAgentError(
                code="ADB_NOT_FOUND",
                category=ErrorCategory.DEVICE,
                message="未找到 Android Platform Tools",
                suggested_action="安装 adb 或配置可执行文件路径",
            )
        return Path(resolved).resolve()

    @staticmethod
    def _validate_args(args: Sequence[str]) -> None:
        if not args:
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="ADB 参数不能为空",
            )
        for argument in args:
            if not isinstance(argument, str) or "\x00" in argument or "\n" in argument:
                raise MobileAgentError(
                    code="INVALID_ARGUMENT",
                    category=ErrorCategory.VALIDATION,
                    message="ADB 参数包含非法字符",
                )
