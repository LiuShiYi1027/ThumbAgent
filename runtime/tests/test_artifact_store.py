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

    def test_screenshot_content_returns_validated_png_bytes(self) -> None:
        data = b"\x89PNG\r\n\x1a\n" + b"fixture-image-body"
        artifact = self.store.write(ArtifactKind.SCREENSHOT, "image/png", data, ".png")

        self.assertEqual(data, self.store.screenshot_content(artifact.artifact_id))

    def test_screenshot_content_rejects_invalid_id_and_unknown_artifact(self) -> None:
        with self.assertRaises(MobileAgentError) as invalid:
            self.store.screenshot_content("../../etc/passwd")
        self.assertEqual("INVALID_ARGUMENT", invalid.exception.code)

        with self.assertRaises(MobileAgentError) as missing:
            self.store.screenshot_content("artifact_" + "0" * 32)
        self.assertEqual("ARTIFACT_NOT_FOUND", missing.exception.code)

    def test_write_rejects_oversized_artifacts_by_kind(self) -> None:
        """写入侧按 kind 限制大小：截图与读取侧同为 8MiB，诊断包对齐 24MiB。"""
        oversized_png = b"\x89PNG\r\n\x1a\n" + b"\0" * (8 * 1024 * 1024)
        with self.assertRaises(MobileAgentError) as screenshot:
            self.store.write(
                ArtifactKind.SCREENSHOT, "image/png", oversized_png, ".png"
            )
        self.assertEqual("ARTIFACT_TOO_LARGE", screenshot.exception.code)

        with self.assertRaises(MobileAgentError) as performance:
            self.store.write(
                ArtifactKind.DEVICE_PERFORMANCE,
                "application/json",
                b"{}" + b"\0" * (1024 * 1024),
                ".json",
            )
        self.assertEqual("ARTIFACT_TOO_LARGE", performance.exception.code)

        with self.assertRaises(MobileAgentError) as bundle:
            self.store.write(
                ArtifactKind.DIAGNOSTIC_BUNDLE,
                "application/zip",
                b"PK" + b"\0" * (24 * 1024 * 1024),
                ".zip",
            )
        self.assertEqual("ARTIFACT_TOO_LARGE", bundle.exception.code)

    def test_write_accepts_artifact_at_kind_limit(self) -> None:
        at_limit = b"\x89PNG\r\n\x1a\n" + b"\0" * (8 * 1024 * 1024 - 8)
        artifact = self.store.write(
            ArtifactKind.SCREENSHOT, "image/png", at_limit, ".png"
        )

        self.assertEqual(len(at_limit), artifact.size_bytes)
        self.assertEqual(at_limit, self.store.screenshot_content(artifact.artifact_id))

    def test_screenshot_content_rejects_non_png_content(self) -> None:
        # 文件名由系统生成且扩展名固定为 .png，但内容仍重新校验签名，
        # 防止磁盘上被替换的文件经端点流出。
        artifact = self.store.write(
            ArtifactKind.SCREENSHOT, "image/png", b"\x89PNG\r\n\x1a\nbody", ".png"
        )
        path = self.store.resolve(artifact.relative_path)
        path.write_bytes(b"not-a-png")

        with self.assertRaises(MobileAgentError) as invalid:
            self.store.screenshot_content(artifact.artifact_id)
        self.assertEqual("ARTIFACT_INVALID", invalid.exception.code)


