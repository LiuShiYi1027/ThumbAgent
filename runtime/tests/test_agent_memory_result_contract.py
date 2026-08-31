"""Contract tests for agent working memory & task results (ITER-0061).

覆盖跨语言契约的两个消费端：Schema 真源结构断言 + Python 校验层与
Schema 上限的一致性（正向、反向、无效样本）。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "contracts" / "schemas"


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text())


class AgentMemoryResultContractTest(unittest.TestCase):
    def test_decision_scratchpad_is_optional_and_bounded(self) -> None:
        schema = _load_schema("agent-decision.schema.json")

        self.assertNotIn("scratchpad", schema["required"])
        scratchpad = schema["properties"]["scratchpad"]
        self.assertEqual("string", scratchpad["type"])
        self.assertEqual(1024, scratchpad["maxLength"])

    def test_finish_criteria_answer_is_optional_payload(self) -> None:
        schema = _load_schema("agent-finish-criteria.schema.json")

        # 验收语义不变：expected_selector 仍必填；answer 只是结果载荷。
        self.assertEqual(["expected_selector"], schema["required"])
        answer = schema["properties"]["answer"]
        self.assertEqual(1, answer["minLength"])
        self.assertEqual(2000, answer["maxLength"])

    def test_observation_summary_carries_nullable_scratchpad(self) -> None:
        schema = _load_schema("agent-observation-summary.schema.json")

        self.assertNotIn("scratchpad", schema["required"])
        kinds = {
            entry.get("type")
            for entry in schema["properties"]["scratchpad"]["oneOf"]
        }
        self.assertEqual({"string", "null"}, kinds)

    def test_task_run_result_requires_answer(self) -> None:
        schema = _load_schema("task-run.schema.json")

        self.assertNotIn("result", schema["required"])
        result = schema["properties"]["result"]
        self.assertEqual(["answer"], result["required"])
        self.assertFalse(result["additionalProperties"])
        self.assertEqual(2000, result["properties"]["answer"]["maxLength"])

    def test_generated_typescript_in_sync(self) -> None:
        generated = ROOT / "contracts" / "generated" / "typescript"

        decision = (generated / "agent-decision.ts").read_text()
        self.assertIn("scratchpad?: string", decision)
        summary = (generated / "agent-observation-summary.ts").read_text()
        self.assertIn("scratchpad?: string | null", summary)
        task_run = (generated / "task-run.ts").read_text()
        self.assertIn("answer: string", task_run)


class AgentMemoryResultPythonParityTest(unittest.TestCase):
    """Python 校验层与 Schema 上限一致（双语言消费端的反向样本）。"""

    def test_scratchpad_round_trip(self) -> None:
        from mobile_agent.agent.planner import parse_llm_decision_payload

        decision = parse_llm_decision_payload(
            {
                "decision_type": "run_tool",
                "tool_id": "navigation.back",
                "arguments": {},
                "reason": "记录已见价格后返回。",
                "scratchpad": "京东 iPhone 17 到手价 ¥5999",
            },
            "test.planner",
        )

        self.assertEqual("京东 iPhone 17 到手价 ¥5999", decision.scratchpad)
        self.assertEqual("京东 iPhone 17 到手价 ¥5999", decision.to_dict()["scratchpad"])

    def test_scratchpad_absent_means_no_update(self) -> None:
        from mobile_agent.agent.planner import parse_llm_decision_payload

        decision = parse_llm_decision_payload(
            {"decision_type": "run_tool", "tool_id": "navigation.back", "arguments": {}},
            "test.planner",
        )

        self.assertIsNone(decision.scratchpad)
        self.assertNotIn("scratchpad", decision.to_dict())

    def test_scratchpad_over_limit_is_rejected(self) -> None:
        from mobile_agent.agent.planner import parse_llm_decision_payload
        from mobile_agent.domain.errors import MobileAgentError

        with self.assertRaises(MobileAgentError) as caught:
            parse_llm_decision_payload(
                {
                    "decision_type": "run_tool",
                    "tool_id": "navigation.back",
                    "arguments": {},
                    "scratchpad": "x" * 1025,
                },
                "test.planner",
            )
        self.assertEqual("MODEL_OUTPUT_INVALID", caught.exception.code)

    def test_scratchpad_non_string_is_rejected(self) -> None:
        from mobile_agent.agent.planner import parse_llm_decision_payload
        from mobile_agent.domain.errors import MobileAgentError

        with self.assertRaises(MobileAgentError):
            parse_llm_decision_payload(
                {
                    "decision_type": "run_tool",
                    "tool_id": "navigation.back",
                    "arguments": {},
                    "scratchpad": 42,
                },
                "test.planner",
            )

    def test_finish_answer_is_accepted(self) -> None:
        from mobile_agent.agent.planner import validate_finish_arguments

        validate_finish_arguments(
            {
                "expected_selector": {"strategy": "text", "value": "价格"},
                "answer": "京东 iPhone 17 到手价 ¥5999",
            }
        )

    def test_finish_answer_invalid_shapes_are_rejected(self) -> None:
        from mobile_agent.agent.planner import validate_finish_arguments
        from mobile_agent.domain.errors import MobileAgentError

        base = {"expected_selector": {"strategy": "text", "value": "价格"}}
        for bad in ("", "x" * 2001, 42):
            with self.assertRaises(MobileAgentError, msg=f"answer={bad!r}"):
                validate_finish_arguments({**base, "answer": bad})

    def test_task_run_result_serialization(self) -> None:
        from mobile_agent.domain.task import TaskRun, TaskStatus

        run = TaskRun(
            task_id="task_" + "0" * 32,
            task_type="agent.run",
            device_id="adb:fake",
            goal="查价",
            status=TaskStatus.SUCCEEDED,
            started_at="2026-08-31T00:00:00Z",
            completed_at="2026-08-31T00:01:00Z",
            steps=(),
            evidence_summary={},
            error=None,
            result={"answer": "¥5999"},
        )

        self.assertEqual({"answer": "¥5999"}, run.to_dict()["result"])
        # 缺省（纯操作类任务）不携带 result 键。
        without = TaskRun(
            task_id="task_" + "0" * 32,
            task_type="agent.run",
            device_id="adb:fake",
            goal="操作",
            status=TaskStatus.SUCCEEDED,
            started_at="2026-08-31T00:00:00Z",
            completed_at="2026-08-31T00:01:00Z",
            steps=(),
            evidence_summary={},
            error=None,
        )
        self.assertNotIn("result", without.to_dict())


if __name__ == "__main__":
    unittest.main()
