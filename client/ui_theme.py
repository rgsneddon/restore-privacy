"""UI theme: Evolve-inspired residual VPN chrome + plain-language status.

Dark tokens match Evolve desktop (``evolve/lib/theme/app_theme.dart``):
``#0D0F14`` canvas, ``#151922`` cards, indigo ``#6C63FF``, teal ``#00D9C0``.
Light mode keeps the same accents on a professional paper stack.
Rounded-edge language is padding + rings (classic Tk has no CSS radius).
"""

from __future__ import annotations

import os
import urllib.parse
from pathlib import Path
from typing import Any

# Exact privacy copy retained for product continuity (static banner/message — not animated)
PRIVACY_MESSAGE_TEXT = (
    "lightweight vpn to restore your privacy - no user data is retained - your privacy is restored"
)

# Evolve desktop chrome (evolve/lib/theme/app_theme.dart) — residual VPN mimic
PALETTE_SOURCE_URL = "evolve/lib/theme/app_theme.dart"
EVOLVE_BG = "#0D0F14"
EVOLVE_CARD = "#151922"
EVOLVE_ACCENT = "#6C63FF"
EVOLVE_SECONDARY = "#00D9C0"
EVOLVE_FILL = "#1A1F2B"
EVOLVE_TEXT = "#E8EAED"
EVOLVE_HAIRLINE = "#2A3142"

# UI mode preference (product settings ``ui_mode``)
UI_MODE_LIGHT = "light"
UI_MODE_DARK = "dark"
UI_MODES = (UI_MODE_LIGHT, UI_MODE_DARK)
# 1.2.4 product default: Evolve dark canvas
DEFAULT_UI_MODE = UI_MODE_DARK

# Light — same indigo/teal accents on a professional paper stack
_LIGHT_TOKENS: dict[str, str] = {
    "chrome_bg": "#F4F5F8",
    "panel_bg": "#FFFFFF",
    "primary": EVOLVE_ACCENT,
    "primary_active": "#8B85FF",
    "primary_dark": "#4A44C4",
    "light_accent": "#EEEDFF",
    "text": "#1A1C23",
    "text_muted": "#5C6470",
    "white": "#FFFFFF",
    "status_ok": "#0B9B8A",
    "status_error": "#C62828",
    "status_warn": "#A67C00",
    "border": "#D5D8E0",
    "neon_border": EVOLVE_ACCENT,
    "neon_teal": EVOLVE_SECONDARY,
    "button_connect_bg": EVOLVE_ACCENT,
    "button_disconnect_bg": "#0B9B8A",
    "button_fg": "#FFFFFF",
    "disabled_fg": "#AAAAAA",
}

# Dark — Evolve canvas / card / indigo / teal
_DARK_TOKENS: dict[str, str] = {
    "chrome_bg": EVOLVE_BG,
    "panel_bg": EVOLVE_CARD,
    "primary": EVOLVE_ACCENT,
    "primary_active": "#8B85FF",
    "primary_dark": "#A8A3FF",
    "light_accent": EVOLVE_FILL,
    "text": EVOLVE_TEXT,
    "text_muted": "#9AA3B2",
    "white": "#FFFFFF",
    "status_ok": EVOLVE_SECONDARY,
    "status_error": "#FF6B6B",
    "status_warn": "#E0B84A",
    "border": EVOLVE_HAIRLINE,
    "neon_border": EVOLVE_ACCENT,
    "neon_teal": EVOLVE_SECONDARY,
    "button_connect_bg": EVOLVE_ACCENT,
    "button_disconnect_bg": EVOLVE_SECONDARY,
    "button_fg": "#0D0F14",
    "disabled_fg": "#5A6270",
}


def normalize_ui_mode(mode: str | None) -> str:
    """Return ``light`` or ``dark``; unknown / empty → dark (1.2.4 default)."""
    m = (mode or "").strip().lower()
    if m in ("light", "day", "white"):
        return UI_MODE_LIGHT
    if m in ("dark", "night", "black"):
        return UI_MODE_DARK
    return DEFAULT_UI_MODE


def theme_tokens(mode: str | None = None) -> dict[str, str]:
    """Shipped chrome/panel/text tokens for *mode* (light or dark).

    Pure map — no Tk. Status OK/error stay distinct in both modes.
    Dark map is the Evolve desktop palette (canvas / card / indigo / teal).
    """
    if normalize_ui_mode(mode) == UI_MODE_DARK:
        return dict(_DARK_TOKENS)
    return dict(_LIGHT_TOKENS)


