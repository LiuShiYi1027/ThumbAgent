"""Device gateway ports and implementations."""

from mobile_agent.devices.base import DeviceAdapter
from mobile_agent.devices.fake import FakeDeviceAdapter
from mobile_agent.devices.lease import DeviceLeaseManager
from mobile_agent.devices.session import SessionTrackingDeviceAdapter
from mobile_agent.devices.unavailable import UnavailableDeviceAdapter

__all__ = [
    "DeviceAdapter",
    "DeviceLeaseManager",
    "FakeDeviceAdapter",
    "SessionTrackingDeviceAdapter",
    "UnavailableDeviceAdapter",
]
