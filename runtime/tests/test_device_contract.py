from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from mobile_agent.domain.device import ConnectionState, Device, Platform


ROOT = Path(__file__).resolve().parents[2]


class DeviceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(
            (ROOT / "contracts/schemas/device.schema.json").read_text(encoding="utf-8")
        )

    def test_serialized_device_matches_public_schema_shape(self) -> None:
        payload = Device(
            device_id="fake:001",
            platform=Platform.ANDROID,
            name="Fake",
            model="fake",
            os_version="15",
            connection=ConnectionState.ONLINE,
            capabilities=("device.inspect@1",),
        ).to_dict()

        self.assertEqual(set(self.schema["required"]), set(payload))
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], payload["schema_version"])
        self.assertIn(payload["platform"], self.schema["properties"]["platform"]["enum"])
        self.assertIn(payload["connection"], self.schema["properties"]["connection"]["enum"])
        pattern = self.schema["properties"]["capabilities"]["items"]["pattern"]
        self.assertTrue(all(re.match(pattern, item) for item in payload["capabilities"]))

    def test_device_rejects_empty_id_and_duplicate_capabilities(self) -> None:
        with self.assertRaises(ValueError):
            Device("", Platform.ANDROID, "", "", "", ConnectionState.UNKNOWN)
        with self.assertRaises(ValueError):
            Device(
                "fake:1",
                Platform.ANDROID,
                "",
                "",
                "",
                ConnectionState.ONLINE,
                ("device.inspect@1", "device.inspect@1"),
            )


if __name__ == "__main__":
    unittest.main()

