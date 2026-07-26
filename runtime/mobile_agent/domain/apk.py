"""Local APK preflight and scoped installation approval contracts."""

from __future__ import annotations

import hashlib
import re
import struct
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.app import InstalledApp


MAX_APK_BYTES = 512 * 1024 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ApkPackage:
    path: Path
    filename: str
    size_bytes: int
    sha256: str
    app_id: str


@dataclass(frozen=True, slots=True)
class ApkInstallApproval:
    approval_id: str
    device_id: str
    package: ApkPackage
    replace_existing: bool
    prepared_at: str
    expires_at: str
    expires_at_epoch: float
    consumed_by_key: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "approval_id": self.approval_id,
            "device_id": self.device_id,
            "filename": self.package.filename,
            "size_bytes": self.package.size_bytes,
            "sha256": self.package.sha256,
            "app_id": self.package.app_id,
            "replace_existing": self.replace_existing,
            "prepared_at": self.prepared_at,
            "expires_at": self.expires_at,
            "confirmation_required": True,
        }


class ApkInspector:
    """Validate one APK below an explicitly authorized local directory."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def inspect(self, value: str) -> ApkPackage:
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 4096
            or any(character in value for character in "\x00\r\n")
        ):
            raise _invalid_apk("APK 路径无效")
        source = Path(value).expanduser()
        if source.is_symlink():
            raise _invalid_apk("APK 不允许使用符号链接")
        try:
            path = source.resolve(strict=True)
        except OSError as error:
            raise _invalid_apk("APK 文件不存在") from error
        if not path.is_relative_to(self.root) or not path.is_file():
            raise _invalid_apk("APK 必须位于 Runtime 授权目录内")
        if path.suffix.lower() != ".apk":
            raise _invalid_apk("仅支持单个 .apk 文件")
        size = path.stat().st_size
        if size < 1 or size > MAX_APK_BYTES:
            raise _invalid_apk("APK 文件大小必须在 1 字节到 512 MiB 之间")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        try:
            with zipfile.ZipFile(path) as archive:
                info = archive.getinfo("AndroidManifest.xml")
                if info.file_size > MAX_MANIFEST_BYTES:
                    raise _invalid_apk("APK Manifest 超过安全上限")
                manifest = archive.read(info)
        except (KeyError, OSError, zipfile.BadZipFile) as error:
            raise _invalid_apk("APK ZIP 或 Manifest 无效") from error
        try:
            app_id = parse_binary_manifest_package(manifest)
        except MobileAgentError:
            raise
        except (IndexError, struct.error, UnicodeError) as error:
            raise _invalid_apk("APK Manifest binary XML 无效") from error
        return ApkPackage(path, path.name[:256], size, digest.hexdigest(), app_id)


class ApkInstallApprovalStore:
    """Keep short-lived, single-use High-risk approvals in Runtime memory."""

    def __init__(self, clock: Callable[[], float] = time.time, ttl_seconds: float = 600) -> None:
        self._clock = clock
        self._ttl = ttl_seconds
        self._items: dict[str, ApkInstallApproval] = {}
        self._lock = threading.Lock()

    def create(
        self, device_id: str, package: ApkPackage, replace_existing: bool
    ) -> ApkInstallApproval:
        now = self._clock()
        approval = ApkInstallApproval(
            f"approval_{uuid.uuid4().hex}", device_id, package, replace_existing,
            _iso(now), _iso(now + self._ttl), now + self._ttl,
        )
        with self._lock:
            self._items[approval.approval_id] = approval
        return approval

    def claim(self, approval_id: str, idempotency_key: str) -> ApkInstallApproval:
        with self._lock:
            approval = self._items.get(approval_id)
            if approval is None:
                raise _approval_error("安装 Approval 不存在或 Runtime 已重启")
            if self._clock() >= approval.expires_at_epoch:
                raise _approval_error("安装 Approval 已过期")
            if approval.consumed_by_key not in {None, idempotency_key}:
                raise _approval_error("安装 Approval 已被另一请求使用")
            if approval.consumed_by_key is None:
                approval = replace(approval, consumed_by_key=idempotency_key)
                self._items[approval_id] = approval
            return approval


@dataclass(frozen=True, slots=True)
class ApkInstallResult:
    skill_call_id: str
    device_id: str
    app: InstalledApp
    apk_sha256: str
    apk_size_bytes: int
    replaced_existing: bool
    started_at: str
    completed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "skill_call_id": self.skill_call_id,
            "skill_id": "app.install",
            "skill_version": "1.0.0",
            "device_id": self.device_id,
            "success": True,
            "status": "succeeded",
            "verification": "verified",
            "app": self.app.to_dict(),
            "apk_sha256": self.apk_sha256,
            "apk_size_bytes": self.apk_size_bytes,
            "replaced_existing": self.replaced_existing,
            "evidence_refs": [],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


def parse_binary_manifest_package(data: bytes) -> str:
    """Read the manifest package attribute from bounded Android binary XML."""

    if len(data) < 8 or struct.unpack_from("<H", data)[0] != 0x0003:
        raise _invalid_apk("APK Manifest 不是受支持的 Android binary XML")
    strings: tuple[str, ...] = ()
    offset = struct.unpack_from("<H", data, 2)[0]
    while offset + 8 <= len(data):
        chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", data, offset)
        if chunk_size < header_size or offset + chunk_size > len(data):
            raise _invalid_apk("APK Manifest chunk 无效")
        if chunk_type == 0x0001:
            strings = _parse_string_pool(data[offset : offset + chunk_size])
        elif chunk_type == 0x0102 and strings:
            value = _manifest_package_from_start(data, offset, header_size, strings)
            if value is not None:
                if re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", value) is None:
                    raise _invalid_apk("APK Manifest package id 无效")
                return value
        offset += chunk_size
    raise _invalid_apk("APK Manifest 缺少 package id")


def _parse_string_pool(chunk: bytes) -> tuple[str, ...]:
    if len(chunk) < 28:
        raise _invalid_apk("APK Manifest string pool 无效")
    header_size = struct.unpack_from("<H", chunk, 2)[0]
    count, _, flags, strings_start, _ = struct.unpack_from("<IIIII", chunk, 8)
    if count > 100_000 or header_size + count * 4 > len(chunk):
        raise _invalid_apk("APK Manifest string pool 超限")
    utf8 = bool(flags & 0x100)
    result: list[str] = []
    for index in range(count):
        relative = struct.unpack_from("<I", chunk, header_size + index * 4)[0]
        start = strings_start + relative
        if start >= len(chunk):
            raise _invalid_apk("APK Manifest string offset 无效")
        if utf8:
            _, cursor = _length8(chunk, start)
            length, cursor = _length8(chunk, cursor)
            raw = chunk[cursor : cursor + length]
            result.append(raw.decode("utf-8", errors="strict"))
        else:
            length, cursor = _length16(chunk, start)
            raw = chunk[cursor : cursor + length * 2]
            result.append(raw.decode("utf-16le", errors="strict"))
    return tuple(result)


def _manifest_package_from_start(
    data: bytes, offset: int, header_size: int, strings: tuple[str, ...]
) -> str | None:
    ext = offset + header_size
    if ext + 20 > len(data):
        return None
    name_index = struct.unpack_from("<I", data, ext + 4)[0]
    if name_index >= len(strings) or strings[name_index] != "manifest":
        return None
    attribute_start, attribute_size, count = struct.unpack_from("<HHH", data, ext + 8)
    if attribute_size < 20 or count > 256:
        raise _invalid_apk("APK Manifest attributes 无效")
    cursor = ext + attribute_start
    for _ in range(count):
        if cursor + 20 > len(data):
            raise _invalid_apk("APK Manifest attribute 越界")
        attr_name, raw_value = struct.unpack_from("<II", data, cursor + 4)
        data_type = data[cursor + 15]
        typed_value = struct.unpack_from("<I", data, cursor + 16)[0]
        if attr_name < len(strings) and strings[attr_name] == "package":
            value_index = raw_value if raw_value != 0xFFFFFFFF else typed_value if data_type == 3 else -1
            return strings[value_index] if 0 <= value_index < len(strings) else None
        cursor += attribute_size
    return None


def _length8(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    return (((first & 0x7F) << 8) | data[offset + 1], offset + 2) if first & 0x80 else (first, offset + 1)


def _length16(data: bytes, offset: int) -> tuple[int, int]:
    first = struct.unpack_from("<H", data, offset)[0]
    return ((((first & 0x7FFF) << 16) | struct.unpack_from("<H", data, offset + 2)[0]), offset + 4) if first & 0x8000 else (first, offset + 2)


def _invalid_apk(message: str) -> MobileAgentError:
    return MobileAgentError("APK_INVALID", ErrorCategory.VALIDATION, message)


def _approval_error(message: str) -> MobileAgentError:
    return MobileAgentError("APPROVAL_INVALID", ErrorCategory.POLICY, message)
