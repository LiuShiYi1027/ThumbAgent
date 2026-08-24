"""Parser for bounded `dumpsys notification` snapshots.

The parser keeps only package, an optional platform-exposed title and an
optional post timestamp per record. Notification body text and every other
field are discarded here inside the Adapter and never leave it.
"""

from __future__ import annotations

import re

_RECORD_START = re.compile(r"NotificationRecord\(.*?\bpkg=([A-Za-z0-9_.]+)")
_TITLE = re.compile(r'android\.title=String [\(\[](.*?)[\)\]]')
# 部分厂商 ROM（如 MagicOS）在 dumpsys 中脱敏 extras，标题只剩长度标记
# `String [length=N]`；该标记不是标题内容，必须按缺失处理，不能当作标题返回。
_REDACTED_LENGTH = re.compile(r"length=\d+")
_WHEN = re.compile(r"\b(?:when|postTime|mPostTime)=(\d{10,14})\b")
_SECTION = re.compile(r"Notification List", re.IGNORECASE)


def parse_notification_records(
    output: str,
) -> list[tuple[str, str | None, int | None]] | None:
    """Parse one dumpsys notification snapshot.

    Returns a list of ``(package, title, posted_epoch_ms)`` tuples, an empty
    list when the service reports zero notifications, or None when the output
    has no recognizable structure (vendor format change, truncated dump).
    """

    section = _SECTION.search(output)
    if section is None:
        return None
    body = output[section.end() :]

    records: list[tuple[str, str | None, int | None]] = []
    current_package: str | None = None
    current_title: str | None = None
    current_posted: int | None = None

    def flush() -> None:
        nonlocal current_package, current_title, current_posted
        if current_package is not None:
            records.append((current_package, current_title, current_posted))
        current_package = None
        current_title = None
        current_posted = None

    for line in body.splitlines():
        record_match = _RECORD_START.search(line)
        if record_match:
            flush()
            current_package = record_match.group(1)
            continue
        if current_package is None:
            continue
        if current_title is None:
            title_match = _TITLE.search(line)
            if title_match:
                value = title_match.group(1).strip()
                if not _REDACTED_LENGTH.fullmatch(value):
                    current_title = value
                continue
        if current_posted is None:
            when_match = _WHEN.search(line)
            if when_match:
                current_posted = int(when_match.group(1))
    flush()
    return records
