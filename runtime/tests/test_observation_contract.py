from __future__ import annotations

import json
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.evidence.artifacts import ArtifactStore


ROOT = Path(__file__).resolve().parents[2]


class ObservationContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_fake_observation_matches_contract_shapes_and_artifacts(self) -> None:
        observation_schema = json.loads(
            (ROOT / "contracts/schemas/observation.schema.json").read_text(encoding="utf-8")
        )
        artifact_schema = json.loads(
            (ROOT / "contracts/schemas/artifact.schema.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory))
            payload = (await FakeDeviceAdapter().observe("fake:android-001", store)).to_dict()

            self.assertEqual(set(observation_schema["required"]), set(payload))
            self.assertRegex(payload["observation_id"], r"^obs_[a-f0-9]{32}$")
            screenshot = payload["screen"]["screenshot"]
            self.assertEqual(set(artifact_schema["required"]), set(screenshot))
            self.assertTrue(re.match(artifact_schema["properties"]["sha256"]["pattern"], screenshot["sha256"]))
            self.assertEqual(b"\x89PNG\r\n\x1a\n", store.resolve(screenshot["relative_path"]).read_bytes()[:8])
            xml_path = store.resolve(payload["ui_tree"]["artifact"]["relative_path"])
            self.assertEqual("hierarchy", ET.fromstring(xml_path.read_bytes()).tag)

