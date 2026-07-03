from __future__ import annotations

import unittest
from pathlib import Path
import struct
import tempfile

from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.domain.device import ConnectionState, Platform
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.evidence.artifacts import ArtifactStore
from runtime.tests.fakes import FakeProcessRunner, result


class AndroidAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovers_devices_and_only_inspects_online_device(self) -> None:
        responses = {
            ("devices", "-l"): result(
                ("devices", "-l"),
                """List of devices attached
emulator-5554 device model:Pixel_8 device:emu
locked unauthorized usb:1-1
""",
            ),
            ("-s", "emulator-5554", "shell", "getprop", "ro.build.version.release"): result(
                ("-s", "emulator-5554", "shell", "getprop", "ro.build.version.release"),
                "15\n",
            ),
        }
        process = FakeProcessRunner(responses)
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))

        devices = await adapter.list_devices()

        self.assertEqual(2, len(devices))
        self.assertEqual("adb:emulator-5554", devices[0].device_id)
        self.assertEqual(Platform.ANDROID, devices[0].platform)
        self.assertEqual("15", devices[0].os_version)
        self.assertEqual(
            (
                "device.inspect@1",
                "screen.observe@1",
                "app.launch@1",
                "navigation.back@1",
                "navigation.home@1",
                "input.tap@1",
            ),
            devices[0].capabilities,
        )
        self.assertEqual(ConnectionState.UNAUTHORIZED, devices[1].connection)
        self.assertEqual((), devices[1].capabilities)
        self.assertEqual(2, len(process.calls))

    async def test_captures_standard_observation_and_artifacts(self) -> None:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1080, 2400) + b"pixels"
        ui_xml = b'<?xml version="1.0"?><hierarchy rotation="0"><node text="Safe fixture"/></hierarchy>'
        responses = {
            ("devices", "-l"): result(
                ("devices", "-l"),
                "List of devices attached\nserial-1 device model:Pixel_8 device:pixel\n",
            ),
            ("-s", "serial-1", "shell", "getprop", "ro.build.version.release"): result(
                ("-s", "serial-1", "shell", "getprop", "ro.build.version.release"), "15\n"
            ),
            ("-s", "serial-1", "shell", "dumpsys", "window"): result(
                ("-s", "serial-1", "shell", "dumpsys", "window"),
                "mCurrentFocus=Window{1 u0 com.example/.MainActivity}\n",
            ),
            ("-s", "serial-1", "exec-out", "screencap", "-p"): result(
                ("-s", "serial-1", "exec-out", "screencap", "-p"), png
            ),
            ("-s", "serial-1", "exec-out", "uiautomator", "dump", "/dev/tty"): result(
                ("-s", "serial-1", "exec-out", "uiautomator", "dump", "/dev/tty"),
                ui_xml + b"\nUI hierarchy dumped",
            ),
        }
        process = FakeProcessRunner(responses)
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory))

            observation = await adapter.observe("adb:serial-1", store)

            self.assertEqual(1080, observation.screen.width)
            self.assertEqual(2400, observation.screen.height)
            self.assertEqual("portrait", observation.screen.orientation.value)
            self.assertEqual("com.example", observation.foreground_app.app_id)
            self.assertEqual(".MainActivity", observation.foreground_app.activity)
            self.assertEqual(png, store.resolve(observation.screen.screenshot.relative_path).read_bytes())
            self.assertEqual(ui_xml, store.resolve(observation.ui_tree.artifact.relative_path).read_bytes())

    async def test_observe_rejects_unauthorized_device_with_structured_error(self) -> None:
        process = FakeProcessRunner(
            {
                ("devices", "-l"): result(
                    ("devices", "-l"),
                    "List of devices attached\nlocked unauthorized usb:1-1\n",
                )
            }
        )
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(MobileAgentError) as raised:
                await adapter.observe("adb:locked", ArtifactStore(Path(directory)))
        self.assertEqual("DEVICE_OFFLINE", raised.exception.code)
        self.assertEqual("unauthorized", raised.exception.details["connection"])

    async def test_observe_rejects_invalid_screenshot_with_structured_error(self) -> None:
        responses = {
            ("devices", "-l"): result(
                ("devices", "-l"),
                "List of devices attached\nserial-1 device model:Pixel_8 device:pixel\n",
            ),
            ("-s", "serial-1", "shell", "getprop", "ro.build.version.release"): result(
                ("-s", "serial-1", "shell", "getprop", "ro.build.version.release"), "15\n"
            ),
            ("-s", "serial-1", "shell", "dumpsys", "window"): result(
                ("-s", "serial-1", "shell", "dumpsys", "window"),
                "mCurrentFocus=Window{1 u0 com.example/.MainActivity}\n",
            ),
            ("-s", "serial-1", "exec-out", "screencap", "-p"): result(
                ("-s", "serial-1", "exec-out", "screencap", "-p"), b"not-a-png"
            ),
        }
        adapter = AndroidDeviceAdapter(
            AdbRunner(Path("/safe/adb"), FakeProcessRunner(responses))
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(MobileAgentError) as raised:
                await adapter.observe("adb:serial-1", ArtifactStore(Path(directory)))
        self.assertEqual("OBSERVATION_FAILED", raised.exception.code)

    async def test_basic_actions_use_fixed_adb_argument_arrays(self) -> None:
        launch = (
            "-s",
            "serial-1",
            "shell",
            "monkey",
            "-p",
            "com.android.settings",
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        )
        back = ("-s", "serial-1", "shell", "input", "keyevent", "4")
        home = ("-s", "serial-1", "shell", "input", "keyevent", "3")
        tap = ("-s", "serial-1", "shell", "input", "tap", "10", "20")
        process = FakeProcessRunner(
            {
                launch: result(launch),
                back: result(back),
                home: result(home),
                tap: result(tap),
            }
        )
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))

        await adapter.launch_app("adb:serial-1", "com.android.settings")
        await adapter.press_back("adb:serial-1")
        await adapter.press_home("adb:serial-1")
        await adapter.tap("adb:serial-1", 10, 20)

        self.assertEqual([launch, back, home, tap], [call[1] for call in process.calls])

    async def test_launch_rejects_invalid_package_before_process_call(self) -> None:
        process = FakeProcessRunner({})
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))
        with self.assertRaises(MobileAgentError) as raised:
            await adapter.launch_app("adb:serial-1", "bad package; command")
        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)
        self.assertEqual([], process.calls)