def hero_orb_palette(
    state: str,
    tokens: dict[str, str] | None = None,
) -> dict[str, str]:
    """Ring / core / glow / dot colors for the main-window status orb.

    Pure helper (no Tk). *state* is disconnected | connecting | connected |
    disconnecting | error. Unknown → disconnected.
    """
    t = dict(tokens) if tokens else theme_tokens(DEFAULT_UI_MODE)
    s = (state or "").strip().lower()
    if s == "connected":
        return {
            "ring": t["status_ok"],
            "core": t["panel_bg"],
            "glow": t["status_ok"],
            "dot": t["status_ok"],
        }
    if s in ("connecting", "disconnecting"):
        return {
            "ring": t["primary"],
            "core": t["light_accent"],
            "glow": t["primary"],
            "dot": t["primary_active"],
        }
    if s in ("error", "failed"):
        return {
            "ring": t["status_error"],
            "core": t["panel_bg"],
            "glow": t["status_error"],
            "dot": t["status_error"],
        }
    return {
        "ring": t["border"],
        "core": t["light_accent"],
        "glow": t["chrome_bg"],
        "dot": t["text_muted"],
    }


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


# Module-level constants = 1.2.4 dark (Evolve) defaults
CHROME_BG = _DARK_TOKENS["chrome_bg"]
PANEL_BG = _DARK_TOKENS["panel_bg"]
PRIMARY = _DARK_TOKENS["primary"]
PRIMARY_ACTIVE = _DARK_TOKENS["primary_active"]
PRIMARY_DARK = _DARK_TOKENS["primary_dark"]
LIGHT_ACCENT = _DARK_TOKENS["light_accent"]
TEXT = _DARK_TOKENS["text"]
TEXT_MUTED = _DARK_TOKENS["text_muted"]
WHITE = _DARK_TOKENS["white"]
STATUS_OK = _DARK_TOKENS["status_ok"]
STATUS_ERROR = _DARK_TOKENS["status_error"]
STATUS_ERROR_FG = STATUS_ERROR  # alias for fg= usage
STATUS_WARN = _DARK_TOKENS["status_warn"]
BORDER = _DARK_TOKENS["border"]
NEON_BORDER = _DARK_TOKENS["neon_border"]
NEON_TEAL = _DARK_TOKENS["neon_teal"]
BUTTON_CONNECT_BG = _DARK_TOKENS["button_connect_bg"]
BUTTON_DISCONNECT_BG = _DARK_TOKENS["button_disconnect_bg"]
BUTTON_FG = _DARK_TOKENS["button_fg"]
DISABLED_FG = _DARK_TOKENS["disabled_fg"]
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
BANNER_BG_ARGB = 0xFF6C63FF
CHROME_BG_ARGB = 0xFF0D0F14
WINDOW_BG_ARGB = 0xFF151922
WINDOW_FG_ARGB = 0xFFE8EAED
BUTTON_BG_ARGB = 0xFF6C63FF
BUTTON_ACTIVE_ARGB = 0xFF00D9C0

APP_TITLE = "Restore Privacy"
BANNER_TITLE = "Restore Privacy - Virtual Private Network"

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
    if v:
        return v
    # Prefer support-log resolver (frozen MEIPASS / install tree)
    try:
        from client.connection_log import product_client_version

        pv = (product_client_version() or "").strip()
        if pv and pv not in ("unknown", "0.5.8"):
            return pv
    except Exception:  # noqa: BLE001
        pass
    # Last resort: never invent 0.5.8
    return "0.0.0"


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
        return "0.0.0"
    # Highest product pin wins (stale VERSION files lose)
    return max(found, key=version_tuple)


# Process-lifetime cache for remote monopin (avoids hammering status host).
_REMOTE_CATALOG_VERSION_CACHE: str | None = None
_REMOTE_CATALOG_INFO_CACHE: dict | None = None
_REMOTE_CATALOG_FETCHED: bool = False

PUBLIC_STATUS_BASE_URL = "https://restoreprivacy.online"
CATALOG_VERSION_API_PATH = "/api/catalog-version"


