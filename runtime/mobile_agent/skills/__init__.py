"""Goal-level deterministic skills."""

from mobile_agent.skills.open_app import OpenAppSkill
from mobile_agent.skills.device_logs import DeviceLogsCollectSkill
from mobile_agent.skills.device_performance import DevicePerformanceSnapshotSkill
from mobile_agent.skills.settings_navigate import SettingsNavigateSkill, SettingsScrollNavigateSkill

__all__ = [
    "DeviceLogsCollectSkill",
    "DevicePerformanceSnapshotSkill",
    "OpenAppSkill",
    "SettingsNavigateSkill",
    "SettingsScrollNavigateSkill",
]
