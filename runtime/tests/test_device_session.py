from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.devices.session import SessionTrackingDeviceAdapter
from mobile_agent.domain.device import ConnectionState, Device, Platform
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore


def _device(connection: ConnectionState = ConnectionState.ONLINE) -> Device:
    return Device(
        device_id="fake:android-001",
        platform=Platform.ANDROID,
        name="Fake Android Device",
        model="fake_android",
        os_version="15",
        connection=connection,
        capabilities=("device.inspect@1", "navigation.home@1"),
    )


class DeviceSessionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.artifacts = ArtifactStore(Path(self.directory.name))
        self.underlying = FakeDeviceAdapter([_device()])
        session_ids = iter(
            (
                "session_00000000000000000000000000000001",
                "session_00000000000000000000000000000002",
                "session_00000000000000000000000000000003",
            )
        )
        self.adapter = SessionTrackingDeviceAdapter(
            self.underlying, lambda: next(session_ids)
        )

    async def test_continuously_online_device_keeps_same_session(self) -> None:
        first = (await self.adapter.list_devices())[0]
        second = (await self.adapter.list_devices())[0]

        self.assertEqual(first.session_id, second.session_id)
        self.assertEqual(
            "session_00000000000000000000000000000001", first.session_id
        )

    async def test_missing_then_reconnected_device_gets_new_session(self) -> None:
        first = (await self.adapter.list_devices())[0]
        self.underlying._devices = []  # noqa: SLF001 - mutable discovery fixture
        self.assertEqual([], await self.adapter.list_devices())
        self.underlying._devices = [_device()]  # noqa: SLF001

        reconnected = (await self.adapter.list_devices())[0]

        self.assertNotEqual(first.session_id, reconnected.session_id)

    async def test_offline_then_online_device_gets_new_session(self) -> None:
        first = (await self.adapter.list_devices())[0]
        self.underlying._devices = [_device(ConnectionState.OFFLINE)]  # noqa: SLF001
        offline = (await self.adapter.list_devices())[0]
        self.underlying._devices = [_device()]  # noqa: SLF001
        reconnected = (await self.adapter.list_devices())[0]

        self.assertIsNone(offline.session_id)
        self.assertNotEqual(first.session_id, reconnected.session_id)

    async def test_bound_task_rejects_action_after_reconnect(self) -> None:
        session_id = await self.adapter.require_online_session("fake:android-001")
        with self.adapter.bind_session("fake:android-001", session_id):
            self.underlying._devices = []  # noqa: SLF001
            await self.adapter.list_devices()
            self.underlying._devices = [_device()]  # noqa: SLF001

            with self.assertRaises(MobileAgentError) as raised:
                await self.adapter.press_home("fake:android-001")

        self.assertEqual("DEVICE_SESSION_CHANGED", raised.exception.code)
        self.assertEqual([], self.underlying.actions)


if __name__ == "__main__":
    unittest.main()
