"""Minimal deny-by-default action policy."""

from __future__ import annotations

from mobile_agent.domain.action import RiskLevel
from mobile_agent.domain.errors import ErrorCategory, ErrorOutcome, MobileAgentError


class PolicyEngine:
    def authorize(self, risk: RiskLevel, confirmed: bool = False) -> None:
        if risk is RiskLevel.LOW:
            return
        if risk is RiskLevel.MEDIUM and confirmed:
            return
        if risk is RiskLevel.MEDIUM:
            raise MobileAgentError(
                code="CONFIRMATION_REQUIRED",
                category=ErrorCategory.POLICY,
                message="该设备动作需要明确确认",
                outcome=ErrorOutcome.REJECTED,
            )
        raise MobileAgentError(
            code="ACTION_REJECTED_BY_POLICY",
            category=ErrorCategory.POLICY,
            message="当前策略禁止执行该设备动作",
            outcome=ErrorOutcome.REJECTED,
        )

