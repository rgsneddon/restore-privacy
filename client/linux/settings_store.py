"""Durable product settings for Linux client (JSON under XDG data).

Startup/autoconnect default **off** so manual Connect remains until the user
opts in. Optional privacy-scale layers (shape / outer obfuscation / multi-hop)
also default **off** for lean residual (same product policy as Windows).
"""

from __future__ import annotations

import json
import os
import stat
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

SETTINGS_FILENAME = "settings.json"
KEY_RUN_AT_STARTUP = "run_at_startup"
KEY_AUTOCONNECT_ON_LAUNCH = "autoconnect_on_launch"
KEY_PRIVACY_TRAFFIC_SHAPE = "privacy_traffic_shape"
KEY_PRIVACY_OUTER_OBFUSCATION = "privacy_outer_obfuscation"
KEY_PRIVACY_MULTIHOP = "privacy_multihop"
KEY_ENTRY_COUNTRY = "entry_country"
AUTOSTART_DESKTOP_NAME = "restore-privacy.desktop"


def normalize_entry_country(code: str | None) -> str:
    """Product Settings entry-country pin (IS / RO / DE); default Iceland."""
    from client.multihop import normalize_entry_country as _norm

    return _norm(code)


@dataclass
class ProductSettings:
    run_at_startup: bool = False
    autoconnect_on_launch: bool = False
    privacy_traffic_shape: bool = False
    privacy_outer_obfuscation: bool = False
    privacy_multihop: bool = False
    # Residual entry country: IS (default), RO, or DE.
    entry_country: str = "IS"


def settings_dir() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "restore-privacy"
    return Path.home() / ".local" / "share" / "restore-privacy"


def settings_path() -> Path:
    return settings_dir() / SETTINGS_FILENAME


def default_settings() -> ProductSettings:
    return ProductSettings(
        run_at_startup=False,
        autoconnect_on_launch=False,
        privacy_traffic_shape=False,
        privacy_outer_obfuscation=False,
        privacy_multihop=False,
        entry_country="IS",
    )


def load_settings(path: Optional[Path] = None) -> ProductSettings:
    p = path or settings_path()
    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return default_settings()
        return ProductSettings(
            run_at_startup=bool(data.get(KEY_RUN_AT_STARTUP, False)),
            autoconnect_on_launch=bool(data.get(KEY_AUTOCONNECT_ON_LAUNCH, False)),
            privacy_traffic_shape=bool(data.get(KEY_PRIVACY_TRAFFIC_SHAPE, False)),
            privacy_outer_obfuscation=bool(
                data.get(KEY_PRIVACY_OUTER_OBFUSCATION, False)
            ),
            privacy_multihop=bool(data.get(KEY_PRIVACY_MULTIHOP, False)),
            entry_country=normalize_entry_country(
                data.get(KEY_ENTRY_COUNTRY, "IS")
            ),
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return default_settings()


def save_settings(settings: ProductSettings, path: Optional[Path] = None) -> Path:
    p = path or settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        KEY_RUN_AT_STARTUP: bool(settings.run_at_startup),
        KEY_AUTOCONNECT_ON_LAUNCH: bool(settings.autoconnect_on_launch),
        KEY_PRIVACY_TRAFFIC_SHAPE: bool(settings.privacy_traffic_shape),
        KEY_PRIVACY_OUTER_OBFUSCATION: bool(settings.privacy_outer_obfuscation),
        KEY_PRIVACY_MULTIHOP: bool(settings.privacy_multihop),
        KEY_ENTRY_COUNTRY: normalize_entry_country(
            getattr(settings, "entry_country", "IS")
        ),
    }
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return p


def should_autoconnect_on_launch(settings: Optional[ProductSettings] = None) -> bool:
    s = settings if settings is not None else load_settings()
    return bool(s.autoconnect_on_launch)


def should_run_at_startup(settings: Optional[ProductSettings] = None) -> bool:
    s = settings if settings is not None else load_settings()
    return bool(s.run_at_startup)


def autostart_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "autostart"
    return Path.home() / ".config" / "autostart"


def autostart_desktop_path() -> Path:
    return autostart_dir() / AUTOSTART_DESKTOP_NAME


def resolve_client_launch_command() -> list[str]:
    """Command argv for XDG autostart Exec= line."""
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).resolve())]
    root = str(Path(__file__).resolve().parents[2])
    return [str(Path(sys.executable).resolve()), "-m", "client.linux"]


def apply_run_at_startup(enabled: bool) -> str:
    """Create or remove XDG autostart desktop entry. Best-effort status string."""
    if sys.platform == "win32":
        return "skipped:non_linux"
    link = autostart_desktop_path()
    if not enabled:
        try:
            if link.is_file():
                link.unlink()
            return "disabled"
        except OSError as exc:
            return f"failed:remove:{exc}"
    try:
        folder = autostart_dir()
        folder.mkdir(parents=True, exist_ok=True)
        cmd = resolve_client_launch_command()
        # Escape for desktop Exec (quote if spaces)
        parts = []
        for c in cmd:
            if any(ch in c for ch in ' \t"'):
                parts.append('"' + c.replace('"', '\\"') + '"')
            else:
                parts.append(c)
        exec_line = " ".join(parts)
        root = str(Path(__file__).resolve().parents[2])
        body = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Version=1.0\n"
            "Name=Privacy Restored\n"
            "Comment=Restore Privacy VPN client\n"
            f"Exec={exec_line}\n"
            f"Path={root}\n"
            "Terminal=false\n"
            "Categories=Network;Security;\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        link.write_text(body, encoding="utf-8")
        try:
            link.chmod(link.stat().st_mode | stat.S_IXUSR)
        except OSError:
            pass
        return "enabled"
    except Exception as exc:  # noqa: BLE001
        return f"failed:create:{exc}"


def is_run_at_startup_registered() -> bool:
    try:
        return autostart_desktop_path().is_file()
    except OSError:
        return False


def settings_to_dict(settings: ProductSettings) -> dict[str, bool]:
    return asdict(settings)
