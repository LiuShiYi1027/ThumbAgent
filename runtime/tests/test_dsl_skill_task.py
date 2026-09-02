"""Asynchronous skill.dsl.run task tests (ITER-0062, ADR-0013/0021).

覆盖：task_type 契约枚举新增（Schema + 生成 TS 同步）、提交→执行→报告链路
（goal=skill_id@version、evidence_summary 步骤摘要）、幂等、 confirmed 门、
禁用/未知 Skill 拒绝，以及取消/deadline 在 DSL 步骤边界生效。
"""

from __future__ import annotations

import asyncio
import json
import threading
import unittest
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from mobile_agent.api.server import RuntimeRequestHandler
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.skill_dsl import parse_skill_dsl_document
from mobile_agent.domain.task import TaskStatus
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.policy.engine import PolicyEngine
from mobile_agent.runtime import RuntimeService
from mobile_agent.tasks.dsl_skill import DslSkillTaskRunner
from mobile_agent.tasks.execution import ExecutionStatus, InMemoryTaskExecutionStore, TaskExecution
from mobile_agent.tools.runtime import ToolRegistry, ToolRuntime

ROOT = Path(__file__).resolve().parents[2]
DEVICE_ID = "fake:android-001"
_TOKEN = "test-token"


def _document(
    skill_id: str = "custom.smoke_check",
    version: str = "1.0.0",
    iterations: int = 3,
) -> dict:
    return {
        "schema_version": "1.0.0",
        "skill_id": skill_id,
        "skill_version": version,
        "name": "Smoke check",
        "description": "Open an app then loop home/back.",
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
                "type": "loop",
                "step_id": "traverse",
                "max_duration_seconds": 60,
                "max_iterations": iterations,
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


class _TerminalStore(InMemoryTaskExecutionStore):
    def __init__(self) -> None:
        super().__init__()
        self.terminal = threading.Event()

    def save_execution(self, execution: TaskExecution) -> None:
        super().save_execution(execution)
        if execution.status in {
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.TIMED_OUT,
        }:
            self.terminal.set()


def _post(
    runtime: RuntimeService,
    path: str,
    body: dict,
    *,
    idempotency_key: str | None = "key-1",
) -> dict:
    handler = object.__new__(RuntimeRequestHandler)
    handler.path = path
    headers = Message()
    headers["Host"] = "127.0.0.1:8765"
    headers["Content-Type"] = "application/json"
    headers["Authorization"] = f"Bearer {_TOKEN}"
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    handler.headers = headers
    handler.server = SimpleNamespace(
        runtime=runtime,
        api_token=_TOKEN,
        allowed_origins=frozenset(),
        server_port=8765,
    )
    handler._read_json = lambda: body
    captured: dict[str, object] = {}
    handler._write_json = lambda status, payload: captured.update(
        {"status": status, "payload": payload}
    )
    handler.do_POST()
    return captured


class DslSkillTaskContractTests(unittest.TestCase):
    def test_task_run_schema_accepts_dsl_task_type(self) -> None:
        schema = json.loads(
            (ROOT / "contracts/schemas/task-run.schema.json").read_text()
        )
        self.assertIn("skill.dsl.run", schema["properties"]["task_type"]["enum"])
        step = schema["properties"]["steps"]["items"]["properties"]
        self.assertIn("skill.dsl.run", step["name"]["enum"])
        self.assertIn("skill", step["kind"]["enum"])

    def test_task_execution_schema_accepts_dsl_task_type(self) -> None:
        schema = json.loads(
            (ROOT / "contracts/schemas/task-execution.schema.json").read_text()
        )
        self.assertIn("skill.dsl.run", schema["properties"]["task_type"]["enum"])

    def test_generated_typescript_in_sync(self) -> None:
        task_run = (ROOT / "contracts/generated/typescript/task-run.ts").read_text()
        task_execution = (
            ROOT / "contracts/generated/typescript/task-execution.ts"
        ).read_text()
        self.assertIn('"skill.dsl.run"', task_run)
        self.assertIn('"skill.dsl.run"', task_execution)


class DslSkillTaskSubmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.adapter = FakeDeviceAdapter()
        self.store = _TerminalStore()
        self.runtime = RuntimeService(
            self.adapter,
            ArtifactStore(Path(self.directory.name)),
            task_execution_store=self.store,
        )
        register = _post(
            self.runtime,
            "/v1/skills/custom",
            {"document": _document(), "confirmed": True},
        )
        self.assertEqual(HTTPStatus.OK, register["status"])

    def _submit(self, body: dict | None = None, **kwargs) -> dict:
        return _post(
            self.runtime,
            "/v1/tasks/skill.dsl.run/async",
            body
            or {
                "device_id": DEVICE_ID,
                "skill_id": "custom.smoke_check",
                "inputs": {"app_id": "com.android.settings"},
                "confirmed": True,
            },
            **kwargs,
        )

    def test_submit_executes_and_reports_skill_summary(self) -> None:
        captured = self._submit()
        self.assertEqual(HTTPStatus.ACCEPTED, captured["status"])
        execution = captured["payload"]["execution"]
        self.assertEqual("skill.dsl.run", execution["task_type"])
        self.assertEqual("custom.smoke_check@1.0.0", execution["goal"])
        self.assertTrue(self.store.terminal.wait(5), "DSL 异步任务未完成")

        status, task_payload = self.runtime.get_task_sync(execution["task_id"])
        self.assertEqual(HTTPStatus.OK, status)
        task = task_payload["task"]
        self.assertEqual("skill.dsl.run", task["task_type"])
        self.assertEqual("custom.smoke_check@1.0.0", task["goal"])
        self.assertEqual("succeeded", task["status"])
        self.assertEqual("skill_result", task["completion_source"])
        # 每个 DSL 步骤都有 TaskStep 记录。
        steps = task["steps"]
        self.assertEqual(5, len(steps))  # open + 3 次循环体 + loop 容器
        for step in steps:
            self.assertEqual("skill", step["kind"])
            self.assertEqual("skill.dsl.run", step["name"])
        # 报告携带 DslSkillResult 摘要。
        evidence = task["evidence_summary"]
        self.assertEqual("low", evidence["derived_risk"])
        self.assertEqual(5, evidence["step_count"])
        self.assertEqual([], evidence["failed_step_ids"])
        self.assertRegex(evidence["document_sha256"], r"^[a-f0-9]{64}$")
        self.assertEqual(
            ["open", "go_home", "go_home", "go_home", "traverse"],
            [record["step_id"] for record in evidence["step_records"]],
        )
        # 设备动作按文档顺序真实发生。
        self.assertEqual(
            ("app.launch", DEVICE_ID, "com.android.settings"),
            self.adapter.actions[0],
        )
        self.assertEqual(4, len(self.adapter.actions))

    def test_missing_idempotency_key_rejected(self) -> None:
        captured = self._submit(idempotency_key=None)
        self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])
        self.assertEqual("INVALID_ARGUMENT", captured["payload"]["error"]["code"])

    def test_idempotent_replay_returns_same_task(self) -> None:
        first = self._submit()
        self.assertEqual(HTTPStatus.ACCEPTED, first["status"])
        replay = self._submit()
        self.assertEqual(HTTPStatus.ACCEPTED, replay["status"])
        self.assertEqual(
            first["payload"]["execution"]["task_id"],
            replay["payload"]["execution"]["task_id"],
        )
        self.assertTrue(self.store.terminal.wait(5))

    def test_idempotency_conflict_on_different_body(self) -> None:
        first = self._submit()
        self.assertEqual(HTTPStatus.ACCEPTED, first["status"])
        conflict = self._submit(
            {
                "device_id": DEVICE_ID,
                "skill_id": "custom.smoke_check",
                "inputs": {"app_id": "com.android.calculator2"},
                "confirmed": True,
            }
        )
        self.assertEqual(HTTPStatus.CONFLICT, conflict["status"])
        self.assertEqual(
            "IDEMPOTENCY_CONFLICT", conflict["payload"]["error"]["code"]
        )
        self.assertTrue(self.store.terminal.wait(5))

    def test_unknown_skill_rejected_before_task_creation(self) -> None:
        captured = self._submit(
            {
                "device_id": DEVICE_ID,
                "skill_id": "custom.missing",
                "inputs": {},
                "confirmed": True,
            }
        )
        self.assertEqual(HTTPStatus.NOT_FOUND, captured["status"])
        self.assertEqual("SKILL_NOT_FOUND", captured["payload"]["error"]["code"])

    def test_disabled_skill_rejected(self) -> None:
        toggle = _post(
            self.runtime,
            "/v1/skills/custom/custom.smoke_check/versions/1.0.0/disable",
            {},
        )
        self.assertEqual(HTTPStatus.OK, toggle["status"])
        captured = self._submit()
        self.assertEqual(HTTPStatus.CONFLICT, captured["status"])
        self.assertEqual("SKILL_DISABLED", captured["payload"]["error"]["code"])

    def test_medium_risk_requires_confirmation(self) -> None:
        document = _document(skill_id="custom.tap_loop")
        document["steps"] = [
            {
                "type": "tool",
                "step_id": "tap",
                "tool_id": "input.tap",
                "arguments": {"x": 1, "y": 1},
            }
        ]
        register = _post(
            self.runtime,
            "/v1/skills/custom",
            {"document": document, "confirmed": True},
        )
        self.assertEqual(HTTPStatus.OK, register["status"])
        self.assertEqual("medium", register["payload"]["skill"]["derived_risk"])
        captured = self._submit(
            {
                "device_id": DEVICE_ID,
                "skill_id": "custom.tap_loop",
                "inputs": {"app_id": "com.android.settings"},
                "confirmed": False,
            }
        )
        self.assertEqual(HTTPStatus.FORBIDDEN, captured["status"])
        self.assertEqual(
            "CONFIRMATION_REQUIRED", captured["payload"]["error"]["code"]
        )

    def test_unknown_body_fields_rejected(self) -> None:
        captured = self._submit(
            {
                "device_id": DEVICE_ID,
                "skill_id": "custom.smoke_check",
                "inputs": {"app_id": "com.android.settings"},
                "confirmed": True,
                "raw_command": "pm list",
            }
        )
        self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])
        self.assertEqual("INVALID_ARGUMENT", captured["payload"]["error"]["code"])

    def test_invalid_skill_id_rejected(self) -> None:
        captured = self._submit(
            {
                "device_id": DEVICE_ID,
                "skill_id": "INVALID",
                "inputs": {},
                "confirmed": True,
            }
        )
        self.assertEqual(HTTPStatus.BAD_REQUEST, captured["status"])
        self.assertEqual("INVALID_ARGUMENT", captured["payload"]["error"]["code"])

    def test_version_pinning_selects_requested_version(self) -> None:
        register = _post(
            self.runtime,
            "/v1/skills/custom",
            {"document": _document(version="2.0.0", iterations=1), "confirmed": True},
        )
        self.assertEqual(HTTPStatus.OK, register["status"])
        captured = self._submit(
            {
                "device_id": DEVICE_ID,
                "skill_id": "custom.smoke_check",
                "skill_version": "2.0.0",
                "inputs": {"app_id": "com.android.settings"},
                "confirmed": True,
            }
        )
        self.assertEqual(HTTPStatus.ACCEPTED, captured["status"])
        self.assertEqual(
            "custom.smoke_check@2.0.0", captured["payload"]["execution"]["goal"]
        )
        self.assertTrue(self.store.terminal.wait(5))

    def test_cancel_during_loop_takes_effect_at_step_boundary(self) -> None:
        register = _post(
            self.runtime,
            "/v1/skills/custom",
            {
                "document": _document(skill_id="custom.long_loop", iterations=200),
                "confirmed": True,
            },
        )
        self.assertEqual(HTTPStatus.OK, register["status"])
        submitted = self._submit(
            {
                "device_id": DEVICE_ID,
                "skill_id": "custom.long_loop",
                "inputs": {"app_id": "com.android.settings"},
                "confirmed": True,
            }
        )
        self.assertEqual(HTTPStatus.ACCEPTED, submitted["status"])
        task_id = submitted["payload"]["execution"]["task_id"]
        cancel = _post(
            self.runtime, f"/v1/task-executions/{task_id}/cancel", {}
        )
        self.assertIn(
            cancel["payload"]["execution"]["status"],
            {"cancelling", "cancelled"},
        )
        self.assertTrue(self.store.terminal.wait(5), "取消后任务未收敛到终态")
        final = self.runtime.get_task_execution_sync(task_id)[1]["execution"]
        self.assertEqual("cancelled", final["status"])
        status, task_payload = self.runtime.get_task_sync(task_id)
        self.assertEqual(HTTPStatus.OK, status)
        self.assertEqual("cancelled", task_payload["task"]["status"])
        self.assertEqual(
            "TASK_CANCELLED", task_payload["task"]["error"]["code"]
        )


