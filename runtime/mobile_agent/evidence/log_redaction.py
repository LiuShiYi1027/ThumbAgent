"""Conservative redaction for untrusted device diagnostic logs."""

from __future__ import annotations

import re


_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
        "[REDACTED_EMAIL]",
    ),
    (
        re.compile(r"(?<!\d)(?:(?:\+?86)[ -]?)?1[3-9]\d{9}(?!\d)"),
        "[REDACTED_PHONE]",
    ),
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
        "[REDACTED_JWT]",
    ),
    (
        re.compile(
            r"(?i)\b(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token)"
            r"\s*[:=]\s*(?:bearer\s+)?[^\s,;]+"
        ),
        r"\1=[REDACTED_SECRET]",
    ),
    (re.compile(r"(?<!\d)\d{12,19}(?!\d)"), "[REDACTED_IDENTIFIER]"),
)


def redact_device_log(data: bytes) -> tuple[bytes, int]:
    """Decode, normalize and redact common identifiers without retaining originals."""

    text = data.decode("utf-8", errors="replace").replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    replacements = 0
    for pattern, replacement in _PATTERNS:
        text, count = pattern.subn(replacement, text)
        replacements += count
    return text.encode("utf-8"), replacements
