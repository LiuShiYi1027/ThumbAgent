"""Contract tests for device.logs.collect crash_check (ITER-0065).

覆盖兼容性新增的全流程：Schema 真源结构断言、Python 生产端序列化、
生成 TypeScript 同步，以及签名提取只在脱敏文本上进行的负向约束。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from mobile_agent.domain.artifact import Artifact, ArtifactKind
from mobile_agent.domain.device_log import DeviceLogCaptureResult, DeviceLogLevel
from mobile_agent.evidence.log_redaction import (
    MAX_CRASH_SIGNATURES,
    MAX_CRASH_SUMMARY_LENGTH,
    redact_device_log,
    scan_crash_signatures,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "contracts" / "schemas"


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text())


def _result(crash_check: dict | None) -> DeviceLogCaptureResult:
    artifact = Artifact(
        artifact_id="artifact_" + "0" * 32,
        kind=ArtifactKind.DEVICE_LOG,
        content_type="text/plain",
        relative_path="device_log/sample.log",
        size_bytes=16,
        sha256="0" * 64,
        created_at="2026-09-08T00:00:00Z",
    )
    kwargs = {} if crash_check is None else {"crash_check": crash_check}
    return DeviceLogCaptureResult(
        skill_call_id="skillcall_" + "0" * 32,
        device_id="fake:android-001",
        minimum_level=DeviceLogLevel.INFO,
        requested_max_lines=100,
        captured_bytes=16,
        truncated=False,
        redaction_count=0,
        artifact=artifact,
        started_at="2026-09-08T00:00:00Z",
        completed_at="2026-09-08T00:00:01Z",
        **kwargs,
    )


class DeviceLogCrashCheckSchemaTest(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = _load_schema("device-log-capture-result.schema.json")

    def test_crash_check_is_optional_compatibility_addition(self) -> None:
        self.assertIn("crash_check", self.schema["properties"])
        self.assertNotIn("crash_check", self.schema["required"])

    def test_crash_check_shape_bounds_payload(self) -> None:
        crash_check = self.schema["properties"]["crash_check"]
        self.assertEqual("object", crash_check["type"])
        self.assertFalse(crash_check["additionalProperties"])
        self.assertEqual({"checked_lines", "signatures"}, set(crash_check["required"]))

        checked_lines = crash_check["properties"]["checked_lines"]
        self.assertEqual("integer", checked_lines["type"])
        self.assertEqual(0, checked_lines["minimum"])

        signatures = crash_check["properties"]["signatures"]
        self.assertEqual("array", signatures["type"])
        self.assertEqual(MAX_CRASH_SIGNATURES, signatures["maxItems"])

        item = signatures["items"]
        self.assertFalse(item["additionalProperties"])
        self.assertEqual({"kind", "summary"}, set(item["required"]))
        self.assertEqual(["crash", "anr"], item["properties"]["kind"]["enum"])
        self.assertEqual(
            MAX_CRASH_SUMMARY_LENGTH, item["properties"]["summary"]["maxLength"]
        )

    def test_generated_typescript_in_sync(self) -> None:
        generated = (
            ROOT / "contracts" / "generated" / "typescript"
        ) / "device-log-capture-result.ts"
        text = generated.read_text()

        self.assertIn("crash_check", text)
        self.assertIn('"crash" | "anr"', text)


class DeviceLogCrashCheckPythonParityTest(unittest.TestCase):
    """Python 生产端与 Schema 的正向/反向样本。"""

    def test_result_omits_crash_check_when_absent(self) -> None:
        payload = _result(None).to_dict()

        self.assertNotIn("crash_check", payload)
        self.assertNotIn("crash_check", self._required())

    def test_result_serializes_crash_check_within_schema_bounds(self) -> None:
        crash_check = {
            "checked_lines": 3,
            "signatures": [
                {"kind": "crash", "summary": "FATAL EXCEPTION: main"},
                {"kind": "anr", "summary": "ANR in com.example.app"},
            ],
        }

        payload = _result(crash_check).to_dict()

        self.assertEqual(crash_check, payload["crash_check"])
        item_schema = self._signature_item_schema()
        for signature in payload["crash_check"]["signatures"]:
            self.assertIn(
                signature["kind"], item_schema["properties"]["kind"]["enum"]
            )
            self.assertLessEqual(
                len(signature["summary"]),
                item_schema["properties"]["summary"]["maxLength"],
            )

    def test_invalid_signature_kind_is_not_produced(self) -> None:
        redacted, _ = redact_device_log(b"E AndroidRuntime: FATAL EXCEPTION: main\n")

        crash_check = scan_crash_signatures(redacted.decode("utf-8"))

        kinds = {signature["kind"] for signature in crash_check["signatures"]}
        self.assertLessEqual(kinds, {"crash", "anr"})

    def _required(self) -> list[str]:
        return _load_schema("device-log-capture-result.schema.json")["required"]

    def _signature_item_schema(self) -> dict:
        schema = _load_schema("device-log-capture-result.schema.json")
        return schema["properties"]["crash_check"]["properties"]["signatures"]["items"]


class CrashSignatureExtractionTest(unittest.TestCase):
    """签名提取只消费脱敏文本，且缺省时仍返回空 signatures。"""

    def test_no_signature_lines_yield_empty_signatures(self) -> None:
        crash_check = scan_crash_signatures("I MobileAgent: ready\nI MobileAgent: ok\n")

        self.assertEqual([], crash_check["signatures"])
        self.assertEqual(2, crash_check["checked_lines"])

    def test_summary_carries_redacted_line_not_raw_log(self) -> None:
        raw = (
            b"E AndroidRuntime: FATAL EXCEPTION: main (contact user@example.com)\n"
        )
        redacted, redaction_count = redact_device_log(raw)

        crash_check = scan_crash_signatures(redacted.decode("utf-8"))

        self.assertEqual(1, redaction_count)
        summary = crash_check["signatures"][0]["summary"]
        self.assertIn("[REDACTED_EMAIL]", summary)
        self.assertNotIn("user@example.com", summary)

    def test_summary_is_truncated_to_schema_bound(self) -> None:
        line = "E AndroidRuntime: FATAL EXCEPTION: main " + "x" * 200

        crash_check = scan_crash_signatures(line)

        self.assertEqual(
            MAX_CRASH_SUMMARY_LENGTH, len(crash_check["signatures"][0]["summary"])
        )

    def test_signatures_are_capped_at_schema_bound(self) -> None:
        text = "\n".join(["FATAL EXCEPTION: main"] * (MAX_CRASH_SIGNATURES + 5))

        crash_check = scan_crash_signatures(text)

        self.assertEqual(MAX_CRASH_SIGNATURES, len(crash_check["signatures"]))
        self.assertEqual(MAX_CRASH_SIGNATURES + 5, crash_check["checked_lines"])


if __name__ == "__main__":
    unittest.main()
