"""Bounded redaction for UI text included in model-facing summaries."""

from __future__ import annotations

import re


_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_MAINLAND_PHONE = re.compile(r"(?<!\d)(?:(?:\+?86)[ -]?)?1[3-9]\d{9}(?!\d)")
_MASKED_PHONE = re.compile(r"(?<![\d*])\d{2,}\*{2,}\d{2,}(?![\d*])")
_LONG_NUMERIC_IDENTIFIER = re.compile(r"(?<!\d)\d{12,19}(?!\d)")


def redact_ui_text(value: str) -> str:
    """Redact common identifiers before UI text enters a model prompt or task summary."""

    redacted = _EMAIL.sub("[REDACTED_EMAIL]", value)
    redacted = _MAINLAND_PHONE.sub("[REDACTED_PHONE]", redacted)
    redacted = _MASKED_PHONE.sub("[REDACTED_PHONE]", redacted)
    return _LONG_NUMERIC_IDENTIFIER.sub("[REDACTED_IDENTIFIER]", redacted)
