"""UI theme: restorebritain.org.uk contact palette, plain-language status, labels.

Palette extracted from https://www.restorebritain.org.uk/contact page stack
(jQuery UI Cupertino theme CSS loaded by that page) plus light chrome for a
sleek product shell. Rounded-edge language is expressed via CORNER_RADIUS and
padding (Tk has limited native rounded widgets).
"""

from __future__ import annotations

import os
from pathlib import Path

# Exact privacy copy retained for product continuity (static banner/message — not animated)
PRIVACY_MESSAGE_TEXT = (
    "lightweight vpn to restore your privacy - no user data is retained - your privacy is restored"
)

# --- Palette (restorebritain.org.uk/contact -> Cupertino theme CSS) ---
# Source: ajax.googleapis.com/.../themes/cupertino/jquery-ui.css as loaded by the contact page
PALETTE_SOURCE_URL = "https://www.restorebritain.org.uk/contact"

# UI mode preference (product settings ``ui_mode``)
UI_MODE_LIGHT = "light"
UI_MODE_DARK = "dark"
UI_MODES = (UI_MODE_LIGHT, UI_MODE_DARK)

# Light (default product chrome)
_LIGHT_TOKENS: dict[str, str] = {
    "chrome_bg": "#F2F5F7",  # cupertino soft page background
    "panel_bg": "#FFFFFF",  # white cards / status panel
    "primary": "#2779AA",
    "primary_active": "#2694E8",
    "primary_dark": "#0070A3",
    "light_accent": "#DEEDF7",
    "text": "#222222",
    "text_muted": "#363636",
    "white": "#FFFFFF",
    "status_ok": "#1B767E",
    "status_error": "#CD0A0A",
    "status_warn": "#A67C00",
    "border": "#AED0EA",
    "neon_border": "#2EE6D6",
    "neon_teal": "#1B767E",
    "button_connect_bg": "#2779AA",
    "button_disconnect_bg": "#1B767E",
    "button_fg": "#FFFFFF",
    "disabled_fg": "#AAAAAA",
}

# Dark mode — keep Connected/error readable; neon accents stay high-contrast
_DARK_TOKENS: dict[str, str] = {
    "chrome_bg": "#0B1218",
    "panel_bg": "#152028",
    "primary": "#4BA3D9",
    "primary_active": "#6BB8E8",
    "primary_dark": "#8EC8EA",
    "light_accent": "#1A2A38",
    "text": "#E8EEF2",
    "text_muted": "#A8B4BE",
    "white": "#FFFFFF",
    "status_ok": "#2EE6D6",
    "status_error": "#FF6B6B",
    "status_warn": "#E0B84A",
    "border": "#2A4A5C",
    "neon_border": "#2EE6D6",
    "neon_teal": "#1B767E",
    "button_connect_bg": "#2779AA",
    "button_disconnect_bg": "#1B767E",
    "button_fg": "#FFFFFF",
    "disabled_fg": "#6A7680",
}


def normalize_ui_mode(mode: str | None) -> str:
    """Return ``light`` or ``dark``; unknown / empty → light (product default)."""
    m = (mode or "").strip().lower()
    if m in ("dark", "night", "black"):
        return UI_MODE_DARK
    return UI_MODE_LIGHT


def theme_tokens(mode: str | None = None) -> dict[str, str]:
    """Shipped chrome/panel/text tokens for *mode* (light or dark).

    Pure map — no Tk. Status OK/error stay distinct in both modes.
    """
    if normalize_ui_mode(mode) == UI_MODE_DARK:
        return dict(_DARK_TOKENS)
    return dict(_LIGHT_TOKENS)


def theme_mode_label(mode: str | None) -> str:
    """Short label for the *current* mode (button chrome)."""
    return "Dark" if normalize_ui_mode(mode) == UI_MODE_DARK else "Light"


def theme_toggle_target(mode: str | None) -> str:
    """Opposite mode after a user toggle."""
    return UI_MODE_LIGHT if normalize_ui_mode(mode) == UI_MODE_DARK else UI_MODE_DARK


