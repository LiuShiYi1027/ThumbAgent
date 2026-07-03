"""Stable domain errors shared by runtime interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
    VALIDATION = "validation"
    DEVICE = "device"
    CAPABILITY = "capability"
    POLICY = "policy"
    EXECUTION = "execution"
    STORAGE = "storage"
    INTERNAL = "internal"


class ErrorOutcome(str, Enum):
    KNOWN_FAILURE = "known_failure"
    UNKNOWN_OUTCOME = "unknown_outcome"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class MobileAgentError(Exception):
    """A safe, structured error crossing application boundaries."""

    code: str
    category: ErrorCategory
    message: str
    retryable: bool = False
    outcome: ErrorOutcome = ErrorOutcome.KNOWN_FAILURE
    suggested_action: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category.value,
            "message": self.message,
            "retryable": self.retryable,
            "outcome": self.outcome.value,
            "suggested_action": self.suggested_action,
            "details": self.details,
        }

