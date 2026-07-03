"""Device gateway ports and implementations."""

from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.devices.fake import FakeDeviceAdapter

__all__ = ["DeviceAdapter", "FakeDeviceAdapter"]

