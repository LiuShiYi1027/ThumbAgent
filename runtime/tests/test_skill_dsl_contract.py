"""Contract tests for the declarative skill DSL (ITER-0062, ADR-0021).

Schema 真源结构断言 + Python 解析层与 Schema 边界的一致性（正向/反向样本）。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.domain.skill_dsl import (
    IfStep,
    LoopStep,
    SkillStep,
    ToolStep,
    parse_skill_dsl_document,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "contracts" / "schemas"


def _load_schema() -> dict:
    return json.loads((SCHEMAS / "skill-dsl.schema.json").read_text())


def _valid_document() -> dict:
    return {
        "schema_version": "1.0.0",
        "skill_id": "app.stability_test",
        "skill_version": "1.0.0",
        "name": "Stability smoke",
        "description": "Deterministic traversal within a time box.",
        "timeout_seconds": 300,
        "inputs": [
            {"name": "app_id", "type": "string", "required": True, "max_length": 128},
            {"name": "rounds", "type": "integer", "minimum": 1, "maximum": 20},
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
                        "step_id": "swipe_up",
                        "tool_id": "input.swipe",
                        "arguments": {"direction": "up"},
                    },
                    {
                        "type": "tool",
                        "step_id": "snap",
                        "tool_id": "device.performance.capture",
                        "arguments": {"app_id": "$inputs.app_id"},
                    },
                ],
            },
            {
                "type": "if",
                "step_id": "on_open_failed",
                "condition": {"step": "open", "field": "status", "equals": "failed"},
                "then": [
                    {
                        "type": "tool",
                        "step_id": "go_home",
                        "tool_id": "navigation.home",
                        "arguments": {},
                    }
                ],
            },
        ],
    }


class SkillDslContractSchemaTests(unittest.TestCase):
    def test_schema_declares_control_flow_and_reference_kinds(self) -> None:
        schema = _load_schema()
        defs = schema["$defs"]
        self.assertEqual({"tool_step", "skill_step", "loop_step", "if_step"}, set(defs))
        items = schema["properties"]["steps"]["items"]
        self.assertEqual(4, len(items["oneOf"]))

    def test_skill_step_shape(self) -> None:
        skill_step = _load_schema()["$defs"]["skill_step"]
        self.assertEqual("skill", skill_step["properties"]["type"]["const"])
        self.assertEqual(
            {"type", "step_id", "skill_id", "arguments"}, set(skill_step["required"])
        )
        self.assertFalse(skill_step["additionalProperties"])

    def test_loop_requires_dual_bounds(self) -> None:
        loop = _load_schema()["$defs"]["loop_step"]
        self.assertEqual(
            {"type", "step_id", "max_duration_seconds", "max_iterations", "steps"},
            set(loop["required"]),
        )
        self.assertEqual(600, loop["properties"]["max_duration_seconds"]["maximum"])
        self.assertEqual(200, loop["properties"]["max_iterations"]["maximum"])

    def test_control_bodies_contain_action_steps_only(self) -> None:
        defs = _load_schema()["$defs"]
        allowed = {"#/$defs/tool_step", "#/$defs/skill_step"}
        for holder, key in (
            (defs["loop_step"], "steps"),
            (defs["if_step"], "then"),
            (defs["if_step"], "else"),
        ):
            members = {
                entry["$ref"]
                for entry in holder["properties"][key]["items"]["oneOf"]
            }
            self.assertEqual(allowed, members)

    def test_condition_is_status_only(self) -> None:
        condition = _load_schema()["$defs"]["if_step"]["properties"]["condition"]
        self.assertEqual("status", condition["properties"]["field"]["const"])
        self.assertEqual(
            ["succeeded", "failed"],
            condition["properties"]["equals"]["enum"],
        )
        self.assertFalse(condition["additionalProperties"])

    def test_generated_typescript_in_sync(self) -> None:
        generated = ROOT / "contracts" / "generated" / "typescript" / "skill-dsl.ts"
        content = generated.read_text()
        for marker in ("ToolStep", "LoopStep", "IfStep", "SkillDsl"):
            self.assertIn(marker, content)


class SkillStepContractTests(unittest.TestCase):
    def test_skill_step_parses_and_resolves_refs(self) -> None:
        payload = _valid_document()
        payload["steps"].insert(
            1,
            {
                "type": "skill",
                "step_id": "sample",
                "skill_id": "device.performance.snapshot",
                "arguments": {"app_id": "$inputs.app_id"},
            },
        )
        document = parse_skill_dsl_document(payload)
        step = document.steps[1]
        self.assertIsInstance(step, SkillStep)
        self.assertEqual("device.performance.snapshot", step.skill_id)

    def test_loop_body_accepts_skill_steps_but_not_control_flow(self) -> None:
        payload = _valid_document()
        payload["steps"][1]["steps"].append(
            {
                "type": "skill",
                "step_id": "loop_sample",
                "skill_id": "device.logs.collect",
                "arguments": {},
            }
        )
        document = parse_skill_dsl_document(payload)
        loop = document.steps[1]
        self.assertIsInstance(loop.steps[-1], SkillStep)

    def test_skill_step_rejects_bad_skill_id(self) -> None:
        payload = _valid_document()
        payload["steps"].append(
            {
                "type": "skill",
                "step_id": "bad",
                "skill_id": "not-a-skill",
                "arguments": {},
            }
        )
        with self.assertRaises(MobileAgentError) as raised:
            parse_skill_dsl_document(payload)
        self.assertEqual("skill_id", raised.exception.details["field"])

    def test_non_whitelisted_skill_reference_rejected_at_derivation(self) -> None:
        from mobile_agent.skills.dsl_risk import derive_skill_risk

        for skill_id in (
            "app.install",  # 写类内置 Skill 不在白名单
            "custom.whatever",  # 自定义 Skill 不可引用
        ):
            payload = _valid_document()
            payload["steps"].append(
                {
                    "type": "skill",
                    "step_id": "ref",
                    "skill_id": skill_id,
                    "arguments": {},
                }
            )
            document = parse_skill_dsl_document(payload)
            with self.assertRaises(MobileAgentError, msg=skill_id) as raised:
                derive_skill_risk(document)
            self.assertEqual("SKILL_REFERENCE_NOT_ALLOWED", raised.exception.code)

    def test_whitelisted_skill_reference_derives_medium_risk(self) -> None:
        from mobile_agent.skills.dsl_risk import derive_skill_risk

        payload = _valid_document()
        payload["steps"] = [
            {
                "type": "skill",
                "step_id": "sample",
                "skill_id": "device.performance.snapshot",
                "arguments": {"app_id": "$inputs.app_id"},
            }
        ]
        document = parse_skill_dsl_document(payload)
        self.assertEqual("medium", derive_skill_risk(document).value)


class SkillDslParserTests(unittest.TestCase):
    def test_valid_document_parses_all_step_kinds(self) -> None:
        document = parse_skill_dsl_document(_valid_document())

        self.assertEqual("app.stability_test", document.skill_id)
        tool, loop, branch = document.steps
        self.assertIsInstance(tool, ToolStep)
        self.assertIsInstance(loop, LoopStep)
        self.assertIsInstance(branch, IfStep)
        self.assertEqual("$inputs.app_id", tool.arguments["app_id"])
        self.assertEqual(("swipe_up", "snap"), tuple(s.step_id for s in loop.steps))
        self.assertEqual("open", branch.condition_step)
        self.assertEqual((), branch.else_steps)

    def test_rejects_wrong_schema_version(self) -> None:
        payload = _valid_document()
        payload["schema_version"] = "2.0.0"
        with self.assertRaises(MobileAgentError) as raised:
            parse_skill_dsl_document(payload)
        self.assertEqual("SKILL_DSL_INVALID", raised.exception.code)
        self.assertEqual("schema_version", raised.exception.details["field"])

    def test_rejects_nested_control_flow_in_loop_body(self) -> None:
        payload = _valid_document()
        payload["steps"][1]["steps"].append(
            {
                "type": "loop",
                "step_id": "nested",
                "max_duration_seconds": 10,
                "max_iterations": 2,
                "steps": [
                    {
                        "type": "tool",
                        "step_id": "inner",
                        "tool_id": "navigation.back",
                        "arguments": {},
                    }
                ],
            }
        )
        with self.assertRaises(MobileAgentError) as raised:
            parse_skill_dsl_document(payload)
        self.assertEqual("SKILL_DSL_INVALID", raised.exception.code)

    def test_rejects_loop_beyond_bounds(self) -> None:
        for field, value in (
            ("max_duration_seconds", 601),
            ("max_iterations", 201),
            ("max_iterations", 0),
        ):
            payload = _valid_document()
            payload["steps"][1][field] = value
            with self.assertRaises(MobileAgentError, msg=field):
                parse_skill_dsl_document(payload)

    def test_rejects_arbitrary_condition_field(self) -> None:
        payload = _valid_document()
        payload["steps"][2]["condition"]["field"] = "result_text"
        with self.assertRaises(MobileAgentError) as raised:
            parse_skill_dsl_document(payload)
        self.assertEqual("condition.field", raised.exception.details["field"])

    def test_rejects_condition_referencing_future_step(self) -> None:
        payload = _valid_document()
        payload["steps"][2]["condition"]["step"] = "snap"
        with self.assertRaises(MobileAgentError, msg="loop body step is not a prior top-level step"):
            parse_skill_dsl_document(payload)
        payload = _valid_document()
        payload["steps"][2]["condition"]["step"] = "on_open_failed"
        with self.assertRaises(MobileAgentError, msg="self reference"):
            parse_skill_dsl_document(payload)

    def test_rejects_duplicate_step_and_input_names(self) -> None:
        payload = _valid_document()
        payload["steps"][1]["step_id"] = "open"
        with self.assertRaises(MobileAgentError, msg="duplicate step_id"):
            parse_skill_dsl_document(payload)
        payload = _valid_document()
        payload["inputs"].append({"name": "app_id", "type": "string"})
        with self.assertRaises(MobileAgentError, msg="duplicate input"):
            parse_skill_dsl_document(payload)

    def test_rejects_non_literal_argument_values(self) -> None:
        payload = _valid_document()
        payload["steps"][0]["arguments"]["app_id"] = ["$inputs.app_id"]
        with self.assertRaises(MobileAgentError, msg="array argument"):
            parse_skill_dsl_document(payload)
        payload["steps"][0]["arguments"]["app_id"] = None
        with self.assertRaises(MobileAgentError, msg="null argument"):
            parse_skill_dsl_document(payload)

    def test_rejects_too_many_steps(self) -> None:
        payload = _valid_document()
        payload["steps"] = [
            {
                "type": "tool",
                "step_id": f"s{i}",
                "tool_id": "navigation.back",
                "arguments": {},
            }
            for i in range(33)
        ]
        with self.assertRaises(MobileAgentError):
            parse_skill_dsl_document(payload)


if __name__ == "__main__":
    unittest.main()
