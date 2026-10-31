"""DSL skill 引用步骤 invoker 装配与 app.stability_test@1.1.0 任务链路测试（ITER-0063）。

ADR-0021 修订一：DSL 文档可经白名单引用两个内置观察 Skill
（device.performance.snapshot / device.logs.collect）。覆盖：

- build_dsl_skill_invoker 闭包的严格 arguments 校验（负向优先：任何不合法
  输入都在触碰设备前抛出，FakeDeviceAdapter 零动作）与白名单外 id 的防御性
  兜底；
- RuntimeService 真实装配下经任务处理器执行 app.stability_test@1.1.0：
  循环内每迭代一次性能采样、循环结束后收尾日志采集、派生风险 MEDIUM、
  报告 step_records 携带 skill_id；
- 1.0.0 回归：同链路执行结果与 ITER-0062 一致（step_records 全部
  skill_id=None，设备动作序列不变）；
- 两个版本文档共存：自动加载均成功，latest 解析为 1.1.0。
"""

from __future__ import annotations

import threading
import unittest
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

from mobile_agent.api.server import RuntimeRequestHandler
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.runtime import RuntimeService
from mobile_agent.tasks.dsl_skill import build_dsl_skill_invoker
from mobile_agent.tasks.execution import ExecutionStatus, InMemoryTaskExecutionStore, TaskExecution

DEVICE_ID = "fake:android-001"
TARGET_APP = "com.example.fake"
_TOKEN = "test-token"


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


class DslSkillInvokerClosureTests(unittest.IsolatedAsyncioTestCase):
    """build_dsl_skill_invoker 闭包级校验：负向用例零设备动作。"""

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.adapter = FakeDeviceAdapter()
        self.runtime = RuntimeService(
            self.adapter, ArtifactStore(Path(self.directory.name))
        )
        self.invoker = build_dsl_skill_invoker(self.runtime)

    async def _assert_rejected(self, skill_id: str, arguments: dict, code: str) -> None:
        with self.assertRaises(MobileAgentError) as caught:
            await self.invoker(skill_id, DEVICE_ID, arguments)
        self.assertEqual(code, caught.exception.code)
        # 任何校验失败都发生在设备动作之前。
        self.assertEqual([], self.adapter.actions)

    # ---- 负向：严格 arguments 校验 ----

    async def test_performance_snapshot_rejects_any_arguments(self) -> None:
        await self._assert_rejected(
            "device.performance.snapshot", {"app_id": TARGET_APP}, "SKILL_INPUT_INVALID"
        )

    async def test_logs_collect_rejects_unknown_arguments(self) -> None:
        await self._assert_rejected(
            "device.logs.collect", {"level": "debug"}, "SKILL_INPUT_INVALID"
        )
        await self._assert_rejected(
            "device.logs.collect",
            {"max_lines": 100, "follow": True},
            "SKILL_INPUT_INVALID",
        )

    async def test_logs_collect_max_lines_boundary(self) -> None:
        for bad_max_lines in (0, 2001, True, "500"):
            with self.subTest(max_lines=bad_max_lines):
                await self._assert_rejected(
                    "device.logs.collect",
                    {"max_lines": bad_max_lines},
                    "INVALID_ARGUMENT",
                )

    async def test_logs_collect_rejects_unknown_minimum_level(self) -> None:
        await self._assert_rejected(
            "device.logs.collect",
            {"minimum_level": "chatty"},
            "INVALID_ARGUMENT",
        )

    async def test_non_whitelisted_skill_rejected(self) -> None:
        # preflight 已强制白名单；闭包再兜底一次。
        await self._assert_rejected(
            "device.notifications.read", {}, "SKILL_REFERENCE_NOT_ALLOWED"
        )

    # ---- 正向：默认值与显式参数直达内置 Skill ----

    async def test_performance_snapshot_invokes_runtime(self) -> None:
        result = await self.invoker("device.performance.snapshot", DEVICE_ID, {})

        self.assertIsInstance(result, dict)
        self.assertEqual(
            [("device.performance.capture", DEVICE_ID)], self.adapter.actions
        )

    async def test_logs_collect_defaults_and_explicit_arguments(self) -> None:
        await self.invoker("device.logs.collect", DEVICE_ID, {})
        await self.invoker(
            "device.logs.collect",
            DEVICE_ID,
            {"max_lines": 100, "minimum_level": "error"},
        )

        self.assertEqual(
            [
                ("device.logs.capture", DEVICE_ID, 500, "info"),
                ("device.logs.capture", DEVICE_ID, 100, "error"),
            ],
            self.adapter.actions,
        )