def theme_toggle_button_text(mode: str | None) -> str:
    """Header control text: shows the mode you switch *to* (sun/moon + word)."""
    if normalize_ui_mode(mode) == UI_MODE_DARK:
        return "☀ Light"
    return "☾ Dark"


# Module-level constants = light defaults (import compatibility / legacy tests)
CHROME_BG = _LIGHT_TOKENS["chrome_bg"]
PANEL_BG = _LIGHT_TOKENS["panel_bg"]
PRIMARY = _LIGHT_TOKENS["primary"]
PRIMARY_ACTIVE = _LIGHT_TOKENS["primary_active"]
PRIMARY_DARK = _LIGHT_TOKENS["primary_dark"]
LIGHT_ACCENT = _LIGHT_TOKENS["light_accent"]
TEXT = _LIGHT_TOKENS["text"]
TEXT_MUTED = _LIGHT_TOKENS["text_muted"]
WHITE = _LIGHT_TOKENS["white"]
STATUS_OK = _LIGHT_TOKENS["status_ok"]
STATUS_ERROR = _LIGHT_TOKENS["status_error"]
STATUS_ERROR_FG = STATUS_ERROR  # alias for fg= usage
STATUS_WARN = _LIGHT_TOKENS["status_warn"]
BORDER = _LIGHT_TOKENS["border"]
NEON_BORDER = _LIGHT_TOKENS["neon_border"]
NEON_TEAL = _LIGHT_TOKENS["neon_teal"]
BUTTON_CONNECT_BG = _LIGHT_TOKENS["button_connect_bg"]
BUTTON_DISCONNECT_BG = _LIGHT_TOKENS["button_disconnect_bg"]
BUTTON_FG = _LIGHT_TOKENS["button_fg"]
DISABLED_FG = _LIGHT_TOKENS["disabled_fg"]
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

    Order is package-first (module / frozen payload), then install dir, then
    cwd leftovers. :func:`read_running_version` picks the **highest** parsed
    version among readable candidates so a stale ``0.2.3`` file next to an
    older install path cannot override a current package pin.
    """
    import sys

    here = Path(__file__).resolve().parent  # client/
    root = here.parent
    out: list[Path] = [
        # Package pin (source of truth in monorepo and onedir _internal)
        here / "VERSION",
        root / "client" / "VERSION",
    ]
    # Next to frozen executable / install dir (installer also writes VERSION)
    try:
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            out.extend(
                [
                    exe_dir / "_internal" / "client" / "VERSION",
                    exe_dir / "_internal" / "VERSION",
                    exe_dir / "client" / "VERSION",
                    exe_dir / "VERSION",
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
            # Dev: also honor cwd for testing
            out.append(Path.cwd() / "client" / "VERSION")
            out.append(Path.cwd() / "VERSION")
    except Exception:
        pass
    # Standard Windows install location (even when launched via shortcut)
    try:
        local = os.environ.get("LOCALAPPDATA") or ""
        if local:
            out.append(Path(local) / "Programs" / "RestorePrivacy" / "VERSION")
            out.append(
                Path(local)
                / "Programs"
                / "RestorePrivacy"
                / "client"
                / "VERSION"
            )
            out.append(
                Path(local)
                / "Programs"
                / "RestorePrivacy"
                / "_internal"
                / "client"
                / "VERSION"
            )
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
    # Fallback matches monorepo catalog pin — never a stale prior ship
    return v or "0.3.6"


def read_running_version(version_file: Path | None = None) -> str:
    """Read the installed/running product version.

    Collects VERSION from package / install candidates and returns the
    **newest** dotted version found (plus the embedded package pin). That way
    a leftover ``0.2.3`` install path cannot make a current ``0.3.6`` package
    report the old number. Explicit *version_file* still wins when readable.
    """
    if version_file is not None:
        v = _read_version_text(version_file)
        if v:
            return v
        return embedded_package_version()

    found: list[str] = []
    for cand in version_file_candidates():
        v = _read_version_text(cand)
        if v:
            found.append(v)
    emb = embedded_package_version()
    if emb:
        found.append(emb)
    if not found:
        return "0.3.6"
    # Highest product pin wins (stale VERSION files lose)
    return max(found, key=version_tuple)


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
        return "https://restoreprivacy.online/#downloads"


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
