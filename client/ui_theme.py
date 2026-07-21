"""UI theme: restorebritain.org.uk contact palette, plain-language status, labels.

Palette extracted from https://www.restorebritain.org.uk/contact page stack
(jQuery UI Cupertino theme CSS loaded by that page) plus light chrome for a
sleek product shell. Rounded-edge language is expressed via CORNER_RADIUS and
padding (Tk has limited native rounded widgets).
"""

from __future__ import annotations

import os
from pathlib import Path

# Exact privacy copy retained for product continuity
SCROLLING_PRIVACY_TEXT = (
    "lightweight vpn to restore your privacy - no user data is retained - your privacy is restored"
)

# --- Palette (restorebritain.org.uk/contact -> Cupertino theme CSS) ---
# Source: ajax.googleapis.com/.../themes/cupertino/jquery-ui.css as loaded by the contact page
PALETTE_SOURCE_URL = "https://www.restorebritain.org.uk/contact"
CHROME_BG = "#F2F5F7"  # cupertino #f2f5f7  -  soft page background
PANEL_BG = "#FFFFFF"  # white cards / status panel
PRIMARY = "#2779AA"  # cupertino primary blue
PRIMARY_ACTIVE = "#2694E8"  # lighter interactive blue
PRIMARY_DARK = "#0070A3"
LIGHT_ACCENT = "#DEEDF7"  # cupertino soft blue panel
TEXT = "#222222"  # cupertino body text
TEXT_MUTED = "#363636"
WHITE = "#FFFFFF"
STATUS_OK = "#1B767E"  # site teal accent (homepage embed)  -  color for Connected
STATUS_ERROR = "#CD0A0A"  # cupertino error red  -  color for failed Connect (never a message string)
STATUS_ERROR_FG = STATUS_ERROR  # alias for fg= usage
STATUS_WARN = "#A67C00"
BORDER = "#AED0EA"  # cupertino border blue
BUTTON_CONNECT_BG = PRIMARY
BUTTON_DISCONNECT_BG = "#1B767E"
BUTTON_FG = WHITE
DISABLED_FG = "#AAAAAA"

# Legacy aliases (tests / older imports)
BANNER_BG = PRIMARY_DARK
BANNER_FG = WHITE
WINDOW_BG = PANEL_BG
WINDOW_FG = TEXT
STATUS_FG = TEXT_MUTED
ACCENT_GREEN = STATUS_OK
BUTTON_BG = BUTTON_CONNECT_BG
BUTTON_BG_ACTIVE = BUTTON_DISCONNECT_BG

# Flutter / ARGB
BANNER_BG_ARGB = 0xFF0070A3
CHROME_BG_ARGB = 0xFFF2F5F7
WINDOW_BG_ARGB = 0xFFFFFFFF
WINDOW_FG_ARGB = 0xFF222222
BUTTON_BG_ARGB = 0xFF2779AA
BUTTON_ACTIVE_ARGB = 0xFF1B767E

APP_TITLE = "Restore Privacy"
BANNER_TITLE = "Restore Privacy - UK VPN"

# Rounded-edge visual language (Tk approximates with padx/pady + relief)
CORNER_RADIUS = 14
PANEL_PAD = 12
BUTTON_PAD_X = 18
BUTTON_PAD_Y = 12


def logo_png_candidates() -> list[Path]:
    here = Path(__file__).resolve().parent
    root = here.parent
    return [
        here / "windows" / "native" / "app_icon.png",
        root / "assets" / "brand" / "logo-256.png",
        root / "assets" / "brand" / "logo-512.png",
        root / "assets" / "brand" / "app_icon.png",
    ]


def resolve_logo_png() -> Path | None:
    for p in logo_png_candidates():
        if p.is_file():
            return p
    return None


def connect_button_label(connected: bool) -> str:
    """Primary control: Connect when down, Disconnect when up."""
    return "Disconnect" if connected else "Connect"


# Tunnel UI states (plain language labels  -  never overwrite color constants above)
STATUS_DISCONNECTED = "Disconnected"
STATUS_CONNECTING = "Connecting..."
STATUS_DISCONNECTING = "Disconnecting..."
STATUS_CONNECTED = "Connected - protected"
STATUS_ERROR_LABEL = "Could not connect"


def plain_tunnel_status(
    state: str,
    *,
    vpn_ip: str | None = None,
    detail: str | None = None,
    residual_capture: bool | None = None,
    ipv6_protected: bool | None = None,
) -> str:
    """Map machine state to a short string any user can understand.

    state: disconnected | connecting | connected | disconnecting | error

    When ``residual_capture`` is False, do not claim residual public IP uses the VPN
    (session/queue-only is not product residual protection).

    When residual capture is on but ``ipv6_protected`` is False, do not claim full
    protection — IPv6 may still use the ISP path.
    """
    s = (state or "").strip().lower()
    if s == "connecting":
        return STATUS_CONNECTING
    if s == "disconnecting":
        return STATUS_DISCONNECTING
    if s == "connected":
        if residual_capture is False:
            if vpn_ip:
                return f"Session only - residual IP still on ISP ({vpn_ip})"
            return "Session only - residual IP still on ISP"
        # Residual IPv4 path active
        if ipv6_protected is False:
            if vpn_ip:
                return f"Connected - IPv4 via VPN; IPv6 not protected ({vpn_ip})"
            return "Connected - IPv4 via VPN; IPv6 not protected"
        if ipv6_protected is True:
            if vpn_ip:
                return f"Connected - VPN active; IPv6 ISP path blocked ({vpn_ip})"
            return "Connected - VPN active; IPv6 ISP path blocked"
        # ipv6_protected unknown (legacy callers): keep prior residual wording
        if vpn_ip:
            return f"Connected - your traffic uses the VPN ({vpn_ip})"
        return STATUS_CONNECTED
    if s in ("error", "failed"):
        if detail:
            # Keep short: one line
            d = detail.strip().replace("\n", " ")
            if len(d) > 72:
                d = d[:69] + "..."
            return f"{STATUS_ERROR_LABEL}: {d}"
        return STATUS_ERROR_LABEL
    return STATUS_DISCONNECTED


