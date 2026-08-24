"""Shared RFC 3501 Modified UTF-7 reference decoder for encoder/orchestration tests."""

from __future__ import annotations

import base64


def reference_decode_modified_utf7(encoded: str) -> str:
    """独立的参考解码器，镜像 Helper IME 的 x-IMAP-mailbox-name 语义。"""

    out: list[str] = []
    index = 0
    while index < len(encoded):
        char = encoded[index]
        if char != "&":
            out.append(char)
            index += 1
            continue
        end = encoded.index("-", index)
        block = encoded[index + 1 : end]
        if block:
            standard = block.replace(",", "/")
            standard += "=" * (-len(standard) % 4)
            out.append(base64.b64decode(standard).decode("utf-16-be"))
        else:
            out.append("&")
        index = end + 1
    return "".join(out)
