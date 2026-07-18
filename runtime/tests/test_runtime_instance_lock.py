from __future__ import annotations

import stat
import tempfile
import unittest
from pathlib import Path

from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.runtime_lock import RuntimeInstanceLock


class RuntimeInstanceLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "runtime.lock"

    def test_second_runtime_for_same_data_directory_is_rejected(self) -> None:
        first = RuntimeInstanceLock(self.path)
        second = RuntimeInstanceLock(self.path)
        first.acquire()
        self.addCleanup(first.release)

        with self.assertRaises(MobileAgentError) as raised:
            second.acquire()

        self.assertEqual("RUNTIME_ALREADY_RUNNING", raised.exception.code)

    def test_release_allows_next_runtime_and_lock_file_is_private(self) -> None:
        first = RuntimeInstanceLock(self.path).acquire()
        first.release()

        second = RuntimeInstanceLock(self.path).acquire()
        self.addCleanup(second.release)

        self.assertEqual(0o600, stat.S_IMODE(self.path.stat().st_mode))


if __name__ == "__main__":
    unittest.main()