class StabilityTestV11TaskTests(unittest.TestCase):
    """RuntimeService 真实装配（含 invoker 接线）下跑内置 1.1.0 文档。"""

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

    def _submit(self, body: dict) -> dict:
        return _post(self.runtime, "/v1/tasks/skill.dsl.run/async", body)

    def _run_stability(self, version: str, **input_overrides: int) -> dict:
        inputs = {
            "app_id": TARGET_APP,
            "duration_seconds": 600,
            "max_actions": 200,
            **input_overrides,
        }
        captured = self._submit(
            {
                "device_id": DEVICE_ID,
                "skill_id": "app.stability_test",
                "skill_version": version,
                "inputs": inputs,
                "confirmed": True,
            }
        )
        self.assertEqual(HTTPStatus.ACCEPTED, captured["status"])
        task_id = captured["payload"]["execution"]["task_id"]
        self.assertTrue(self.store.terminal.wait(10), "DSL 异步任务未完成")
        status, task_payload = self.runtime.get_task_sync(task_id)
        self.assertEqual(HTTPStatus.OK, status)
        return task_payload["task"]

    def test_builtin_versions_coexist_and_latest_is_1_1_0(self) -> None:
        status, payload = self.runtime.list_custom_skill_versions_sync(
            "app.stability_test"
        )

        self.assertEqual(HTTPStatus.OK, status)
        versions = {item["skill_version"]: item for item in payload["versions"]}
        self.assertEqual({"1.0.0", "1.1.0"}, set(versions))
        for item in versions.values():
            self.assertEqual("builtin-dsl", item["source"])
            self.assertTrue(item["enabled"])
            self.assertEqual("medium", item["derived_risk"])
        # 版本不可变：latest 按 semver 解析到 1.1.0。
        status, latest = self.runtime.list_custom_skills_sync()
        self.assertEqual(HTTPStatus.OK, status)
        latest_by_id = {
            item["skill_id"]: item["skill_version"] for item in latest["skills"]
        }
        self.assertEqual("1.1.0", latest_by_id["app.stability_test"])

    def test_v11_samples_every_iteration_and_collects_logs_at_wrapup(self) -> None:
        task = self._run_stability("1.1.0")

        self.assertEqual("succeeded", task["status"])
        self.assertEqual("app.stability_test@1.1.0", task["goal"])
        self.assertEqual("skill_result", task["completion_source"])

        # 设备动作：launch → 200×(swipe,swipe,back,采样) → 收尾日志 → relaunch。
        actions = self.adapter.actions
        self.assertEqual(1 + 200 * 4 + 1 + 1, len(actions))
        self.assertEqual(("app.launch", DEVICE_ID, TARGET_APP), actions[0])
        self.assertEqual(("app.launch", DEVICE_ID, TARGET_APP), actions[-1])
        self.assertEqual(
            ["input.swipe", "input.swipe", "navigation.back", "device.performance.capture"]
            * 200,
            [action[0] for action in actions[1:-2]],
        )
        # 日志采集在循环结束之后、relaunch 之前，max_lines=500。
        self.assertEqual(
            ("device.logs.capture", DEVICE_ID, 500, "info"), actions[-2]
        )

        # 报告：派生风险 MEDIUM；step_records 携带 skill_id。
        evidence = task["evidence_summary"]
        self.assertEqual("medium", evidence["derived_risk"])
        self.assertEqual([], evidence["failed_step_ids"])
        records = evidence["step_records"]
        self.assertEqual(1 + 200 * 4 + 1 + 1 + 1, len(records))
        self.assertEqual(len(records), evidence["step_count"])
        self.assertEqual(len(records), len(task["steps"]))

        launch, *body, container, collect, relaunch = (
            records[0],
            *records[1:-3],
            records[-3],
            records[-2],
            records[-1],
        )
        self.assertEqual(
            ("launch_target_app", "app.launch", None),
            (launch["step_id"], launch["tool_id"], launch["skill_id"]),
        )
        # 循环内采样：每迭代第 4 步为 skill 步骤，skill_id 有值、tool_id 为 None。
        self.assertEqual(
            ["swipe_up", "swipe_down", "navigate_back", "sample_performance"] * 200,
            [record["step_id"] for record in body],
        )
        samples = body[3::4]
        self.assertTrue(
            all(
                record["skill_id"] == "device.performance.snapshot"
                and record["tool_id"] is None
                and record["status"] == "succeeded"
                for record in samples
            )
        )
        tool_records = [
            record for offset in range(3) for record in body[offset::4]
        ]
        self.assertTrue(
            all(
                record["skill_id"] is None and record["tool_id"] is not None
                for record in tool_records
            )
        )
        # loop 容器记录：tool_id 与 skill_id 均为 None。
        self.assertEqual(
            ("stress_traverse", None, None),
            (container["step_id"], container["tool_id"], container["skill_id"]),
        )
        # 收尾日志记录：在容器之后、relaunch 之前。
        self.assertEqual(
            ("collect_logs", None, "device.logs.collect"),
            (collect["step_id"], collect["tool_id"], collect["skill_id"]),
        )
        self.assertEqual(
            ("relaunch_target_app", "app.launch", None),
            (relaunch["step_id"], relaunch["tool_id"], relaunch["skill_id"]),
        )
        # 结构化收尾：设备回到目标应用前台。
        self.assertEqual(TARGET_APP, self.adapter.foreground_app)

    def test_v11_action_budget_stops_loop_and_preserves_wrapup(self) -> None:
        task = self._run_stability("1.1.0", max_actions=2)

        self.assertEqual("succeeded", task["status"])
        self.assertEqual(
            [
                "app.launch",
                *["input.swipe", "input.swipe", "navigation.back", "device.performance.capture"] * 2,
                "device.logs.capture",
                "app.launch",
            ],
            [action[0] for action in self.adapter.actions],
        )
        self.assertEqual(2, len(task["evidence_summary"]["sampling_series"]))
        self.assertIn("crash_check", task["evidence_summary"])

    def test_v11_duration_budget_stops_loop_and_preserves_wrapup(self) -> None:
        clock = mock.patch(
            "mobile_agent.skills.dsl_interpreter.monotonic",
            side_effect=[100.0, 100.0, 100.5] + [102.0] * 1000,
        )
        with clock:
            task = self._run_stability("1.1.0", duration_seconds=1)

        self.assertEqual("succeeded", task["status"])
        self.assertEqual(
            [
                "app.launch",
                *["input.swipe", "input.swipe", "navigation.back", "device.performance.capture"] * 2,
                "device.logs.capture",
                "app.launch",
            ],
            [action[0] for action in self.adapter.actions],
        )
        self.assertIn("crash_check", task["evidence_summary"])

    def test_v11_medium_risk_requires_confirmation(self) -> None:
        captured = self._submit(
            {
                "device_id": DEVICE_ID,
                "skill_id": "app.stability_test",
                "skill_version": "1.1.0",
                "inputs": {"app_id": TARGET_APP},
                "confirmed": False,
            }
        )

        self.assertEqual(HTTPStatus.FORBIDDEN, captured["status"])
        self.assertEqual(
            "CONFIRMATION_REQUIRED", captured["payload"]["error"]["code"]
        )
        self.assertEqual([], self.adapter.actions)

    def test_v10_regression_unchanged(self) -> None:
        task = self._run_stability("1.0.0")

        self.assertEqual("succeeded", task["status"])
        self.assertEqual("app.stability_test@1.0.0", task["goal"])
        # 设备动作序列与 ITER-0062 一致：launch → 200×(swipe,swipe,back) → relaunch。
        actions = self.adapter.actions
        self.assertEqual(2 + 200 * 3, len(actions))
        self.assertEqual(
            ["input.swipe", "input.swipe", "navigation.back"] * 200,
            [action[0] for action in actions[1:-1]],
        )
        evidence = task["evidence_summary"]
        self.assertEqual("medium", evidence["derived_risk"])
        self.assertEqual(603, evidence["step_count"])
        # 1.0.0 无 skill 步骤：所有 step_records 的 skill_id 均为 None。
        self.assertTrue(
            all(
                record["skill_id"] is None for record in evidence["step_records"]
            )
        )

    def test_default_version_resolves_to_1_1_0(self) -> None:
        captured = self._submit(
            {
                "device_id": DEVICE_ID,
                "skill_id": "app.stability_test",
                "inputs": {"app_id": TARGET_APP},
                "confirmed": True,
            }
        )

        self.assertEqual(HTTPStatus.ACCEPTED, captured["status"])
        self.assertEqual(
            "app.stability_test@1.1.0", captured["payload"]["execution"]["goal"]
        )
        self.assertTrue(self.store.terminal.wait(10))


if __name__ == "__main__":
    unittest.main()