def client_platform_key() -> str:
    """Platform key for catalog readiness (windows / macos / linux / …)."""
    import sys

    env = (os.environ.get("RPT_CLIENT_PLATFORM") or "").strip().lower()
    if env:
        return env
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def remote_catalog_platform_ready(
    info: dict | None,
    *,
    platform: str | None = None,
) -> bool | None:
    """Whether remote catalog payload marks *platform* package as deployed.

    Returns:
      True  — host explicitly says this platform package is ready
      False — host explicitly says not ready (or platforms_ready omits it as false)
      None  — payload has no readiness signal (legacy API)
    """
    if not isinstance(info, dict):
        return None
    plat = (platform or client_platform_key()).strip().lower()
    # Explicit single-key shortcuts
    for key in (f"{plat}_ready", "windows_ready" if plat == "windows" else ""):
        if key and key in info:
            return bool(info.get(key))
    ready_map = info.get("platforms_ready") or info.get("platform_ready")
    if isinstance(ready_map, dict):
        if plat in ready_map:
            return bool(ready_map.get(plat))
        # map present but platform missing → not ready for this client
        return False
    return None


def fetch_remote_catalog_info(
    *,
    base_url: str | None = None,
    timeout: float = 2.0,
    force: bool = False,
) -> dict | None:
    """GET public ``/api/catalog-version`` JSON (fail-soft)."""
    global _REMOTE_CATALOG_VERSION_CACHE, _REMOTE_CATALOG_INFO_CACHE, _REMOTE_CATALOG_FETCHED
    if _REMOTE_CATALOG_FETCHED and not force:
        return _REMOTE_CATALOG_INFO_CACHE
    base = (base_url or PUBLIC_STATUS_BASE_URL).rstrip("/")
    url = f"{base}{CATALOG_VERSION_API_PATH}"
    try:
        import json
        import urllib.request

        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "RestorePrivacy-client"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=float(timeout)) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        if not isinstance(data, dict):
            data = {}
        ver = str((data or {}).get("catalog_version") or "").strip().lstrip("vV")
        if ver and ver[0].isdigit():
            _REMOTE_CATALOG_VERSION_CACHE = ver
        _REMOTE_CATALOG_INFO_CACHE = data
        _REMOTE_CATALOG_FETCHED = True
        return data
    except Exception:  # noqa: BLE001
        pass
    _REMOTE_CATALOG_FETCHED = True
    return _REMOTE_CATALOG_INFO_CACHE


def fetch_remote_catalog_version(
    *,
    base_url: str | None = None,
    timeout: float = 2.0,
    force: bool = False,
) -> str | None:
    """GET public catalog monopin string only (fail-soft)."""
    info = fetch_remote_catalog_info(
        base_url=base_url, timeout=timeout, force=force
    )
    if not info:
        return _REMOTE_CATALOG_VERSION_CACHE
    ver = str((info or {}).get("catalog_version") or "").strip().lstrip("vV")
    if ver and ver[0].isdigit():
        return ver
    return _REMOTE_CATALOG_VERSION_CACHE


def local_catalog_version() -> str:
    """Monorepo / frozen local catalog pin (never invents a future monopin)."""
    try:
        from status_page.downloads import RELEASE_VERSION

        v = str(RELEASE_VERSION).strip().lstrip("vV")
        if v:
            return v
    except Exception:
        pass
    return embedded_package_version()


def catalog_latest_version(
    *,
    prefer_remote: bool = True,
    platform: str | None = None,
) -> str:
    """Latest **honest** product monopin for upgrade UX.

    Remote pin is used only when it is not ahead of the running package **or**
    the host explicitly marks this client platform package as deployed
    (``platforms_ready`` / ``windows_ready``). Phantom Mac-only bumps
    (e.g. remote 1.1.10 without Windows PE) must not surface as “latest”.
    """
    emb = embedded_package_version()
    local = local_catalog_version() or emb
    plat = platform or client_platform_key()
    if prefer_remote:
        info = fetch_remote_catalog_info()
        remote = None
        if info:
            remote = str((info or {}).get("catalog_version") or "").strip().lstrip(
                "vV"
            )
        if remote and remote[0].isdigit():
            # Remote not newer than what we already ship → fine to report
            if not version_is_behind(emb, remote) and not version_is_behind(
                local, remote
            ):
                return remote
            # Remote is ahead — only trust if this platform package is ready
            ready = remote_catalog_platform_ready(info, platform=plat)
            if ready is True:
                return remote
            # ready False or None (legacy API without readiness) → do not
            # recommend undeployed / phantom monopin; stay on local pin
            return local or emb
    return local or emb


def upgrade_available(
    running: str | None = None,
    latest: str | None = None,
    *,
    platform: str | None = None,
) -> bool:
    """True only when latest is honestly ahead of running for this platform."""
    run = running if running is not None else read_running_version()
    lat = (
        latest
        if latest is not None
        else catalog_latest_version(platform=platform)
    )
    # Unknown/placeholder must not force a false "update available"
    if not run or run in ("0.0.0", "0", "unknown"):
        run = embedded_package_version()
    if not lat or lat in ("0.0.0", "0", "unknown"):
        lat = embedded_package_version()
    if not version_is_behind(run, lat):
        return False
    # Belt: if latest came from remote and platform not ready, refuse
    if latest is None:
        info = _REMOTE_CATALOG_INFO_CACHE
        ready = remote_catalog_platform_ready(info, platform=platform)
        if ready is False:
            return False
        # Legacy API (ready is None) already filtered in catalog_latest_version
    return True


def _public_status_base_url() -> str:
    """Absolute https origin for paid catalog / pay links (never relative)."""
    try:
        from status_page.payments import DEFAULT_PRODUCTION_PUBLIC_BASE_URL

        return str(DEFAULT_PRODUCTION_PUBLIC_BASE_URL).rstrip("/")
    except Exception:
        return PUBLIC_STATUS_BASE_URL.rstrip("/")


def absolute_status_url(path_or_url: str, *, base: str | None = None) -> str:
    """Ensure *path_or_url* is an absolute https URL openable by webbrowser.

    Catalog ``pay_path`` is same-origin relative (``/pay?platform=…``) for HTML.
    Desktop/mobile shells must open absolute ``https://restoreprivacy.online/…``.
    """
    s = (path_or_url or "").strip()
    if not s:
        return f"{(base or _public_status_base_url()).rstrip('/')}/#downloads"
    if s.startswith("https://") or s.startswith("http://"):
        return s
    origin = (base or _public_status_base_url()).rstrip("/")
    if s.startswith("/"):
        return f"{origin}{s}"
    return f"{origin}/{s}"


def catalog_installer_filename(platform: str, version: str | None = None) -> str | None:
    """Current (or *version*) monopin installer basename for *platform*.

    Pure path for tests and upgrade CTA honesty — never a free GitHub URL.
    """
    plat = (platform or "").strip().lower()
    if not plat:
        return None
    ver = (version or "").strip().lstrip("vV")
    if not ver:
        try:
            ver = catalog_latest_version(prefer_remote=False)
        except Exception:  # noqa: BLE001
            ver = embedded_package_version()
    # Canonical basenames (must match status_page.downloads RELEASE_ASSETS)
    suffix = {
        "windows": f"windows-x64-setup.exe",
        "android": "android.apk",
        "macos": "macos.zip",
        "ios": "ios.zip",
        "linux": "linux-x64.tar.gz",
    }.get(plat)
    if not suffix:
        return None
    return f"restore-privacy-client-{ver}-{suffix}"


def upgrade_download_path(
    platform: str | None = None,
    *,
    keygen: str = "",
    session_id: str = "",
    token: str = "",
) -> str:
    """Relative status-host path that starts a **platform monopin installer** fetch.

    Prefer ``/download?token=`` when a grant token is already minted.
    Otherwise ``/upgrade-download?platform=…`` (+ keygen/session when known) so
    the host mints a grant and redirects — **not** ``/pay`` Checkout.
    """
    tok = (token or "").strip()
    if tok:
        return f"/download?token={urllib.parse.quote(tok, safe='')}"
    plat = (platform or "").strip().lower()
    if not plat:
        plat = (os.environ.get("RPT_CLIENT_PLATFORM") or "").strip().lower() or "windows"
    q: list[tuple[str, str]] = [("platform", plat)]
    kg = (keygen or "").strip()
    sid = (session_id or "").strip()
    if kg:
        q.append(("keygen", kg))
    elif sid:
        q.append(("session_id", sid))
    # Embed monopin basename for operators/tests (host always re-resolves live pin)
    fname = catalog_installer_filename(plat)
    if fname:
        q.append(("filename", fname))
    return "/upgrade-download?" + urllib.parse.urlencode(q)


