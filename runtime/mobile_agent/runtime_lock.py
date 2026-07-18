"""Exclusive local Runtime ownership for one data directory."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
from typing import TextIO

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError


class RuntimeInstanceLock:
    """Hold a non-blocking process lock for one Runtime data directory."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._file: TextIO | None = None

    def acquire(self) -> RuntimeInstanceLock:
        """Acquire the lock or reject a second Runtime immediately."""

        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+", encoding="utf-8")
        os.chmod(self._path, 0o600)
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            handle.close()
            raise MobileAgentError(
                code="RUNTIME_ALREADY_RUNNING",
                category=ErrorCategory.EXECUTION,
                message="同一数据目录已有 Mobile Agent Runtime 正在运行",
                retryable=False,
                suggested_action="继续使用已启动的 Runtime，或先将其正常停止",
            ) from error
        handle.seek(0)
        handle.truncate()
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        self._file = handle
        return self

    def release(self) -> None:
        """Release ownership while leaving the diagnostic lock file in place."""

        handle = self._file
        if handle is None:
            return
        self._file = None
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    def __enter__(self) -> RuntimeInstanceLock:
        return self.acquire()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()
