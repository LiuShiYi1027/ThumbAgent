"""Android Device Adapter."""

from mobile_agent.devices.adapters.android.adapter import AndroidDeviceAdapter
from mobile_agent.devices.adapters.android.adb import AdbRunner

__all__ = ["AdbRunner", "AndroidDeviceAdapter"]

