"""UI theme: restorebritain.org.uk contact palette, plain-language status, labels.

Palette extracted from https://www.restorebritain.org.uk/contact page stack
(jQuery UI Cupertino theme CSS loaded by that page) plus light chrome for a
sleek product shell. Rounded-edge language is expressed via CORNER_RADIUS and
padding (Tk has limited native rounded widgets).
"""

from __future__ import annotations

from pathlib import Path

# Exact privacy copy retained for product continuity
SCROLLING_PRIVACY_TEXT = (
    "lightweight vpn to restore your privacy - no user data is retained - your privacy is restored"
)

# --- Palette (restorebritain.org.uk/contact → Cupertino theme CSS) ---
# Source: ajax.googleapis.com/.../themes/cupertino/jquery-ui.css as loaded by the contact page
PALETTE_SOURCE_URL = "https://www.restorebritain.org.uk/contact"
CHROME_BG = "#F2F5F7"  # cupertino #f2f5f7 — soft page background
PANEL_BG = "#FFFFFF"  # white cards / status panel
PRIMARY = "#2779AA"  # cupertino primary blue
PRIMARY_ACTIVE = "#2694E8"  # lighter interactive blue
PRIMARY_DARK = "#0070A3"
LIGHT_ACCENT = "#DEEDF7"  # cupertino soft blue panel
TEXT = "#222222"  # cupertino body text
TEXT_MUTED = "#363636"
WHITE = "#FFFFFF"
STATUS_OK = "#1B767E"  # site teal accent (homepage embed) — color for Connected
STATUS_ERROR = "#CD0A0A"  # cupertino error red — color for failed Connect (never a message string)
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
BANNER_TITLE = "Restore Privacy — UK VPN"

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


# Tunnel UI states (plain language labels — never overwrite color constants above)
STATUS_DISCONNECTED = "Disconnected"
STATUS_CONNECTING = "Connecting…"
STATUS_DISCONNECTING = "Disconnecting…"
STATUS_CONNECTED = "Connected — protected"
STATUS_ERROR_LABEL = "Could not connect"


def plain_tunnel_status(
    state: str,
    *,
    vpn_ip: str | None = None,
    detail: str | None = None,
    residual_capture: bool | None = None,
) -> str:
    """Map machine state to a short string any user can understand.

    state: disconnected | connecting | connected | disconnecting | error

    When ``residual_capture`` is False, do not claim residual public IP uses the VPN
    (session/queue-only is not product residual protection).
    """
    s = (state or "").strip().lower()
    if s == "connecting":
        return STATUS_CONNECTING
    if s == "disconnecting":
        return STATUS_DISCONNECTING
    if s == "connected":
        if residual_capture is False:
            if vpn_ip:
                return f"Session only — residual IP still on ISP ({vpn_ip})"
            return "Session only — residual IP still on ISP"
        if vpn_ip:
            return f"Connected — your traffic uses the VPN ({vpn_ip})"
        return STATUS_CONNECTED
    if s in ("error", "failed"):
        if detail:
            # Keep short: one line
            d = detail.strip().replace("\n", " ")
            if len(d) > 72:
                d = d[:69] + "…"
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
        # keep trailing zeros meaningful only if mid segments exist — leave as-is
        break
    return tuple(parts) if parts else (0,)


def version_is_behind(running: str, latest: str) -> bool:
    """True when running product version is older than catalog latest."""
    return version_tuple(running) < version_tuple(latest)


def read_running_version(version_file: Path | None = None) -> str:
    """Read client/VERSION (or explicit path)."""
    if version_file is None:
        version_file = Path(__file__).resolve().parent / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


def catalog_latest_version() -> str:
    """Latest published product version from status_page downloads catalog."""
    try:
        from status_page.downloads import RELEASE_VERSION

        return str(RELEASE_VERSION).strip()
    except Exception:
        return read_running_version()


def upgrade_available(running: str | None = None, latest: str | None = None) -> bool:
    run = running if running is not None else read_running_version()
    lat = latest if latest is not None else catalog_latest_version()
    return version_is_behind(run, lat)


def upgrade_download_url() -> str:
    """Windows installer URL for the catalog release (best-effort)."""
    try:
        from status_page.downloads import available_downloads

        for a in available_downloads():
            if a.platform == "windows":
                return a.url
    except Exception:
        pass
    return (
        "https://github.com/rgsneddon/restore-privacy/releases/latest"
    )


def upgrade_banner_text(running: str | None = None, latest: str | None = None) -> str | None:
    """Human message when upgrade is available; None if current."""
    run = running if running is not None else read_running_version()
    lat = latest if latest is not None else catalog_latest_version()
    if not version_is_behind(run, lat):
        return None
    return f"Update available: you have v{run}, latest is v{lat}"
