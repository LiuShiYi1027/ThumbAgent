"""Preview Agent Loop runner built on safe Tools and legacy Skills."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from mobile_agent.agent.planner import (
    AgentDecision,
    AgentDecisionType,
    AgentObservationSummary,
    Planner,
    validate_agent_tool_arguments,
    validate_finish_arguments,
)
from mobile_agent.agent.redaction import redact_ui_text
from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.domain.action import ActionResult
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.observation import Observation
from mobile_agent.domain.task import TaskRun, TaskStatus, TaskStep
from mobile_agent.evaluation import AgentGoalAcceptance
from mobile_agent.evidence.artifacts import ArtifactStore
from mobile_agent.skills.settings_navigate import SettingsScrollNavigateSkill
from mobile_agent.tools.runtime import ToolRuntime
from mobile_agent.ui.locator import UiLocator
from mobile_agent.ui.model import UiNode, UiSelector
from mobile_agent.ui.parser import UiHierarchyParser


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AgentRunner:
    """Run a bounded Observe-Plan-Act preview task."""

    _ALLOWED_SKILLS = frozenset({"settings.scroll_navigate"})
    _ALLOWED_TOOLS = frozenset(
        {
            "app.launch",
            "input.tap_element",
            "input.swipe",
            "navigation.back",
            "navigation.home",
        }
    )

    def __init__(
        self,
        adapter: DeviceAdapter,
        artifacts: ArtifactStore,
        planner: Planner,
        tools: ToolRuntime,
        settings_scroll_navigate: SettingsScrollNavigateSkill,
    ) -> None:
        self._adapter = adapter
        self._artifacts = artifacts
        self._planner = planner
        self._tools = tools
        self._settings_scroll_navigate = settings_scroll_navigate
        self._parser = UiHierarchyParser()
        self._locator = UiLocator()

    async def run(
        self,
        device_id: str,
        goal: str,
        confirmed: bool = False,
        max_rounds: int = 6,
        acceptance: AgentGoalAcceptance | None = None,
        execution_goal: str | None = None,
        goal_spec: dict[str, Any] | None = None,
        task_id: str | None = None,
        on_step: Callable[[TaskStep], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
        deadline_exceeded: Callable[[], bool] | None = None,
        deadline_seconds: float | None = None,
    ) -> TaskRun:
        """Run one preview Agent task and return an auditable report."""

        task_started_at = _now()
        task_id = task_id or f"task_{uuid.uuid4().hex}"
        if not isinstance(max_rounds, int) or isinstance(max_rounds, bool) or max_rounds < 1 or max_rounds > 6:
            failed = self._failed_task(
                task_id,
                device_id,
                goal,
                task_started_at,
                1,
                "INVALID_ARGUMENT",
                "max_rounds 必须在 1 到 6 之间",
                acceptance,
                goal_spec,
            )
            if on_step is not None:
                on_step(failed.steps[0])
            return failed

        acceptance_payload = acceptance.to_dict() if acceptance is not None else None
        planner_goal = execution_goal or goal
        steps: list[TaskStep] = []
        last_decision: AgentDecision | None = None
        last_action_feedback: dict[str, Any] | None = None
        pending_summary: AgentObservationSummary | None = None
        pending_decision: AgentDecision | None = None
        pending_round = 0
        pending_step_id = ""
        pending_step_started_at = task_started_at
        last_recoverable_error: MobileAgentError | None = None
        last_completed_summary: AgentObservationSummary | None = None
        last_completed_decision: AgentDecision | None = None
        try:
            for round_index in range(1, max_rounds + 1):
                self._raise_if_stopped(cancellation_requested, deadline_exceeded)
                step_started_at = _now()
                step_id = f"step_{uuid.uuid4().hex}"
                observation = await self._adapter.observe(device_id, self._artifacts)
                self._raise_if_stopped(cancellation_requested, deadline_exceeded)
                summary = self._summarize_observation(observation, last_action_feedback)
                pending_summary = summary
                pending_round = round_index
                pending_step_id = step_id
                pending_step_started_at = step_started_at
                decision = self._planner.decide(planner_goal, summary, round_index)
                self._raise_if_stopped(cancellation_requested, deadline_exceeded)
                last_decision = decision
                self._validate_decision(decision)
                pending_decision = decision
                self._reject_repeated_no_progress(decision, last_action_feedback)
                recoverable_error: MobileAgentError | None = None
                try:
                    round_result = await self._run_decision(
                        device_id, observation, decision, confirmed, acceptance
                    )
                except MobileAgentError as error:
                    if not self._is_recoverable_decision_error(decision, error):
                        raise
                    recoverable_error = error
                    last_recoverable_error = error
                    round_result = {
                        "action_feedback": self._recoverable_feedback(
                            decision, error, acceptance
                        )
                    }
                current_action_feedback = round_result.get("action_feedback")
                if recoverable_error is None:
                    last_recoverable_error = None
                step_result = {
                    "schema_version": "1.0.0",
                    "round": round_index,
                    "observation": summary.to_dict(),
                    "decision": decision.to_dict(),
                    "action_feedback": current_action_feedback,
                    "action_result": round_result.get("action_result"),
                    "skill_result": round_result.get("skill_result"),
                    "verified_node": round_result.get("verified_node"),
                }
                completed_at = _now()
                completed_step = TaskStep(
                        step_id=step_id,
                        sequence=round_index,
                        kind="agent_round",
                        name="agent.round",
                        status=(
                            TaskStatus.FAILED
                            if recoverable_error is not None
                            else TaskStatus.SUCCEEDED
                        ),
                        started_at=step_started_at,
                        completed_at=completed_at,
                        result=step_result,
                        error=(
                            recoverable_error.to_dict()
                            if recoverable_error is not None
                            else None
                        ),
                    )
                steps.append(completed_step)
                if on_step is not None:
                    on_step(completed_step)
                last_completed_summary = summary
                last_completed_decision = decision
                pending_summary = None
                pending_decision = None
                last_action_feedback = (
                    current_action_feedback if isinstance(current_action_feedback, dict) else None
                )
                self._raise_if_stopped(cancellation_requested, deadline_exceeded)
                if decision.decision_type is AgentDecisionType.RUN_SKILL:
                    skill_result = round_result.get("skill_result")
                    return TaskRun(
                        task_id=task_id,
                        task_type="agent.run",
                        device_id=device_id,
                        goal=goal,
                        status=TaskStatus.SUCCEEDED,
                        started_at=task_started_at,
                        completed_at=completed_at,
                        steps=tuple(steps),
                        evidence_summary={
                            "rounds": round_index,
                            "planner_id": decision.planner_id,
                            "legacy_skill_completed": True,
                            "verified_node": skill_result.get("verified_node")
                            if isinstance(skill_result, dict)
                            else None,
                        },
                        goal_spec=goal_spec,
                        goal_acceptance=acceptance_payload,
                        completion_source=(
                            "runtime_acceptance"
                            if acceptance is not None
                            else "skill_result"
                        ),
                        deadline_seconds=deadline_seconds,
                    )
                if (
                    decision.decision_type is AgentDecisionType.FINISH
                    and recoverable_error is None
                ):
                    return TaskRun(
                        task_id=task_id,
                        task_type="agent.run",
                        device_id=device_id,
                        goal=goal,
                        status=TaskStatus.SUCCEEDED,
                        started_at=task_started_at,
                        completed_at=completed_at,
                        steps=tuple(steps),
                        evidence_summary={
                            "rounds": round_index,
                            "planner_id": decision.planner_id,
                            "final_foreground_app": observation.foreground_app.to_dict(),
                            "verified_node": round_result.get("verified_node"),
                        },
                        goal_spec=goal_spec,
                        goal_acceptance=acceptance_payload,
                        completion_source=(
                            "runtime_acceptance"
                            if acceptance is not None
                            else "planner_finish"
                        ),
                        deadline_seconds=deadline_seconds,
                    )
            if last_recoverable_error is not None:
                completed_at = _now()
                error_dict = last_recoverable_error.to_dict()
                return TaskRun(
                    task_id=task_id,
                    task_type="agent.run",
                    device_id=device_id,
                    goal=goal,
                    status=TaskStatus.FAILED,
                    started_at=task_started_at,
                    completed_at=completed_at,
                    steps=tuple(steps),
                    evidence_summary={
                        "rounds_completed": len(steps),
                        "last_observation": last_completed_summary.to_dict()
                        if last_completed_summary is not None
                        else None,
                        "last_decision": last_completed_decision.to_dict()
                        if last_completed_decision is not None
                        else None,
                    },
                    error=error_dict,
                    goal_spec=goal_spec,
                    goal_acceptance=acceptance_payload,
                    deadline_seconds=deadline_seconds,
                )
            raise MobileAgentError(
                code="NO_PROGRESS",
                category=ErrorCategory.EXECUTION,
                message="Agent 在轮次预算内未完成目标",
                details={
                    "max_rounds": max_rounds,
                    "last_decision": last_decision.to_dict() if last_decision else None,
                },
            )
        except MobileAgentError as error:
            completed_at = _now()
            error_dict = error.to_dict()
            if error.code in {"TASK_CANCELLED", "TASK_DEADLINE_EXCEEDED"}:
                return TaskRun(
                    task_id=task_id,
                    task_type="agent.run",
                    device_id=device_id,
                    goal=goal,
                    status=(
                        TaskStatus.CANCELLED
                        if error.code == "TASK_CANCELLED"
                        else TaskStatus.TIMED_OUT
                    ),
                    started_at=task_started_at,
                    completed_at=completed_at,
                    steps=tuple(steps),
                    evidence_summary={"rounds_completed": len(steps)},
                    error=error_dict,
                    goal_spec=goal_spec,
                    goal_acceptance=acceptance_payload,
                    deadline_seconds=deadline_seconds,
                )
            failed_result = None
            if pending_summary is not None and pending_decision is not None:
                failed_result = {
                    "schema_version": "1.0.0",
                    "round": pending_round,
                    "observation": pending_summary.to_dict(),
                    "decision": pending_decision.to_dict(),
                    "action_feedback": None,
                    "action_result": None,
                    "skill_result": None,
                    "verified_node": None,
                }
            failed_step = TaskStep(
                    step_id=pending_step_id or f"step_{uuid.uuid4().hex}",
                    sequence=len(steps) + 1,
                    kind="agent_round",
                    name="agent.round",
                    status=TaskStatus.FAILED,
                    started_at=pending_step_started_at if pending_step_id else completed_at,
                    completed_at=completed_at,
                    result=failed_result,
                    error=error_dict,
                )
            steps.append(failed_step)
            if on_step is not None:
                on_step(failed_step)
            return TaskRun(
                task_id=task_id,
                task_type="agent.run",
                device_id=device_id,
                goal=goal,
                status=TaskStatus.FAILED,
                started_at=task_started_at,
                completed_at=completed_at,
                steps=tuple(steps),
                evidence_summary={
                    "rounds_completed": len(steps) - 1,
                    "last_observation": pending_summary.to_dict()
                    if pending_summary is not None
                    else None,
                    "last_decision": pending_decision.to_dict()
                    if pending_decision is not None
                    else None,
                },
                error=error_dict,
                goal_spec=goal_spec,
                goal_acceptance=acceptance_payload,
                deadline_seconds=deadline_seconds,
            )

    @staticmethod
    def _raise_if_stopped(
        cancellation_requested: Callable[[], bool] | None,
        deadline_exceeded: Callable[[], bool] | None,
    ) -> None:
        if cancellation_requested is not None and cancellation_requested():
            raise MobileAgentError(
                code="TASK_CANCELLED",
                category=ErrorCategory.EXECUTION,
                message="任务已按用户请求取消",
            )
        if deadline_exceeded is not None and deadline_exceeded():
            raise MobileAgentError(
                code="TASK_DEADLINE_EXCEEDED",
                category=ErrorCategory.EXECUTION,
                message="任务已超过总执行时间预算",
                suggested_action="提高任务 deadline 或缩小目标范围后重试",
            )

    def _summarize_observation(
        self,
        observation: Observation,
        last_action_feedback: dict[str, Any] | None = None,
    ) -> AgentObservationSummary:
        ui_summary, total_candidates = self._ui_summary(observation)
        return AgentObservationSummary(
            observation_id=observation.observation_id,
            foreground_app=observation.foreground_app.to_dict(),
            device_state=observation.device_state.value,
            ui_summary=tuple(ui_summary),
            ui_summary_total_candidates=total_candidates,
            ui_summary_truncated=total_candidates > len(ui_summary),
            last_action_feedback=last_action_feedback,
        )

    def _ui_summary(self, observation: Observation) -> tuple[list[dict[str, Any]], int]:
        nodes = self._nodes_from_observation(observation)
        nodes_by_id = {node.node_id: node for node in nodes}
        candidates: list[tuple[int, int, int, int, dict[str, Any]]] = []
        seen: set[tuple[str, str, str]] = set()
        for node in nodes:
            if not node.visible:
                continue
            text = redact_ui_text(node.text.strip())
            content_description = redact_ui_text(node.content_description.strip())
            resource_id = node.resource_id.strip()
            if not text and not content_description:
                continue
            key = (text, content_description, resource_id)
            if key in seen:
                continue
            seen.add(key)
            clickable_ancestor = self._has_clickable_ancestor(node, nodes_by_id)
            actionable = node.clickable or clickable_ancestor
            if text:
                priority = 0 if actionable else 1
            else:
                priority = 2 if actionable else 3
            candidates.append(
                (
                    priority,
                    node.bounds.top,
                    node.bounds.left,
                    node.depth,
                    {
                        "text": text[:120],
                        "content_description": content_description[:120],
                        "resource_id": resource_id[:160],
                        "class_name": node.class_name[:120],
                        "clickable": node.clickable,
                        "clickable_ancestor": clickable_ancestor,
                        "enabled": node.enabled,
                    },
                )
            )
        candidates.sort(key=lambda item: item[:4])
        return [item[4] for item in candidates[:30]], len(candidates)

    @staticmethod
    def _has_clickable_ancestor(node: UiNode, nodes_by_id: dict[str, UiNode]) -> bool:
        parent_id = node.parent_id
        remaining_depth = 64
        while parent_id is not None and remaining_depth > 0:
            parent = nodes_by_id.get(parent_id)
            if parent is None:
                return False
            if parent.clickable and parent.visible and parent.enabled:
                return True
            parent_id = parent.parent_id
            remaining_depth -= 1
        return False

    def _validate_decision(self, decision: AgentDecision) -> None:
        if decision.decision_type is AgentDecisionType.RUN_SKILL:
            if decision.skill_id not in self._ALLOWED_SKILLS:
                raise MobileAgentError(
                    code="ACTION_REJECTED_BY_POLICY",
                    category=ErrorCategory.POLICY,
                    message="Planner 决策不在 Agent Preview Skill allowlist 内",
                    details={"skill_id": decision.skill_id},
                )
            return
        if decision.decision_type is AgentDecisionType.RUN_TOOL:
            if decision.tool_id not in self._ALLOWED_TOOLS:
                raise MobileAgentError(
                    code="ACTION_REJECTED_BY_POLICY",
                    category=ErrorCategory.POLICY,
                    message="Planner 决策不在 Agent Preview Tool allowlist 内",
                    details={"tool_id": decision.tool_id},
                )
            validate_agent_tool_arguments(decision.tool_id, decision.arguments)
            return
        if decision.decision_type is AgentDecisionType.FINISH:
            validate_finish_arguments(decision.arguments)
            return
        raise MobileAgentError(
            code="MODEL_OUTPUT_INVALID",
            category=ErrorCategory.VALIDATION,
            message="Planner 输出了不支持的决策类型",
            details={"decision_type": decision.decision_type.value},
        )

    @staticmethod
    def _reject_repeated_no_progress(
        decision: AgentDecision,
        last_action_feedback: dict[str, Any] | None,
    ) -> None:
        if decision.decision_type not in {
            AgentDecisionType.RUN_TOOL,
            AgentDecisionType.FINISH,
        } or not last_action_feedback:
            return
        if last_action_feedback.get("effect") != "unchanged":
            return
        decision_target = (
            decision.tool_id
            if decision.decision_type is AgentDecisionType.RUN_TOOL
            else "finish"
        )
        if decision_target != last_action_feedback.get("tool_id"):
            return
        if decision.arguments != last_action_feedback.get("arguments"):
            return
        raise MobileAgentError(
            code="NO_PROGRESS",
            category=ErrorCategory.EXECUTION,
            message="Planner 重复了未产生页面进展的相同动作",
            suggested_action="调整动作参数或尝试相反的导航方向",
            details={"tool_id": decision.tool_id, "arguments": decision.arguments},
        )

    async def _run_decision(
        self,
        device_id: str,
        observation: Observation,
        decision: AgentDecision,
        confirmed: bool,
        acceptance: AgentGoalAcceptance | None,
    ) -> dict[str, Any]:
        if decision.decision_type is AgentDecisionType.RUN_SKILL:
            skill_result = await self._run_skill_decision(device_id, decision, confirmed)
            result: dict[str, Any] = {"skill_result": skill_result.to_dict()}
            if acceptance is not None:
                verification_observation = await self._adapter.observe(
                    device_id, self._artifacts
                )
                verified = self._verify_goal_acceptance(
                    verification_observation, acceptance
                )
                result["verified_node"] = verified.to_dict() if verified else None
            return result
        if decision.decision_type is AgentDecisionType.RUN_TOOL:
            action = await self._tools.execute(
                decision.tool_id,
                device_id,
                decision.arguments,
                confirmed=confirmed,
            )
            return {
                "action_result": action.to_dict(),
                "action_feedback": self._action_feedback(action, decision.arguments),
            }
        if decision.decision_type is AgentDecisionType.FINISH:
            if acceptance is not None:
                verified_node = self._verify_goal_acceptance(observation, acceptance)
                return {
                    "verified_node": verified_node.to_dict() if verified_node else None
                }
            verified_node = self._verify_finish(observation, decision.arguments)
            return {"verified_node": verified_node.to_dict()}
        raise AssertionError("unreachable decision type")

    @staticmethod
    def _action_feedback(action: ActionResult, arguments: dict[str, Any]) -> dict[str, Any]:
        foreground_changed = (
            action.before.foreground_app.app_id != action.after.foreground_app.app_id
            or action.before.foreground_app.activity != action.after.foreground_app.activity
        )
        ui_changed = action.before.ui_tree.artifact.sha256 != action.after.ui_tree.artifact.sha256
        effect = "changed" if foreground_changed or ui_changed else "unchanged"
        message = (
            "页面产生了可观察变化，可基于新 Observation 继续规划。"
            if effect == "changed"
            else "页面未产生可观察变化；请调整动作、参数或导航方向。"
        )
        return {
            "schema_version": "1.0.0",
            "tool_id": action.tool_id,
            "arguments": dict(arguments),
            "effect": effect,
            "basis": "ui_tree_and_foreground",
            "message": message,
        }

    async def _run_skill_decision(
        self, device_id: str, decision: AgentDecision, confirmed: bool
    ) -> Any:
        arguments = decision.arguments
        target = arguments.get("target_selector")
        expected = arguments.get("expected_selector")
        if not isinstance(target, dict) or not isinstance(expected, dict):
            raise MobileAgentError(
                code="MODEL_OUTPUT_INVALID",
                category=ErrorCategory.VALIDATION,
                message="Planner 输出缺少有效 Selector",
            )
        return await self._settings_scroll_navigate.invoke(
            device_id,
            target,
            expected,
            direction=_string_arg(arguments, "direction", "up"),
            max_scrolls=_int_arg(arguments, "max_scrolls", 3),
            confirmed=confirmed,
            distance_percent=_float_arg(arguments, "distance_percent", 0.8),
            duration_ms=_int_arg(arguments, "duration_ms", 800),
            settle_seconds=_float_arg(arguments, "settle_seconds", 0.8),
        )

    def _verify_finish(self, observation: Observation, arguments: dict[str, Any]) -> UiNode:
        expected_foreground = arguments.get("expected_foreground_app")
        if isinstance(expected_foreground, dict):
            actual = observation.foreground_app
            app_id = expected_foreground.get("app_id")
            activity = expected_foreground.get("activity")
            if (isinstance(app_id, str) and actual.app_id != app_id) or (
                isinstance(activity, str) and actual.activity != activity
            ):
                raise MobileAgentError(
                    code="TARGET_NOT_FOUND",
                    category=ErrorCategory.DEVICE,
                    message="finish 前台应用验证未通过",
                    details={
                        "expected_app_id": app_id or "",
                        "expected_activity": activity or "",
                        "actual_app_id": actual.app_id,
                        "actual_activity": actual.activity,
                    },
                )
        raw_selector = arguments.get("expected_selector")
        if not isinstance(raw_selector, dict):
            raise MobileAgentError(
                code="MODEL_OUTPUT_INVALID",
                category=ErrorCategory.VALIDATION,
                message="finish 决策必须提供 expected_selector",
            )
        selector = UiSelector.from_dict(raw_selector)
        matches = self._locator.find_all(self._nodes_from_observation(observation), selector)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise MobileAgentError(
                code="TARGET_AMBIGUOUS",
                category=ErrorCategory.DEVICE,
                message="finish 验证目标匹配不唯一",
                details={
                    "match_count": len(matches),
                    "candidates": [
                        {
                            "resource_id": node.resource_id[:160],
                            "class_name": node.class_name[:120],
                        }
                        for node in matches[:10]
                    ],
                },
            )
        raise MobileAgentError(
            code="TARGET_NOT_FOUND",
            category=ErrorCategory.DEVICE,
            message="finish 验证未找到目标 UI 元素",
        )

    def _verify_goal_acceptance(
        self, observation: Observation, acceptance: AgentGoalAcceptance
    ) -> UiNode | None:
        actual = observation.foreground_app
        if (
            acceptance.foreground_app_id is not None
            and actual.app_id != acceptance.foreground_app_id
        ):
            raise MobileAgentError(
                code="TARGET_NOT_FOUND",
                category=ErrorCategory.DEVICE,
                message="Runtime 成功条件的前台应用验证未通过",
                details={
                    "verification_source": "runtime_acceptance",
                    "expected_app_id": acceptance.foreground_app_id,
                    "actual_app_id": actual.app_id,
                },
            )
        if (
            acceptance.foreground_activity is not None
            and actual.activity != acceptance.foreground_activity
        ):
            raise MobileAgentError(
                code="TARGET_NOT_FOUND",
                category=ErrorCategory.DEVICE,
                message="Runtime 成功条件的 Activity 验证未通过",
                details={
                    "verification_source": "runtime_acceptance",
                    "expected_activity": acceptance.foreground_activity,
                    "actual_activity": actual.activity,
                },
            )
        selector = acceptance.expected_selector
        if selector is None:
            return None
        matches = self._locator.find_all(self._nodes_from_observation(observation), selector)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise MobileAgentError(
                code="TARGET_AMBIGUOUS",
                category=ErrorCategory.DEVICE,
                message="Runtime 成功条件的 UI Selector 匹配不唯一",
                details={
                    "verification_source": "runtime_acceptance",
                    "match_count": len(matches),
                    "candidates": [
                        {
                            "resource_id": node.resource_id[:160],
                            "class_name": node.class_name[:120],
                        }
                        for node in matches[:10]
                    ],
                },
            )
        raise MobileAgentError(
            code="TARGET_NOT_FOUND",
            category=ErrorCategory.DEVICE,
            message="Runtime 成功条件未找到目标 UI 元素",
            details={"verification_source": "runtime_acceptance"},
        )

    @staticmethod
    def _is_recoverable_decision_error(
        decision: AgentDecision, error: MobileAgentError
    ) -> bool:
        recoverable_codes = {
            "TARGET_NOT_FOUND",
            "TARGET_AMBIGUOUS",
            "TARGET_NOT_CLICKABLE",
            "TARGET_NOT_INTERACTABLE",
            "TARGET_OUT_OF_BOUNDS",
        }
        return (
            decision.decision_type in {
                AgentDecisionType.RUN_TOOL,
                AgentDecisionType.FINISH,
            }
            and error.code in recoverable_codes
        )

    @staticmethod
    def _recoverable_feedback(
        decision: AgentDecision,
        error: MobileAgentError,
        acceptance: AgentGoalAcceptance | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "tool_id": decision.tool_id or "finish",
            "arguments": dict(decision.arguments),
            "effect": "unchanged",
            "basis": (
                "runtime_acceptance"
                if decision.decision_type is AgentDecisionType.FINISH
                and acceptance is not None
                else (
                    "finish_verification"
                    if decision.decision_type is AgentDecisionType.FINISH
                    else "pre_dispatch_validation"
                )
            ),
            "message": "本轮未产生设备副作用；请根据错误和候选信息收紧目标或调整导航。",
            "error_code": error.code,
            "details": dict(error.details),
        }

    def _nodes_from_observation(self, observation: Observation) -> list[UiNode]:
        path = self._artifacts.resolve(observation.ui_tree.artifact.relative_path)
        return self._parser.parse(path.read_bytes())

    def _failed_task(
        self,
        task_id: str,
        device_id: str,
        goal: str,
        started_at: str,
        sequence: int,
        code: str,
        message: str,
        acceptance: AgentGoalAcceptance | None = None,
        goal_spec: dict[str, Any] | None = None,
    ) -> TaskRun:
        completed_at = _now()
        error = MobileAgentError(code=code, category=ErrorCategory.VALIDATION, message=message)
        error_dict = error.to_dict()
        step = TaskStep(
            step_id=f"step_{uuid.uuid4().hex}",
            sequence=sequence,
            kind="agent_round",
            name="agent.round",
            status=TaskStatus.FAILED,
            started_at=started_at,
            completed_at=completed_at,
            error=error_dict,
        )
        return TaskRun(
            task_id=task_id,
            task_type="agent.run",
            device_id=device_id,
            goal=goal,
            status=TaskStatus.FAILED,
            started_at=started_at,
            completed_at=completed_at,
            steps=(step,),
            evidence_summary={},
            error=error_dict,
            goal_spec=goal_spec,
            goal_acceptance=acceptance.to_dict() if acceptance is not None else None,
        )


def _string_arg(arguments: dict[str, Any], name: str, default: str) -> str:
    value = arguments.get(name, default)
    if not isinstance(value, str):
        raise MobileAgentError(
            code="MODEL_OUTPUT_INVALID",
            category=ErrorCategory.VALIDATION,
            message="Planner 输出参数类型无效",
            details={"argument": name},
        )
    return value


def _int_arg(arguments: dict[str, Any], name: str, default: int) -> int:
    value = arguments.get(name, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise MobileAgentError(
            code="MODEL_OUTPUT_INVALID",
            category=ErrorCategory.VALIDATION,
            message="Planner 输出参数类型无效",
            details={"argument": name},
        )
    return value


def _float_arg(arguments: dict[str, Any], name: str, default: float) -> float:
    value = arguments.get(name, default)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise MobileAgentError(
            code="MODEL_OUTPUT_INVALID",
            category=ErrorCategory.VALIDATION,
            message="Planner 输出参数类型无效",
            details={"argument": name},
        )
    return float(value)
