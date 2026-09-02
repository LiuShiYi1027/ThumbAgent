"""REST management-surface tests for custom DSL skills (ITER-0062, ADR-0021).

覆盖：注册 confirmed 门、清单/版本/详情、启停、删除、审计序列、内置保护、
未知 id 404、严格未知字段、Bearer 鉴权与审计跨重启持久化。
"""

from __future__ import annotations

import re
import unittest
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from mobile_agent.api.server import RuntimeRequestHandler
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService
from mobile_agent.storage.skills import SQLiteCustomSkillStore, SQLiteSkillAuditStore

_TOKEN = "test-token"


def _document(skill_id: str = "custom.smoke_check", version: str = "1.0.0") -> dict:
    return {
        "schema_version": "1.0.0",
        "skill_id": skill_id,
        "skill_version": version,
        "name": "Smoke check",
        "description": "Open an app and press home.",
        "inputs": [
            {"name": "app_id", "type": "string", "required": True, "max_length": 128}
        ],
        "steps": [
            {
                "type": "tool",
                "step_id": "open",
                "tool_id": "app.launch",
                "arguments": {"app_id": "$inputs.app_id"},
            },
            {
                "type": "tool",
                "step_id": "home",
                "tool_id": "navigation.home",
                "arguments": {},
            },
        ],
    }


def _drive(
    runtime: RuntimeService,
    method: str,
    path: str,
    body: dict | None = None,
    *,
    token: str | None = _TOKEN,
    extra_headers: dict[str, str] | None = None,
) -> dict:
    handler = object.__new__(RuntimeRequestHandler)
    handler.path = path
    headers = Message()
    headers["Host"] = "127.0.0.1:8765"
    if body is not None:
        headers["Content-Type"] = "application/json"
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
    for name, value in (extra_headers or {}).items():
        headers[name] = value
    handler.headers = headers
    handler.server = SimpleNamespace(
        runtime=runtime,
        api_token=_TOKEN,
        allowed_origins=frozenset(),
        server_port=8765,
    )
    if body is not None:
        handler._read_json = lambda: body
    captured: dict[str, object] = {}
    handler._write_json = lambda status, payload: captured.update(
        {"status": status, "payload": payload}
    )
    getattr(handler, method)()
    return captured


class CustomSkillRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.runtime = RuntimeService(
            FakeDeviceAdapter(), ArtifactStore(Path(self.directory.name))
        )

    def _register(self, body: dict, **kwargs) -> dict:
        return _drive(self.runtime, "do_POST", "/v1/skills/custom", body, **kwargs)

    def test_register_requires_confirmation(self) -> None:
        captured = self._register({"document": _document()})
        self.assertEqual(HTTPStatus.FORBIDDEN, captured["status"])
        self.assertEqual(
            "CONFIRMATION_REQUIRED", captured["payload"]["error"]["code"]
        )
        # 未确认不得有任何持久化痕迹。
        listing = _drive(self.runtime, "do_GET", "/v1/skills/custom")
        self.assertEqual([], listing["payload"]["skills"])

    def test_register_persists_skill_summary(self) -> None:
        captured = self._register({"document": _document(), "confirmed": True})
        self.assertEqual(HTTPStatus.OK, captured["status"])
        skill = captured["payload"]["skill"]
        self.assertEqual("custom.smoke_check", skill["skill_id"])
        self.assertEqual("1.0.0", skill["skill_version"])
        self.assertEqual("low", skill["derived_risk"])
        self.assertTrue(skill["enabled"])
        self.assertEqual("rest", skill["source"])
        self.assertRegex(skill["document_sha256"], r"^[a-f0-9]{64}$")
        # 摘要不携带 DSL 原文。
        self.assertNotIn("document", skill)

    def test_register_rejects_invalid_document(self) -> None:
        document = _document()
        del document["skill_version"]
        captured = self._register({"document": document, "confirmed": True})
        self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])
        self.assertEqual("SKILL_DSL_INVALID", captured["payload"]["error"]["code"])

    def test_register_rejects_builtin_skill_id(self) -> None:
        captured = self._register(
            {"document": _document(skill_id="app.open"), "confirmed": True}
        )
        self.assertEqual(HTTPStatus.FORBIDDEN, captured["status"])
        self.assertEqual(
            "SKILL_BUILTIN_PROTECTED", captured["payload"]["error"]["code"]
        )

    def test_register_rejects_duplicate_version(self) -> None:
        first = self._register({"document": _document(), "confirmed": True})
        self.assertEqual(HTTPStatus.OK, first["status"])
        second = self._register({"document": _document(), "confirmed": True})
        self.assertEqual(HTTPStatus.CONFLICT, second["status"])
        self.assertEqual(
            "SKILL_VERSION_CONFLICT", second["payload"]["error"]["code"]
        )

    def test_register_rejects_unknown_body_fields(self) -> None:
        captured = self._register(
            {"document": _document(), "confirmed": True, "unexpected": 1}
        )
        self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])
        self.assertEqual("INVALID_ARGUMENT", captured["payload"]["error"]["code"])

    def test_register_requires_bearer_token(self) -> None:
        captured = self._register(
            {"document": _document(), "confirmed": True}, token=None
        )
        self.assertEqual(HTTPStatus.UNAUTHORIZED, captured["status"])
        self.assertEqual("UNAUTHORIZED", captured["payload"]["error"]["code"])


class CustomSkillQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.runtime = RuntimeService(
            FakeDeviceAdapter(), ArtifactStore(Path(self.directory.name))
        )
        for version in ("1.0.0", "1.1.0"):
            _drive(
                self.runtime,
                "do_POST",
                "/v1/skills/custom",
                {"document": _document(version=version), "confirmed": True},
            )

    def test_list_omits_document_source(self) -> None:
        captured = _drive(self.runtime, "do_GET", "/v1/skills/custom")
        self.assertEqual(HTTPStatus.OK, captured["status"])
        skills = captured["payload"]["skills"]
        self.assertEqual(2, len(skills))
        for skill in skills:
            self.assertNotIn("document", skill)
            self.assertIn("derived_risk", skill)
            self.assertIn("enabled", skill)
            self.assertIn("document_sha256", skill)

    def test_versions_listing(self) -> None:
        captured = _drive(
            self.runtime, "do_GET", "/v1/skills/custom/custom.smoke_check"
        )
        self.assertEqual(HTTPStatus.OK, captured["status"])
        payload = captured["payload"]
        self.assertEqual("custom.smoke_check", payload["skill_id"])
        self.assertEqual(
            ["1.0.0", "1.1.0"],
            [item["skill_version"] for item in payload["versions"]],
        )

    def test_version_detail_includes_document(self) -> None:
        captured = _drive(
            self.runtime,
            "do_GET",
            "/v1/skills/custom/custom.smoke_check/versions/1.1.0",
        )
        self.assertEqual(HTTPStatus.OK, captured["status"])
        skill = captured["payload"]["skill"]
        self.assertEqual(_document(version="1.1.0"), skill["document"])

    def test_unknown_skill_returns_not_found(self) -> None:
        for path in (
            "/v1/skills/custom/custom.missing",
            "/v1/skills/custom/custom.missing/versions/1.0.0",
            "/v1/skills/custom/custom.missing/audit",
        ):
            with self.subTest(path=path):
                captured = _drive(self.runtime, "do_GET", path)
                self.assertEqual(HTTPStatus.NOT_FOUND, captured["status"])
                self.assertEqual(
                    "SKILL_NOT_FOUND", captured["payload"]["error"]["code"]
                )

    def test_malformed_skill_id_falls_through_to_resource_not_found(self) -> None:
        captured = _drive(self.runtime, "do_GET", "/v1/skills/custom/INVALID")
        self.assertEqual(HTTPStatus.NOT_FOUND, captured["status"])
        self.assertEqual(
            "RESOURCE_NOT_FOUND", captured["payload"]["error"]["code"]
        )


class CustomSkillLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.runtime = RuntimeService(
            FakeDeviceAdapter(), ArtifactStore(Path(self.directory.name))
        )
        _drive(
            self.runtime,
            "do_POST",
            "/v1/skills/custom",
            {"document": _document(), "confirmed": True},
        )
        self.base = "/v1/skills/custom/custom.smoke_check/versions/1.0.0"

    def test_disable_enable_roundtrip(self) -> None:
        disabled = _drive(self.runtime, "do_POST", f"{self.base}/disable", {})
        self.assertEqual(HTTPStatus.OK, disabled["status"])
        self.assertFalse(disabled["payload"]["skill"]["enabled"])
        enabled = _drive(self.runtime, "do_POST", f"{self.base}/enable", {})
        self.assertEqual(HTTPStatus.OK, enabled["status"])
        self.assertTrue(enabled["payload"]["skill"]["enabled"])

    def test_toggle_rejects_non_empty_body(self) -> None:
        for action in ("enable", "disable"):
            with self.subTest(action=action):
                captured = _drive(
                    self.runtime,
                    "do_POST",
                    f"{self.base}/{action}",
                    {"confirmed": True},
                )
                self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])
                self.assertEqual(
                    "INVALID_ARGUMENT", captured["payload"]["error"]["code"]
                )

    def test_toggle_unknown_version_returns_not_found(self) -> None:
        captured = _drive(
            self.runtime,
            "do_POST",
            "/v1/skills/custom/custom.smoke_check/versions/9.9.9/disable",
            {},
        )
        self.assertEqual(HTTPStatus.NOT_FOUND, captured["status"])
        self.assertEqual("SKILL_NOT_FOUND", captured["payload"]["error"]["code"])

    def test_delete_requires_confirmation(self) -> None:
        captured = _drive(self.runtime, "do_POST", f"{self.base}/delete", {})
        self.assertEqual(HTTPStatus.FORBIDDEN, captured["status"])
        self.assertEqual(
            "CONFIRMATION_REQUIRED", captured["payload"]["error"]["code"]
        )
        # 未确认时版本仍在。
        detail = _drive(self.runtime, "do_GET", self.base)
        self.assertEqual(HTTPStatus.OK, detail["status"])

    def test_delete_removes_version_but_keeps_audit(self) -> None:
        deleted = _drive(
            self.runtime, "do_POST", f"{self.base}/delete", {"confirmed": True}
        )
        self.assertEqual(HTTPStatus.OK, deleted["status"])
        self.assertTrue(deleted["payload"]["deleted"])
        detail = _drive(self.runtime, "do_GET", self.base)
        self.assertEqual(HTTPStatus.NOT_FOUND, detail["status"])
        audit = _drive(
            self.runtime, "do_GET", "/v1/skills/custom/custom.smoke_check/audit"
        )
        self.assertEqual(HTTPStatus.OK, audit["status"])
        self.assertEqual(
            ["skill.registered", "skill.deleted"],
            [event["event_type"] for event in audit["payload"]["audit"]],
        )

    def test_delete_unknown_version_returns_not_found(self) -> None:
        captured = _drive(
            self.runtime,
            "do_POST",
            "/v1/skills/custom/custom.smoke_check/versions/9.9.9/delete",
            {"confirmed": True},
        )
        self.assertEqual(HTTPStatus.NOT_FOUND, captured["status"])
        self.assertEqual("SKILL_NOT_FOUND", captured["payload"]["error"]["code"])

    def test_audit_sequence_records_lifecycle(self) -> None:
        _drive(self.runtime, "do_POST", f"{self.base}/disable", {})
        _drive(self.runtime, "do_POST", f"{self.base}/enable", {})
        _drive(self.runtime, "do_POST", f"{self.base}/delete", {"confirmed": True})
        captured = _drive(
            self.runtime, "do_GET", "/v1/skills/custom/custom.smoke_check/audit"
        )
        self.assertEqual(HTTPStatus.OK, captured["status"])
        events = captured["payload"]["audit"]
        self.assertEqual(
            [
                "skill.registered",
                "skill.disabled",
                "skill.enabled",
                "skill.deleted",
            ],
            [event["event_type"] for event in events],
        )
        self.assertEqual(
            [1, 2, 3, 4], [event["id"] for event in events]
        )
        for event in events:
            self.assertRegex(event["document_sha256"], r"^[a-f0-9]{64}$")
            # 审计 payload 只携带摘要，绝不包含 DSL 原文。
            self.assertNotIn("steps", event["payload"])
            self.assertNotIn("document", event["payload"])


class CustomSkillAuditPersistenceTests(unittest.TestCase):
    def test_audit_and_registry_survive_runtime_restart(self) -> None:
        with TemporaryDirectory() as directory:
            artifacts = ArtifactStore(Path(directory))
            first = RuntimeService(FakeDeviceAdapter(), artifacts)
            _drive(
                first,
                "do_POST",
                "/v1/skills/custom",
                {"document": _document(), "confirmed": True},
            )
            database = Path(directory) / "custom-skills.db"
            # 同一数据库重新装配（模拟重启后的 RuntimeService）。
            second = RuntimeService(
                FakeDeviceAdapter(),
                ArtifactStore(Path(directory)),
                custom_skill_store=SQLiteCustomSkillStore(database),
                skill_audit_store=SQLiteSkillAuditStore(database),
            )
            listing = _drive(second, "do_GET", "/v1/skills/custom")
            self.assertEqual(1, len(listing["payload"]["skills"]))
            audit = _drive(
                second, "do_GET", "/v1/skills/custom/custom.smoke_check/audit"
            )
            self.assertEqual(HTTPStatus.OK, audit["status"])
            self.assertEqual(
                ["skill.registered"],
                [event["event_type"] for event in audit["payload"]["audit"]],
            )


if __name__ == "__main__":
    unittest.main()
