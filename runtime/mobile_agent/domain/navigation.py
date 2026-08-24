"""Enumerated system navigation targets for the app.navigate capability.

The Runtime only ever accepts a NavigationTarget enum id. Platform adapters map
the enum to their own fixed launch arguments; callers (including model output)
can never supply a raw action, component, URI or extras. Each target declares
the expected foreground app and activity tokens so post-action verification is
deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from mobile_agent.domain.errors import ErrorCategory, MobileAgentError


class NavigationTarget(str, Enum):
    """Allowlisted system settings destinations supported by app.navigate@1."""

    SETTINGS_HOME = "settings.home"
    SETTINGS_WIFI = "settings.wifi"
    SETTINGS_BLUETOOTH = "settings.bluetooth"
    SETTINGS_WIRELESS = "settings.wireless"
    SETTINGS_DISPLAY = "settings.display"
    SETTINGS_SOUND = "settings.sound"
    SETTINGS_STORAGE = "settings.storage"
    SETTINGS_APPS = "settings.apps"
    SETTINGS_SECURITY = "settings.security"
    SETTINGS_LOCATION = "settings.location"
    SETTINGS_DATE = "settings.date"
    SETTINGS_LANGUAGE = "settings.language"
    SETTINGS_ACCESSIBILITY = "settings.accessibility"
    SETTINGS_ABOUT = "settings.about"


@dataclass(frozen=True, slots=True)
class NavigationTargetSpec:
    """Platform-neutral verification metadata for one navigation target."""

    target: NavigationTarget
    label: str
    expected_app_id: str
    activity_tokens: tuple[str, ...] = ()


_SETTINGS_APP = "com.android.settings"

NAVIGATION_TARGETS: dict[NavigationTarget, NavigationTargetSpec] = {
    NavigationTarget.SETTINGS_HOME: NavigationTargetSpec(
        NavigationTarget.SETTINGS_HOME, "系统设置首页", _SETTINGS_APP
    ),
    NavigationTarget.SETTINGS_WIFI: NavigationTargetSpec(
        NavigationTarget.SETTINGS_WIFI, "WLAN 设置", _SETTINGS_APP, ("wifi",)
    ),
    NavigationTarget.SETTINGS_BLUETOOTH: NavigationTargetSpec(
        NavigationTarget.SETTINGS_BLUETOOTH, "蓝牙设置", _SETTINGS_APP, ("bluetooth",)
    ),
    NavigationTarget.SETTINGS_WIRELESS: NavigationTargetSpec(
        NavigationTarget.SETTINGS_WIRELESS,
        "网络和互联网设置",
        _SETTINGS_APP,
        ("wireless", "network"),
    ),
    NavigationTarget.SETTINGS_DISPLAY: NavigationTargetSpec(
        NavigationTarget.SETTINGS_DISPLAY, "显示设置", _SETTINGS_APP, ("display",)
    ),
    NavigationTarget.SETTINGS_SOUND: NavigationTargetSpec(
        NavigationTarget.SETTINGS_SOUND, "声音设置", _SETTINGS_APP, ("sound", "volume")
    ),
    NavigationTarget.SETTINGS_STORAGE: NavigationTargetSpec(
        NavigationTarget.SETTINGS_STORAGE, "存储设置", _SETTINGS_APP, ("storage",)
    ),
    NavigationTarget.SETTINGS_APPS: NavigationTargetSpec(
        NavigationTarget.SETTINGS_APPS,
        "应用管理",
        _SETTINGS_APP,
        ("manageapplications", "installedapp", "apps"),
    ),
    NavigationTarget.SETTINGS_SECURITY: NavigationTargetSpec(
        NavigationTarget.SETTINGS_SECURITY, "安全设置", _SETTINGS_APP, ("security",)
    ),
    NavigationTarget.SETTINGS_LOCATION: NavigationTargetSpec(
        NavigationTarget.SETTINGS_LOCATION, "位置信息设置", _SETTINGS_APP, ("location",)
    ),
    NavigationTarget.SETTINGS_DATE: NavigationTargetSpec(
        NavigationTarget.SETTINGS_DATE, "日期和时间设置", _SETTINGS_APP, ("date",)
    ),
    NavigationTarget.SETTINGS_LANGUAGE: NavigationTargetSpec(
        NavigationTarget.SETTINGS_LANGUAGE,
        "语言设置",
        _SETTINGS_APP,
        ("locale", "language"),
    ),
    NavigationTarget.SETTINGS_ACCESSIBILITY: NavigationTargetSpec(
        NavigationTarget.SETTINGS_ACCESSIBILITY,
        "无障碍设置",
        _SETTINGS_APP,
        ("accessibility",),
    ),
    NavigationTarget.SETTINGS_ABOUT: NavigationTargetSpec(
        NavigationTarget.SETTINGS_ABOUT,
        "关于手机",
        _SETTINGS_APP,
        ("deviceinfo", "about", "status"),
    ),
}


def parse_navigation_target(raw: object) -> NavigationTarget:
    """Resolve a caller-supplied enum id, rejecting anything not registered."""

    if not isinstance(raw, str):
        raise MobileAgentError(
            code="INVALID_ARGUMENT",
            category=ErrorCategory.VALIDATION,
            message="导航目标必须是字符串枚举 ID",
        )
    try:
        return NavigationTarget(raw)
    except ValueError as error:
        raise MobileAgentError(
            code="NAVIGATION_ACTION_UNKNOWN",
            category=ErrorCategory.VALIDATION,
            message="未登记的导航目标",
            suggested_action="从 app.navigate 支持的枚举 ID 中选择",
        ) from error


def navigation_target_matches(
    spec: NavigationTargetSpec, foreground_app_id: str, foreground_activity: str
) -> bool:
    """Deterministically verify that the foreground matches the target."""

    if foreground_app_id != spec.expected_app_id:
        return False
    if not spec.activity_tokens:
        return True
    activity = foreground_activity.lower()
    return any(token in activity for token in spec.activity_tokens)


@dataclass(frozen=True, slots=True)
class AppNavigationResult:
    """Verified public result of one app.navigate Skill invocation."""

    skill_call_id: str
    device_id: str
    target: NavigationTarget
    label: str
    foreground_app_id: str
    foreground_activity: str
    evidence_refs: tuple[str, ...]
    started_at: str
    completed_at: str
    schema_version: str = "1.0.0"
    skill_id: str = "app.navigate"
    skill_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "skill_call_id": self.skill_call_id,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "device_id": self.device_id,
            "success": True,
            "status": "succeeded",
            "verification": "verified",
            "target": self.target.value,
            "label": self.label,
            "foreground_app": {
                "app_id": self.foreground_app_id,
                "activity": self.foreground_activity,
            },
            "evidence_refs": list(self.evidence_refs),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }
