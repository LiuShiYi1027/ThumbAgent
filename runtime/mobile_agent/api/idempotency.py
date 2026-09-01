"""Stable client-side Idempotency-Key derivation for Runtime API submissions."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_idempotency_key(
    prefix: str, endpoint: str, params: dict[str, Any]
) -> str:
    """Derive a retry-safe key from the endpoint and canonicalized parameters.

    The digest input is the endpoint plus the parameters serialized with
    sorted keys and compact separators, so identical logical requests reuse
    one key and hit the task engine's dedup, while any parameter or endpoint
    change yields a different key. The result matches the server-side
    Idempotency-Key pattern ``[A-Za-z0-9._:-]{1,128}``.
    """

    canonical = json.dumps(
        params, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    digest = hashlib.sha256(f"{endpoint}\n{canonical}".encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:32]}"
