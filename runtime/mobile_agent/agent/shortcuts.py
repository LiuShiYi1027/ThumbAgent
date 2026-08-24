"""Deterministic goal-to-shortcut mapping for registered system pages.

When a goal clearly targets one registered system settings destination, the
Runtime executes the deterministic app.navigate path instead of spending model
rounds on GUI exploration. Matching is keyword-based, ordered most-specific
first, and only ever produces a NavigationTarget enum — never raw arguments.
"""

from __future__ import annotations

from mobile_agent.domain.navigation import NavigationTarget

# Ordered: specific pages before the generic settings home.
_SHORTCUT_KEYWORDS: tuple[tuple[NavigationTarget, tuple[str, ...]], ...] = (
    (NavigationTarget.SETTINGS_WIFI, ("wifi", "wi-fi", "wlan", "无线局域网")),
    (NavigationTarget.SETTINGS_BLUETOOTH, ("蓝牙", "bluetooth")),
    (NavigationTarget.SETTINGS_WIRELESS, ("网络和互联网", "无线和网络", "wireless")),
    (NavigationTarget.SETTINGS_DISPLAY, ("显示设置", "显示与亮度", "display")),
    (NavigationTarget.SETTINGS_SOUND, ("声音设置", "音量设置", "sound")),
    (NavigationTarget.SETTINGS_STORAGE, ("存储设置", "存储空间", "storage")),
    (NavigationTarget.SETTINGS_APPS, ("应用管理", "应用列表", "manage apps")),
    (NavigationTarget.SETTINGS_SECURITY, ("安全设置", "security settings")),
    (NavigationTarget.SETTINGS_LOCATION, ("位置信息", "定位设置", "location")),
    (NavigationTarget.SETTINGS_DATE, ("日期和时间", "date settings")),
    (NavigationTarget.SETTINGS_LANGUAGE, ("语言设置", "language settings")),
    (NavigationTarget.SETTINGS_ACCESSIBILITY, ("无障碍", "accessibility")),
    (NavigationTarget.SETTINGS_ABOUT, ("关于手机", "关于本机", "about phone")),
    (NavigationTarget.SETTINGS_HOME, ("系统设置", "open settings", "打开设置")),
)


def match_navigation_shortcut(goal: str) -> NavigationTarget | None:
    """Return the registered navigation target a goal clearly refers to."""

    normalized = goal.strip().lower()
    if not normalized:
        return None
    for target, keywords in _SHORTCUT_KEYWORDS:
        if any(keyword.lower() in normalized for keyword in keywords):
            return target
    return None
