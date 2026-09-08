"""Conservative redaction for untrusted device diagnostic logs."""

from __future__ import annotations

import re
from typing import Any

# 崩溃/ANR 判定只认保守的 AOSP 标准签名子集；未命中不等于无崩溃。
CRASH_SIGNATURE_MARKERS: tuple[tuple[str, str], ...] = (
    ("crash", "FATAL EXCEPTION"),
    ("anr", "ANR in "),
)

# 与 device-log-capture-result.schema.json 的 crash_check 上限保持一致。
MAX_CRASH_SIGNATURES = 20
MAX_CRASH_SUMMARY_LENGTH = 120


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


def scan_crash_signatures(text: str) -> dict[str, Any]:
    """Scan redacted log text for the fixed AOSP crash/ANR signature markers.

    只能传入脱敏后的文本：summary 直接取自命中行，绝不携带原始日志。
    """

    lines = text.splitlines()
    signatures: list[dict[str, str]] = []
    for line in lines:
        for kind, marker in CRASH_SIGNATURE_MARKERS:
            if marker in line:
                signatures.append(
                    {"kind": kind, "summary": line.strip()[:MAX_CRASH_SUMMARY_LENGTH]}
                )
                break
        if len(signatures) >= MAX_CRASH_SIGNATURES:
            break
    return {"checked_lines": len(lines), "signatures": signatures}