def upgrade_download_url(
    platform: str | None = None,
    *,
    keygen: str = "",
    session_id: str = "",
    token: str = "",
    base_url: str | None = None,
) -> str:
    """Absolute URL that retrieves the platform monopin installer (not /pay).

    With *token*: opens ``/download?token=…`` (browser starts package retrieval).
    With *keygen* / *session_id*: opens ``/upgrade-download`` which mints a grant
    for active subscribers and 302s to the installer.
    Without credentials: still ``/upgrade-download?platform=…`` (keygen form on
    host) — never Stripe Checkout as the primary hop.

    Always absolute ``https://`` for webbrowser / url_launcher.
    """
    base = (base_url or _public_status_base_url()).rstrip("/")
    path = upgrade_download_path(
        platform, keygen=keygen, session_id=session_id, token=token
    )
    return absolute_status_url(path, base=base)


def resolve_upgrade_download_url(
    platform: str | None = None,
    *,
    keygen: str = "",
    session_id: str = "",
    base_url: str | None = None,
    mint_fn: Any = None,
    timeout: float = 8.0,
) -> str:
    """Best-effort mint → direct ``/download?token=`` URL for active subscribers.

    When mint succeeds the browser opens the grant URL and the OS begins the
    installer download immediately. Falls soft to :func:`upgrade_download_url`
    (still not /pay) on network/entitlement failure.
    """
    plat = (platform or "").strip().lower() or (
        (os.environ.get("RPT_CLIENT_PLATFORM") or "").strip().lower() or "windows"
    )
    base = (base_url or _public_status_base_url()).rstrip("/")
    kg = (keygen or "").strip()
    sid = (session_id or "").strip()
    if not kg and not sid:
        return upgrade_download_url(plat, base_url=base)
    if mint_fn is not None:
        try:
            minted = mint_fn(platform=plat, keygen=kg, session_id=sid)
            if isinstance(minted, dict):
                url = str(minted.get("download_url") or "").strip()
                tok = str(minted.get("token") or "").strip()
                if url.startswith("http"):
                    return url
                if tok:
                    return upgrade_download_url(plat, token=tok, base_url=base)
        except Exception:  # noqa: BLE001
            pass
        return upgrade_download_url(
            plat, keygen=kg, session_id=sid, base_url=base
        )
    # Live HTTP mint (JSON)
    try:
        import json
        import urllib.request

        q = urllib.parse.urlencode(
            {
                "platform": plat,
                **({"keygen": kg} if kg else {}),
                **({"session_id": sid} if sid and not kg else {}),
                "format": "json",
            }
        )
        req = urllib.request.Request(
            f"{base}/api/subscriber-upgrade-download?{q}",
            headers={
                "Accept": "application/json",
                "User-Agent": "RestorePrivacy-client-upgrade",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=float(timeout)) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        if isinstance(data, dict) and data.get("ok"):
            url = str(data.get("download_url") or "").strip()
            if url.startswith("http") and "/download?token=" in url:
                return url
            tok = str(data.get("token") or "").strip()
            if tok:
                return upgrade_download_url(plat, token=tok, base_url=base)
    except Exception:  # noqa: BLE001
        pass
    return upgrade_download_url(plat, keygen=kg, session_id=sid, base_url=base)


def upgrade_banner_text(running: str | None = None, latest: str | None = None) -> str | None:
    """Human message when upgrade is available; None if current.

    Wording includes **New version available** so all shells share a clear prompt.
    Uses platform-honest :func:`catalog_latest_version` so phantom monopin
    bumps without a Windows PE never appear.
    """
    run = running if running is not None else read_running_version()
    lat = latest if latest is not None else catalog_latest_version()
    if not run or run in ("0.0.0", "0", "unknown"):
        run = embedded_package_version()
    if not lat or lat in ("0.0.0", "0", "unknown"):
        lat = embedded_package_version()
    if not upgrade_available(running=run, latest=lat):
        return None
    return f"New version available: you have v{run}, latest is v{lat}"


def upgrade_surfaces() -> dict[str, str]:
    """Map of product shell → how upgrade messaging is wired (docs/tests)."""
    return {
        "windows": "client/windows/app.py upgrade_frame + upgrade_banner_text",
        "linux": "client/linux/app.py upgrade banner + upgrade_banner_text",
        "macos": "client_app/lib/main.dart UpgradeBanner (Flutter)",
        "ios": "client_app/lib/main.dart UpgradeBanner (Flutter)",
        "android": "client_app/lib/main.dart UpgradeBanner (Flutter)",
    }
