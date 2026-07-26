"""Parsers for bounded Android package-manager output."""

from __future__ import annotations

import re

from mobile_agent.domain.app import InstalledApp


APP_ID_PATTERN = re.compile(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+")


def valid_app_id(value: str) -> bool:
    """Return whether a value is safe as one Android package argument."""

    return bool(APP_ID_PATTERN.fullmatch(value))


def parse_package_list(output: str) -> tuple[str, ...]:
    """Parse and sort strict ``package:<id>`` lines, ignoring malformed output."""

    app_ids = {
        value
        for line in output.splitlines()
        if line.startswith("package:")
        for value in (line.removeprefix("package:").strip(),)
        if valid_app_id(value)
    }
    return tuple(sorted(app_ids))


def parse_package_details(app_id: str, output: str) -> InstalledApp:
    """Extract the stable, privacy-minimized fields used by the public Contract."""

    version_name_match = re.search(r"^\s*versionName=([^\r\n]+)", output, re.MULTILINE)
    version_code_match = re.search(r"^\s*versionCode=(\d+)\b", output, re.MULTILINE)
    installer_match = re.search(
        r"^\s*installerPackageName=([^\s\r\n]+)", output, re.MULTILINE
    )
    enabled_match = re.search(r"^\s*enabled=(true|false|[0-4])\b", output, re.MULTILINE)
    flags_match = re.search(
        r"^\s*(?:pkgFlags|flags)=\[([^\]\r\n]*)\]", output, re.MULTILINE
    )
    installer = installer_match.group(1) if installer_match else None
    if installer in {"null", "None"} or (installer is not None and not valid_app_id(installer)):
        installer = None
    return InstalledApp(
        app_id=app_id,
        version_name=version_name_match.group(1).strip()[:256]
        if version_name_match
        else None,
        version_code=int(version_code_match.group(1)) if version_code_match else None,
        installer_app_id=installer,
        enabled=(enabled_match.group(1) in {"true", "0", "1"})
        if enabled_match
        else None,
        system_app=("SYSTEM" in flags_match.group(1).split())
        if flags_match
        else None,
    )
