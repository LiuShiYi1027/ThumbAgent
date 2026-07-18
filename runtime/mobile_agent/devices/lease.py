"""Process-local exclusive leases for device write ownership."""

from __future__ import annotations

import threading
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic
from typing import Callable

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class DeviceLease:
    """One exclusive write ownership record."""

    device_id: str
    owner_id: str
    session_id: str
    acquired_at: str
    expires_at_monotonic: float


class _LeaseContext(AbstractContextManager[DeviceLease]):
    def __init__(self, manager: DeviceLeaseManager, lease: DeviceLease) -> None:
        self._manager = manager
        self._lease = lease

    def __enter__(self) -> DeviceLease:
        return self._lease

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._manager.release(self._lease)


class DeviceLeaseManager:
    """Serialize device writes without treating lease expiry as safe recovery."""

    def __init__(self, monotonic_clock: Callable[[], float] = monotonic) -> None:
        self._monotonic = monotonic_clock
        self._leases: dict[str, DeviceLease] = {}
        self._lock = threading.Lock()

    def hold(
        self,
        device_id: str,
        owner_id: str,
        lease_seconds: float,
        session_id: str = "session_unbound",
    ) -> AbstractContextManager[DeviceLease]:
        """Acquire a non-reentrant lease or raise DEVICE_LOCKED."""

        if not device_id or not owner_id or lease_seconds <= 0:
            raise MobileAgentError(
                code="INVALID_ARGUMENT",
                category=ErrorCategory.VALIDATION,
                message="设备租约参数无效",
            )
        with self._lock:
            existing = self._leases.get(device_id)
            if existing is not None:
                raise MobileAgentError(
                    code="DEVICE_LOCKED",
                    category=ErrorCategory.DEVICE,
                    message="设备正由另一个任务使用",
                    retryable=True,
                    suggested_action="等待当前任务结束或取消后重试",
                    details={
                        "owner_id": existing.owner_id,
                        "session_id": existing.session_id,
                        "lease_expired": self._monotonic()
                        >= existing.expires_at_monotonic,
                    },
                )
            lease = DeviceLease(
                device_id=device_id,
                owner_id=owner_id,
                session_id=session_id,
                acquired_at=_now(),
                expires_at_monotonic=self._monotonic() + lease_seconds,
            )
            self._leases[device_id] = lease
        return _LeaseContext(self, lease)

    def release(self, lease: DeviceLease) -> None:
        """Release only when the current owner still matches the handle."""

        with self._lock:
            current = self._leases.get(lease.device_id)
            if current == lease:
                del self._leases[lease.device_id]

    def current(self, device_id: str) -> DeviceLease | None:
        """Return the current lease for diagnostics without changing ownership."""

        with self._lock:
            return self._leases.get(device_id)
