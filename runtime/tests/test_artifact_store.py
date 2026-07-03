from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from mobile_agent.domain.artifact import ArtifactKind
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore


class ArtifactStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = ArtifactStore(Path(self.directory.name))

    def test_writes_generated_relative_path_hash_and_size(self) -> None:
        data = b"safe screenshot fixture"

        artifact = self.store.write(ArtifactKind.SCREENSHOT, "image/png", data, ".png")

        self.assertFalse(Path(artifact.relative_path).is_absolute())
        self.assertEqual(len(data), artifact.size_bytes)
        self.assertEqual(hashlib.sha256(data).hexdigest(), artifact.sha256)
        self.assertEqual(data, self.store.resolve(artifact.relative_path).read_bytes())
        self.assertEqual([], list(self.store.root.rglob(".tmp-*")))

    def test_rejects_path_escape_and_unsupported_type(self) -> None:
        with self.assertRaises(MobileAgentError) as escaped:
            self.store.resolve("../outside")
        self.assertEqual("INVALID_ARTIFACT_PATH", escaped.exception.code)

        with self.assertRaises(MobileAgentError) as unsupported:
            self.store.write(ArtifactKind.SCREENSHOT, "text/plain", b"x", ".txt")
        self.assertEqual("INVALID_ARGUMENT", unsupported.exception.code)

