"""Interpreter tests for the declarative skill DSL (ITER-0062, ADR-0021).

负向矩阵先断言 preflight 拒绝且「零设备动作」（adapter.actions 为空）；
正向用 FakeDeviceAdapter + ToolRuntime 真实装配验证执行语义。
"""

from __future__ import annotations

import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest import mock

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.action import RiskLevel
from mobile_agent.domain.errors import ErrorCategory, ErrorOutcome, MobileAgentError
from mobile_agent.domain.skill_dsl import SkillDslDocument, parse_skill_dsl_document
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.skills.dsl_interpreter import (
    DslStepRecord,
    SkillInvoker,
    run_dsl_skill,
)
from mobile_agent.tools.runtime import ToolRegistry, ToolRuntime

DEVICE_ID = "fake:android-001"


def _tool_step(
    step_id: str, tool_id: str, arguments: dict | None = None
) -> dict:
    return {
        "type": "tool",
        "step_id": step_id,
        "tool_id": tool_id,
        "arguments": arguments or {},
    }


def _skill_step(
    step_id: str, skill_id: str, arguments: dict | None = None
) -> dict:
    return {
        "type": "skill",
        "step_id": step_id,
        "skill_id": skill_id,
        "arguments": arguments or {},
    }


class _RecordingInvoker:
    """记录调用的 SkillInvoker 假实现；可配置每次调用抛出同一个错误。"""

    def __init__(self, error: MobileAgentError | None = None) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.error = error

    async def __call__(
        self, skill_id: str, device_id: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls.append((skill_id, device_id, dict(arguments)))
        if self.error is not None:
            raise self.error
        return {"status": "ok"}


def _invoker_error(code: str = "DEVICE_LOST") -> MobileAgentError:
    return MobileAgentError(
        code=code,
        category=ErrorCategory.DEVICE,
        message="设备连接丢失",
        outcome=ErrorOutcome.KNOWN_FAILURE,
    )


def _document(steps: list[dict], inputs: list[dict] | None = None) -> SkillDslDocument:
    return parse_skill_dsl_document(
        {
            "schema_version": "1.0.0",
            "skill_id": "custom.test_skill",
            "skill_version": "1.0.0",
            "name": "Test composite",
            "description": "Interpreter test fixture.",
            "inputs": inputs or [],
            "steps": steps,
        }
    )


class DslInterpreterTests(unittest.IsolatedAsyncioTestCase):
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

    async def _run(
        self,
        document: SkillDslDocument,
        inputs: dict | None = None,
        confirmed: bool = False,
    ):
        return await run_dsl_skill(
            document,
            device_id=DEVICE_ID,
            inputs=inputs or {},
            confirmed=confirmed,
            tools=self.runtime,
        )

    def _assert_preflight_rejected(self, result, code: str) -> None:
        self.assertEqual("failed", result.status)
        self.assertEqual((), result.step_records)
        self.assertIsNotNone(result.error)
        self.assertEqual(code, result.error.code)
        # 零设备动作：preflight 失败发生在任何设备动作之前。
        self.assertEqual([], self.adapter.actions)

    # ---- 负向：preflight 拒绝矩阵 ----

    async def test_unknown_tool_id_rejected_before_any_device_action(self) -> None:
        document = _document([_tool_step("boom", "app.explode")])
        result = await self._run(document)
        self._assert_preflight_rejected(result, "TOOL_NOT_FOUND")

    async def test_inputs_reference_to_undeclared_input_rejected(self) -> None:
        document = _document(
            [_tool_step("open", "app.launch", {"app_id": "$inputs.missing"})]
        )
        result = await self._run(document)
        self._assert_preflight_rejected(result, "SKILL_INPUT_INVALID")

    async def test_required_input_missing_rejected(self) -> None:
        document = _document(
            [_tool_step("open", "app.launch", {"app_id": "$inputs.app_id"})],
            inputs=[{"name": "app_id", "type": "string", "required": True}],
        )
        result = await self._run(document, inputs={})
        self._assert_preflight_rejected(result, "SKILL_INPUT_INVALID")

    async def test_input_type_mismatch_rejected(self) -> None:
        for declared_type, bad_value in (
            ("string", 1),
            ("integer", "1"),
            ("integer", True),  # bool 是 int 子类，必须拒绝
            ("number", "1.5"),
            ("boolean", 1),
        ):
            with self.subTest(declared_type=declared_type, bad_value=bad_value):
                document = _document(
                    [_tool_step("open", "app.launch")],
                    inputs=[{"name": "value", "type": declared_type, "required": True}],
                )
                result = await self._run(document, inputs={"value": bad_value})
                self._assert_preflight_rejected(result, "SKILL_INPUT_INVALID")

    async def test_input_bounds_violation_rejected(self) -> None:
        for declaration, bad_value in (
            ({"name": "rounds", "type": "integer", "minimum": 1, "maximum": 10}, 0),
            ({"name": "rounds", "type": "integer", "minimum": 1, "maximum": 10}, 11),
            ({"name": "label", "type": "string", "max_length": 3}, "abcd"),
        ):
            with self.subTest(declaration=declaration, bad_value=bad_value):
                document = _document(
                    [_tool_step("open", "app.launch")],
                    inputs=[declaration],
                )
                result = await self._run(document, inputs={declaration["name"]: bad_value})
                self._assert_preflight_rejected(result, "SKILL_INPUT_INVALID")

    async def test_medium_risk_requires_confirmation(self) -> None:
        document = _document([_tool_step("tap", "input.tap", {"x": 1, "y": 1})])
        result = await self._run(document, confirmed=False)
        self._assert_preflight_rejected(result, "CONFIRMATION_REQUIRED")
        self.assertEqual(RiskLevel.MEDIUM, result.derived_risk)

    async def test_high_risk_tool_rejected_by_policy_even_when_confirmed(self) -> None:
        document = _document(
            [_tool_step("install", "app.install", {"apk_path": "/tmp/x.apk"})]
        )
        result = await self._run(document, confirmed=True)
        self._assert_preflight_rejected(result, "ACTION_REJECTED_BY_POLICY")
        self.assertEqual(RiskLevel.HIGH, result.derived_risk)

    # ---- 正向：执行语义 ----

    async def test_sequential_steps_resolve_inputs_and_execute_in_order(self) -> None:
        document = _document(
            [
                _tool_step("open", "app.launch", {"app_id": "$inputs.app_id"}),
                _tool_step("home", "navigation.home"),
                _tool_step("back", "navigation.back"),
            ],
            inputs=[{"name": "app_id", "type": "string", "required": True}],
        )
        result = await self._run(document, inputs={"app_id": "com.android.settings"})

        self.assertEqual("succeeded", result.status)
        self.assertIsNone(result.error)
        self.assertEqual(RiskLevel.LOW, result.derived_risk)
        self.assertEqual(
            [
                ("app.launch", DEVICE_ID, "com.android.settings"),
                ("navigation.home", DEVICE_ID),
                ("navigation.back", DEVICE_ID),
            ],
            self.adapter.actions,
        )
        self.assertEqual(
            [("open", "app.launch"), ("home", "navigation.home"), ("back", "navigation.back")],
            [(record.step_id, record.tool_id) for record in result.step_records],
        )
        self.assertTrue(
            all(record.status == "succeeded" for record in result.step_records)
        )

    async def test_loop_stops_at_max_iterations(self) -> None:
        document = _document(
            [
                {
                    "type": "loop",
                    "step_id": "repeat",
                    "max_duration_seconds": 600,
                    "max_iterations": 3,
                    "steps": [_tool_step("go_back", "navigation.back")],
                }
            ]
        )
        result = await self._run(document)

        self.assertEqual("succeeded", result.status)
        self.assertEqual(
            [("navigation.back", DEVICE_ID)] * 3, self.adapter.actions
        )
        body_records = [r for r in result.step_records if r.tool_id == "navigation.back"]
        self.assertEqual(3, len(body_records))
        loop_record = result.step_records[-1]
        self.assertEqual(("repeat", None, "succeeded"), (loop_record.step_id, loop_record.tool_id, loop_record.status))

    async def test_loop_stops_at_max_duration(self) -> None:
        document = _document(
            [
                {
                    "type": "loop",
                    "step_id": "repeat",
                    "max_duration_seconds": 1,
                    "max_iterations": 200,
                    "steps": [_tool_step("go_back", "navigation.back")],
                }
            ]
        )
        # deadline=101：迭代检查依次看到 100.0、100.5（放行），102.0（停止）。
        clock = mock.patch(
            "mobile_agent.skills.dsl_interpreter.monotonic",
            side_effect=[100.0, 100.0, 100.5, 102.0],
        )
        with clock:
            result = await self._run(document)

        self.assertEqual("succeeded", result.status)
        self.assertEqual(
            [("navigation.back", DEVICE_ID)] * 2, self.adapter.actions
        )

    async def test_loop_body_failure_is_recorded_and_loop_continues(self) -> None:
        document = _document(
            [
                {
                    "type": "loop",
                    "step_id": "repeat",
                    "max_duration_seconds": 600,
                    "max_iterations": 2,
                    "steps": [_tool_step("tap", "input.tap", {"x": 99, "y": 99})],
                }
            ]
        )
        result = await self._run(document, confirmed=True)

        # 循环体失败被容忍：整体成功，失败逐步记录，循环跑满迭代上限。
        self.assertEqual("succeeded", result.status)
        body_records = [r for r in result.step_records if r.step_id == "tap"]
        self.assertEqual(2, len(body_records))
        self.assertTrue(
            all(
                r.status == "failed" and r.error_code == "INVALID_ARGUMENT"
                for r in body_records
            )
        )
        self.assertEqual("succeeded", result.step_records[-1].status)
        # 越界坐标在派发前被拒绝：零设备动作。
        self.assertEqual([], self.adapter.actions)

    async def test_if_selects_then_branch_and_skips_else(self) -> None:
        document = _document(
            [
                _tool_step("home", "navigation.home"),
                {
                    "type": "if",
                    "step_id": "check",
                    "condition": {"step": "home", "field": "status", "equals": "succeeded"},
                    "then": [_tool_step("go_back", "navigation.back")],
                    "else": [_tool_step("open", "app.launch", {"app_id": "com.android.settings"})],
                },
            ]
        )
        result = await self._run(document)

        self.assertEqual("succeeded", result.status)
        self.assertEqual(
            [("navigation.home", DEVICE_ID), ("navigation.back", DEVICE_ID)],
            self.adapter.actions,
        )
        executed = {record.step_id for record in result.step_records}
        self.assertIn("go_back", executed)
        self.assertNotIn("open", executed)  # else 分支被跳过

    async def test_if_selects_else_branch_and_skips_then(self) -> None:
        document = _document(
            [
                _tool_step("home", "navigation.home"),
                {
                    "type": "if",
                    "step_id": "check",
                    "condition": {"step": "home", "field": "status", "equals": "failed"},
                    "then": [_tool_step("go_back", "navigation.back")],
                    "else": [_tool_step("open", "app.launch", {"app_id": "com.android.settings"})],
                },
            ]
        )
        result = await self._run(document)

        self.assertEqual("succeeded", result.status)
        self.assertEqual(
            [
                ("navigation.home", DEVICE_ID),
                ("app.launch", DEVICE_ID, "com.android.settings"),
            ],
            self.adapter.actions,
        )
        executed = {record.step_id for record in result.step_records}
        self.assertIn("open", executed)
        self.assertNotIn("go_back", executed)  # then 分支被跳过

    async def test_top_level_failure_aborts_remaining_steps(self) -> None:
        document = _document(
            [
                _tool_step("tap", "input.tap", {"x": 99, "y": 99}),
                _tool_step("home", "navigation.home"),
            ]
        )
        result = await self._run(document, confirmed=True)

        self.assertEqual("failed", result.status)
        self.assertIsNotNone(result.error)
        self.assertEqual("INVALID_ARGUMENT", result.error.code)
        self.assertEqual(["tap"], [record.step_id for record in result.step_records])
        self.assertEqual("failed", result.step_records[0].status)
        # 后续步骤未执行；越界 tap 也未派发：零设备动作。
        self.assertEqual([], self.adapter.actions)


class DslInterpreterSkillStepTests(unittest.IsolatedAsyncioTestCase):
    """Skill 引用步骤（ADR-0021 修订一）的解释器语义。"""

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
        self.on_step_records: list[DslStepRecord] = []

    async def _run(
        self,
        document: SkillDslDocument,
        inputs: dict | None = None,
        confirmed: bool = True,
        skill_invoker: SkillInvoker | None = None,
        on_step: Callable[[DslStepRecord], None] | None = None,
    ):
        return await run_dsl_skill(
            document,
            device_id=DEVICE_ID,
            inputs=inputs or {},
            confirmed=confirmed,
            tools=self.runtime,
            skill_invoker=skill_invoker,
            on_step=on_step,
        )

    # ---- 负向 ----

    async def test_skill_step_without_invoker_fails_preflight_zero_device_actions(
        self,
    ) -> None:
        document = _document(
            [_skill_step("snap", "device.performance.snapshot")]
        )
        result = await self._run(document, skill_invoker=None)

        self.assertEqual("failed", result.status)
        self.assertEqual((), result.step_records)
        self.assertIsNotNone(result.error)
        self.assertEqual("SKILL_DSL_INVALID", result.error.code)
        self.assertEqual([], self.adapter.actions)

    async def test_non_whitelisted_skill_rejected_end_to_end(self) -> None:
        invoker = _RecordingInvoker()
        document = _document(
            [_skill_step("record_screen", "device.screen.record")]
        )
        result = await self._run(document, skill_invoker=invoker)

        self.assertEqual("failed", result.status)
        self.assertEqual((), result.step_records)
        self.assertIsNotNone(result.error)
        self.assertEqual("SKILL_REFERENCE_NOT_ALLOWED", result.error.code)
        # 白名单拒绝发生在任何派发之前：invoker 与设备都未被触碰。
        self.assertEqual([], invoker.calls)
        self.assertEqual([], self.adapter.actions)

    async def test_skill_invoker_error_at_top_level_aborts_run(self) -> None:
        invoker = _RecordingInvoker(error=_invoker_error())
        document = _document(
            [
                _skill_step("snap", "device.performance.snapshot"),
                _tool_step("home", "navigation.home"),
            ]
        )
        result = await self._run(document, skill_invoker=invoker)

        self.assertEqual("failed", result.status)
        self.assertIsNotNone(result.error)
        self.assertEqual("DEVICE_LOST", result.error.code)
        self.assertEqual(1, len(result.step_records))
        record = result.step_records[0]
        self.assertEqual("snap", record.step_id)
        self.assertIsNone(record.tool_id)
        self.assertEqual("device.performance.snapshot", record.skill_id)
        self.assertEqual("failed", record.status)
        self.assertEqual("DEVICE_LOST", record.error_code)
        # 顶层失败中止：后续 tool 步骤未执行。
        self.assertEqual([], self.adapter.actions)

    async def test_skill_invoker_error_inside_loop_body_is_recorded_and_continues(
        self,
    ) -> None:
        invoker = _RecordingInvoker(error=_invoker_error())
        document = _document(
            [
                {
                    "type": "loop",
                    "step_id": "repeat",
                    "max_duration_seconds": 600,
                    "max_iterations": 2,
                    "steps": [_skill_step("snap", "device.performance.snapshot")],
                }
            ]
        )
        result = await self._run(document, skill_invoker=invoker)

        # 与 tool 步骤一致：循环体失败被容忍，跑满迭代上限后整体成功。
        self.assertEqual("succeeded", result.status)
        self.assertEqual(2, len(invoker.calls))
        body_records = [r for r in result.step_records if r.step_id == "snap"]
        self.assertEqual(2, len(body_records))
        for record in body_records:
            self.assertIsNone(record.tool_id)
            self.assertEqual("device.performance.snapshot", record.skill_id)
            self.assertEqual("failed", record.status)
            self.assertEqual("DEVICE_LOST", record.error_code)
        loop_record = result.step_records[-1]
        self.assertEqual("repeat", loop_record.step_id)
        self.assertIsNone(loop_record.tool_id)
        self.assertIsNone(loop_record.skill_id)
        self.assertEqual("succeeded", loop_record.status)

    async def test_skill_step_with_undeclared_input_reference_rejected(self) -> None:
        invoker = _RecordingInvoker()
        document = _document(
            [
                _skill_step(
                    "collect",
                    "device.logs.collect",
                    {"max_lines": "$inputs.missing"},
                )
            ]
        )
        result = await self._run(document, skill_invoker=invoker)

        self.assertEqual("failed", result.status)
        self.assertIsNotNone(result.error)
        self.assertEqual("SKILL_INPUT_INVALID", result.error.code)
        self.assertEqual([], invoker.calls)
        self.assertEqual([], self.adapter.actions)

    # ---- 正向 ----

    async def test_skill_step_executes_with_resolved_arguments_and_on_step(self) -> None:
        invoker = _RecordingInvoker()
        document = _document(
            [
                _skill_step(
                    "collect",
                    "device.logs.collect",
                    {
                        "max_lines": "$inputs.max_lines",
                        "minimum_level": "warning",
                    },
                )
            ],
            inputs=[{"name": "max_lines", "type": "integer", "required": True}],
        )
        result = await self._run(
            document,
            inputs={"max_lines": 100},
            skill_invoker=invoker,
            on_step=self.on_step_records.append,
        )

        self.assertEqual("succeeded", result.status)
        self.assertIsNone(result.error)
        self.assertEqual(RiskLevel.MEDIUM, result.derived_risk)
        # $inputs 引用已解析后传给 invoker。
        self.assertEqual(
            [
                (
                    "device.logs.collect",
                    DEVICE_ID,
                    {"max_lines": 100, "minimum_level": "warning"},
                )
            ],
            invoker.calls,
        )
        self.assertEqual(1, len(result.step_records))
        record = result.step_records[0]
        self.assertEqual("collect", record.step_id)
        self.assertIsNone(record.tool_id)
        self.assertEqual("device.logs.collect", record.skill_id)
        self.assertEqual("succeeded", record.status)
        # on_step 对 skill 步骤同样触发，且与结果中的记录一致。
        self.assertEqual(list(result.step_records), self.on_step_records)

    async def test_skill_step_inside_loop_body_executes_each_iteration(self) -> None:
        invoker = _RecordingInvoker()
        document = _document(
            [
                {
                    "type": "loop",
                    "step_id": "repeat",
                    "max_duration_seconds": 600,
                    "max_iterations": 3,
                    "steps": [_skill_step("snap", "device.performance.snapshot")],
                }
            ]
        )
        result = await self._run(
            document,
            skill_invoker=invoker,
            on_step=self.on_step_records.append,
        )

        self.assertEqual("succeeded", result.status)
        self.assertEqual(
            [("device.performance.snapshot", DEVICE_ID, {})] * 3, invoker.calls
        )
        body_records = [r for r in result.step_records if r.step_id == "snap"]
        self.assertEqual(3, len(body_records))
        self.assertTrue(
            all(
                r.status == "succeeded"
                and r.tool_id is None
                and r.skill_id == "device.performance.snapshot"
                for r in body_records
            )
        )
        # 3 条体内记录 + 1 条循环容器记录，on_step 全覆盖。
        self.assertEqual(4, len(self.on_step_records))
        self.assertEqual(list(result.step_records), self.on_step_records)


if __name__ == "__main__":
    unittest.main()
