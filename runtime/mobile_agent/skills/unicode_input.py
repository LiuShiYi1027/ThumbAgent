"""Deterministic input.unicode_text@1 Skill (ADR-0019)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from mobile_agent.domain.unicode_input import UnicodeInputResult
from mobile_agent.tools.unicode_input import UnicodeTextInputTool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class UnicodeTextInputSkill:
    """Input verified Unicode text into one editable field via the Helper IME."""

    skill_id = "input.unicode_text"
    version = "1.0.0"

    def __init__(self, tool: UnicodeTextInputTool) -> None:
        self._tool = tool

    async def invoke(
        self,
        device_id: str,
        selector: dict[str, Any],
        text: str,
        confirmed: bool = False,
        submit: str | None = None,
    ) -> UnicodeInputResult:
        started_at = _now()
        captured = await self._tool.execute(
            device_id, selector, text, confirmed, submit
        )
        node = captured.match.target_node
        return UnicodeInputResult(
            skill_call_id=f"skillcall_{uuid.uuid4().hex}",
            device_id=device_id,
            field_selector={
                "strategy": captured.match.selector.strategy.value,
                "value": captured.match.selector.value,
                "match": captured.match.selector.match.value,
            },
            field_package=node.package,
            field_resource_id=node.resource_id or None,
            text_length=captured.text_length,
            text_sha256=captured.text_sha256,
            ime_helper_id=captured.helper_ime_id,
            ime_previous_id=captured.previous_ime_id,
            evidence_refs=captured.evidence_refs,
            started_at=started_at,
            completed_at=_now(),
            submitted=captured.submitted,
        )
