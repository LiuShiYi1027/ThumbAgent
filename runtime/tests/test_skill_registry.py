"""Tests for the custom skill registry (ITER-0062, ADR-0021)."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.skills.registry import (
    CustomSkillRegistry,
    builtin_skill_ids,
)
from mobile_agent.storage.skills import SQLiteCustomSkillStore
from mobile_agent.storage.sqlite import migrate_database


def _low_risk_document() -> dict:
    return {
        "schema_version": "1.0.0",
        "skill_id": "app.stability_test",
        "skill_version": "1.0.0",
        "name": "Stability smoke",
        "description": "Deterministic traversal within a time box.",
        "timeout_seconds": 300,
        "inputs": [
            {"name": "app_id", "type": "string", "required": True, "max_length": 128},
        ],
        "steps": [
            {
                "type": "tool",
                "step_id": "open",
                "tool_id": "app.launch",
                "arguments": {"app_id": "$inputs.app_id"},
            },
            {
                "type": "loop",
                "step_id": "traverse",
                "max_duration_seconds": 120,
                "max_iterations": 10,
                "steps": [
                    {
                        "type": "tool",
                        "step_id": "go_home",
                        "tool_id": "navigation.home",
                        "arguments": {},
                    },
                ],
            },
        ],
    }


def _high_risk_document() -> dict:
    document = _low_risk_document()
    document["skill_id"] = "app.risky_install"
    document["steps"] = [
        {
            "type": "tool",
            "step_id": "sideload",
            "tool_id": "app.install",
            "arguments": {"app_id": "$inputs.app_id"},
        }
    ]
    return document


class SkillRegistryMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "mobile-agent.db"

    def test_migration_creates_custom_skills_table(self) -> None:
        migrate_database(self.database)
        with sqlite3.connect(self.database) as connection:
            columns = connection.execute(
                "SELECT name FROM pragma_table_info('custom_skills')"
            ).fetchall()
        self.assertEqual(
            [
                "skill_id",
                "skill_version",
                "document_json",
                "document_sha256",
                "derived_risk",
                "enabled",
                "source",
                "created_at",
                "updated_at",
            ],
            [str(row[0]) for row in columns],
        )

    def test_migration_is_idempotent(self) -> None:
        migrate_database(self.database)
        migrate_database(self.database)
        with sqlite3.connect(self.database) as connection:
            revisions = connection.execute(
                "SELECT revision FROM schema_migrations ORDER BY revision"
            ).fetchall()
        self.assertEqual(
            [
                "0001_task_store",
                "0002_task_executions",
                "0003_custom_skills",
                "0004_skill_audit",
            ],
            [str(row[0]) for row in revisions],
        )


class CustomSkillRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "mobile-agent.db"
        self.audit_events: list[tuple[str, dict]] = []
        self.registry = CustomSkillRegistry(
            SQLiteCustomSkillStore(self.database),
            emit_audit=self._record_audit,
        )

    def _record_audit(self, event: str, payload: dict) -> None:
        self.audit_events.append((event, payload))

    def test_register_roundtrip_derives_and_persists_risk(self) -> None:
        record = self.registry.register(_low_risk_document(), source="cli")

        self.assertEqual("app.stability_test", record.skill_id)
        self.assertEqual("1.0.0", record.skill_version)
        self.assertEqual("low", record.derived_risk.value)
        self.assertTrue(record.enabled)
        self.assertEqual("cli", record.source)
        self.assertEqual(64, len(record.document_sha256))
        self.assertTrue(record.created_at.endswith("Z"))

        fetched = self.registry.get("app.stability_test", "1.0.0")
        self.assertEqual(record, fetched)
        self.assertEqual("open", fetched.document.steps[0].step_id)

    def test_register_derives_high_risk_from_tools_not_document(self) -> None:
        record = self.registry.register(_high_risk_document(), source="cli")
        self.assertEqual("high", record.derived_risk.value)
        stored = self.registry.get("app.risky_install", "1.0.0")
        self.assertEqual("high", stored.derived_risk.value)

    def test_version_is_immutable(self) -> None:
        self.registry.register(_low_risk_document(), source="cli")
        with self.assertRaises(MobileAgentError) as caught:
            self.registry.register(_low_risk_document(), source="cli")
        self.assertEqual("SKILL_VERSION_CONFLICT", caught.exception.code)
        self.assertEqual("validation", caught.exception.category.value)

    def test_builtin_skill_id_is_protected(self) -> None:
        self.assertIn("app.open", builtin_skill_ids())
        payload = _low_risk_document()
        payload["skill_id"] = "app.open"
        with self.assertRaises(MobileAgentError) as caught:
            self.registry.register(payload, source="cli")
        self.assertEqual("SKILL_BUILTIN_PROTECTED", caught.exception.code)

    def test_get_without_version_returns_latest_semver(self) -> None:
        self.registry.register(_low_risk_document(), source="cli")
        newer = _low_risk_document()
        newer["skill_version"] = "1.10.0"
        self.registry.register(newer, source="cli")
        middle = _low_risk_document()
        middle["skill_version"] = "1.9.0"
        self.registry.register(middle, source="cli")

        latest = self.registry.get("app.stability_test")
        self.assertEqual("1.10.0", latest.skill_version)
        self.assertEqual(
            {"1.0.0", "1.9.0", "1.10.0"},
            {record.skill_version for record in self.registry.list()},
        )

    def test_enabled_state_persists_across_connections(self) -> None:
        self.registry.register(_low_risk_document(), source="cli")
        disabled = self.registry.set_enabled("app.stability_test", "1.0.0", False)
        self.assertFalse(disabled.enabled)

        reopened = CustomSkillRegistry(SQLiteCustomSkillStore(self.database))
        fetched = reopened.get("app.stability_test", "1.0.0")
        self.assertFalse(fetched.enabled)

        enabled = reopened.set_enabled("app.stability_test", "1.0.0", True)
        self.assertTrue(enabled.enabled)

    def test_audit_events_carry_digest_not_document(self) -> None:
        self.registry.register(_low_risk_document(), source="cli")
        self.registry.set_enabled("app.stability_test", "1.0.0", False)
        self.registry.set_enabled("app.stability_test", "1.0.0", True)
        self.registry.delete("app.stability_test", "1.0.0")

        self.assertEqual(
            ["skill.registered", "skill.disabled", "skill.enabled", "skill.deleted"],
            [event for event, _ in self.audit_events],
        )
        for _, payload in self.audit_events:
            self.assertIn("document_sha256", payload)
            self.assertEqual(64, len(payload["document_sha256"]))
            self.assertNotIn("document_json", payload)
            self.assertNotIn("steps", payload)
            self.assertNotIn("document", payload)

    def test_delete_then_get_raises_not_found(self) -> None:
        self.registry.register(_low_risk_document(), source="cli")
        self.registry.delete("app.stability_test", "1.0.0")
        with self.assertRaises(MobileAgentError) as caught:
            self.registry.get("app.stability_test", "1.0.0")
        self.assertEqual("SKILL_NOT_FOUND", caught.exception.code)
        with self.assertRaises(MobileAgentError) as caught_latest:
            self.registry.get("app.stability_test")
        self.assertEqual("SKILL_NOT_FOUND", caught_latest.exception.code)

    def test_missing_skill_mutations_raise_not_found(self) -> None:
        with self.assertRaises(MobileAgentError) as caught:
            self.registry.set_enabled("app.ghost", "1.0.0", False)
        self.assertEqual("SKILL_NOT_FOUND", caught.exception.code)
        with self.assertRaises(MobileAgentError) as caught_delete:
            self.registry.delete("app.ghost", "1.0.0")
        self.assertEqual("SKILL_NOT_FOUND", caught_delete.exception.code)


if __name__ == "__main__":
    unittest.main()
