from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

from mobile_agent.devices.adapters.android.adb import AsyncProcessRunner
from mobile_agent.domain.errors import MobileAgentError


class AsyncProcessRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_enforces_timeout(self) -> None:
        runner = AsyncProcessRunner(timeout_seconds=0.05)

        with self.assertRaises(MobileAgentError) as raised:
            await runner.run(Path(sys.executable), ("-c", "import time; time.sleep(5)"))

        self.assertEqual("ACTION_TIMEOUT", raised.exception.code)

    async def test_enforces_output_limit(self) -> None:
        runner = AsyncProcessRunner(max_output_bytes=16)

        with self.assertRaises(MobileAgentError) as raised:
            await runner.run(Path(sys.executable), ("-c", "print('x' * 100)"))

        self.assertEqual("PROCESS_OUTPUT_LIMIT_EXCEEDED", raised.exception.code)

    async def test_propagates_cancellation(self) -> None:
        runner = AsyncProcessRunner(timeout_seconds=5)
        task = asyncio.create_task(
            runner.run(Path(sys.executable), ("-c", "import time; time.sleep(5)"))
        )
        await asyncio.sleep(0.02)

        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await task
