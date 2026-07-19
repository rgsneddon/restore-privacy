"""Durable product settings for Windows client (JSON under LocalAppData).

Defaults are both **off** so existing manual-Connect behavior remains until
the user opts into seamless power-up.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional


SETTINGS_FILENAME = "settings.json"
KEY_RUN_AT_STARTUP = "run_at_startup"
KEY_AUTOCONNECT_ON_LAUNCH = "autoconnect_on_launch"


@dataclass
class ProductSettings:
    run_at_startup: bool = False
    autoconnect_on_launch: bool = False


def settings_dir() -> Path:
    """Directory for durable prefs (created on save)."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "RestorePrivacy"


def settings_path() -> Path:
    return settings_dir() / SETTINGS_FILENAME


def default_settings() -> ProductSettings:
    return ProductSettings(run_at_startup=False, autoconnect_on_launch=False)


def load_settings(path: Optional[Path] = None) -> ProductSettings:
    """Load settings from disk; missing/corrupt file → defaults (both off)."""
    p = path or settings_path()
    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return default_settings()
        return ProductSettings(
            run_at_startup=bool(data.get(KEY_RUN_AT_STARTUP, False)),
            autoconnect_on_launch=bool(data.get(KEY_AUTOCONNECT_ON_LAUNCH, False)),
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return default_settings()


def save_settings(settings: ProductSettings, path: Optional[Path] = None) -> Path:
    """Persist settings; returns path written."""
    p = path or settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        KEY_RUN_AT_STARTUP: bool(settings.run_at_startup),
        KEY_AUTOCONNECT_ON_LAUNCH: bool(settings.autoconnect_on_launch),
    }
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return p


def should_autoconnect_on_launch(settings: Optional[ProductSettings] = None) -> bool:
    s = settings if settings is not None else load_settings()
    return bool(s.autoconnect_on_launch)


def should_run_at_startup(settings: Optional[ProductSettings] = None) -> bool:
    s = settings if settings is not None else load_settings()
    return bool(s.run_at_startup)


def startup_shortcut_name() -> str:
    return "Privacy Restored.lnk"


def startup_folder() -> Path:
    """Per-user Startup folder (no elevation required)."""
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return (
        Path(appdata)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )


def resolve_client_launch_target() -> tuple[str, str, str]:
    """Return (exe_or_python, args, cwd) for Startup shortcut target."""
    if getattr(sys, "frozen", False):
        exe = str(Path(sys.executable).resolve())
        return exe, "", str(Path(exe).parent)
    # Dev: pythonw -m client.windows from repo root when possible
    try:
        from client.windows.launch_gui import resolve_pythonw, launch_argv_windowed

        exe, args, cwd = launch_argv_windowed()
        return exe, " ".join(args) if isinstance(args, list) else str(args), cwd
    except Exception:
        exe = str(Path(sys.executable).resolve())
        root = str(Path(__file__).resolve().parents[2])
        return exe, "-m client.windows", root


def apply_run_at_startup(enabled: bool) -> str:
    """Create or remove Startup-folder shortcut. Returns status string.

    Best-effort; does not raise on permission failures (returns failed:…).
    """
    if sys.platform != "win32":
        return "skipped:non_windows"
    folder = startup_folder()
    link = folder / startup_shortcut_name()
    if not enabled:
        try:
            if link.is_file():
                link.unlink()
            return "disabled"
        except OSError as exc:
            return f"failed:remove:{exc}"

    try:
        folder.mkdir(parents=True, exist_ok=True)
        target, params, cwd = resolve_client_launch_target()
        # PowerShell WScript.Shell shortcut
        import subprocess

        ps = (
            f'$ws = New-Object -ComObject WScript.Shell; '
            f'$s = $ws.CreateShortcut({str(link)!r}); '
            f'$s.TargetPath = {target!r}; '
            f'$s.Arguments = {params!r}; '
            f'$s.WorkingDirectory = {cwd!r}; '
            f'$s.Description = "Privacy Restored — start with Windows"; '
            f"$s.Save();"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0 or not link.is_file():
            err = (r.stderr or r.stdout or "shortcut failed").strip()[:160]
            return f"failed:create:{err}"
        return "enabled"
    except Exception as exc:
        return f"failed:create:{exc}"


def is_run_at_startup_registered() -> bool:
    """True when Startup shortcut currently exists."""
    try:
        return (startup_folder() / startup_shortcut_name()).is_file()
    except OSError:
        return False


def settings_to_dict(settings: ProductSettings) -> dict[str, bool]:
    return asdict(settings)
