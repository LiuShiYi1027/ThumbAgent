"""Integration tests for the shipped app.stability_test DSL document (ITER-0062).

文档真源（skills/dsl_documents/app.stability_test.json）经
parse_skill_dsl_document 解析，并在 FakeDeviceAdapter + ToolRuntime 真实
装配上由 run_dsl_skill 完整执行：断言步骤序列、派生风险 MEDIUM、循环双上限
与 DslSkillResult 形状。device.performance.capture（direct_invocation=false）
在 DSL 步骤中被 TOOL_REQUIRES_SKILL 阻断，用负向用例钉死该取舍（ADR-0021）。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.action import RiskLevel
from mobile_agent.domain.skill_dsl import (
    LoopStep,
    SkillDslDocument,
    ToolStep,
    parse_skill_dsl_document,
)
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.skills.dsl_interpreter import run_dsl_skill
from mobile_agent.tools.runtime import ToolRegistry, ToolRuntime

DOCUMENT_PATH = (
    Path(__file__).resolve().parents[1]
    / "mobile_agent"
    / "skills"
    / "dsl_documents"
    / "app.stability_test.json"
)
DEVICE_ID = "fake:android-001"
TARGET_APP = "com.example.fake"


def _load_document() -> SkillDslDocument:
    return parse_skill_dsl_document(json.loads(DOCUMENT_PATH.read_text()))


def _full_inputs() -> dict:
    return {"app_id": TARGET_APP, "duration_seconds": 600, "max_actions": 200}


class StabilityTestDslTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.adapter = FakeDeviceAdapter()
        self.runtime = ToolRuntime(
            self.adapter,
            ArtifactStore(Path(self.directory.name)),
            ToolRegistry(),
            PolicyEngine(),
        )
        self.document = _load_document()

    async def _run(self, inputs: dict, confirmed: bool = True):
        return await run_dsl_skill(
            self.document,
            device_id=DEVICE_ID,
            inputs=inputs,
            confirmed=confirmed,
            tools=self.runtime,
        )

    # ---- 文档形状：解析器真源断言 ----

    def test_document_shape_matches_contract(self) -> None:
        document = self.document
        self.assertEqual("app.stability_test", document.skill_id)
        self.assertEqual("1.0.0", document.skill_version)
        self.assertTrue(document.name)
        self.assertTrue(document.description)
        self.assertEqual(900, document.timeout_seconds)

        inputs = {item.name: item for item in document.inputs}
        self.assertEqual({"app_id", "duration_seconds", "max_actions"}, set(inputs))
        self.assertEqual("string", inputs["app_id"].type)
        self.assertTrue(inputs["app_id"].required)
        self.assertEqual("integer", inputs["duration_seconds"].type)
        self.assertFalse(inputs["duration_seconds"].required)
        self.assertEqual((1.0, 600.0), (
            inputs["duration_seconds"].minimum,
            inputs["duration_seconds"].maximum,
        ))
        self.assertEqual("integer", inputs["max_actions"].type)
        self.assertFalse(inputs["max_actions"].required)
        self.assertEqual((1.0, 200.0), (
            inputs["max_actions"].minimum,
            inputs["max_actions"].maximum,
        ))

        launch, loop, relaunch = document.steps
        self.assertIsInstance(launch, ToolStep)
        self.assertIsInstance(loop, LoopStep)
        self.assertIsInstance(relaunch, ToolStep)
        self.assertEqual(
            ("launch_target_app", "stress_traverse", "relaunch_target_app"),
            (launch.step_id, loop.step_id, relaunch.step_id),
        )
        self.assertEqual(
            {"app_id": "$inputs.app_id"}, launch.arguments
        )
        self.assertEqual(launch.arguments, relaunch.arguments)
        # 循环双上限：文档内常量即绝对天花板（600 秒 / 200 次）。
        self.assertEqual(600, loop.max_duration_seconds)
        self.assertEqual(200, loop.max_iterations)
        self.assertEqual(
            ["swipe_up", "swipe_down", "navigate_back"],
            [step.step_id for step in loop.steps],
        )
        self.assertEqual(
            ["input.swipe", "input.swipe", "navigation.back"],
            [step.tool_id for step in loop.steps],
        )
        # arguments 只允许字面量与 $inputs 引用（解析器已强制，此处钉死文档内容）。
        self.assertEqual({"direction": "up"}, loop.steps[0].arguments)
        self.assertEqual({"direction": "down"}, loop.steps[1].arguments)
        self.assertEqual({}, loop.steps[2].arguments)

    # ---- 派生风险与 preflight ----

    async def test_derived_risk_is_medium_and_requires_confirmation(self) -> None:
        result = await self._run(_full_inputs(), confirmed=False)

        self.assertEqual("failed", result.status)
        self.assertEqual((), result.step_records)
        self.assertEqual(RiskLevel.MEDIUM, result.derived_risk)
        self.assertIsNotNone(result.error)
        self.assertEqual("CONFIRMATION_REQUIRED", result.error.code)
        # preflight 失败发生在任何设备动作之前。
        self.assertEqual([], self.adapter.actions)

    async def test_input_declaration_bounds_enforced(self) -> None:
        for bad_inputs in (
            {"duration_seconds": 0},
            {"duration_seconds": 601},
            {"max_actions": 0},
            {"max_actions": 201},
            {"app_id": 1},
        ):
            with self.subTest(bad_inputs=bad_inputs):
                inputs = {**_full_inputs(), **bad_inputs}
                result = await self._run(inputs)
                self.assertEqual("failed", result.status)
                self.assertIsNotNone(result.error)
                self.assertEqual("SKILL_INPUT_INVALID", result.error.code)
                self.assertEqual([], self.adapter.actions)

        missing = _full_inputs()
        del missing["app_id"]
        result = await self._run(missing)
        self.assertEqual("SKILL_INPUT_INVALID", result.error.code)

    # ---- 真实执行：步骤序列 / 循环上限 / 结果形状 ----

    async def test_full_run_succeeds_with_expected_step_sequence(self) -> None:
        result = await self._run(_full_inputs())

        self.assertEqual("succeeded", result.status)
        self.assertIsNone(result.error)
        self.assertEqual(RiskLevel.MEDIUM, result.derived_risk)

        # 设备动作序列：launch → 200 × (swipe_up, swipe_down, back) → relaunch。
        actions = self.adapter.actions
        self.assertEqual(2 + 200 * 3, len(actions))
        self.assertEqual(("app.launch", DEVICE_ID, TARGET_APP), actions[0])
        self.assertEqual(("app.launch", DEVICE_ID, TARGET_APP), actions[-1])
        body_names = [action[0] for action in actions[1:-1]]
        self.assertEqual(
            ["input.swipe", "input.swipe", "navigation.back"] * 200, body_names
        )

        # 结果形状：600 条循环体记录 + 1 条 loop 容器记录 + 2 条 launch 记录。
        records = result.step_records
        self.assertEqual(603, len(records))
        self.assertTrue(all(record.status == "succeeded" for record in records))
        self.assertTrue(all(record.error_code is None for record in records))
        counts: dict[str, int] = {}
        for record in records:
            counts[record.step_id] = counts.get(record.step_id, 0) + 1
        self.assertEqual(
            {
                "launch_target_app": 1,
                "swipe_up": 200,
                "swipe_down": 200,
                "navigate_back": 200,
                "stress_traverse": 1,
                "relaunch_target_app": 1,
            },
            counts,
        )
        # loop 迭代上限生效：每个循环体步骤恰好执行 max_iterations=200 次。
        loop_record = records[601]
        self.assertEqual("stress_traverse", loop_record.step_id)
        self.assertIsNone(loop_record.tool_id)  # 容器步骤无 tool_id
        self.assertEqual("succeeded", loop_record.status)
        self.assertEqual(
            ("launch_target_app", "app.launch"),
            (records[0].step_id, records[0].tool_id),
        )
        self.assertEqual(
            ("relaunch_target_app", "app.launch"),
            (records[-1].step_id, records[-1].tool_id),
        )
        # 结构化收尾：设备回到目标应用前台。
        self.assertEqual(TARGET_APP, self.adapter.foreground_app)

    async def test_loop_duration_ceiling_stops_before_iteration_limit(self) -> None:
        # deadline=600.0：迭代检查依次看到 0.0（放行）、700.0（停止）→ 仅 1 轮。
        clock = mock.patch(
            "mobile_agent.skills.dsl_interpreter.monotonic",
            side_effect=[0.0, 0.0, 700.0],
        )
        with clock:
            result = await self._run(_full_inputs())

        self.assertEqual("succeeded", result.status)
        self.assertEqual(
            ["app.launch", "input.swipe", "input.swipe", "navigation.back", "app.launch"],
            [action[0] for action in self.adapter.actions],
        )
        counts: dict[str, int] = {}
        for record in result.step_records:
            counts[record.step_id] = counts.get(record.step_id, 0) + 1
        self.assertEqual(1, counts["swipe_up"])
        self.assertEqual(1, counts["swipe_down"])
        self.assertEqual(1, counts["navigate_back"])

    # ---- 被阻断项：device.performance.capture 不可经 DSL 调用 ----

    async def test_performance_capture_is_blocked_in_dsl_steps(self) -> None:
        document = parse_skill_dsl_document(
            {
                "schema_version": "1.0.0",
                "skill_id": "custom.performance_probe",
                "skill_version": "1.0.0",
                "name": "Performance probe",
                "description": "Pins TOOL_REQUIRES_SKILL for non-direct tools.",
                "inputs": [],
                "steps": [
                    {
                        "type": "tool",
                        "step_id": "snap",
                        "tool_id": "device.performance.capture",
                        "arguments": {"app_id": TARGET_APP},
                    }
                ],
            }
        )
        result = await run_dsl_skill(
            document,
            device_id=DEVICE_ID,
            inputs={},
            confirmed=True,
            tools=self.runtime,
        )

        # 工具已注册且风险 LOW，preflight 通过；执行期才被 direct_invocation 拦截。
        self.assertEqual("failed", result.status)
        self.assertIsNotNone(result.error)
        self.assertEqual("TOOL_REQUIRES_SKILL", result.error.code)
        self.assertEqual(
            [("snap", "device.performance.capture", "failed", "TOOL_REQUIRES_SKILL")],
            [
                (r.step_id, r.tool_id, r.status, r.error_code)
                for r in result.step_records
            ],
        )
        self.assertEqual([], self.adapter.actions)


if __name__ == "__main__":
    unittest.main()
