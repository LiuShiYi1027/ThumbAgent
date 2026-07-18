"""Platform-neutral device connection session tracking gateway."""

from __future__ import annotations

import contextvars
import threading
import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from typing import Callable

from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.domain.artifact import ArtifactWriter
from mobile_agent.domain.device import ConnectionState, Device
from mobile_agent.domain.device_log import DeviceLogLevel
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.domain.observation import Observation
from mobile_agent.domain.performance import DevicePerformanceSnapshot


@dataclass(frozen=True, slots=True)
class _SessionState:
    connection: ConnectionState | None
    session_id: str | None
    present: bool


class _SessionBinding(AbstractContextManager[None]):
    def __init__(
        self,
        variable: contextvars.ContextVar[tuple[str, str] | None],
        device_id: str,
        session_id: str,
    ) -> None:
        self._variable = variable
        self._binding = (device_id, session_id)
        self._token: contextvars.Token[tuple[str, str] | None] | None = None

    def __enter__(self) -> None:
        self._token = self._variable.set(self._binding)

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._token is not None:
            self._variable.reset(self._token)


class SessionTrackingDeviceAdapter:
    """Decorate a platform Adapter with reconnect-safe session identities."""

    def __init__(
        self,
        adapter: DeviceAdapter,
        session_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._adapter = adapter
        self._session_id_factory = session_id_factory or (
            lambda: f"session_{uuid.uuid4().hex}"
        )
        self._states: dict[str, _SessionState] = {}
        self._lock = threading.Lock()
        self._binding: contextvars.ContextVar[tuple[str, str] | None] = (
            contextvars.ContextVar("mobile_agent_device_session", default=None)
        )

    async def list_devices(self) -> list[Device]:
        devices = await self._adapter.list_devices()
        visible_ids = {device.device_id for device in devices}
        tracked: list[Device] = []
        with self._lock:
            for known_id, state in tuple(self._states.items()):
                if known_id not in visible_ids:
                    self._states[known_id] = _SessionState(
                        connection=state.connection,
                        session_id=state.session_id,
                        present=False,
                    )
            for device in devices:
                previous = self._states.get(device.device_id)
                session_id: str | None = None
                if device.connection is ConnectionState.ONLINE:
                    if (
                        previous is None
                        or not previous.present
                        or previous.connection is not ConnectionState.ONLINE
                    ):
                        session_id = self._session_id_factory()
                    else:
                        session_id = previous.session_id
                self._states[device.device_id] = _SessionState(
                    connection=device.connection,
                    session_id=session_id,
                    present=True,
                )
                tracked.append(replace(device, session_id=session_id))
        return tracked

    async def require_online_session(self, device_id: str) -> str:
        """Return the current online session or a stable device error."""

        devices = await self.list_devices()
        device = next((item for item in devices if item.device_id == device_id), None)
        if device is None:
            raise MobileAgentError(
                code="DEVICE_NOT_FOUND",
                category=ErrorCategory.DEVICE,
                message="设备不存在",
            )
        if device.connection is not ConnectionState.ONLINE or device.session_id is None:
            raise MobileAgentError(
                code="DEVICE_OFFLINE",
                category=ErrorCategory.DEVICE,
                message="设备当前不可交互",
                retryable=True,
                details={"connection": device.connection.value},
            )
        return device.session_id

    def bind_session(
        self, device_id: str, session_id: str
    ) -> AbstractContextManager[None]:
        """Bind subsequent Adapter calls to one immutable connection session."""

        return _SessionBinding(self._binding, device_id, session_id)

    async def _validate_binding(self, device_id: str) -> None:
        binding = self._binding.get()
        if binding is None:
            return
        bound_device_id, expected_session_id = binding
        if bound_device_id != device_id:
            raise MobileAgentError(
                code="DEVICE_SESSION_CHANGED",
                category=ErrorCategory.DEVICE,
                message="任务绑定的设备与当前动作设备不一致",
            )
        try:
            current_session_id = await self.require_online_session(device_id)
        except MobileAgentError as error:
            if error.code in {"DEVICE_NOT_FOUND", "DEVICE_OFFLINE"}:
                raise MobileAgentError(
                    code="DEVICE_SESSION_CHANGED",
                    category=ErrorCategory.DEVICE,
                    message="设备连接会话已失效",
                    retryable=False,
                    suggested_action="确认设备重新连接后创建新任务",
                ) from error
            raise
        if current_session_id != expected_session_id:
            raise MobileAgentError(
                code="DEVICE_SESSION_CHANGED",
                category=ErrorCategory.DEVICE,
                message="设备已重新连接，旧任务不能继续执行",
                retryable=False,
                suggested_action="基于新设备会话重新创建任务",
            )

    async def observe(self, device_id: str, artifacts: ArtifactWriter) -> Observation:
        await self._validate_binding(device_id)
        return await self._adapter.observe(device_id, artifacts)

    async def launch_app(self, device_id: str, app_id: str) -> None:
        await self._validate_binding(device_id)
        await self._adapter.launch_app(device_id, app_id)

    async def press_back(self, device_id: str) -> None:
        await self._validate_binding(device_id)
        await self._adapter.press_back(device_id)

    async def press_home(self, device_id: str) -> None:
        await self._validate_binding(device_id)
        await self._adapter.press_home(device_id)

    async def tap(self, device_id: str, x: int, y: int) -> None:
        await self._validate_binding(device_id)
        await self._adapter.tap(device_id, x, y)

    async def swipe(
        self,
        device_id: str,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int,
    ) -> None:
        await self._validate_binding(device_id)
        await self._adapter.swipe(
            device_id, start_x, start_y, end_x, end_y, duration_ms
        )

    async def input_text(self, device_id: str, text: str) -> None:
        await self._validate_binding(device_id)
        await self._adapter.input_text(device_id, text)

    async def collect_logs(
        self, device_id: str, max_lines: int, minimum_level: DeviceLogLevel
    ) -> bytes:
        await self._validate_binding(device_id)
        return await self._adapter.collect_logs(device_id, max_lines, minimum_level)

    async def capture_performance(
        self, device_id: str
    ) -> DevicePerformanceSnapshot:
        await self._validate_binding(device_id)
        return await self._adapter.capture_performance(device_id)
