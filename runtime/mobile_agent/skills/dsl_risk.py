"""Risk derivation for declarative composite skills (ITER-0062, ADR-0021).

Lives in the skills layer: it composes the Tool Registry (tool → capability)
with the Capability Catalog (capability → risk), both of which sit below.
The DSL document's own risk declarations are display-only; consumers MUST use
this derived value so a document can never downgrade its effective risk.
"""

from __future__ import annotations

from mobile_agent.domain.action import RiskLevel
from mobile_agent.domain.capability import CapabilityCatalog
from mobile_agent.domain.errors import ErrorCategory, ErrorOutcome, MobileAgentError
from mobile_agent.domain.skill_dsl import (
    IfStep,
    LoopStep,
    SkillDslDocument,
    SkillStep,
    Step,
    ToolStep,
)
from mobile_agent.tools.runtime import ToolRegistry

_RISK_ORDER = (
    RiskLevel.LOW,
    RiskLevel.MEDIUM,
    RiskLevel.HIGH,
    RiskLevel.PROHIBITED,
)

# ADR-0021 Amendment 1：DSL 唯一允许引用的 Skill 集合（编译期常量，不接受
# 文档或 REST 传入扩展）。只含内置观察类 Skill；写类与自定义 Skill 不在其列。
DSL_SKILL_REFERENCE_WHITELIST: dict[str, RiskLevel] = {
    "device.performance.snapshot": RiskLevel.MEDIUM,
    "device.logs.collect": RiskLevel.MEDIUM,
}


def skill_reference_not_allowed(skill_id: str) -> MobileAgentError:
    return MobileAgentError(
        code="SKILL_REFERENCE_NOT_ALLOWED",
        category=ErrorCategory.POLICY,
        message="DSL 只能引用白名单内的内置观察类 Skill（ADR-0021 修订一）",
        outcome=ErrorOutcome.REJECTED,
        details={"skill_id": skill_id},
    )


def iter_tool_ids(document: SkillDslDocument) -> tuple[str, ...]:
    """All tool ids referenced by the document, in execution order."""

    collected: list[str] = []

    def _walk(steps: tuple[Step, ...] | tuple[ToolStep | SkillStep, ...]) -> None:
        for step in steps:
            if isinstance(step, ToolStep):
                collected.append(step.tool_id)
            elif isinstance(step, LoopStep):
                _walk(step.steps)
            elif isinstance(step, IfStep):
                _walk(step.then_steps)
                _walk(step.else_steps)

    _walk(document.steps)
    return tuple(collected)


def iter_skill_ids(document: SkillDslDocument) -> tuple[str, ...]:
    """All skill ids referenced by the document, in execution order."""

    collected: list[str] = []

    def _walk(steps: tuple[Step, ...] | tuple[ToolStep | SkillStep, ...]) -> None:
        for step in steps:
            if isinstance(step, SkillStep):
                collected.append(step.skill_id)
            elif isinstance(step, LoopStep):
                _walk(step.steps)
            elif isinstance(step, IfStep):
                _walk(step.then_steps)
                _walk(step.else_steps)

    _walk(document.steps)
    return tuple(collected)


def derive_skill_risk(document: SkillDslDocument) -> RiskLevel:
    """Composite risk = max of the referenced tools' and skills' risks.

    Also doubles as preflight validation: an unregistered tool raises the
    Tool Registry's lookup error, and a non-whitelisted skill reference raises
    SKILL_REFERENCE_NOT_ALLOWED — both before any device action can be planned.
    """

    registry = ToolRegistry()
    catalog = CapabilityCatalog()
    derived = RiskLevel.LOW
    for tool_id in iter_tool_ids(document):
        capability = catalog.get(registry.get(tool_id).capability)
        if _RISK_ORDER.index(capability.risk) > _RISK_ORDER.index(derived):
            derived = capability.risk
    for skill_id in iter_skill_ids(document):
        skill_risk = DSL_SKILL_REFERENCE_WHITELIST.get(skill_id)
        if skill_risk is None:
            raise skill_reference_not_allowed(skill_id)
        if _RISK_ORDER.index(skill_risk) > _RISK_ORDER.index(derived):
            derived = skill_risk
    return derived