class DslSkillTaskRunnerBoundaryTests(unittest.TestCase):
    """Runner 级确定性验证：取消/deadline 精确作用于步骤边界。"""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.adapter = FakeDeviceAdapter()
        self.tools = ToolRuntime(
            self.adapter,
            ArtifactStore(Path(self.directory.name)),
            ToolRegistry(),
            PolicyEngine(),
        )
        self.runner = DslSkillTaskRunner(self.tools)
        self.document = parse_skill_dsl_document(_document(iterations=200))

    def _run(self, **kwargs) -> object:
        return asyncio.run(
            self.runner.run(
                "task_" + "0" * 32,
                DEVICE_ID,
                self.document,
                document_sha256="f" * 64,
                inputs={"app_id": "com.android.settings"},
                confirmed=True,
                deadline_seconds=600.0,
                **kwargs,
            )
        )

    def test_cancellation_stops_at_step_boundary(self) -> None:
        calls = {"count": 0}

        def cancelled() -> bool:
            calls["count"] += 1
            return calls["count"] > 4

        streamed: list = []
        task = self._run(cancellation_requested=cancelled, on_step=streamed.append)

        self.assertEqual(TaskStatus.CANCELLED, task.status)
        self.assertEqual("TASK_CANCELLED", task.error["code"])
        # 取消在第 4 次边界检查后生效：只有少量步骤完成，绝非 200 次迭代。
        self.assertLessEqual(len(task.steps), 4)
        self.assertGreaterEqual(len(task.steps), 1)
        self.assertEqual(len(task.steps), len(self.adapter.actions))
        # on_step 实时流式回调与最终 TaskRun 步骤一致。
        self.assertEqual([step.step_id for step in task.steps], [s.step_id for s in streamed])
        for index, step in enumerate(task.steps, start=1):
            self.assertEqual(index, step.sequence)
            self.assertEqual("skill.dsl.run", step.name)

    def test_deadline_stops_at_step_boundary(self) -> None:
        calls = {"count": 0}

        def expired() -> bool:
            calls["count"] += 1
            return calls["count"] > 2

        task = self._run(deadline_exceeded=expired)

        self.assertEqual(TaskStatus.TIMED_OUT, task.status)
        self.assertEqual("TASK_DEADLINE_EXCEEDED", task.error["code"])
        self.assertLessEqual(len(task.steps), 2)

    def test_cancel_requested_before_start_yields_empty_run(self) -> None:
        task = self._run(cancellation_requested=lambda: True)

        self.assertEqual(TaskStatus.CANCELLED, task.status)
        self.assertEqual((), task.steps)
        self.assertEqual([], self.adapter.actions)


if __name__ == "__main__":
    unittest.main()
