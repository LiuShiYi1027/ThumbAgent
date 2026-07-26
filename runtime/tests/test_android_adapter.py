from __future__ import annotations

import unittest
from pathlib import Path
import struct
import tempfile

from mobile_agent.devices.adapters.android import AdbRunner, AndroidDeviceAdapter
from mobile_agent.domain.device import ConnectionState, Platform
from mobile_agent.domain.errors import MobileAgentError
from mobile_agent.domain.device_log import DeviceLogLevel
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
                "input.swipe@1",
                "input.text@1",
                "logs.collect@1",
                "performance.snapshot@1",
                "app.inspect@1",
                "app.install@1",
                "app.uninstall@1",
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
            "am",
            "start",
            "-W",
            "-a",
            "android.settings.SETTINGS",
            "-f",
            "0x14000000",
        )
        back = ("-s", "serial-1", "shell", "input", "keyevent", "4")
        home = ("-s", "serial-1", "shell", "input", "keyevent", "3")
        tap = ("-s", "serial-1", "shell", "input", "touchscreen", "tap", "10", "20")
        text = ("-s", "serial-1", "shell", "input", "text", "hello_1")
        swipe = (
            "-s",
            "serial-1",
            "shell",
            "input",
            "swipe",
            "100",
            "900",
            "100",
            "300",
            "250",
        )
        process = FakeProcessRunner(
            {
                launch: result(launch),
                back: result(back),
                home: result(home),
                tap: result(tap),
                text: result(text),
                swipe: result(swipe),
            }
        )
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))

        await adapter.launch_app("adb:serial-1", "com.android.settings")
        await adapter.press_back("adb:serial-1")
        await adapter.press_home("adb:serial-1")
        await adapter.tap("adb:serial-1", 10, 20)
        await adapter.input_text("adb:serial-1", "hello_1")
        await adapter.swipe("adb:serial-1", 100, 900, 100, 300, 250)

        self.assertEqual([launch, back, home, tap, text, swipe], [call[1] for call in process.calls])

    async def test_launch_rejects_invalid_package_before_process_call(self) -> None:
        process = FakeProcessRunner({})
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))
        with self.assertRaises(MobileAgentError) as raised:
            await adapter.launch_app("adb:serial-1", "bad package; command")
        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)
        self.assertEqual([], process.calls)

    async def test_log_capture_uses_fixed_bounded_logcat_arguments(self) -> None:
        logcat = (
            "-s",
            "serial-1",
            "logcat",
            "-d",
            "-t",
            "500",
            "-v",
            "threadtime",
            "*:W",
        )
        process = FakeProcessRunner({logcat: result(logcat, b"one safe line\n")})
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))

        captured = await adapter.collect_logs(
            "adb:serial-1", 500, DeviceLogLevel.WARN
        )

        self.assertEqual(b"one safe line\n", captured)
        self.assertEqual([logcat], [call[1] for call in process.calls])

    async def test_log_capture_rejects_unbounded_lines_before_process_call(self) -> None:
        process = FakeProcessRunner({})
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))

        with self.assertRaises(MobileAgentError) as raised:
            await adapter.collect_logs(
                "adb:serial-1", 2001, DeviceLogLevel.INFO
            )

        self.assertEqual("INVALID_ARGUMENT", raised.exception.code)
        self.assertEqual([], process.calls)

    async def test_log_capture_maps_nonzero_exit_without_leaking_stderr(self) -> None:
        logcat = (
            "-s",
            "serial-1",
            "logcat",
            "-d",
            "-t",
            "100",
            "-v",
            "threadtime",
            "*:I",
        )
        process = FakeProcessRunner(
            {logcat: result(logcat, stderr="token=secret-value", code=1)}
        )
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))

        with self.assertRaises(MobileAgentError) as raised:
            await adapter.collect_logs("adb:serial-1", 100, DeviceLogLevel.INFO)

        self.assertEqual("LOG_CAPTURE_FAILED", raised.exception.code)
        self.assertNotIn("secret-value", str(raised.exception.to_dict()))

    async def test_performance_snapshot_uses_only_fixed_aggregate_commands(self) -> None:
        commands = (
            ("-s", "serial-1", "shell", "dumpsys", "cpuinfo"),
            ("-s", "serial-1", "shell", "dumpsys", "meminfo"),
            ("-s", "serial-1", "shell", "dumpsys", "battery"),
            ("-s", "serial-1", "shell", "cat", "/proc/uptime"),
            ("-s", "serial-1", "shell", "cat", "/proc/loadavg"),
        )
        outputs = (
            " 7.5% TOTAL: 3% user + 4.5% kernel\n",
            " Total RAM: 8,000,000K\n Free RAM: 3,000,000K\n",
            " status: 2\n level: 80\n scale: 100\n plugged: 2\n temperature: 310\n",
            "3600.50 1200.00\n",
            "1.00 0.80 0.60 1/100 123\n",
        )
        process = FakeProcessRunner(
            {args: result(args, output) for args, output in zip(commands, outputs)}
        )
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))

        snapshot = await adapter.capture_performance("adb:serial-1")

        self.assertEqual(7.5, snapshot.cpu_total_usage_percent)
        self.assertEqual(8_192_000_000, snapshot.memory_total_bytes)
        self.assertEqual(31.0, snapshot.battery_temperature_celsius)
        self.assertEqual(list(commands), [call[1] for call in process.calls])

    async def test_input_security_exception_maps_to_device_unauthorized(self) -> None:
        tap = ("-s", "serial-1", "shell", "input", "touchscreen", "tap", "10", "20")
        stderr = (
            "Exception occurred while executing 'tap':\n"
            "java.lang.SecurityException: Injecting input events requires the caller "
            "to have the INJECT_EVENTS permission."
        )
        process = FakeProcessRunner({tap: result(tap, stderr=stderr, code=255)})
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))

        with self.assertRaises(MobileAgentError) as raised:
            await adapter.tap("adb:serial-1", 10, 20)

        self.assertEqual("DEVICE_UNAUTHORIZED", raised.exception.code)
        self.assertEqual("input_event_injection_denied", raised.exception.details["reason"])

    async def test_observe_recaptures_explicit_primary_display_when_device_warns(self) -> None:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1080, 2400) + b"pixels"
        warning = b"[Warning] Multiple displays were found, but no display id was specified!\n"
        ui_xml = b'<?xml version="1.0"?><hierarchy rotation="0"></hierarchy>'
        list_args = ("devices", "-l")
        version_args = ("-s", "serial-1", "shell", "getprop", "ro.build.version.release")
        window_args = ("-s", "serial-1", "shell", "dumpsys", "window")
        initial_capture = ("-s", "serial-1", "exec-out", "screencap", "-p")
        display_args = (
            "-s",
            "serial-1",
            "shell",
            "dumpsys",
            "SurfaceFlinger",
            "--display-id",
        )
        explicit_capture = (
            "-s",
            "serial-1",
            "exec-out",
            "screencap",
            "-d",
            "12345",
            "-p",
        )
        ui_args = ("-s", "serial-1", "exec-out", "uiautomator", "dump", "/dev/tty")
        process = FakeProcessRunner(
            {
                list_args: result(
                    list_args,
                    "List of devices attached\nserial-1 device model:Pixel_8 device:pixel\n",
                ),
                version_args: result(version_args, "15\n"),
                window_args: result(
                    window_args, "mCurrentFocus=Window{1 u0 com.example/.MainActivity}\n"
                ),
                initial_capture: result(initial_capture, warning + png),
                display_args: result(
                    display_args,
                    'Display 12345 (HWC display 0): port=1 pnpId=QCM displayName=""\n'
                    'Display 67890 (HWC display 5): port=2 pnpId=QCM displayName=""\n',
                ),
                explicit_capture: result(explicit_capture, png),
                ui_args: result(ui_args, ui_xml),
            }
        )
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))
        with tempfile.TemporaryDirectory() as directory:
            observation = await adapter.observe(
                "adb:serial-1", ArtifactStore(Path(directory))
            )
        self.assertEqual(1080, observation.screen.width)
        self.assertIn(explicit_capture, [call[1] for call in process.calls])

    async def test_observe_retries_one_empty_ui_dump(self) -> None:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1080, 2400) + b"pixels"
        ui_xml = b'<?xml version="1.0"?><hierarchy rotation="0"></hierarchy>'
        list_args = ("devices", "-l")
        version_args = ("-s", "serial-1", "shell", "getprop", "ro.build.version.release")
        window_args = ("-s", "serial-1", "shell", "dumpsys", "window")
        capture_args = ("-s", "serial-1", "exec-out", "screencap", "-p")
        ui_args = ("-s", "serial-1", "exec-out", "uiautomator", "dump", "/dev/tty")
        process = FakeProcessRunner(
            {
                list_args: result(
                    list_args,
                    "List of devices attached\nserial-1 device model:Pixel_8 device:pixel\n",
                ),
                version_args: result(version_args, "15\n"),
                window_args: result(
                    window_args, "mCurrentFocus=Window{1 u0 com.example/.MainActivity}\n"
                ),
                capture_args: result(capture_args, png),
                ui_args: [
                    result(ui_args, "ERROR: null root node"),
                    result(ui_args, ui_xml),
                ],
            }
        )
        adapter = AndroidDeviceAdapter(AdbRunner(Path("/safe/adb"), process))
        with tempfile.TemporaryDirectory() as directory:
            observation = await adapter.observe(
                "adb:serial-1", ArtifactStore(Path(directory))
            )
        self.assertEqual("application/xml", observation.ui_tree.artifact.content_type)
        self.assertEqual(2, [call[1] for call in process.calls].count(ui_args))
