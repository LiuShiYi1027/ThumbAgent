"""Risk derivation for declarative composite skills (ITER-0062, ADR-0021).

Lives in the skills layer: it composes the Tool Registry (tool → capability)
with the Capability Catalog (capability → risk), both of which sit below.
The DSL document's own risk declarations are display-only; consumers MUST use
this derived value so a document can never downgrade its effective risk.
"""

from __future__ import annotations

from mobile_agent.domain.action import RiskLevel
from mobile_agent.domain.capability import CapabilityCatalog
from mobile_agent.domain.skill_dsl import IfStep, LoopStep, SkillDslDocument, Step, ToolStep
from mobile_agent.tools.runtime import ToolRegistry

_RISK_ORDER = (
    RiskLevel.LOW,
    RiskLevel.MEDIUM,
    RiskLevel.HIGH,
    RiskLevel.PROHIBITED,
)


def iter_tool_ids(document: SkillDslDocument) -> tuple[str, ...]:
    """All tool ids referenced by the document, in execution order."""

    collected: list[str] = []

    def _walk(steps: tuple[Step, ...] | tuple[ToolStep, ...]) -> None:
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


def derive_skill_risk(document: SkillDslDocument) -> RiskLevel:
    """Composite risk = max of the referenced tools' capability risks.

    Also doubles as preflight validation: an unregistered tool raises the
    Tool Registry's lookup error before any device action can be planned.
    """

    registry = ToolRegistry()
    catalog = CapabilityCatalog()
    derived = RiskLevel.LOW
    for tool_id in iter_tool_ids(document):
        capability = catalog.get(registry.get(tool_id).capability)
        if _RISK_ORDER.index(capability.risk) > _RISK_ORDER.index(derived):
            derived = capability.risk
    return derived
