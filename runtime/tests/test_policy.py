from __future__ import annotations

import unittest

from mobile_agent.domain.action import RiskLevel
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.policy.engine import PolicyEngine


class PolicyEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = PolicyEngine()

    def test_low_is_allowed_and_medium_requires_confirmation(self) -> None:
        self.policy.authorize(RiskLevel.LOW)
        with self.assertRaises(MobileAgentError) as raised:
            self.policy.authorize(RiskLevel.MEDIUM)
        self.assertEqual("CONFIRMATION_REQUIRED", raised.exception.code)
        self.policy.authorize(RiskLevel.MEDIUM, confirmed=True)

    def test_high_and_prohibited_are_rejected_even_when_confirmed(self) -> None:
        for risk in (RiskLevel.HIGH, RiskLevel.PROHIBITED):
            with self.assertRaises(MobileAgentError) as raised:
                self.policy.authorize(risk, confirmed=True)
            self.assertEqual("ACTION_REJECTED_BY_POLICY", raised.exception.code)

