"""Unicode text input domain values: Modified UTF-7 encoder and result contract.

See ADR-0019. 编码产物只含纯 ASCII，经既有固定 argv `input text` 管道送入
Helper IME（helpers/unicode-ime/）解码上屏；文本原文不进入结果、日志或
Artifact，仅记录长度与 NFC 归一化后的 SHA-256。
"""

from __future__ import annotations

import base64
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError

# Helper 登记值：与 helpers/unicode-ime/ 的包名、服务类与 dist/SHA256SUMS.txt
# 保持一致；任何变化都必须重新评审并同步两侧。
HELPER_PACKAGE = "com.thumbagent.unicodeime"
HELPER_IME_ID = f"{HELPER_PACKAGE}/.UnicodeImeService"
HELPER_APK_SHA256 = "46c45d70ae95ec353e5974fe9eaac1b9f2252f7721a553e42472fe808e9cabfe"

MAX_TEXT_LENGTH = 256

# 纯 ASCII 快路径集合：与 input.text@1 的合法字符集一致。
_ASCII_FAST_PATH = re.compile(r"[A-Za-z0-9._-]{1,64}")
# 敏感数字形态：验证码（4-8 位）与手机号（11+ 位），与 input.text@1 拦截一致。
_SENSITIVE_DIGITS = (re.compile(r"\d{4,8}"), re.compile(r"\d{11,}"))

# 直传字符集：可打印 ASCII，排除 '&'（Modified UTF-7 移位符）、空格与 '%'
# （`input text` 的设备端解析对二者有歧义，一律进 base64 块）。
_DIRECT_CHARS = frozenset(
    chr(c) for c in range(0x21, 0x7F) if chr(c) not in {"&", "%"}
)


def validate_unicode_text(raw: object) -> str:
    """Validate one public Unicode text request before any device action."""

    if not isinstance(raw, str) or not raw:
        raise MobileAgentError(
            code="INVALID_ARGUMENT",
            category=ErrorCategory.VALIDATION,
            message="无效的文本参数：text",
        )
    if len(raw) > MAX_TEXT_LENGTH:
        raise MobileAgentError(
            code="INVALID_ARGUMENT",
            category=ErrorCategory.VALIDATION,
            message=f"文本长度超过 {MAX_TEXT_LENGTH} 字符上限",
        )
    # 控制字符（含换行）会被 commitText 原样上屏，可能触发表单提交，一律拒绝。
    if any(unicodedata.category(char).startswith("C") for char in raw):
        raise MobileAgentError(
            code="INVALID_ARGUMENT",
            category=ErrorCategory.VALIDATION,
            message="文本包含不允许的控制字符",
        )
    if any(pattern.fullmatch(raw) for pattern in _SENSITIVE_DIGITS):
        raise MobileAgentError(
            code="ACTION_REJECTED_BY_POLICY",
            category=ErrorCategory.POLICY,
            message="当前策略禁止输入疑似验证码、手机号或敏感数字",
        )
    if _ASCII_FAST_PATH.fullmatch(raw):
        raise MobileAgentError(
            code="INVALID_ARGUMENT",
            category=ErrorCategory.VALIDATION,
            message="纯 ASCII 文本应走 input.text 快路径",
            suggested_action="改用 input.text，不触发 IME 切换",
        )
    return raw


def encode_modified_utf7(text: str) -> str:
    """Encode text as Modified UTF-7 (RFC 3501) with a conservative direct set.

    与 Java 端 `x-IMAP-mailbox-name` 解码器兼容：base64 块以 '&' 开始、'-' 结束，
    块内用 ',' 替代 '/' 且不带 '=' 填充；'&' 直传为 '&-'。
    """

    parts: list[str] = []
    block: list[str] = []

    def flush_block() -> None:
        if not block:
            return
        raw = "".join(block).encode("utf-16-be")
        encoded = base64.b64encode(raw).decode("ascii").rstrip("=").replace("/", ",")
        parts.append(f"&{encoded}-")
        block.clear()

    for char in text:
        if char == "&":
            flush_block()
            parts.append("&-")
        elif char in _DIRECT_CHARS:
            flush_block()
            parts.append(char)
        else:
            block.append(char)
    flush_block()
    return "".join(parts)


def decode_modified_utf7(encoded: str) -> str:
    """Decode Modified UTF-7 produced by encode_modified_utf7.

    Runtime 正常路径不需要解码（设备端 Helper IME 负责）；此函数供测试
    Fake 与诊断脚本模拟设备端行为，实现与编码器严格对称。
    """

    out: list[str] = []
    index = 0
    while index < len(encoded):
        char = encoded[index]
        if char != "&":
            out.append(char)
            index += 1
            continue
        end = encoded.find("-", index)
        if end < 0:
            raise ValueError("unterminated modified UTF-7 block")
        block = encoded[index + 1 : end]
        if block:
            standard = block.replace(",", "/")
            standard += "=" * (-len(standard) % 4)
            out.append(base64.b64decode(standard).decode("utf-16-be"))
        else:
            out.append("&")
        index = end + 1
    return "".join(out)


def normalize_for_verification(text: str) -> str:
    """NFC 归一化，读回验证的唯一比对形态（ADR-0019 容差决策）。"""

    return unicodedata.normalize("NFC", text)


def text_digest(text: str) -> str:
    """SHA-256 of the NFC-normalized text; the original text is never persisted."""

    return hashlib.sha256(normalize_for_verification(text).encode("utf-8")).hexdigest()


def is_helper_ime(ime_id: str) -> bool:
    """Match installed/enabled IME ids regardless of full or shorthand form."""

    return ime_id.startswith(HELPER_PACKAGE + "/")


@dataclass(frozen=True, slots=True)
class UnicodeInputResult:
    """Verified public result of the input.unicode_text Skill."""

    skill_call_id: str
    device_id: str
    field_selector: dict[str, str]
    field_package: str
    text_length: int
    text_sha256: str
    ime_helper_id: str
    ime_previous_id: str
    evidence_refs: tuple[str, ...]
    started_at: str
    completed_at: str
    field_resource_id: str | None = None
    schema_version: str = "1.0.0"
    skill_id: str = "input.unicode_text"
    skill_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        field: dict[str, Any] = {
            "selector": self.field_selector,
            "package": self.field_package,
        }
        if self.field_resource_id is not None:
            field["resource_id"] = self.field_resource_id
        return {
            "schema_version": self.schema_version,
            "skill_call_id": self.skill_call_id,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "device_id": self.device_id,
            "success": True,
            "status": "succeeded",
            "verification": "verified",
            "field": field,
            "text_length": self.text_length,
            "text_sha256": self.text_sha256,
            "ime": {
                "helper_id": self.ime_helper_id,
                "previous_id": self.ime_previous_id,
                "restored": True,
            },
            "evidence_refs": list(self.evidence_refs),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }
