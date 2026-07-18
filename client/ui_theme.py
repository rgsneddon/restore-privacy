"""UI tokens: dark-blue chrome, black log, high-contrast white text, logo paths."""

from __future__ import annotations

from pathlib import Path

# Exact scrolling string retained for privacy copy / tests
SCROLLING_PRIVACY_TEXT = (
    "lightweight vpn to restore your privacy - no user data is retained - your privacy is restored"
)

# High-contrast product palette
CHROME_BG = "#0A1F5C"  # dark blue main chrome
BANNER_BG = "#000080"  # classic dark blue (legacy)
BANNER_FG = "#FFFFFF"  # white title text
WINDOW_BG = "#000000"  # black log / output area
WINDOW_FG = "#FFFFFF"  # white text
STATUS_FG = "#E0E0E0"  # light status line
BUTTON_BG = "#1D4ED8"  # connect button blue
BUTTON_BG_ACTIVE = "#047857"  # disconnect (connected) green
BUTTON_FG = "#FFFFFF"
ACCENT_GREEN = "#00FF00"
BORDER_LIGHT = "#3B5BDB"
CORNER_RADIUS = 16  # visual language for rounded chrome (Flutter / canvas)

APP_TITLE = "RESTORE PRIVACY"
BANNER_TITLE = "Restore Privacy - Tunnel Client"

# Flutter / Android color ints (ARGB)
BANNER_BG_ARGB = 0xFF000080
CHROME_BG_ARGB = 0xFF0A1F5C
WINDOW_BG_ARGB = 0xFF000000
WINDOW_FG_ARGB = 0xFFFFFFFF
BUTTON_BG_ARGB = 0xFF1D4ED8
BUTTON_ACTIVE_ARGB = 0xFF047857


def logo_png_candidates() -> list[Path]:
    """Ordered paths for product logo (first existing file wins)."""
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
    """Single control label: Connect when down, Disconnect when up."""
    return "Disconnect" if connected else "Connect"


def connect_button_is_disconnect_mode(connected: bool) -> bool:
    return bool(connected)
