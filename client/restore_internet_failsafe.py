"""Cross-platform Restore Internet failsafe — pure helpers for packaging/tests.

User-facing name: **Restore Internet**
Behaviour: (1) restore residual/normal internet (2) complete product removal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]

# Display name required in every catalog installer
RESTORE_INTERNET_DISPLAY_NAME = "Restore Internet"

# Source paths shipped into packages (relative to repo root)
WINDOWS_BAT = Path("client/windows/Restore Internet.bat")
# ASCII-safe alias without spaces for some copy steps
WINDOWS_BAT_ALIAS = Path("client/windows/RestoreInternet.bat")
LINUX_SCRIPT = Path("client/linux/Restore Internet")
MACOS_COMMAND = Path("client_app/macos/Restore Internet.command")
IOS_TXT = Path("client_app/ios/Restore Internet.txt")
ANDROID_ASSET = Path("client_app/android/app/src/main/assets/Restore Internet.txt")

PLATFORM_SOURCES: dict[str, Path] = {
    "windows": WINDOWS_BAT,
    "linux": LINUX_SCRIPT,
    "macos": MACOS_COMMAND,
    "ios": IOS_TXT,
    "android": ANDROID_ASSET,
}


def windows_residual_restore_markers() -> tuple[str, ...]:
    """Substrings that must appear in the Windows Restore Internet script."""
    return (
        "route delete 0.0.0.0 mask 128.0.0.0",
        "route delete 128.0.0.0 mask 128.0.0.0",
        "RPT-KS",
        "DefaultOutboundAction",
        "ms_tcpip6",
        "RestorePrivacy",
        rmdir_marker(),
        # Portable SFX extract: remove tree next to this bat (not LocalAppData-only)
        "%~dp0RestorePrivacy.exe",
        "Remove-Item -LiteralPath",
    )


def rmdir_marker() -> str:
    return "LOCALAPPDATA"


def linux_residual_restore_markers() -> tuple[str, ...]:
    return (
        "ip route del 0.0.0.0/1",
        "ip route del 128.0.0.0/1",
        "RPT_KILLSWITCH",
        ".restore-privacy",
        "Restore Internet",
    )


def assert_source_files_exist(root: Path | None = None) -> list[str]:
    """Return list of missing platform Restore Internet source paths."""
    base = root or ROOT
    missing: list[str] = []
    for plat, rel in PLATFORM_SOURCES.items():
        if not (base / rel).is_file():
            missing.append(f"{plat}:{rel.as_posix()}")
    return missing


def package_member_names_for_platform(platform: str) -> tuple[str, ...]:
    """Archive member name fragments that identify Restore Internet in a package."""
    p = platform.lower().strip()
    if p == "windows":
        return ("Restore Internet.bat", "RestoreInternet.bat")
    if p == "linux":
        return ("Restore Internet",)
    if p == "macos":
        return ("Restore Internet.command",)
    if p == "ios":
        return ("Restore Internet.txt",)
    if p == "android":
        return ("Restore Internet.txt", "assets/Restore Internet.txt")
    return (RESTORE_INTERNET_DISPLAY_NAME,)


def inventory_packaging_sources(root: Path | None = None) -> dict[str, str]:
    """Map platform → absolute path of Restore Internet source for packaging."""
    base = root or ROOT
    out: dict[str, str] = {}
    for plat, rel in PLATFORM_SOURCES.items():
        p = base / rel
        out[plat] = str(p) if p.is_file() else ""
    return out
