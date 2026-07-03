from __future__ import annotations

import unittest

from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.domain.device import ConnectionState, Platform


class FakeAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_adapter_returns_one_online_android_device(self) -> None:
        devices = await FakeDeviceAdapter().list_devices()

        self.assertEqual(1, len(devices))
        self.assertEqual(Platform.ANDROID, devices[0].platform)
        self.assertEqual(ConnectionState.ONLINE, devices[0].connection)
        self.assertIn("device.inspect@1", devices[0].capabilities)

