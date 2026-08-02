"""Regression tests for the TypeScript contract generator."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_ts_contracts import check_files, expected_files


class TsContractsGeneratorTests(unittest.TestCase):
    def test_device_contract_contains_expected_members(self) -> None:
        outputs = expected_files()
        device = outputs[REPO_ROOT / "contracts/generated/typescript/device.ts"]
        self.assertIn("export interface Device {", device)
        self.assertIn('platform: "android" | "ios" | "harmonyos";', device)
        self.assertIn("session_id: string | null;", device)
        self.assertIn("capabilities: string[];", device)

    def test_readiness_contract_imports_device_and_unions_null(self) -> None:
        outputs = expected_files()
        readiness = outputs[REPO_ROOT / "contracts/generated/typescript/runtime-readiness.ts"]
        self.assertIn('import type { Device } from "./device";', readiness)
        self.assertIn("device: Device;", readiness)
        self.assertIn("issue: Issue | null;", readiness)
        self.assertIn('status: "ready" | "attention" | "blocked";', readiness)

    def test_committed_generated_files_are_in_sync(self) -> None:
        self.assertEqual(check_files(expected_files()), [])

    def test_drift_is_reported(self) -> None:
        outputs = expected_files()
        device_path = REPO_ROOT / "contracts/generated/typescript/device.ts"
        outputs[device_path] = outputs[device_path] + "// drift\n"
        errors = check_files(outputs)
        self.assertEqual(len(errors), 1)
        self.assertIn("out of date", errors[0])


if __name__ == "__main__":
    unittest.main()
