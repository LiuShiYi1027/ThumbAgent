from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from mobile_agent.devices.adapters.android.adb import AdbRunner
from mobile_agent.domain.errors import MobileAgentError
from runtime.tests.fakes import FakeProcessRunner, result


class AdbRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_passes_fixed_executable_and_argument_array(self) -> None:
        process = FakeProcessRunner({("devices", "-l"): result(("devices", "-l"))})
        runner = AdbRunner(Path("/safe/adb"), process)

        await runner.run("devices", "-l")

        self.assertEqual([(Path("/safe/adb"), ("devices", "-l"))], process.calls)

    async def test_rejects_newline_in_arguments(self) -> None:
        runner = AdbRunner(Path("/safe/adb"), FakeProcessRunner({}))
        with self.assertRaises(MobileAgentError) as raised:
            await runner.run("devices\nrm")
        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)

    def test_missing_adb_is_a_structured_error(self) -> None:
        with patch("shutil.which", return_value=None):
            with self.assertRaises(MobileAgentError) as raised:
                AdbRunner()
        self.assertEqual("ADB_NOT_FOUND", raised.exception.code)

