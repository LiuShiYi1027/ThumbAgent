from __future__ import annotations

import unittest

from mobile_agent.devices.adapters.android.parser import parse_adb_devices
from mobile_agent.domain.device import ConnectionState


class AdbParserTests(unittest.TestCase):
    def test_parses_online_offline_unauthorized_and_unknown_devices(self) -> None:
        output = """List of devices attached
emulator-5554 device product:sdk model:Pixel_8 device:emu transport_id:1
phone-offline offline transport_id:2
phone-locked unauthorized usb:1-1
future-state recovery product:test
"""

        records = parse_adb_devices(output)

        self.assertEqual(4, len(records))
        self.assertEqual(ConnectionState.ONLINE, records[0].connection)
        self.assertEqual("Pixel_8", records[0].properties["model"])
        self.assertEqual(ConnectionState.OFFLINE, records[1].connection)
        self.assertEqual(ConnectionState.UNAUTHORIZED, records[2].connection)
        self.assertEqual(ConnectionState.UNKNOWN, records[3].connection)

    def test_empty_list_and_daemon_noise_return_no_devices(self) -> None:
        output = """* daemon not running; starting now at tcp:5037
* daemon started successfully
List of devices attached

"""
        self.assertEqual([], parse_adb_devices(output))