def version_tuple(version: str) -> tuple[int, ...]:
    """Parse dotted version to comparable ints (non-digits ignored per segment)."""
    parts: list[int] = []
    for seg in (version or "").strip().lstrip("vV").split("."):
        num = "".join(c for c in seg if c.isdigit())
        parts.append(int(num) if num else 0)
    while parts and parts[-1] == 0 and len(parts) > 1:
        # keep trailing zeros meaningful only if mid segments exist  -  leave as-is
        break
    return tuple(parts) if parts else (0,)


def version_is_behind(running: str, latest: str) -> bool:
    """True when running product version is older than catalog latest."""
    return version_tuple(running) < version_tuple(latest)


def _read_version_text(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    # First line only; ignore trailing junk
    line = text.splitlines()[0].strip().lstrip("vV")
    return line or None


def version_file_candidates() -> list[Path]:
    """Locations where product VERSION may live (install tree, frozen, repo).

    Installer writes ``VERSION`` next to the client .exe under
    ``%LOCALAPPDATA%/Programs/RestorePrivacy/``. Frozen PyInstaller layouts
    keep package data under ``_internal`` / ``_MEIPASS``  -  not only
    ``client/ui_theme.py``'s sibling path.
    """
    import sys

    here = Path(__file__).resolve().parent  # client/
    root = here.parent
    out: list[Path] = [
        here / "VERSION",
        root / "client" / "VERSION",
    ]
    # Next to frozen executable / install dir
    try:
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            out.extend(
                [
                    exe_dir / "VERSION",
                    exe_dir / "client" / "VERSION",
                    exe_dir / "_internal" / "client" / "VERSION",
                    exe_dir / "_internal" / "VERSION",
                ]
            )
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                base = Path(meipass)
                out.extend(
                    [
                        base / "client" / "VERSION",
                        base / "VERSION",
                    ]
                )
        else:
            # Dev: also honor cwd and common install dir for testing
            out.append(Path.cwd() / "VERSION")
            out.append(Path.cwd() / "client" / "VERSION")
    except Exception:
        pass
    # Standard Windows install location (even when launched via shortcut)
    try:
        local = os.environ.get("LOCALAPPDATA") or ""
        if local:
            out.append(Path(local) / "Programs" / "RestorePrivacy" / "VERSION")
    except Exception:
        pass
    # De-dupe preserving order
    seen: set[str] = set()
    unique: list[Path] = []
    for p in out:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    return unique


def embedded_package_version() -> str:
    """Version shipped next to this package module (repo / onedir data)."""
    v = _read_version_text(Path(__file__).resolve().parent / "VERSION")
    return v or "0.1.8"


def read_running_version(version_file: Path | None = None) -> str:
    """Read the installed/running product version.

    Prefer an explicit path, then install/frozen/repo candidates, then the
    package-embedded VERSION. Never return a silent ``0.0.0`` when a real
    product version is available on disk or embedded.
    """
    if version_file is not None:
        v = _read_version_text(version_file)
        if v:
            return v
        return embedded_package_version()

    for cand in version_file_candidates():
        v = _read_version_text(cand)
        if v:
            return v
    return embedded_package_version()


def catalog_latest_version() -> str:
    """Latest published product version from status_page downloads catalog."""
    try:
        from status_page.downloads import RELEASE_VERSION

        return str(RELEASE_VERSION).strip()
    except Exception:
        # Frozen clients may lack status_page  -  treat package version as catalog
        return embedded_package_version()


def upgrade_available(running: str | None = None, latest: str | None = None) -> bool:
    run = running if running is not None else read_running_version()
    lat = latest if latest is not None else catalog_latest_version()
    # Unknown/placeholder must not force a false "update available"
    if not run or run in ("0.0.0", "0", "unknown"):
        run = embedded_package_version()
    if not lat or lat in ("0.0.0", "0", "unknown"):
        lat = embedded_package_version()
    return version_is_behind(run, lat)


def upgrade_download_url() -> str:
    """Paid catalog / Windows pay entry (repo is private — never free GH releases).

    Prefer the Stripe payment page for the Windows package so an in-app
    "update" opens the same seamless pay → webhook → one-time proxy path as
    the public status downloads. Fall back to the status host downloads
    section when the catalog module is unavailable (frozen clients).
    """
    try:
        from status_page.downloads import available_downloads

        for a in available_downloads():
            if a.platform == "windows":
                # pay_path, not a.url (a.url is bookkeeping-only GitHub asset URL)
                return a.pay_path
    except Exception:
        pass
    try:
        from status_page.payments import DEFAULT_PRODUCTION_PUBLIC_BASE_URL

        return f"{DEFAULT_PRODUCTION_PUBLIC_BASE_URL}/#downloads"
    except Exception:
        return "https://restore-privacy-status.onrender.com/#downloads"


def upgrade_banner_text(running: str | None = None, latest: str | None = None) -> str | None:
    """Human message when upgrade is available; None if current."""
    run = running if running is not None else read_running_version()
    lat = latest if latest is not None else catalog_latest_version()
    if not run or run in ("0.0.0", "0", "unknown"):
        run = embedded_package_version()
    if not lat or lat in ("0.0.0", "0", "unknown"):
        lat = embedded_package_version()
    if not version_is_behind(run, lat):
        return None
    return f"Update available: you have v{run}, latest is v{lat}"
