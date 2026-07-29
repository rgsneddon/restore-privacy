#!/usr/bin/env python3
"""Windows RPT client — seamless Connect/Disconnect product shell.

Licence acceptance required before Connect. Anonymous device registration
(no admin verification). Residual tunnel may still elevate for OS routing.
Close hides the window; Disconnect stops the tunnel.
"""

from __future__ import annotations

import os
import sys
import threading
import webbrowser
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import font as tkfont

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from client.connect import ConnectState, RptClient
from client.ui_theme import (
    APP_TITLE,
    BANNER_TITLE,
    BORDER,
    BUTTON_CONNECT_BG,
    BUTTON_DISCONNECT_BG,
    BUTTON_FG,
    CHROME_BG,
    CORNER_RADIUS,
    DISABLED_FG,
    LIGHT_ACCENT,
    PANEL_BG,
    PANEL_PAD,
    PRIMARY,
    PRIMARY_DARK,
    PRIVACY_MESSAGE_TEXT,
    STATUS_ERROR,
    STATUS_ERROR_FG,
    STATUS_OK,
    STATUS_WARN,
    TEXT,
    TEXT_MUTED,
    WHITE,
    catalog_latest_version,
    connect_button_label,
    normalize_ui_mode,
    plain_tunnel_status,
    read_running_version,
    resolve_logo_png,
    theme_tokens,
    theme_toggle_button_text,
    theme_toggle_target,
    upgrade_available,
    upgrade_banner_text,
    upgrade_download_url,
)
from client.windows.elevate import (
    elevate_if_needed,
    is_admin,
    should_exit_after_elevation,
)
from client.connection_log import (
    KIND_CONNECT,
    KIND_DISCONNECT,
    KIND_ERROR,
    KIND_LEAK_TEST,
    KIND_SESSION,
    append_event,
    format_export,
    read_events,
)
from client.leak_test import run_product_leak_test
from client.licence_gate import (
    LICENCE_ACCEPT_BUTTON,
    LICENCE_PROMPT_TITLE,
    accept_licence,
    assert_may_connect,
    has_accepted_licence,
    licence_url,
    may_connect,
    needs_keygen_unlock,
    needs_licence_renewal,
    short_licence_summary,
)
from client.payment_entitlement import (
    CONNECT_BLOCKED_KEYGEN_MSG,
    PAYMENT_CONNECT_DISCLAIMER_PLAIN,
    ensure_entitlement_for_connect,
    import_keygen_and_verify,
    import_session_and_verify,
    load_payment_entitlement,
    payment_allows_connect,
    renew_licence_message,
    renew_licence_url,
)
from client.startup_bootstrap import bootstrap_payment_entitlement
from client.registration_copy import (
    ANON_REGISTRATION_SUMMARY,
    ANON_REGISTRATION_TITLE,
    OS_PRIVILEGE_HONESTY,
    SEAMLESS_HINT,
    SEAMLESS_TAGLINE,
)
from client.transparency_copy import (
    CONNECTION_LOG_DISCLAIMER,
    CONNECTION_LOG_TITLE,
    DPI_MITIGATION_DISCLAIMER,
    DPI_MITIGATION_TITLE,
    EXPORT_LOG_BUTTON,
    LEAK_TEST_BUTTON,
    LEAK_TEST_DISCLAIMER,
    LEAK_TEST_TITLE,
)
from client.node_ping import measure_settings_pings
from client.privacy_live import hot_apply_privacy_scale, prefs_from_product_settings
from client.product_policy import (
    EXPLAINER_CORE_VPN,
    EXPLAINER_MULTIHOP,
    EXPLAINER_OUTER_OBFUSCATION,
    EXPLAINER_TRAFFIC_SHAPE,
)
from client.first_run_flow import (
    FIRST_RUN_SETTINGS_GEOMETRY,
    FIRST_RUN_SETTINGS_MINSIZE,
    MAIN_CONNECT_GEOMETRY,
    first_run_next_surface,
    mark_first_run_settings_completed,
    post_keygen_next_surface,
)
from client.windows.ui_chrome import (
    NEON_BORDER,
    NEON_BORDER_DIM,
    SwitchToggle,
    apply_centered_window,
    bind_scrollable_canvas,
    make_neon_card,
    style_primary_button,
    surface_default_size,
    surface_geometry_string,
    surface_min_size,
)
from client.country_select import (
    catalog_country_options,
    default_entry_country,
    entry_country_allows_connect,
    label_to_country_code,
    option_label_for_code,
    resolve_entry_country_selection,
)
from client.windows.settings_store import (
    ProductSettings,
    apply_run_at_startup,
    load_settings,
    normalize_entry_country,
    save_settings,
    should_autoconnect_on_launch,
)
from client.windows.tray_win import (
    TRAY_DISPLAY_NAME,
    WindowsSystemTray,
    purge_product_tray_icon,
    resolve_tray_icon_path,
)
from client.windows.window_icon import (
    apply_brand_window_icon,
    set_process_app_user_model_id,
)
from client.flag_images import flag_image_path
from client.windows.tunnel_win import (
    ipv6_residual_protected,
    residual_ip_capture_active,
    restore_windows_residual_path,
    session_ok_without_residual_capture,
    start_full_tunnel,
    stop_full_tunnel,
)
from client.windows.window_foreground import bring_tk_window_forward


# Main status line when the user chooses Quit (button or tray).
QUIT_STATUS_REMARK = "quitting RPT client..."


def disconnect_full_tunnel(
    tunnel, client, *, preserve_message: bool = False
) -> None:
    """Idempotent full stop - Disconnect button, Quit, or cleanup after failed attach.

    Always restores residual internet (dual /1, KS, IPv6) even when ``tunnel``
    is None or in-memory flags are incomplete.

    Set ``preserve_message=True`` when cleaning up a failed Connect so
    ``tunnel.message`` is not replaced with the teardown success string.
    """
    try:
        stop_full_tunnel(tunnel, client, preserve_message=preserve_message)
    except Exception:
        try:
            if client is not None:
                client.disconnect()
        except Exception:
            pass
        # stop_full_tunnel failed mid-way — still force residual restore
        try:
            host = getattr(tunnel, "server_host", None) if tunnel is not None else None
            restore_windows_residual_path(server_host=host)
        except Exception:
            pass


def windows_disconnect_quit_teardown_plan() -> list[dict]:
    """Ordered Disconnect/Quit residual stages (pure; for tests/instrumentation).

    Quit uses a **single** ``disconnect_full_tunnel`` pass (which already runs
    residual restore inside ``stop_full_tunnel``). A second top-level restore
    after disconnect is **not** on the critical path (removed as redundant).
    """
    return [
        {
            "stage": "disconnect_full_tunnel",
            "blocks_exit": True,
            "includes_residual_restore": True,
            "note": "stop_full_tunnel: full restore → TUN close → route-only re-pass",
        },
        {
            "stage": "extra_restore_after_disconnect",
            "blocks_exit": False,
            "skipped": True,
            "note": "removed: duplicate full restore after disconnect_full_tunnel",
        },
        {
            "stage": "session_udp_close",
            "blocks_exit": True,
            "note": "inside stop_full_tunnel / client.disconnect",
        },
    ]


def run_quit_residual_teardown(tunnel, client) -> None:
    """Full residual teardown for Quit — safe to run **off** the Tk UI thread.

    Single-pass: ``disconnect_full_tunnel`` → ``stop_full_tunnel`` already
    restores residual routes (dual /1, KS, IPv6) before and (routes-only) after
    TUN close. A second full restore here was pure serial dead time on Quit.

    When *tunnel* is None, ``stop_full_tunnel`` still runs a full residual
    restore so dual /1 is not left applied.
    """
    try:
        disconnect_full_tunnel(tunnel, client)
    except Exception:
        pass


def apply_quit_status_remark(status_var, detail_var=None) -> str:
    """Set main status surface to the product Quit remark. Returns the phrase."""
    remark = QUIT_STATUS_REMARK
    try:
        status_var.set(remark)
    except Exception:
        pass
    if detail_var is not None:
        try:
            detail_var.set(
                "Stopping residual protection and restoring normal internet..."
            )
        except Exception:
            pass
    return remark


def attach_failure_user_message(original: str | None) -> str:
    """User-facing error after a failed tunnel attach (before/after cleanup).

    ``stop_full_tunnel`` rewrites ``result.message`` to a teardown success string;
    Connect must not show that as the reason attach failed.
    """
    msg = (original or "").strip() or "Tunnel setup failed"
    low = msg.lower()
    if "full teardown complete" in low or low.startswith("tunnel stopped"):
        return "Tunnel setup failed"
    return msg


def auto_connect_on_launch_enabled() -> bool:
    """True when user enabled autoconnect in Settings (default off)."""
    return should_autoconnect_on_launch()


def close_disconnects_tunnel() -> bool:
    """Product policy: closing the window leaves the tunnel running."""
    return False


def non_admin_connect_allowed() -> bool:
    """UI may open without Administrator; residual Connect elevates on demand."""
    try:
        from client.windows.residual_privilege import gui_may_run_as_standard_user

        return bool(gui_may_run_as_standard_user())
    except Exception:
        return True


def product_connect_requires_admin() -> bool:
    """True when *this* GUI process must elevate (or use helper) for residual.

    Residual still needs OS privilege (Wintun + dual /1), but the desktop
    shortcut need not be "Run as administrator" every time — Connect prompts
    UAC once or uses the one-time residual helper task.
    """
    try:
        from client.windows.residual_privilege import (
            product_connect_requires_admin_process,
        )

        return bool(product_connect_requires_admin_process())
    except Exception:
        return True


def layout_pack_bottom_controls_first() -> bool:
    """Connect bar packs at bottom before expanding log (always-visible primary control)."""
    return True


class TunnelClientApp:
    """Seamless shell: hero status, Connect/Disconnect, Settings transparency."""

    DEFAULT_GEOMETRY = MAIN_CONNECT_GEOMETRY
    MIN_WIDTH, MIN_HEIGHT = surface_min_size("main")

    def __init__(self) -> None:
        self.root = tk.Tk()
        self._settings = load_settings()
        self._ui_mode = normalize_ui_mode(getattr(self._settings, "ui_mode", "light"))
        self._t = theme_tokens(self._ui_mode)
        self.root.title(APP_TITLE)
        self.root.configure(bg=self._t["chrome_bg"])
        self._keygen_prompt_win: tk.Toplevel | None = None
        self._settings_win: tk.Toplevel | None = None
        self._settings_scroll_unbind: Callable[[], None] | None = None
        # Size + centre on primary work area (not top-left)
        apply_centered_window(self.root, surface="main")
        self._set_window_icon()
        # UI-only close - tunnel stays up until user presses Disconnect
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_ui_only)

        self._connected = False
        self._busy = False
        self._tunnel = None
        self._connect_gen: int = 0
        self._tray: WindowsSystemTray | None = None
        # Last status headline colour (theme re-apply must not wipe Connected teal)
        self._status_headline_fg: str = TEXT
        self.client = RptClient(status_cb=self._on_client_status)
        # Defer tray until after main chrome exists — avoids racing Win32
        # RegisterClass/CreateWindow with Tk widget construction (seen as AV).
        try:
            self.root.after_idle(self._start_system_tray)
        except Exception:
            self._start_system_tray()

        # Outer chrome with padding (rounded language via spacing)
        self.chrome = tk.Frame(
            self.root, bg=self._t["chrome_bg"], padx=PANEL_PAD + 4, pady=PANEL_PAD + 4
        )
        self.chrome.pack(fill=tk.BOTH, expand=True)

        # --- Bottom: primary control first so it never disappears ---
        self.bottom = tk.Frame(self.chrome, bg=self._t["chrome_bg"])
        self.bottom.pack(side=tk.BOTTOM, fill=tk.X)

        # Entry country (national flag images) — main shell above Connect.
        self._country_opts = catalog_country_options()
        self._country_labels = [o.label() for o in self._country_opts]
        self._flag_photos: dict[str, tk.PhotoImage] = {}
        for _opt in self._country_opts:
            _fp = flag_image_path(_opt.code)
            if _fp is not None:
                try:
                    self._flag_photos[_opt.code] = tk.PhotoImage(file=str(_fp))
                except Exception:
                    pass
        init_entry = normalize_entry_country(
            getattr(self._settings, "entry_country", default_entry_country())
        )
        self._entry_label_var = tk.StringVar(
            value=option_label_for_code(init_entry)
        )
        from client.country_select import country_flag_emoji

        self._flag_var = tk.StringVar(
            value=country_flag_emoji(init_entry) or f"[{init_entry}]"
        )
        self.country_frame = tk.Frame(self.bottom, bg=self._t["chrome_bg"])
        self.country_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 2))
        tk.Label(
            self.country_frame,
            text="Entry country",
            bg=self._t["chrome_bg"],
            fg=self._t["text_muted"],
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(side=tk.TOP, fill=tk.X)
        self._country_row = tk.Frame(self.country_frame, bg=self._t["chrome_bg"])
        self._country_row.pack(side=tk.TOP, fill=tk.X, pady=(2, 0))
        self.country_menu = tk.Menubutton(
            self._country_row,
            textvariable=self._entry_label_var,
            image=self._flag_photos.get(init_entry),
            compound=tk.LEFT,
            bg=self._t["panel_bg"],
            fg=self._t["text"],
            activebackground=self._t["light_accent"],
            activeforeground=self._t["text"],
            highlightthickness=1,
            highlightbackground=self._t["border"] if "border" in self._t else BORDER,
            font=("Segoe UI", 10),
            anchor="w",
            relief=tk.RAISED,
            bd=1,
            direction="below",
            indicatoron=True,
        )
        _cmenu = tk.Menu(
            self.country_menu,
            tearoff=0,
            bg=self._t["panel_bg"],
            fg=self._t["text"],
            activebackground=self._t["light_accent"],
            activeforeground=self._t["text"],
            font=("Segoe UI", 10),
        )
        for _opt in self._country_opts:
            _img = self._flag_photos.get(_opt.code)
            _cmenu.add_command(
                label=f"  {_opt.name} ({_opt.code})",
                image=_img,
                compound=tk.LEFT if _img is not None else tk.NONE,
                command=lambda c=_opt.code: self._select_main_entry_country(c),
            )
        self.country_menu.configure(menu=_cmenu)
        self._country_menu_obj = _cmenu
        self.country_menu.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.flag_label = None

        self.btn_var = tk.StringVar(value=connect_button_label(False))
        self.connect_btn = tk.Button(
            self.bottom,
            textvariable=self.btn_var,
            command=self._on_toggle_connect,
            bg=self._t["button_connect_bg"],
            fg=self._t["button_fg"],
            activebackground=self._t["primary"],
            activeforeground=self._t["button_fg"],
            disabledforeground=self._t["disabled_fg"],
            font=("Segoe UI", 14, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=20,
            pady=16,
            bd=0,
            highlightthickness=0,
        )
        style_primary_button(self.connect_btn, neon=True)
        self.connect_btn.pack(side=tk.TOP, fill=tk.X, pady=(10, 6), ipady=8)

        self.hint_row = tk.Frame(self.bottom, bg=self._t["chrome_bg"])
        self.hint_row.pack(side=tk.TOP, fill=tk.X)
        self.hint = tk.Label(
            self.hint_row,
            text=SEAMLESS_HINT,
            bg=self._t["chrome_bg"],
            fg=self._t["text_muted"],
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        )
        self.hint.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.quit_btn = tk.Button(
            self.hint_row,
            text="Quit",
            command=self._quit_app,
            bg=self._t["chrome_bg"],
            fg=self._t["text_muted"],
            activebackground=self._t["light_accent"],
            activeforeground=self._t["text"],
            relief=tk.FLAT,
            font=("Segoe UI", 8, "underline"),
            cursor="hand2",
            bd=0,
            padx=6,
        )
        self.quit_btn.pack(side=tk.RIGHT)

        # --- Header ---
        self.header = tk.Frame(self.chrome, bg=self._t["chrome_bg"])
        self.header.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        self._logo_photo = None
        self._logo_label = None
        logo = resolve_logo_png()
        if logo is not None:
            try:
                img = tk.PhotoImage(file=str(logo))
                if img.width() > 64:
                    factor = max(1, img.width() // 48)
                    img = img.subsample(factor, factor)
                self._logo_photo = img
                self._logo_label = tk.Label(
                    self.header, image=self._logo_photo, bg=self._t["chrome_bg"]
                )
                self._logo_label.pack(side=tk.LEFT, padx=(0, 10))
            except Exception:
                self._logo_photo = None
                self._logo_label = None

        self.title_col = tk.Frame(self.header, bg=self._t["chrome_bg"])
        self.title_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.title_label = tk.Label(
            self.title_col,
            text=APP_TITLE,
            bg=self._t["chrome_bg"],
            fg=self._t["primary_dark"],
            font=("Segoe UI", 18, "bold"),
            anchor="w",
        )
        self.title_label.pack(fill=tk.X)
        self.banner_label = tk.Label(
            self.title_col,
            text=BANNER_TITLE,
            bg=self._t["chrome_bg"],
            fg=self._t["text_muted"],
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.banner_label.pack(fill=tk.X)
        self.tagline_label = tk.Label(
            self.title_col,
            text=SEAMLESS_TAGLINE,
            bg=self._t["chrome_bg"],
            fg=self._t["primary"],
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        )
        self.tagline_label.pack(fill=tk.X, pady=(2, 0))

        # Settings cog (gear) — pack first so it sits at the right edge
        self.settings_btn = tk.Button(
            self.header,
            text="⚙",
            command=self._open_settings,
            bg=self._t["chrome_bg"],
            fg=self._t["primary_dark"],
            activebackground=self._t["light_accent"],
            activeforeground=self._t["primary_dark"],
            relief=tk.FLAT,
            font=("Segoe UI", 16),
            cursor="hand2",
            bd=0,
            padx=8,
        )
        self.settings_btn.pack(side=tk.RIGHT)
        # Dark/light mode switcher — beside the settings cog (same header row)
        self.theme_btn = tk.Button(
            self.header,
            text=theme_toggle_button_text(self._ui_mode),
            command=self._toggle_ui_mode,
            bg=self._t["chrome_bg"],
            fg=self._t["primary_dark"],
            activebackground=self._t["light_accent"],
            activeforeground=self._t["primary_dark"],
            relief=tk.FLAT,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            bd=0,
            padx=6,
        )
        self.theme_btn.pack(side=tk.RIGHT, padx=(0, 2))

        # --- Upgrade banner (only if behind catalog) ---
        self.upgrade_frame = tk.Frame(
            self.chrome,
            bg=self._t["light_accent"],
            padx=10,
            pady=8,
            highlightbackground=self._t["border"],
            highlightthickness=1,
        )
        self._upgrade_msg = upgrade_banner_text()
        if self._upgrade_msg:
            self.upgrade_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))
            tk.Label(
                self.upgrade_frame,
                text=self._upgrade_msg,
                bg=self._t["light_accent"],
                fg=self._t["text"],
                font=("Segoe UI", 9),
                anchor="w",
                wraplength=400,
                justify=tk.LEFT,
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Button(
                self.upgrade_frame,
                text="Get update",
                command=self._open_upgrade,
                bg=self._t["primary"],
                fg=self._t["white"],
                activebackground=self._t["primary_dark"],
                activeforeground=self._t["white"],
                relief=tk.FLAT,
                font=("Segoe UI", 9, "bold"),
                cursor="hand2",
                padx=10,
                pady=4,
            ).pack(side=tk.RIGHT, padx=(8, 0))

        # --- Hero status card (site neon box / residual-honest) ---
        self.status_card, self.status_card_outer = make_neon_card(
            self.chrome,
            padx=PANEL_PAD + 4,
            pady=PANEL_PAD + 4,
            bg=self._t["panel_bg"],
        )
        self.status_card_outer.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        self.hero_top = tk.Frame(self.status_card, bg=self._t["panel_bg"])
        self.hero_top.pack(fill=tk.X)
        self.vpn_status_caption = tk.Label(
            self.hero_top,
            text="VPN status",
            bg=self._t["panel_bg"],
            fg=self._t["text_muted"],
            font=("Segoe UI", 8),
            anchor="w",
        )
        self.vpn_status_caption.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._licence_badge_var = tk.StringVar(
            value="Licence accepted" if may_connect() else "Licence required"
        )
        self._licence_badge = tk.Label(
            self.hero_top,
            textvariable=self._licence_badge_var,
            bg=self._t["light_accent"] if may_connect() else "#FDECEC",
            fg=self._t["primary_dark"] if may_connect() else self._t["status_error"],
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=2,
        )
        self._licence_badge.pack(side=tk.RIGHT)

        self.status_var = tk.StringVar(value=plain_tunnel_status("disconnected"))
        self.status_label = tk.Label(
            self.status_card,
            textvariable=self.status_var,
            bg=self._t["panel_bg"],
            fg=self._t["text"],
            font=("Segoe UI", 16, "bold"),
            anchor="w",
            wraplength=460,
            justify=tk.LEFT,
        )
        self.status_label.pack(fill=tk.X, pady=(8, 0))

        self.detail_var = tk.StringVar(
            value=(
                "Accept the licence, then press Connect for residual protection."
                if not may_connect()
                else "Ready. Press Connect when you want residual protection."
            )
        )
        self.detail_label = tk.Label(
            self.status_card,
            textvariable=self.detail_var,
            bg=self._t["panel_bg"],
            fg=self._t["text_muted"],
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=460,
            justify=tk.LEFT,
        )
        self.detail_label.pack(fill=tk.X, pady=(6, 0))

        # Licence CTA when not yet accepted (seamless first-run)
        self._licence_cta = tk.Frame(self.status_card, bg=self._t["panel_bg"])
        tk.Button(
            self._licence_cta,
            text=LICENCE_ACCEPT_BUTTON,
            command=self._show_licence_prompt,
            bg=self._t["primary"],
            fg=self._t["white"],
            relief=tk.FLAT,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            padx=12,
            pady=5,
        ).pack(side=tk.LEFT, pady=(10, 0))
        tk.Label(
            self._licence_cta,
            text="Required once before Connect",
            bg=self._t["panel_bg"],
            fg=self._t["text_muted"],
            font=("Segoe UI", 8),
        ).pack(side=tk.LEFT, padx=(10, 0), pady=(10, 0))
        if not may_connect():
            self._licence_cta.pack(fill=tk.X)

        # --- Concise activity log (secondary) ---
        tk.Label(
            self.chrome,
            text="Activity",
            bg=CHROME_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(side=tk.TOP, fill=tk.X)

        self.log_shell = tk.Frame(
            self.chrome, bg=PANEL_BG, highlightbackground=BORDER, highlightthickness=1
        )
        self.log_shell.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(4, 0))
        self.output = tk.Text(
            self.log_shell,
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            insertbackground=TEXT,
            font=("Segoe UI", 9),
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief=tk.FLAT,
            padx=10,
            pady=8,
            height=6,
            borderwidth=0,
        )
        self.output.pack(fill=tk.BOTH, expand=True)

        self._log(f"{APP_TITLE} - ready")
        self._log(PRIVACY_MESSAGE_TEXT)
        self._log("Press Connect to start the VPN. Closing this window does not disconnect.")
        ver = read_running_version()
        self._log(f"Version {ver} (latest catalog: {catalog_latest_version()})")
        if not self._upgrade_msg:
            self._log("You are on the latest published version.")

    def connect_button_text(self) -> str:
        return self.btn_var.get()

    def connect_button_visible(self) -> bool:
        try:
            return bool(self.connect_btn.winfo_ismapped() or self.connect_btn.winfo_viewable())
        except Exception:
            return False

    def _set_window_icon(self) -> None:
        """Taskbar/title-bar brand logo (not the Python/Tk feather)."""
        try:
            status = apply_brand_window_icon(self.root)
            self._icon_status = status
            if status.get("iconphoto") or status.get("iconbitmap"):
                self._icon_photo = getattr(self.root, "_rpt_icon_photo", None)

            def _reapply_brand_icon() -> None:
                try:
                    if not self.root.winfo_exists():
                        return
                except Exception:
                    return
                try:
                    apply_brand_window_icon(self.root)
                except Exception:
                    pass

            try:
                self._icon_reapply_after_id = self.root.after(200, _reapply_brand_icon)
            except Exception:
                self._icon_reapply_after_id = None
        except Exception:
            self._icon_status = {"error": True}


    def _start_system_tray(self) -> None:
        """Tray identity: Privacy Restored + product logo (one system-wide icon)."""
        try:
            # Drop any orphan / other-process product icon (fixed GUID).
            try:
                purge_product_tray_icon()
            except Exception:
                pass
            # Idempotent: never stack a second notify icon in this process.
            if self._tray is not None:
                try:
                    if getattr(self._tray, "is_running", lambda: True)():
                        return
                except Exception:
                    pass
                try:
                    self._tray.stop()
                except Exception:
                    pass
                self._tray = None
            tray = WindowsSystemTray(
                on_show=lambda: self.root.after(0, self._restore_from_tray),
                on_quit=lambda: self.root.after(0, self._quit_app),
                on_connect=lambda: self.root.after(0, self._tray_connect),
                on_disconnect=lambda: self.root.after(0, self._tray_disconnect),
            )
            if tray.start():
                self._tray = tray
                self._log(f"System tray: {TRAY_DISPLAY_NAME}")
        except Exception:
            self._tray = None

    def _stop_system_tray(self) -> None:
        """Remove the process tray icon before exit / elevated re-launch."""
        tray = self._tray
        self._tray = None
        if tray is not None:
            try:
                tray.stop()
            except Exception:
                pass
        # Always purge by product GUID so handoff cannot leave a ghost icon.
        try:
            purge_product_tray_icon()
        except Exception:
            pass

    def _handoff_elevated_connect_exit(self) -> None:
        """Leave residual Connect to the elevated child process (one UI/tray).

        Called when UAC re-launch or residual helper started a new elevated
        product instance with ``--rpt-auto-connect``. Stops this process's tray
        and destroys the shell so the user does not see a second icon or a
        "restarted behind" non-admin window.
        """
        try:
            self._stop_system_tray()
        except Exception:
            pass
        try:
            purge_product_tray_icon()
        except Exception:
            pass
        try:
            # Withdraw first so the window does not flash under other apps
            # while the elevated child maps.
            self.root.withdraw()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def _bring_shell_forward(self, *, force_visible: bool = False) -> str:
        """Raise main shell when user is still using it (no permanent topmost)."""
        try:
            return bring_tk_window_forward(
                self.root, force_visible=bool(force_visible)
            )
        except Exception:  # noqa: BLE001
            return "error:bring_shell"

    def _bring_window_forward(self, win, *, force_visible: bool = False) -> str:
        """Raise a Toplevel (Settings / keygen) without permanent always-on-top."""
        try:
            return bring_tk_window_forward(
                win, force_visible=bool(force_visible)
            )
        except Exception:  # noqa: BLE001
            return "error:bring_window"

    def _restore_from_tray(self) -> None:
        # Tray Show is an explicit user order to restore — force visible + raise.
        try:
            self._bring_shell_forward(force_visible=True)
        except Exception:
            try:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
            except Exception:
                pass

    def _tray_connect(self) -> None:
        if not self._connected and not self._busy:
            self._start_connect()

    def _tray_disconnect(self) -> None:
        if self._connected and not self._busy:
            self._start_disconnect()

    def _sync_tray_status(
        self,
        *,
        connected: bool | None = None,
        residual: bool | None = None,
    ) -> None:
        """Push tray tip+icon from explicit flags (do not rely on stale ``_connected``)."""
        if self._tray is None:
            return
        try:
            conn = self._connected if connected is None else bool(connected)
            res = True if residual is None else bool(residual)
            self._tray.update_status(connected=conn, residual=res)
        except Exception:
            pass

    def _log(self, line: str) -> None:
        # Activity pane is user-visible — never show residual monopin IPv4
        try:
            from client.residual_public import redact_residual_hosts_in_text

            text = redact_residual_hosts_in_text(str(line or ""))
        except Exception:
            text = str(line or "")
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, text + "\n")
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)

    def _connection_log(self, kind: str, message: str) -> None:
        """Persist a user-visible connection event locally (Settings export)."""
        try:
            append_event(kind, message)
        except Exception:
            pass

    def _on_client_status(self, msg: str) -> None:
        """Secondary log only - do not dump raw protocol into main status."""
        def ui() -> None:
            short = msg if len(msg) <= 100 else msg[:97] + "..."
            self._log(short)

        self.root.after(0, ui)

    def _set_status(
        self,
        state: str,
        *,
        vpn_ip: str | None = None,
        detail: str | None = None,
        residual_capture: bool | None = None,
        ipv6_protected: bool | None = None,
    ) -> None:
        """Update main status dialogue and tray to match Connect/Disconnect state."""
        s = (state or "").strip().lower()
        self.status_var.set(
            plain_tunnel_status(
                s,
                vpn_ip=vpn_ip,
                detail=detail,
                residual_capture=residual_capture,
                ipv6_protected=ipv6_protected,
            )
        )
        # Headline colour: residual Connect success is always product teal
        # (STATUS_OK). Never paint Connected residual in error-red — that read as
        # "broken" even when residual public IP was on the VPN. IPv6 honesty stays
        # in the detail line (muted), not the big status label.
        if s == "connected" and residual_capture is not False:
            ok = (self._t or {}).get("status_ok") or STATUS_OK
            self._status_headline_fg = ok
            self.status_label.configure(fg=ok)
            if ipv6_protected is False:
                self.detail_var.set(
                    "Connected — residual public IP uses the VPN. "
                    "Note: IPv6 may still use your ISP (not fully blocked)."
                )
            else:
                self.detail_var.set(
                    "Connected — residual public IP uses the VPN node; "
                    "IPv6 ISP path is blocked."
                )
            # Pass connected=True explicitly - _apply_control may not have run yet
            self._sync_tray_status(connected=True, residual=True)
        elif s == "connected":
            # Session without residual — amber warning (not hard-error red)
            warn = (self._t or {}).get("status_warn") or STATUS_WARN
            self._status_headline_fg = warn
            self.status_label.configure(fg=warn)
            self.detail_var.set(
                "Session up but residual public IP still uses your ISP - not fully protected."
            )
            self._sync_tray_status(connected=True, residual=False)
        elif s == "connecting":
            pd = (self._t or {}).get("primary_dark") or PRIMARY_DARK
            self._status_headline_fg = pd
            self.status_label.configure(fg=pd)
            self.detail_var.set(
                detail
                or "Please wait... setting up a secure connection."
            )
            self._sync_tray_status(connected=False, residual=False)
            # User started Connect from the shell — keep status visible mid-path
            # (not only after Connected). Respect minimize / hide-to-tray.
            try:
                self._bring_shell_forward(force_visible=False)
            except Exception:
                pass
        elif s == "disconnecting":
            pd = (self._t or {}).get("primary_dark") or PRIMARY_DARK
            self._status_headline_fg = pd
            self.status_label.configure(fg=pd)
            self.detail_var.set("Stopping the tunnel and restoring normal internet...")
            # Still show connected tray until teardown finishes
            self._sync_tray_status(connected=True, residual=True)
            try:
                self._bring_shell_forward(force_visible=False)
            except Exception:
                pass
        elif s in ("error", "failed"):
            err = (self._t or {}).get("status_error") or STATUS_ERROR_FG
            self._status_headline_fg = err
            self.status_label.configure(fg=err)
            self.detail_var.set(detail or "Check the activity log, then try Connect again.")
            self._sync_tray_status(connected=False, residual=False)
        else:
            # disconnected
            tx = (self._t or {}).get("text") or TEXT
            self._status_headline_fg = tx
            self.status_label.configure(fg=tx)
            self.detail_var.set("Not connected. Press Connect when you want protection.")
            self._sync_tray_status(connected=False, residual=False)

    def _apply_control(self, *, connected: bool, busy: bool) -> None:
        self._connected = connected
        self._busy = busy
        if busy and not connected:
            label = "Connecting..."
        elif busy and connected:
            label = "Disconnecting..."
        else:
            label = connect_button_label(connected)
        self.btn_var.set(label)
        try:
            self.connect_btn.configure(
                state=tk.DISABLED if busy else tk.NORMAL,
                bg=BUTTON_DISCONNECT_BG if connected and not busy else BUTTON_CONNECT_BG,
            )
        except Exception:
            pass
        # Keep tray aligned whenever button state flips (Connect/Disconnect done)
        if not busy:
            self._sync_tray_status(
                connected=connected,
                residual=connected,  # product success path is residual full tunnel
            )

    def _refresh_licence_badge(self) -> None:
        accepted = may_connect()
        try:
            self._licence_badge_var.set(
                "Licence accepted" if accepted else "Licence required"
            )
            self._licence_badge.configure(
                bg=LIGHT_ACCENT if accepted else "#FDECEC",
                fg=PRIMARY_DARK if accepted else STATUS_ERROR_FG,
            )
            if accepted:
                self._licence_cta.pack_forget()
            else:
                self._licence_cta.pack(fill=tk.X)
        except Exception:
            pass

    def _show_renew_licence_prompt(self) -> None:
        """EXPIRED hard-lock: renew your licence *here* + platform pay portal."""
        ent = load_payment_entitlement()
        plat = (ent.platform or "windows").strip().lower() or "windows"
        url = renew_licence_url(plat, renew_url=ent.renew_url)
        body = renew_licence_message(plat, renew_url=ent.renew_url)
        win = tk.Toplevel(self.root)
        win.title("Renew your licence")
        win.configure(bg=CHROME_BG)
        apply_centered_window(win, surface="renew")
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass
        try:
            self._bring_window_forward(win, force_visible=True)
        except Exception:
            pass
        shell = tk.Frame(win, bg=CHROME_BG, padx=16, pady=14)
        shell.pack(fill=tk.BOTH, expand=True)
        pad, card_outer = make_neon_card(shell, padx=16, pady=14)
        card_outer.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            pad,
            text="Renew your licence",
            bg=PANEL_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            pad,
            text="Your subscription is EXPIRED. Renew your licence *here*:",
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI", 10),
            anchor="w",
            wraplength=500,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 6))
        link = tk.Label(
            pad,
            text=url,
            bg=PANEL_BG,
            fg=PRIMARY,
            font=("Segoe UI", 9, "underline"),
            cursor="hand2",
            anchor="w",
            wraplength=500,
            justify=tk.LEFT,
        )
        link.pack(fill=tk.X, pady=(0, 8))

        def _open_portal(_e: object | None = None) -> None:
            try:
                webbrowser.open(url)
            except Exception as exc:  # noqa: BLE001
                self._log(f"Could not open browser: {exc}. Visit: {url}")

        link.bind("<Button-1>", _open_portal)
        tk.Label(
            pad,
            text=body,
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=500,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 10))
        btn_row = tk.Frame(pad, bg=PANEL_BG)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        open_btn = tk.Button(
            btn_row,
            text="Open payment portal",
            command=_open_portal,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
            font=("Segoe UI", 10, "bold"),
            padx=14,
            pady=8,
            cursor="hand2",
        )
        style_primary_button(open_btn)
        open_btn.pack(side=tk.LEFT)
        tk.Button(
            btn_row,
            text="Close",
            command=win.destroy,
            bg=PANEL_BG,
            fg=TEXT,
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=10,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=(8, 0))

    def _present_post_keygen_surface(self, next_s: str) -> None:
        """After valid keygen: open next first-run surface and keep it in front.

        Does **not** restart the process. Closes only the keygen modal; main
        shell stays alive. Raises Settings/renew/main so the transition is not
        buried under other apps.
        """
        surface = (next_s or "").strip().lower() or "settings"
        try:
            self._bring_shell_forward(force_visible=True)
        except Exception:
            pass
        if surface == "settings":
            try:
                self._open_settings(first_run=True)
            except Exception as exc:  # noqa: BLE001
                self._log(f"Post-keygen Settings open failed: {exc}")
            # Settings open may create a new Toplevel — force it forward again
            # (immediate + one idle tick for grab/map settle).
            def _raise_settings() -> None:
                try:
                    sw = getattr(self, "_settings_win", None)
                    if sw is not None and sw.winfo_exists():
                        self._bring_window_forward(sw, force_visible=True)
                except Exception:
                    pass

            _raise_settings()
            try:
                self.root.after(50, _raise_settings)
            except Exception:
                pass
            return
        if surface == "renew":
            try:
                self._show_renew_licence_prompt()
            except Exception as exc:  # noqa: BLE001
                self._log(f"Post-keygen renew open failed: {exc}")
            return
        # main (or unknown): keep main Connect shell visible in front
        try:
            self._bring_shell_forward(force_visible=True)
        except Exception:
            pass

    def _show_keygen_prompt(self) -> None:
        """Forced modal: enter fulfilment keygen to unlock install (not Settings-only).

        Demands a valid RPT-KEY-… before the window can be dismissed. After a
        successful unlock, presents first-run Settings (OK binds → main Connect).
        """
        # EXPIRED installs must renew — never show keygen in place of renew.
        if needs_licence_renewal():
            self._show_renew_licence_prompt()
            return
        # Single instance — re-raise if already open
        try:
            if self._keygen_prompt_win is not None and self._keygen_prompt_win.winfo_exists():
                try:
                    self._bring_window_forward(
                        self._keygen_prompt_win, force_visible=True
                    )
                except Exception:
                    pass
                return
        except Exception:
            pass

        win = tk.Toplevel(self.root)
        self._keygen_prompt_win = win
        win.title("Enter licence keygen")
        win.configure(bg=CHROME_BG)
        apply_centered_window(win, surface="keygen")
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass
        try:
            self._bring_window_forward(win, force_visible=True)
        except Exception:
            pass

        status_var = tk.StringVar(
            value="Keygen is required to unlock this install before Settings and Connect."
        )

        def _on_demand_close() -> None:
            # Demand keygen: refuse dismiss while unlock still required.
            if needs_keygen_unlock():
                status_var.set(
                    "Enter the keygen from your fulfilment email to unlock this install."
                )
                try:
                    self._bring_window_forward(win, force_visible=True)
                except Exception:
                    pass
                return
            try:
                win.destroy()
            except Exception:
                pass
            self._keygen_prompt_win = None

        win.protocol("WM_DELETE_WINDOW", _on_demand_close)

        shell = tk.Frame(win, bg=CHROME_BG, padx=16, pady=14)
        shell.pack(fill=tk.BOTH, expand=True)
        pad, card_outer = make_neon_card(shell, padx=16, pady=14)
        card_outer.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            pad,
            text="Enter licence keygen",
            bg=PANEL_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            pad,
            text=(
                "Your fulfilment email includes a keygen with the text "
                "USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY "
                "(format RPT-KEY-…). Paste it below to unlock this installation. "
                "Download alone does not unlock residual VPN."
            ),
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=500,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            pad,
            text=CONNECT_BLOCKED_KEYGEN_MSG,
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=500,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 10))
        key_var = tk.StringVar()
        entry = tk.Entry(
            pad,
            textvariable=key_var,
            font=("Segoe UI", 11),
            bg=WHITE,
            fg=TEXT,
            relief=tk.SOLID,
            bd=1,
            highlightthickness=1,
            highlightbackground=NEON_BORDER,
            highlightcolor=NEON_BORDER,
        )
        entry.pack(fill=tk.X, pady=(0, 8))
        try:
            entry.focus_set()
        except Exception:
            pass
        tk.Label(
            pad,
            textvariable=status_var,
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=500,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 8))
        btn_row = tk.Frame(pad, bg=PANEL_BG)
        btn_row.pack(fill=tk.X, pady=(8, 0))

        def _unlock() -> None:
            raw = (key_var.get() or "").strip()
            if not raw:
                status_var.set("Paste the keygen from your email first.")
                return
            status_var.set("Verifying keygen with status host…")
            win.update_idletasks()

            def work() -> None:
                try:
                    ent = import_keygen_and_verify(raw, bind_device=True)
                    ok = payment_allows_connect()
                    msg = (
                        f"Unlocked — installation active (status={ent.status})."
                        if ok
                        else (
                            f"Keygen not active (status={ent.status}). "
                            "Check the email code and that your subscription is active."
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    ent = None
                    ok = False
                    msg = f"Could not verify keygen: {exc}"

                def done() -> None:
                    status_var.set(msg)
                    self._log(msg)
                    self._refresh_licence_badge()
                    if ok:
                        self.detail_var.set(
                            "Keygen verified. Review Settings, then OK to open Connect."
                        )
                        # Close keygen modal, then open next surface *immediately*
                        # with a real raise. A delayed after(200) left a gap where
                        # the modal vanished and Settings/main opened buried —
                        # users read that as “app closed and restarted behind”.
                        try:
                            try:
                                win.grab_release()
                            except Exception:
                                pass
                            win.destroy()
                        except Exception:
                            pass
                        self._keygen_prompt_win = None
                        try:
                            self._bring_shell_forward(force_visible=True)
                        except Exception:
                            pass
                        next_s = post_keygen_next_surface()
                        self._log(f"Post-keygen next surface: {next_s}")
                        self._present_post_keygen_surface(next_s)
                    else:
                        self.detail_var.set(msg)
                        try:
                            self._bring_window_forward(win, force_visible=True)
                        except Exception:
                            pass

                try:
                    self.root.after(0, done)
                except Exception:
                    pass

            threading.Thread(target=work, daemon=True).start()

        unlock_btn = tk.Button(
            btn_row,
            text="Unlock installation",
            command=_unlock,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=6,
            cursor="hand2",
        )
        style_primary_button(unlock_btn)
        unlock_btn.pack(side=tk.LEFT)
        tk.Button(
            btn_row,
            text="Cancel",
            command=_on_demand_close,
            bg=PANEL_BG,
            fg=TEXT,
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=10,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=(8, 0))
        try:
            win.bind("<Return>", lambda _e: _unlock())
        except Exception:
            pass

    def _show_licence_prompt(self) -> None:
        """First-run / Settings: accept end-user licence (local only)."""
        win = tk.Toplevel(self.root)
        win.title(LICENCE_PROMPT_TITLE)
        win.configure(bg=CHROME_BG)
        apply_centered_window(win, surface="licence")
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass
        try:
            self._bring_window_forward(win, force_visible=True)
        except Exception:
            pass
        shell = tk.Frame(win, bg=CHROME_BG, padx=16, pady=14)
        shell.pack(fill=tk.BOTH, expand=True)
        pad, card_outer = make_neon_card(shell, padx=16, pady=14)
        card_outer.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            pad,
            text=LICENCE_PROMPT_TITLE,
            bg=PANEL_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            pad,
            text=short_licence_summary(),
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=500,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            pad,
            text=ANON_REGISTRATION_SUMMARY,
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=500,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            pad,
            text=OS_PRIVILEGE_HONESTY,
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=500,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 10))

        def _open_full() -> None:
            try:
                webbrowser.open(licence_url())
            except Exception as exc:
                self._log(f"Could not open licence: {exc}")

        tk.Label(
            pad,
            text="View full end-user licence (LICENSE)",
            bg=PANEL_BG,
            fg=PRIMARY,
            font=("Segoe UI", 9, "underline"),
            cursor="hand2",
            anchor="w",
        ).pack(fill=tk.X)
        pad.winfo_children()[-1].bind("<Button-1>", lambda _e: _open_full())

        btn_row = tk.Frame(pad, bg=PANEL_BG)
        btn_row.pack(fill=tk.X, pady=(16, 0))

        def _do_accept() -> None:
            accept_licence()
            self._log("Licence accepted (stored locally only).")
            self._connection_log("settings", "End-user licence accepted")
            self._refresh_licence_badge()
            self.detail_var.set(
                "Licence accepted. Enter your keygen from the fulfilment email to unlock."
            )
            try:
                try:
                    win.grab_release()
                except Exception:
                    pass
                win.destroy()
            except Exception:
                pass
            try:
                self._bring_shell_forward(force_visible=True)
            except Exception:
                pass
            # Next surface via real first-run sequencer (keygen is mandatory when unlock-absent)
            self._present_first_run_surface(force=True)

        accept_btn = tk.Button(
            btn_row,
            text=LICENCE_ACCEPT_BUTTON,
            command=_do_accept,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
            font=("Segoe UI", 10, "bold"),
            padx=14,
            pady=8,
            cursor="hand2",
        )
        style_primary_button(accept_btn)
        accept_btn.pack(side=tk.LEFT)
        tk.Button(
            btn_row,
            text="Not now",
            command=win.destroy,
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=10,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=(10, 0))

    def _reestablish_residual_for_privacy_scale(self) -> None:
        """Multi-hop privacy-scale change while connected: re-dial residual path.

        Keeps the Settings control interactive — user does not need to find
        Disconnect first. Refreshes multihop config from Settings/env, tears
        down residual, then runs the normal Connect path (licence/keygen still
        enforced inside ``_start_connect``).
        """
        if self._busy:
            self._log(
                "Privacy scale: multi-hop reconnect deferred (Connect busy)."
            )
            return
        self._log(
            "Privacy scale: multi-hop path changed — re-establishing residual…"
        )
        self.detail_var.set(
            "Multi-hop privacy setting changed — re-establishing residual…"
        )

        def work() -> None:
            try:
                self._disconnect_tunnel()
            except Exception as exc:  # noqa: BLE001
                self.root.after(
                    0,
                    lambda: self._log(
                        f"Privacy scale reconnect teardown: {exc}"
                    ),
                )

            def then() -> None:
                self._refresh_multihop_from_settings()
                self._apply_control(connected=False, busy=False)
                self._set_status("disconnected")
                self._start_connect()

            self.root.after(0, then)

        threading.Thread(target=work, daemon=True).start()

    def _refresh_multihop_from_settings(self) -> None:
        """Reload residual path from Settings/env (entry country + multi-hop).

        Must run on every Connect so a disconnected user who changes
        ``entry_country`` / multihop does not dial a stale host from app init.
        """
        try:
            from client.multihop import multihop_config_from_env

            self.client.multihop = multihop_config_from_env()
        except Exception:  # noqa: BLE001
            pass

    def _sync_main_entry_from_settings(self) -> str:
        """Align main-shell picker + residual path with durable Settings.

        Durable ``settings.json`` is the residual source of truth. First-run
        Settings OK (and other save paths) must call this so a stale main-shell
        Iceland label cannot overwrite DE/RO on the next Connect.
        Returns the normalized entry country code.
        """
        try:
            cur = load_settings()
        except Exception:
            cur = self._settings
        code = normalize_entry_country(
            getattr(cur, "entry_country", default_entry_country())
        )
        try:
            if getattr(self, "_entry_label_var", None) is not None:
                self._entry_label_var.set(option_label_for_code(code))
        except Exception:
            pass
        try:
            from client.country_select import country_flag_emoji

            if getattr(self, "_flag_var", None) is not None:
                self._flag_var.set(country_flag_emoji(code) or f"[{code}]")
        except Exception:
            pass
        self._settings = cur
        self._refresh_multihop_from_settings()
        return code


    def _select_main_entry_country(self, code: str | None) -> None:
        """Persist entry from flag menu selection (code) and refresh chrome."""
        try:
            from client.country_select import country_flag_emoji

            code_n = normalize_entry_country(code or default_entry_country())
            cur = load_settings()
            cur.entry_country = code_n
            save_settings(cur)
            self._settings = cur
            self._entry_label_var.set(option_label_for_code(code_n))
            try:
                self._flag_var.set(country_flag_emoji(code_n) or f"[{code_n}]")
            except Exception:
                pass
            try:
                img = getattr(self, "_flag_photos", {}).get(code_n)
                if img is not None and getattr(self, "country_menu", None) is not None:
                    self.country_menu.configure(image=img, compound=tk.LEFT)
            except Exception:
                pass
            self._refresh_multihop_from_settings()
            self._log(
                f"Entry country: {option_label_for_code(code_n)} (next Connect)"
            )
        except Exception as exc:  # noqa: BLE001
            self._log(f"Could not save entry country: {exc}")

    def _on_main_entry_country_changed(self, _label: str | None = None) -> None:
        """Persist main-shell country picker and refresh residual path for next Connect."""
        try:
            from client.country_select import country_flag_emoji

            label = self._entry_label_var.get()
            code = label_to_country_code(label) or default_entry_country()
            code = normalize_entry_country(code)
            cur = load_settings()
            cur.entry_country = code
            save_settings(cur)
            self._settings = cur
            self._entry_label_var.set(option_label_for_code(code))
            try:
                self._flag_var.set(country_flag_emoji(code) or f"[{code}]")
            except Exception:
                pass
            self._refresh_multihop_from_settings()
            self._log(
                f"Entry country: {option_label_for_code(code)} (next Connect)"
            )
        except Exception as exc:  # noqa: BLE001
            self._log(f"Could not save entry country: {exc}")

    def _on_toggle_connect(self) -> None:
        if self._busy:
            return
        if self._connected:
            self._start_disconnect()
        else:
            self._start_connect()

    def _start_connect(self) -> None:
        # Durable Settings is residual truth. Do **not** rewrite settings from a
        # stale main-shell Iceland label (first-run Settings OK race). Align the
        # picker to disk, then dial the configured entry country.
        try:
            entry_code = self._sync_main_entry_from_settings()
        except Exception:
            try:
                entry_code = normalize_entry_country(
                    getattr(load_settings(), "entry_country", "") or ""
                )
            except Exception:
                entry_code = ""
            self._refresh_multihop_from_settings()
        # Entry country must be a live catalog monopin (default United States/US).
        try:
            cur_entry = getattr(load_settings(), "entry_country", "") or entry_code
        except Exception:
            cur_entry = entry_code
        ok_entry, entry_code, _reason = resolve_entry_country_selection(cur_entry)
        if not ok_entry or not entry_country_allows_connect(entry_code):
            msg = (
                "Choose a valid entry country above Connect "
                "(Iceland is the product default)."
            )
            self._log(msg)
            self._set_status("error", detail=msg)
            self.detail_var.set(msg)
            return
        # Local-only gate first (no status-host I/O on the Tk UI thread).
        # Keygen unlock is required before residual HELLO — discovery of a
        # session-only thank-you file must not skip the keygen surface.
        if not has_accepted_licence():
            msg = (
                "Accept the end-user licence before connecting. "
                "Open Settings or the licence prompt, review the licence, then Accept."
            )
            self._log(msg)
            self._set_status("error", detail=msg)
            self.detail_var.set(msg)
            self._show_licence_prompt()
            return
        if needs_licence_renewal():
            ent = load_payment_entitlement()
            msg = renew_licence_message(ent.platform or "windows")
            self._log(msg)
            self._set_status("error", detail=msg)
            self.detail_var.set(msg)
            self._show_renew_licence_prompt()
            return
        if needs_keygen_unlock():
            msg = CONNECT_BLOCKED_KEYGEN_MSG
            self._log(msg)
            self._set_status("error", detail=msg)
            self.detail_var.set(msg)
            # Forced keygen unlock modal (not Settings-only)
            self._show_keygen_prompt()
            return

        # Residual needs OS privilege (Wintun + dual /1). Non-admin must NEVER
        # fall through to start_full_tunnel(require_system_capture=True) — that
        # path fails "Administrator required". Use connect_residual_privilege_dispatch
        # so helper-installed always invokes run_residual_helper_connect (not gated
        # solely on product_connect_requires_admin(), which is False when helper
        # is installed — that bug skipped the only helper call site).
        if not is_admin():
            from client.windows.residual_privilege import (
                connect_residual_privilege_dispatch,
                elevation_result_user_message,
            )

            self._apply_control(connected=False, busy=True)
            self._set_status("connecting")
            try:
                self._bring_shell_forward(force_visible=False)
            except Exception:
                pass
            dispatched = connect_residual_privilege_dispatch()
            action = str(dispatched.get("action") or "")

            if action == "run_helper" and dispatched.get("ok"):
                # Helper task starts an *elevated* product process with
                # --rpt-auto-connect (full GUI + tray). This non-admin shell
                # must hand off completely — otherwise two windows/tray icons.
                self._log(
                    "Connect — residual helper started elevated; handing off "
                    "(this window exits so only one tray icon remains)…"
                )
                helper = dispatched.get("helper") or {}
                self._log(
                    str(
                        helper.get("message")
                        or dispatched.get("message")
                        or "Residual helper started."
                    )
                )
                self._set_status(
                    "connecting",
                    detail="Elevated Connect opening — approve if prompted…",
                )
                self._handoff_elevated_connect_exit()
                return

            if action == "run_helper" and not dispatched.get("ok"):
                self._log(
                    "Residual helper run failed — falling back to UAC elevate…"
                )

            if action == "blocked":
                err = str(
                    dispatched.get("message")
                    or elevation_result_user_message("skipped")
                )
                self._log(f"Could not connect: {err}")
                self._set_status("error", detail=err)
                self._apply_control(connected=False, busy=False)
                return

            # elevate_uac (or helper failed → UAC fallback)
            self._log(
                "Connect — residual needs Administrator once (Wintun + routes). "
                "Approve UAC to re-open elevated and finish Connect. "
                "You do not need 'Run as administrator' on the shortcut every time."
            )
            try:
                self._bring_shell_forward(force_visible=False)
            except Exception:
                pass
            status = elevate_if_needed(extra_args=["--rpt-auto-connect"])
            if should_exit_after_elevation(status):
                # Elevated child resumes Connect via --rpt-auto-connect.
                self._handoff_elevated_connect_exit()
                return
            err = elevation_result_user_message(status)
            self._log(f"Could not connect: {err}")
            self._set_status("error", detail=err)
            self._apply_control(connected=False, busy=False)
            return

        self._apply_control(connected=False, busy=True)
        self._set_status("connecting")
        try:
            self._bring_shell_forward(force_visible=False)
        except Exception:
            pass
        try:
            from client.multihop import (
                country_node_for_code,
                entry_endpoint,
                residual_endpoint,
            )

            _mh = getattr(self.client, "multihop", None)
            _entry_n = country_node_for_code(entry_code)
            _res_ep = residual_endpoint(_mh) if _mh is not None else entry_endpoint(_mh)
            # Dial host is private (Connect path only); UI/support log use country label
            from client.residual_public import public_label_for_code

            _pub = public_label_for_code(
                _entry_n.code, name=getattr(_entry_n, "name", None)
            )
            self._log(
                f"Connect — entry {_pub} (full-tunnel residual)…"
            )
            self._connection_log(
                KIND_CONNECT,
                f"Connect started — entry {_entry_n.code}",
            )
        except Exception:
            self._log(
                "Connect - starting secure session (full-tunnel residual path)..."
            )
            self._connection_log(
                KIND_CONNECT, "Connect started (full-tunnel residual path)"
            )

        self._connect_gen = int(getattr(self, "_connect_gen", 0)) + 1
        connect_gen = self._connect_gen

        def _connect_still_current() -> bool:
            return int(getattr(self, "_connect_gen", 0)) == connect_gen

        def work() -> None:
            # Status-host + residual HELLO stay off the Tk UI thread so Windows
            # does not show "(Not Responding)" during network waits.
            #
            # Warm path: when local entitlement already allows Connect (active
            # + keygen), skip serial bootstrap/refresh before HELLO. Background
            # refresh still runs after dial starts so revokes surface soon.
            from client.payment_entitlement import (
                connect_status_host_refresh_needed,
            )

            need_status_host = True
            try:
                need_status_host = bool(connect_status_host_refresh_needed())
            except Exception:
                need_status_host = True
            # Cold: ensure_entitlement inside assert_may_connect(refresh=True).
            # Warm: local gate only (no serial status-host); bg refresh after.
            ok_lic, lic_msg = assert_may_connect(refresh=need_status_host)
            if not ok_lic:

                def fail_gate() -> None:
                    self._log(lic_msg)
                    self._set_status("error", detail=lic_msg)
                    self.detail_var.set(lic_msg)
                    self._apply_control(connected=False, busy=False)
                    if not has_accepted_licence():
                        self._show_licence_prompt()
                    elif needs_licence_renewal():
                        self._show_renew_licence_prompt()
                    elif needs_keygen_unlock():
                        self._show_keygen_prompt()
                    else:
                        self._open_settings()

                self.root.after(0, fail_gate)
                return

            # Warm-path: re-check entitlement in background (non-blocking HELLO).
            if not need_status_host:

                def _bg_entitlement_refresh() -> None:
                    try:
                        bootstrap_payment_entitlement(bind_device=True)
                    except Exception:
                        pass

                threading.Thread(
                    target=_bg_entitlement_refresh,
                    name="rpt-connect-entitlement-bg",
                    daemon=True,
                ).start()

            # Handshake + residual tunnel attach stay off the Tk UI thread.
            # Prefetch physical GW while HELLO runs to shorten residual attach.
            from concurrent.futures import ThreadPoolExecutor

            from client.windows.tunnel_win import physical_default_gateway

            prior = self._tunnel
            residual_ready = residual_ip_capture_active(prior)
            with ThreadPoolExecutor(max_workers=1) as pool:
                gw_fut = pool.submit(physical_default_gateway)
                result = self.client.connect(timeout=20.0)
                try:
                    phys_gw = gw_fut.result(timeout=8)
                except Exception:
                    phys_gw = None

            if not (result.ok and result.session and result.tunnel_plan):
                msg = result.message or "Connection failed"
                low = msg.lower()
                if "timed out" in low or "no reply" in low or "timeout" in low:
                    try:
                        from client.windows.firewall_allow import (
                            windows_firewall_connect_hint,
                        )

                        msg = f"{msg} {windows_firewall_connect_hint()}"
                    except Exception:
                        pass

                def fail_hs() -> None:
                    self._log(f"Could not connect: {msg}")
                    self._connection_log(KIND_ERROR, f"Connect failed: {msg}")
                    self._set_status("error", detail=msg)
                    self._apply_control(connected=False, busy=False)

                self.root.after(0, fail_hs)
                return

            vpn_ip = result.session.vpn_ip

            def note_session() -> None:
                entry_note = ""
                try:
                    from client.residual_public import public_label_for_code

                    ec = normalize_entry_country(
                        getattr(load_settings(), "entry_country", "") or ""
                    )
                    entry_note = f" entry={public_label_for_code(ec)}"
                except Exception:
                    entry_note = ""
                self._log(
                    f"Session ready (tunnel address {vpn_ip};{entry_note})"
                )
                self._connection_log(
                    KIND_SESSION,
                    f"Session ready (tunnel address {vpn_ip};{entry_note})",
                )
                if residual_ready:
                    self._log("Residual already active — confirming tunnel attach…")
                else:
                    self._log("Attaching residual tunnel (Wintun + routes)…")

            self.root.after(0, note_session)

            try:
                # Product residual path: Wintun + dual /1 only (never on UI thread)
                # prior= reuses residual routes when already applied for this session
                tun_res = start_full_tunnel(
                    self.client,
                    result.tunnel_plan,
                    result.session.endpoint.host,
                    prefer_system_capture=True,
                    require_system_capture=True,
                    prior=prior if residual_ready else None,
                    physical_gw=phys_gw,
                )
            except Exception as exc:
                err = f"Tunnel attach error: {exc}"

                def fail_exc() -> None:
                    self._log(f"Could not connect: {err[:160]}")
                    self._connection_log(KIND_ERROR, f"Connect failed: {err[:160]}")
                    self._set_status("error", detail=err)
                    self._apply_control(connected=False, busy=False)

                self.root.after(0, fail_exc)
                return

            def done() -> None:
                try:
                    self._tunnel = tun_res
                    if residual_ip_capture_active(tun_res):
                        v6 = ipv6_residual_protected(tun_res)
                        # Never paint residual monopin IPv4 in activity / support log
                        entry_bit = ""
                        try:
                            from client.residual_public import public_label_for_code

                            ec = normalize_entry_country(
                                getattr(load_settings(), "entry_country", "") or ""
                            )
                            entry_bit = f" entry={public_label_for_code(ec)}"
                        except Exception:
                            entry_bit = ""
                        self._log(
                            "Tunnel active - residual public IP uses the VPN node "
                            f"(IF={getattr(tun_res, 'if_index', '?')}; "
                            f"ipv6_protected={v6};{entry_bit})"
                        )
                        self._connection_log(
                            KIND_CONNECT,
                            "Connected — residual public IP uses the VPN node "
                            f"(ipv6_protected={v6};{entry_bit})",
                        )
                        # Apply control first so _connected is True, then status+tray
                        self._apply_control(connected=True, busy=False)
                        self._set_status(
                            "connected",
                            vpn_ip=vpn_ip,
                            residual_capture=True,
                            ipv6_protected=v6,
                        )
                        # Keep shell in front after Connect work (user initiated).
                        try:
                            self._bring_shell_forward(force_visible=False)
                        except Exception:
                            pass
                    elif session_ok_without_residual_capture(tun_res):
                        # Settings residual IPv4 OFF — session/dataplane up, not residual capture
                        self._log(
                            "Tunnel session up — residual IPv4 capture off (Settings); "
                            "public IP still uses ISP for IPv4"
                        )
                        self._connection_log(
                            KIND_CONNECT,
                            "Connected — session only (residual IPv4 off in Settings)",
                        )
                        self._apply_control(connected=True, busy=False)
                        self._set_status(
                            "connected",
                            vpn_ip=vpn_ip,
                            residual_capture=False,
                            ipv6_protected=False,
                        )
                        try:
                            self._bring_shell_forward(force_visible=False)
                        except Exception:
                            pass
                    else:
                        # Capture attach failure BEFORE teardown overwrites tun_res.message
                        original_err = getattr(tun_res, "message", None)
                        try:
                            disconnect_full_tunnel(
                                tun_res, self.client, preserve_message=True
                            )
                        except Exception:
                            pass
                        self._tunnel = None
                        # Never surface teardown success as the Connect failure reason
                        err = attach_failure_user_message(original_err)
                        self._log(f"Could not connect: {err[:160]}")
                        self._connection_log(
                            KIND_ERROR, f"Connect failed: {err[:160]}"
                        )
                        self._set_status("error", detail=err)
                        self._apply_control(connected=False, busy=False)
                        try:
                            self._bring_shell_forward(force_visible=False)
                        except Exception:
                            pass
                finally:
                    if self._busy:
                        self._apply_control(connected=self._connected, busy=False)

            self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _disconnect_tunnel(self) -> None:
        """Stop tunnel + session (Disconnect / Quit). Clears ``_tunnel`` first."""
        tunnel = self._tunnel
        self._tunnel = None
        disconnect_full_tunnel(tunnel, self.client)

    def _start_disconnect(self) -> None:
        # Invalidate any in-flight Connect worker (cancel before / during attach)
        self._connect_gen = int(getattr(self, "_connect_gen", 0)) + 1
        self._apply_control(connected=True, busy=True)
        self._set_status("disconnecting")
        self._log("Disconnect - stopping tunnel...")
        self._connection_log(KIND_DISCONNECT, "Disconnect started")

        def work() -> None:
            try:
                self._disconnect_tunnel()
            finally:

                def done() -> None:
                    self._apply_control(connected=False, busy=False)
                    self._set_status("disconnected")
                    self._sync_tray_status(connected=False, residual=False)
                    self._log("Disconnected.")
                    self._connection_log(KIND_DISCONNECT, "Disconnected")
                    try:
                        self._bring_shell_forward(force_visible=False)
                    except Exception:
                        pass

                self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _open_upgrade(self) -> None:
        url = upgrade_download_url(platform="windows")
        self._log(f"Opening download page...")
        try:
            webbrowser.open(url)
        except Exception as exc:
            self._log(f"Could not open browser: {exc}. Visit: {url}")

    def _present_first_run_surface(self, *, force: bool = False) -> None:
        """Show the next first-run surface (licence → keygen → settings → main).

        Always drives :func:`first_run_next_surface` so unlock-absent installs
        demand keygen (not skipped when may_connect is mis-true, and not only
        buried in Settings).
        """
        surface = first_run_next_surface()
        self._log(f"First-run surface: {surface}")
        # Keep product chrome visible when stepping between first-run modals.
        try:
            self._bring_shell_forward(force_visible=True)
        except Exception:
            pass
        if surface == "licence":
            self._show_licence_prompt()
        elif surface == "renew":
            self._show_renew_licence_prompt()
        elif surface == "keygen":
            self._show_keygen_prompt()
        elif surface == "settings":
            self._open_settings(first_run=True)
            try:
                sw = getattr(self, "_settings_win", None)
                if sw is not None and sw.winfo_exists():
                    self._bring_window_forward(sw, force_visible=True)
            except Exception:
                pass
        elif surface == "main" and force:
            self.detail_var.set("Ready — press Connect for residual protection.")
            try:
                self._bring_shell_forward(force_visible=True)
            except Exception:
                pass
        # surface == main without force: stay on main Connect shell

    def _toggle_ui_mode(self) -> None:
        """Header dark/light switcher — persist and recolor main chrome."""
        new_mode = theme_toggle_target(self._ui_mode)
        self._set_ui_mode(new_mode, persist=True)

    def _set_ui_mode(self, mode: str, *, persist: bool = True) -> None:
        self._ui_mode = normalize_ui_mode(mode)
        self._t = theme_tokens(self._ui_mode)
        if persist:
            try:
                cur = load_settings()
                cur.ui_mode = self._ui_mode
                save_settings(cur)
                self._settings = cur
            except Exception:
                pass
        self._apply_main_theme()
        try:
            self.theme_btn.configure(text=theme_toggle_button_text(self._ui_mode))
        except Exception:
            pass
        self._log(f"UI mode: {self._ui_mode}")

    def _apply_main_theme(self) -> None:
        """Recolor main-window chrome/panel/text from ``self._t`` tokens."""
        t = self._t
        chrome = t["chrome_bg"]
        panel = t["panel_bg"]
        text = t["text"]
        muted = t["text_muted"]
        primary = t["primary"]
        primary_dark = t["primary_dark"]
        accent = t["light_accent"]
        try:
            self.root.configure(bg=chrome)
        except Exception:
            pass
        for w in (
            getattr(self, "chrome", None),
            getattr(self, "bottom", None),
            getattr(self, "header", None),
            getattr(self, "hint_row", None),
            getattr(self, "title_col", None),
        ):
            if w is not None:
                try:
                    w.configure(bg=chrome)
                except Exception:
                    pass
        for w, kw in (
            (getattr(self, "title_label", None), {"bg": chrome, "fg": primary_dark}),
            (getattr(self, "banner_label", None), {"bg": chrome, "fg": muted}),
            (getattr(self, "tagline_label", None), {"bg": chrome, "fg": primary}),
            (getattr(self, "hint", None), {"bg": chrome, "fg": muted}),
            (getattr(self, "_logo_label", None), {"bg": chrome}),
        ):
            if w is not None:
                try:
                    w.configure(**kw)
                except Exception:
                    pass
        for btn_name, kw in (
            (
                "settings_btn",
                {
                    "bg": chrome,
                    "fg": primary_dark,
                    "activebackground": accent,
                    "activeforeground": primary_dark,
                },
            ),
            (
                "theme_btn",
                {
                    "bg": chrome,
                    "fg": primary_dark,
                    "activebackground": accent,
                    "activeforeground": primary_dark,
                    "text": theme_toggle_button_text(self._ui_mode),
                },
            ),
            (
                "quit_btn",
                {
                    "bg": chrome,
                    "fg": muted,
                    "activebackground": accent,
                    "activeforeground": text,
                },
            ),
            (
                "connect_btn",
                {
                    "bg": t["button_disconnect_bg"]
                    if self._connected
                    else t["button_connect_bg"],
                    "fg": t["button_fg"],
                    "activebackground": primary,
                    "activeforeground": t["button_fg"],
                    "disabledforeground": t["disabled_fg"],
                },
            ),
        ):
            btn = getattr(self, btn_name, None)
            if btn is not None:
                try:
                    btn.configure(**kw)
                except Exception:
                    pass
        for w in (
            getattr(self, "status_card", None),
            getattr(self, "hero_top", None),
            getattr(self, "_licence_cta", None),
        ):
            if w is not None:
                try:
                    w.configure(bg=panel)
                except Exception:
                    pass
        status_fg = getattr(self, "_status_headline_fg", None) or text
        for w, kw in (
            (getattr(self, "vpn_status_caption", None), {"bg": panel, "fg": muted}),
            (getattr(self, "status_label", None), {"bg": panel, "fg": status_fg}),
            (getattr(self, "detail_label", None), {"bg": panel, "fg": muted}),
        ):
            if w is not None:
                try:
                    w.configure(**kw)
                except Exception:
                    pass
        # Nested labels under licence CTA / status card
        try:
            if getattr(self, "status_card", None) is not None:
                self._paint_descendant_chrome(self.status_card, panel, text, muted)
        except Exception:
            pass
        # Re-assert headline colour after descendant paint (status_label is inside card)
        try:
            if getattr(self, "status_label", None) is not None:
                self.status_label.configure(bg=panel, fg=status_fg)
        except Exception:
            pass

    def _paint_descendant_chrome(
        self,
        widget: tk.Misc,
        panel: str,
        text: str,
        muted: str,
    ) -> None:
        """Best-effort recolor of Frame/Label children under a panel card."""
        try:
            kids = widget.winfo_children()
        except Exception:
            return
        for ch in kids:
            try:
                cls = ch.winfo_class()
            except Exception:
                continue
            try:
                if cls in ("Frame", "Labelframe", "TFrame"):
                    ch.configure(bg=panel)
                elif cls == "Label":
                    # Keep badge / status colors if they already use status tokens
                    ch.configure(bg=panel)
                elif cls == "Button":
                    pass  # leave action buttons
            except Exception:
                pass
            self._paint_descendant_chrome(ch, panel, text, muted)

    def _open_settings(self, *, first_run: bool = False) -> None:
        """Settings: startup prefs, privacy scale, local connection log, leak test.

        When *first_run* is True (post-keygen onboarding), the window is large
        enough for primary controls and an **OK** button binds/persists settings
        then closes to reveal the main Connect shell.
        """
        try:
            if self._settings_win is not None and self._settings_win.winfo_exists():
                try:
                    self._bring_window_forward(
                        self._settings_win, force_visible=True
                    )
                except Exception:
                    pass
                return
        except Exception:
            pass

        t = theme_tokens(self._ui_mode)
        win = tk.Toplevel(self.root)
        self._settings_win = win
        win.title("Settings" + (" — first run" if first_run else ""))
        win.configure(bg=t["chrome_bg"])
        apply_centered_window(
            win,
            surface="settings_first_run" if first_run else "settings",
        )
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass
        try:
            self._bring_window_forward(win, force_visible=True)
        except Exception:
            pass

        def _on_settings_closed() -> None:
            unbind = getattr(self, "_settings_scroll_unbind", None)
            if callable(unbind):
                try:
                    unbind()
                except Exception:
                    pass
            self._settings_scroll_unbind = None
            self._settings_win = None
            try:
                win.destroy()
            except Exception:
                pass
            # Return focus to main shell (user still in product, not minimized).
            try:
                self._bring_shell_forward(force_visible=False)
            except Exception:
                pass

        win.protocol("WM_DELETE_WINDOW", _on_settings_closed)

        cur = load_settings()
        self._settings = cur
        run_var = tk.BooleanVar(value=cur.run_at_startup)
        auto_var = tk.BooleanVar(value=cur.autoconnect_on_launch)
        shape_var = tk.BooleanVar(value=cur.privacy_traffic_shape)
        obfs_var = tk.BooleanVar(value=cur.privacy_outer_obfuscation)
        multihop_var = tk.BooleanVar(value=cur.privacy_multihop)
        # Residual IPv4 is always ON (no user switch). IPv6 remains adjustable.
        ipv6_var = tk.BooleanVar(value=bool(getattr(cur, "residual_ipv6", True)))
        entry_country_var = tk.StringVar(
            value=option_label_for_code(
                normalize_entry_country(getattr(cur, "entry_country", "IS"))
            )
        )
        note_var = tk.StringVar(
            value=(
                "First run: amend settings to suit you, then press OK to continue to Connect."
                if first_run
                else ""
            )
        )
        leak_var = tk.StringVar(value="")

        # Scrollable body for taller transparency content
        canvas = tk.Canvas(win, bg=t["chrome_bg"], highlightthickness=0)
        scroll = tk.Scrollbar(win, orient=tk.VERTICAL, command=canvas.yview)
        pad = tk.Frame(canvas, bg=t["chrome_bg"], padx=16, pady=14)
        pad.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=pad, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            pad,
            text="Settings",
            bg=t["chrome_bg"],
            fg=t["primary_dark"],
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 10))

        card, card_outer = make_neon_card(pad, padx=12, pady=10, bg=t["panel_bg"])
        card_outer.pack(fill=tk.X)

        def _row(parent, text, sub, var, on_toggle) -> None:
            row = tk.Frame(parent, bg=t["panel_bg"])
            row.pack(fill=tk.X, pady=8)
            col = tk.Frame(row, bg=t["panel_bg"])
            col.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(
                col,
                text=text,
                bg=t["panel_bg"],
                fg=t["text"],
                font=("Segoe UI", 10, "bold"),
                anchor="w",
            ).pack(fill=tk.X)
            tk.Label(
                col,
                text=sub,
                bg=t["panel_bg"],
                fg=t["text_muted"],
                font=("Segoe UI", 8),
                anchor="w",
                wraplength=360,
                justify=tk.LEFT,
            ).pack(fill=tk.X)
            # Site-style switch toggle (not stock checkbox chrome)
            sw = SwitchToggle(
                row,
                var,
                command=on_toggle,
                bg=t["panel_bg"],
            )
            sw.pack(side=tk.RIGHT, padx=(12, 0))

        def _current_settings() -> ProductSettings:
            prev_done = bool(
                getattr(cur, "first_run_settings_completed", False)
            )
            mode = normalize_ui_mode(
                getattr(self._settings, "ui_mode", None)
                or getattr(cur, "ui_mode", "light")
                or self._ui_mode
            )
            return ProductSettings(
                run_at_startup=bool(run_var.get()),
                autoconnect_on_launch=bool(auto_var.get()),
                privacy_traffic_shape=bool(shape_var.get()),
                privacy_outer_obfuscation=bool(obfs_var.get()),
                privacy_multihop=bool(multihop_var.get()),
                residual_ipv4=True,  # product policy: always on
                residual_ipv6=bool(ipv6_var.get()),
                entry_country=normalize_entry_country(
                    label_to_country_code(entry_country_var.get())
                    or entry_country_var.get()
                ),
                first_run_settings_completed=prev_done,
                ui_mode=mode,
            )

        def _save_run() -> None:
            s = _current_settings()
            save_settings(s)
            self._settings = s
            st = apply_run_at_startup(s.run_at_startup)
            if s.run_at_startup:
                note_var.set(
                    f"Run at startup: {st}. App will open at sign-in when enabled."
                )
            else:
                note_var.set(f"Run at startup: {st}.")
            self._log(f"Settings: run_at_startup={s.run_at_startup} ({st})")

        def _save_auto() -> None:
            s = _current_settings()
            save_settings(s)
            self._settings = s
            if s.autoconnect_on_launch:
                note_var.set("Autoconnect on launch ON - next cold start will Connect.")
            else:
                note_var.set("Autoconnect on launch OFF - Connect is manual.")
            self._log(f"Settings: autoconnect_on_launch={s.autoconnect_on_launch}")

        def _save_privacy() -> None:
            try:
                from client.free_tier import free_tier_settings_locked

                if free_tier_settings_locked():
                    note_var.set(
                        "Free edition (3.3.3): privacy options are fixed "
                        "(Iceland single-hop, basic residual). Upgrade for full Settings."
                    )
                    return
            except Exception:
                pass
            # Interactive while connected: persist + hot-apply shape/obfs to
            # live residual; multi-hop / entry-country path change re-establishes residual.
            prev = self._settings if self._settings is not None else cur
            prev_mh = bool(getattr(prev, "privacy_multihop", False))
            prev_entry = normalize_entry_country(
                getattr(prev, "entry_country", "IS")
            )
            s = _current_settings()
            save_settings(s)
            self._settings = s
            # Keep RptClient path in sync even while disconnected so next Connect
            # does not dial a stale entry host from app init.
            self._refresh_multihop_from_settings()
            plane = None
            if self._tunnel is not None:
                plane = getattr(self._tunnel, "dataplane", None)
            result = hot_apply_privacy_scale(
                dataplane=plane,
                client=self.client,
                prefs=prefs_from_product_settings(s),
                previous_multihop=prev_mh,
                connected=bool(self._connected),
            )
            entry_changed = prev_entry != normalize_entry_country(s.entry_country)
            note_var.set(result.message)
            if entry_changed:
                from client.multihop import country_node_for_code

                node = country_node_for_code(s.entry_country)
                note_var.set(
                    f"Entry country: {node.name}. "
                    + (
                        "Multi-hop exit is the other catalog country. "
                        if s.privacy_multihop
                        else "Single-hop residual uses this entry. "
                    )
                    + (result.message or "")
                )
                # Keep main-shell country picker aligned with Settings
                try:
                    if getattr(self, "_entry_label_var", None) is not None:
                        self._entry_label_var.set(
                            option_label_for_code(s.entry_country)
                        )
                except Exception:
                    pass
            self._log(
                "Settings: privacy_scale hot-apply "
                f"shape={s.privacy_traffic_shape} "
                f"obfs={s.privacy_outer_obfuscation} "
                f"multihop={s.privacy_multihop} "
                f"entry={s.entry_country} "
                f"connected={self._connected} "
                f"shaping_hot={result.shaping_hot_applied} "
                f"mh_reconnect={result.multihop_reconnect_needed} "
                f"entry_changed={entry_changed}"
            )
            if self._connected and (
                result.multihop_reconnect_needed or entry_changed
            ):
                self.root.after(50, self._reestablish_residual_for_privacy_scale)
            # Refresh ping labels after multi-hop / privacy changes
            try:
                _refresh_pings()
            except NameError:
                pass

        _row(
            card,
            "Run at device startup",
            "Start Privacy Restored when you sign in to Windows",
            run_var,
            _save_run,
        )
        tk.Frame(card, bg=BORDER, height=1).pack(fill=tk.X, pady=4)
        _row(
            card,
            "Autoconnect on launch",
            "When the app opens, start Connect automatically",
            auto_var,
            _save_auto,
        )

        def _save_residual_stack() -> None:
            s = _current_settings()
            save_settings(s)
            self._settings = s
            note_var.set(
                f"Residual stack: IPv4=always on, "
                f"IPv6={'on' if s.residual_ipv6 else 'off'}. "
                "Takes effect on next Connect"
                + (
                    " (disconnect first if currently residual-connected)."
                    if self._connected
                    else "."
                )
            )
            self._log(
                f"Settings: residual_ipv4=always_on "
                f"residual_ipv6={s.residual_ipv6}"
            )

        # Free 3.3.3: no user-amendable privacy-scale (locked lean Iceland).
        _free_locked = False
        try:
            from client.free_tier import free_tier_settings_locked

            _free_locked = bool(free_tier_settings_locked())
        except Exception:
            _free_locked = False

        # --- Privacy scale (IPv4/IPv6 first, then optional residual defenses) ---
        priv_card, priv_outer = make_neon_card(pad, padx=12, pady=10)
        priv_outer.pack(fill=tk.X, pady=(14, 0))
        if _free_locked:
            tk.Label(
                priv_card,
                text="Free edition (3.3.3)",
                bg=PANEL_BG,
                fg=PRIMARY_DARK,
                font=("Segoe UI", 11, "bold"),
                anchor="w",
            ).pack(fill=tk.X, pady=(0, 4))
            tk.Label(
                priv_card,
                text=(
                    "Basic Iceland residual only — privacy options are fixed and "
                    "cannot be changed. Single-hop entry; no multi-hop, traffic "
                    "shaping, or outer obfuscation toggles."
                ),
                bg=PANEL_BG,
                fg=TEXT_MUTED,
                font=("Segoe UI", 8),
                anchor="w",
                wraplength=400,
                justify=tk.LEFT,
            ).pack(fill=tk.X, pady=(0, 8))
            # Force lean vars so any residual save path cannot re-enable extras.
            shape_var.set(False)
            obfs_var.set(False)
            multihop_var.set(False)
            entry_country_var.set(option_label_for_code(default_entry_country()))
        else:
            tk.Label(
                priv_card,
                text="Browsing speed / privacy scale",
                bg=PANEL_BG,
                fg=PRIMARY_DARK,
                font=("Segoe UI", 11, "bold"),
                anchor="w",
            ).pack(fill=tk.X, pady=(0, 4))
            # IPv4 residual always on (label only); IPv6 residual remains adjustable.
            ipv4_info = tk.Frame(priv_card, bg=PANEL_BG)
            ipv4_info.pack(fill=tk.X, pady=8)
            tk.Label(
                ipv4_info,
                text="IPv4 residual",
                bg=PANEL_BG,
                fg=TEXT,
                font=("Segoe UI", 10, "bold"),
                anchor="w",
            ).pack(fill=tk.X)
            tk.Label(
                ipv4_info,
                text=(
                    "Always on: full-tunnel IPv4 capture (dual /1 residual routes "
                    "into the VPN). This cannot be turned off."
                ),
                bg=PANEL_BG,
                fg=TEXT_MUTED,
                font=("Segoe UI", 8),
                anchor="w",
                wraplength=360,
                justify=tk.LEFT,
            ).pack(fill=tk.X)
            tk.Label(
                ipv4_info,
                text="Always on",
                bg=PANEL_BG,
                fg=PRIMARY_DARK,
                font=("Segoe UI", 9, "bold"),
                anchor="e",
            ).pack(anchor="e", pady=(4, 0))
            tk.Frame(priv_card, bg=BORDER, height=1).pack(fill=tk.X, pady=4)
            _row(
                priv_card,
                "IPv6 residual",
                "Block ISP IPv6 while residual is connected (dual-stack leak protection). "
                "ON (default). OFF: IPv6 may use ISP; status will not claim IPv6 protected. "
                "Takes effect on next Connect.",
                ipv6_var,
                _save_residual_stack,
            )
            tk.Frame(priv_card, bg=BORDER, height=1).pack(fill=tk.X, pady=4)
            tk.Label(
                priv_card,
                text=(
                    "Turn optional residual defenses off for a snappier connection. "
                    "Defaults keep privacy layers on (except multi-hop, which is "
                    "single-hop by default). Changes apply live while connected "
                    "(shaping + obfuscation hot-apply; multi-hop re-establishes residual). "
                    "Licence, keygen, and residual tunnel cannot be disabled here."
                ),
                bg=PANEL_BG,
                fg=TEXT_MUTED,
                font=("Segoe UI", 8),
                anchor="w",
                wraplength=400,
                justify=tk.LEFT,
            ).pack(fill=tk.X, pady=(0, 8))
            tk.Label(
                priv_card,
                text=EXPLAINER_CORE_VPN,
                bg=PANEL_BG,
                fg=TEXT,
                font=("Segoe UI", 8),
                anchor="w",
                wraplength=400,
                justify=tk.LEFT,
            ).pack(fill=tk.X, pady=(0, 8))
            tk.Frame(priv_card, bg=BORDER, height=1).pack(fill=tk.X, pady=4)
            _row(
                priv_card,
                "Traffic shaping (pad / jitter / cover)",
                EXPLAINER_TRAFFIC_SHAPE,
                shape_var,
                _save_privacy,
            )
            tk.Frame(priv_card, bg=BORDER, height=1).pack(fill=tk.X, pady=4)
            _row(
                priv_card,
                "Outer obfuscation (QUIC-mimic wrap)",
                EXPLAINER_OUTER_OBFUSCATION,
                obfs_var,
                _save_privacy,
            )
            tk.Frame(priv_card, bg=BORDER, height=1).pack(fill=tk.X, pady=4)
            # Entry country (IS / RO / US + flags) — also on main shell above Connect
            entry_row = tk.Frame(priv_card, bg=PANEL_BG)
            entry_row.pack(fill=tk.X, pady=8)
            entry_col = tk.Frame(entry_row, bg=PANEL_BG)
            entry_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(
                entry_col,
                text="Entry country (node)",
                bg=PANEL_BG,
                fg=TEXT,
                font=("Segoe UI", 10, "bold"),
                anchor="w",
            ).pack(fill=tk.X)
            tk.Label(
                entry_col,
                text=(
                    "Choose residual entry: Iceland, Romania, or United States. "
                    "With multi-hop on, exit is another catalog country."
                ),
                bg=PANEL_BG,
                fg=TEXT_MUTED,
                font=("Segoe UI", 8),
                anchor="w",
                wraplength=360,
                justify=tk.LEFT,
            ).pack(fill=tk.X)
            _entry_labels = [o.label() for o in catalog_country_options()]
            entry_menu = tk.OptionMenu(
                entry_row,
                entry_country_var,
                *_entry_labels,
                command=lambda _v: _save_privacy(),
            )
            entry_menu.configure(
                bg=PANEL_BG,
                fg=TEXT,
                activebackground=LIGHT_ACCENT,
                activeforeground=TEXT,
                highlightthickness=0,
                font=("Segoe UI", 9, "bold"),
            )
            try:
                entry_menu["menu"].configure(bg=PANEL_BG, fg=TEXT)
            except Exception:
                pass
            entry_menu.pack(side=tk.RIGHT, padx=(12, 0))
            # Friendly labels under the code menu
            tk.Label(
                entry_col,
                text="IS = Iceland · RO = Romania · US = United States",
                bg=PANEL_BG,
                fg=TEXT_MUTED,
                font=("Segoe UI", 7),
                anchor="w",
            ).pack(fill=tk.X, pady=(2, 0))
            tk.Frame(priv_card, bg=BORDER, height=1).pack(fill=tk.X, pady=4)
            _row(
                priv_card,
                "Multi-hop residual (exit path)",
                EXPLAINER_MULTIHOP,
                multihop_var,
                _save_privacy,
            )

        # Live device→node ping statistics (entry always; exit when multi-hop on)
        tk.Frame(priv_card, bg=BORDER, height=1).pack(fill=tk.X, pady=8)
        tk.Label(
            priv_card,
            text="Ping statistics (device → node)",
            bg=PANEL_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            priv_card,
            text=(
                "Best-effort RTT to product monopin hosts (UDP residual port, "
                "else TCP status port). Not a browser speedbench. Exit shown "
                "only when multi-hop is on in Settings."
            ),
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 6))
        def _entry_code_for_ping() -> str:
            try:
                return normalize_entry_country(
                    label_to_country_code(entry_country_var.get())
                    or entry_country_var.get()
                    or getattr(load_settings(), "entry_country", "IS")
                )
            except Exception:
                return "IS"

        _init_ping_code = _entry_code_for_ping()
        try:
            from client.multihop import country_node_for_code as _cn

            _init_name = _cn(_init_ping_code).name
        except Exception:
            _init_name = _init_ping_code
        entry_ping_var = tk.StringVar(
            value=f"Entry ({_init_name} / {_init_ping_code}): —"
        )
        exit_ping_var = tk.StringVar(value="Exit: n/a (multi-hop off)")
        tk.Label(
            priv_card,
            textvariable=entry_ping_var,
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            priv_card,
            textvariable=exit_ping_var,
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 6))

        def _refresh_pings() -> None:
            code = _entry_code_for_ping()
            try:
                from client.multihop import country_node_for_code as _cn2

                ename = _cn2(code).name
            except Exception:
                ename = code
            entry_ping_var.set(f"Entry ({ename} / {code}): measuring…")
            if bool(multihop_var.get()):
                exit_ping_var.set("Exit: measuring…")
            else:
                exit_ping_var.set("Exit: n/a (multi-hop off)")
            win.update_idletasks()

            def work() -> None:
                try:
                    snap = measure_settings_pings(
                        multihop_enabled=bool(multihop_var.get()),
                        timeout_s=1.5,
                        entry_country=code,
                    )
                    e_txt = f"{snap.entry_label()}: {snap.entry_display()}"
                    x_txt = f"{snap.exit_label()}: {snap.exit_display()}"
                except Exception as exc:  # noqa: BLE001
                    e_txt = f"Entry ({ename} / {code}): n/a ({exc})"
                    x_txt = "Exit: n/a"

                def done() -> None:
                    entry_ping_var.set(e_txt)
                    exit_ping_var.set(x_txt)

                try:
                    self.root.after(0, done)
                except Exception:
                    pass

            threading.Thread(target=work, daemon=True).start()

        tk.Button(
            priv_card,
            text="Measure ping now",
            command=_refresh_pings,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=4,
            cursor="hand2",
        ).pack(anchor="w", pady=(0, 4))
        # Auto-measure once when Settings opens (off UI thread)
        self.root.after(200, _refresh_pings)

        tk.Label(
            pad,
            textvariable=note_var,
            bg=CHROME_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(12, 0))

        tk.Label(
            pad,
            text="Startup/autoconnect default off. Seamless power-up needs both on. "
            "Open the app as a normal user; Connect requests residual privilege once "
            "(or use residual helper). Privacy-scale toggles hot-apply while connected "
            "(multi-hop re-establishes residual when the path changes).",
            bg=CHROME_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(8, 0))

        # --- Residual privilege (no Run-as-admin on shortcut every day) ---
        priv_help, priv_help_outer = make_neon_card(pad, padx=12, pady=8)

        priv_help_outer.pack(fill=tk.X, pady=(14, 0))
        tk.Label(
            priv_help,
            text="Residual privilege (Windows)",
            bg=PANEL_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))
        residual_status_var = tk.StringVar(value="Checking residual privilege…")

        def _refresh_residual_priv() -> None:
            try:
                from client.windows.residual_privilege import residual_privilege_status

                st = residual_privilege_status()
                if st.get("process_is_admin"):
                    residual_status_var.set(
                        "This window is elevated — residual Connect can apply routes."
                    )
                elif st.get("helper_installed"):
                    residual_status_var.set(
                        "Residual helper installed — day-to-day Connect need not "
                        "Run as administrator."
                    )
                else:
                    residual_status_var.set(
                        "Helper not installed — Connect will ask for UAC once, "
                        "or install the residual helper below (one-time admin)."
                    )
            except Exception as exc:  # noqa: BLE001
                residual_status_var.set(f"Status unavailable ({exc})")

        tk.Label(
            priv_help,
            textvariable=residual_status_var,
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X)
        tk.Label(
            priv_help,
            text=(
                "Honest residual (Wintun + dual /1) always needs privilege somewhere. "
                "Install helper once so the app window stays a normal user."
            ),
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(6, 4))

        def _install_residual_helper() -> None:
            from client.windows.elevate import elevate_if_needed, is_admin
            from client.windows.residual_privilege import install_residual_helper

            if not is_admin():
                note_var.set(
                    "Approving UAC re-opens elevated — then use Install residual helper again."
                )
                st = elevate_if_needed()
                if should_exit_after_elevation(st):
                    try:
                        win.destroy()
                        self.root.destroy()
                    except Exception:
                        pass
                    return
                note_var.set(
                    "Need Administrator once to install the residual helper. "
                    "Approve UAC, then try Install again."
                )
                return
            res = install_residual_helper()
            if res.get("ok"):
                note_var.set("Residual helper installed. You can use Connect as a normal user.")
                self._log("Settings: residual helper scheduled task installed.")
            else:
                note_var.set(
                    f"Helper install failed: {res.get('error') or res.get('detail') or res}"
                )
            _refresh_residual_priv()

        tk.Button(
            priv_help,
            text="Install residual helper (one-time Administrator)",
            command=_install_residual_helper,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=4,
            cursor="hand2",
        ).pack(anchor="w", pady=(6, 0))
        self.root.after(50, _refresh_residual_priv)

        # --- Licence + anonymous registration honesty ---
        lic_card, lic_outer = make_neon_card(pad, padx=12, pady=8)
        lic_outer.pack(fill=tk.X, pady=(14, 0))
        tk.Label(
            lic_card,
            text=LICENCE_PROMPT_TITLE,
            bg=PANEL_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))
        lic_status = (
            "Accepted on this device."
            if has_accepted_licence()
            else "Not accepted — Connect is blocked until you accept."
        )
        tk.Label(
            lic_card,
            text=lic_status,
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X)
        tk.Button(
            lic_card,
            text=LICENCE_ACCEPT_BUTTON,
            command=lambda: (self._show_licence_prompt(), note_var.set("Review licence…")),
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=4,
            cursor="hand2",
        ).pack(anchor="w", pady=(8, 0))

        # --- Payment entitlement (keygen → active subscription unlock) ---
        pay_card, pay_card_outer = make_neon_card(pad, padx=12, pady=8)

        pay_card_outer.pack(fill=tk.X, pady=(14, 0))
        tk.Label(
            pay_card,
            text="Payment entitlement / keygen",
            bg=PANEL_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            pay_card,
            text=PAYMENT_CONNECT_DISCLAIMER_PLAIN,
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X)
        _pay = load_payment_entitlement()
        _pay_status = (
            f"Status: {_pay.status or 'unknown'}"
            + (f" (keygen {_pay.keygen[:18]}…)" if _pay.keygen else "")
            + (f" (session {_pay.session_id[:18]}…)" if _pay.session_id else " (no keygen)")
        )
        pay_status_var = tk.StringVar(value=_pay_status)
        tk.Label(
            pay_card,
            textvariable=pay_status_var,
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(6, 2))
        tk.Label(
            pay_card,
            text="Enter keygen from your fulfilment email "
            "(USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY). "
            "Optional: session id (cs_…) or auto-import payment_entitlement.json:",
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X)
        session_var = tk.StringVar(value=_pay.keygen or _pay.session_id or "")
        session_entry = tk.Entry(
            pay_card,
            textvariable=session_var,
            font=("Segoe UI", 9),
            bg=WHITE,
            fg=TEXT,
            relief=tk.SOLID,
            bd=1,
        )
        session_entry.pack(fill=tk.X, pady=(4, 4))

        def _verify_payment() -> None:
            from client.payment_entitlement import import_keygen_and_verify

            raw = (session_var.get() or "").strip()
            note_var.set("Verifying payment entitlement…")
            win.update_idletasks()

            def work() -> None:
                try:
                    if raw.upper().startswith("RPT-KEY") or raw.upper().startswith(
                        "RPTKEY"
                    ):
                        ent = import_keygen_and_verify(raw)
                    elif raw.startswith("cs_") or raw.startswith("cs_test"):
                        ent = import_session_and_verify(raw)
                    elif raw:
                        # Prefer keygen path for non-session tokens
                        ent = import_keygen_and_verify(raw)
                    else:
                        ent = ensure_entitlement_for_connect(bind_device=True)
                    ok = payment_allows_connect()
                    st = getattr(ent, "status", None) or load_payment_entitlement().status
                    msg = (
                        f"Payment active — Connect allowed (status={st})."
                        if ok
                        else (
                            f"Payment not active (status={st}). "
                            "Connect stays blocked until active subscription "
                            "(enter keygen from email, or place "
                            "payment_entitlement.json in Downloads)."
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    msg = f"Could not verify payment: {exc}"
                    ok = False

                def done() -> None:
                    note_var.set(msg)
                    ent2 = load_payment_entitlement()
                    pay_status_var.set(f"Status: {ent2.status}")
                    if ent2.keygen:
                        session_var.set(ent2.keygen)
                    elif ent2.session_id:
                        session_var.set(ent2.session_id)
                    self._log(msg)
                    self._refresh_licence_badge()
                    if ok:
                        self.detail_var.set(
                            "Payment verified. Press Connect when you want protection."
                        )

                try:
                    self.root.after(0, done)
                except Exception:
                    pass

            import threading

            threading.Thread(target=work, daemon=True).start()

        tk.Button(
            pay_card,
            text="Verify keygen / unlock Connect",
            command=_verify_payment,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=4,
            cursor="hand2",
        ).pack(anchor="w", pady=(4, 0))

        tk.Label(
            lic_card,
            text=ANON_REGISTRATION_TITLE,
            bg=PANEL_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(12, 2))
        tk.Label(
            lic_card,
            text=ANON_REGISTRATION_SUMMARY,
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X)
        tk.Label(
            lic_card,
            text=OS_PRIVILEGE_HONESTY,
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(4, 0))

        # --- Connection log (local only, exportable) ---
        log_card, log_card_outer = make_neon_card(pad, padx=12, pady=8)

        log_card_outer.pack(fill=tk.X, pady=(14, 0))
        tk.Label(
            log_card,
            text=CONNECTION_LOG_TITLE,
            bg=PANEL_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            log_card,
            text=CONNECTION_LOG_DISCLAIMER,
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 6))
        log_box = tk.Text(
            log_card,
            height=7,
            wrap=tk.WORD,
            font=("Consolas", 8),
            bg=CHROME_BG,
            fg=TEXT,
            relief=tk.FLAT,
            state=tk.DISABLED,
        )
        log_box.pack(fill=tk.X)

        def _refresh_log_view() -> None:
            events = read_events(limit=80)
            body = (
                "\n".join(ev.format_line() for ev in events)
                if events
                else "(No connection events yet. Connect or Disconnect to record.)"
            )
            log_box.configure(state=tk.NORMAL)
            log_box.delete("1.0", tk.END)
            log_box.insert(tk.END, body)
            log_box.configure(state=tk.DISABLED)

        def _export_log() -> None:
            from tkinter import filedialog

            dest = filedialog.asksaveasfilename(
                parent=win,
                title="Export connection log",
                defaultextension=".txt",
                filetypes=[
                    ("Text", "*.txt"),
                    ("All files", "*.*"),
                ],
                initialfile="restore-privacy-connection-log.txt",
            )
            if not dest:
                return
            try:
                from pathlib import Path as _P

                from client.connection_log import export_to_file

                export_to_file(_P(dest))
                note_var.set(f"Exported connection log to {dest}")
                self._log(f"Settings: exported connection log to {dest}")
            except Exception as exc:
                note_var.set(f"Export failed: {exc}")

        btn_row = tk.Frame(log_card, bg=PANEL_BG)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        tk.Button(
            btn_row,
            text=EXPORT_LOG_BUTTON,
            command=_export_log,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=4,
            cursor="hand2",
        ).pack(side=tk.LEFT)
        tk.Button(
            btn_row,
            text="Refresh",
            command=_refresh_log_view,
            bg=LIGHT_ACCENT,
            fg=PRIMARY_DARK,
            relief=tk.FLAT,
            font=("Segoe UI", 8),
            padx=10,
            pady=4,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=(8, 0))
        _refresh_log_view()

        # --- Leak test ---
        leak_card, leak_card_outer = make_neon_card(pad, padx=12, pady=8)

        leak_card_outer.pack(fill=tk.X, pady=(14, 0))
        tk.Label(
            leak_card,
            text=LEAK_TEST_TITLE,
            bg=PANEL_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            leak_card,
            text=LEAK_TEST_DISCLAIMER,
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 6))

        def _run_leak_test() -> None:
            residual = residual_ip_capture_active(self._tunnel)
            ipv6 = ipv6_residual_protected(self._tunnel) if residual else False
            # Offline-safe default: no live public-IP probe (CI / no network).
            # Decision still uses real residual + shipped DNS plan.
            result = run_product_leak_test(
                residual_capture_active=residual,
                ipv6_protected=ipv6,
                run_public_ip_probe=False,
            )
            msg = result.format_user_message()
            leak_var.set(msg)
            self._connection_log(KIND_LEAK_TEST, f"{result.verdict}: {result.summary}")
            self._log(f"Leak test: {result.verdict} — {result.summary}")
            note_var.set(f"Leak test: {result.verdict}")
            _refresh_log_view()

        tk.Button(
            leak_card,
            text=LEAK_TEST_BUTTON,
            command=_run_leak_test,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
            font=("Segoe UI", 9, "bold"),
            padx=12,
            pady=5,
            cursor="hand2",
        ).pack(anchor="w")
        tk.Label(
            leak_card,
            textvariable=leak_var,
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI", 8),
            anchor="w",
            justify=tk.LEFT,
            wraplength=400,
        ).pack(fill=tk.X, pady=(8, 0))

        # --- DPI / traffic-analysis honesty ---
        dpi_card, dpi_card_outer = make_neon_card(pad, padx=12, pady=8)

        dpi_card_outer.pack(fill=tk.X, pady=(14, 0))
        tk.Label(
            dpi_card,
            text=DPI_MITIGATION_TITLE,
            bg=PANEL_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            dpi_card,
            text=DPI_MITIGATION_DISCLAIMER,
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X)

        # Legal / policy documents (stable public GitHub URLs)
        from client.legal_links import LEGAL_DOC_LINKS

        docs_card, docs_outer = make_neon_card(pad, padx=12, pady=8)
        docs_outer.pack(fill=tk.X, pady=(14, 0))
        tk.Label(
            docs_card,
            text="Documents",
            bg=PANEL_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))

        def _open_legal(url: str, label: str) -> None:
            self._log(f"Opening {label}...")
            try:
                webbrowser.open(url)
            except Exception as exc:
                self._log(f"Could not open browser: {exc}. Visit: {url}")
                note_var.set(f"Open manually: {url}")

        for link in LEGAL_DOC_LINKS:
            lbl = tk.Label(
                docs_card,
                text=link.label,
                bg=PANEL_BG,
                fg=PRIMARY,
                font=("Segoe UI", 9, "underline"),
                cursor="hand2",
                anchor="w",
            )
            lbl.pack(fill=tk.X, pady=2)
            lbl.bind(
                "<Button-1>",
                lambda _e, u=link.url, t=link.label: _open_legal(u, t),
            )

        btn_bar = tk.Frame(pad, bg=CHROME_BG)
        btn_bar.pack(fill=tk.X, pady=(14, 0))

        def _ok_bind_and_close() -> None:
            """Persist current toggles, mark first-run settings done, show main Connect."""
            s = _current_settings()
            s.first_run_settings_completed = True
            save_settings(s)
            self._settings = s
            try:
                apply_run_at_startup(s.run_at_startup)
            except Exception:
                pass
            try:
                mark_first_run_settings_completed(settings=s)
            except Exception:
                # save_settings already wrote completed flag on s
                pass
            # Critical: first-run OK must align main-shell picker + multihop with
            # the just-saved entry_country (DE/RO), not leave stale Iceland.
            try:
                self._sync_main_entry_from_settings()
            except Exception:
                try:
                    if getattr(self, "_entry_label_var", None) is not None:
                        self._entry_label_var.set(
                            option_label_for_code(s.entry_country)
                        )
                    self._refresh_multihop_from_settings()
                except Exception:
                    pass
            self._log(
                "Settings OK — preferences bound; main Connect surface ready "
                f"(entry={normalize_entry_country(s.entry_country)})."
            )
            self.detail_var.set(
                "Settings saved. Press Connect for residual protection."
            )
            _on_settings_closed()
            # _on_settings_closed already raises main shell; pulse again after OK
            # so first-run return is not buried under other apps.
            try:
                self._bring_shell_forward(force_visible=False)
            except Exception:
                pass

        if first_run:
            tk.Button(
                btn_bar,
                text="OK",
                command=_ok_bind_and_close,
                bg=PRIMARY,
                fg=WHITE,
                relief=tk.FLAT,
                font=("Segoe UI", 11, "bold"),
                padx=28,
                pady=10,
                cursor="hand2",
            ).pack(side=tk.RIGHT)
            tk.Label(
                btn_bar,
                text="OK saves your settings and opens the main Connect window.",
                bg=CHROME_BG,
                fg=TEXT_MUTED,
                font=("Segoe UI", 8),
                anchor="w",
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        else:
            tk.Button(
                btn_bar,
                text="OK",
                command=_ok_bind_and_close,
                bg=PRIMARY,
                fg=WHITE,
                relief=tk.FLAT,
                font=("Segoe UI", 9, "bold"),
                padx=14,
                pady=6,
                cursor="hand2",
            ).pack(side=tk.RIGHT)
            tk.Button(
                btn_bar,
                text="Close",
                command=_on_settings_closed,
                bg=PANEL_BG,
                fg=TEXT,
                relief=tk.FLAT,
                font=("Segoe UI", 9),
                padx=12,
                pady=6,
                cursor="hand2",
            ).pack(side=tk.RIGHT, padx=(0, 8))

        # Wheel / trackpad / mouse-ball scroll on body (not scrollbar-only).
        # Bind after children exist so descendant hover targets receive events.
        try:
            win.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
        except Exception:
            pass
        self._settings_scroll_unbind = bind_scrollable_canvas(canvas, pad, win)

    def _on_close_ui_only(self) -> None:
        """Hide UI; keep process + tunnel alive (tray / taskbar). Disconnect is separate.

        Destroying the window would end mainloop and kill residual dual /1 routes
        without rollback - so we withdraw to tray instead of destroy.
        """
        try:
            self._log(
                f"Window hidden - VPN keeps running if connected. "
                f"Restore from the system tray ({TRAY_DISPLAY_NAME}) or taskbar. "
                "Press Disconnect to stop, or Quit to exit."
            )
        except Exception:
            pass
        try:
            self.root.withdraw()
        except Exception:
            try:
                self.root.iconify()
            except Exception:
                pass

    def _show_quitting_status(self) -> None:
        """Paint Quit remark so the UI does not look frozen during residual teardown."""
        apply_quit_status_remark(self.status_var, self.detail_var)
        try:
            t = getattr(self, "_t", None) or {}
            fg = t.get("primary_dark") or PRIMARY_DARK
            self.status_label.configure(fg=fg)
        except Exception:
            pass
        try:
            self.btn_var.set("Quitting...")
            self.connect_btn.configure(state=tk.DISABLED)
            self.quit_btn.configure(state=tk.DISABLED)
        except Exception:
            pass
        try:
            # Force Tk to paint before long residual work starts off-thread.
            self.root.update_idletasks()
        except Exception:
            pass

    def _quit_app(self) -> None:
        """Explicit quit: show status, tear down residual off UI thread, then exit.

        Residual disconnect/restore previously ran **synchronously** on the button
        callback, which froze the Tk loop and triggered Windows "Not Responding".
        Order now: status remark → yield → tray stop (non-join) → worker teardown
        → ``root.destroy`` on the UI thread.
        """
        if getattr(self, "_quitting", False):
            return
        self._quitting = True
        try:
            self._log("Quit - stopping tunnel and restoring internet...")
        except Exception:
            pass

        # 1) Status first so the user sees intentional shutdown (not a freeze).
        self._show_quitting_status()

        # 2) Tray stop is PostMessage-based (no join) — keep off the residual path.
        try:
            self._stop_system_tray()
        except Exception:
            pass

        tunnel = self._tunnel
        self._tunnel = None
        client = self.client

        def _teardown_worker() -> None:
            try:
                run_quit_residual_teardown(tunnel, client)
            finally:

                def _destroy_ui() -> None:
                    try:
                        self.root.destroy()
                    except Exception:
                        pass

                try:
                    self.root.after(0, _destroy_ui)
                except Exception:
                    try:
                        self.root.destroy()
                    except Exception:
                        pass

        def _start_teardown() -> None:
            threading.Thread(
                target=_teardown_worker,
                name="rpt-quit-teardown",
                daemon=True,
            ).start()

        # 3) Yield one event-loop turn so the quitting remark paints, then worker.
        try:
            self.root.after(0, _start_teardown)
        except Exception:
            _start_teardown()

    def run(self) -> None:
        # No finally-teardown on hide: tunnel is user-controlled (Disconnect / Quit)
        self.root.mainloop()


# Back-compat alias for imports / older tests
RetroClientApp = TunnelClientApp


def _launch_diag(message: str) -> None:
    """Append one line to local launch log (diagnose instant-exit vs crash)."""
    try:
        from pathlib import Path
        import time

        base = os.environ.get("LOCALAPPDATA") or str(
            Path.home() / "AppData" / "Local"
        )
        p = Path(base) / "RestorePrivacy" / "launch.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(f"{time.time():.3f} {message}\n")
    except Exception:
        pass


def _enable_crash_fault_log() -> None:
    """Always-on faulthandler → %LOCALAPPDATA%\\RestorePrivacy\\fault.log."""
    try:
        import faulthandler
        from pathlib import Path

        base = os.environ.get("LOCALAPPDATA") or str(
            Path.home() / "AppData" / "Local"
        )
        p = Path(base) / "RestorePrivacy" / "fault.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        # Keep handle alive for process lifetime (module attr)
        _enable_crash_fault_log._fh = p.open("a", encoding="utf-8", buffering=1)  # type: ignore[attr-defined]
        fh = _enable_crash_fault_log._fh  # type: ignore[attr-defined]
        faulthandler.enable(file=fh, all_threads=True)
        fh.write(f"\n--- fault log enable pid={os.getpid()} ---\n")
        fh.flush()
    except Exception:
        pass


def main() -> int:
    """Launch UI; residual Connect elevates (Wintun + dual /1). No cold auto-connect."""
    _enable_crash_fault_log()
    try:
        set_process_app_user_model_id()
    except Exception:
        pass
    # Detect handoff *before* stripping flags (single-instance allows handoff).
    resume_after_elevate = "--rpt-auto-connect" in sys.argv
    is_elev_flag = "--rpt-elevated" in sys.argv
    if "--rpt-elevated" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--rpt-elevated"]
    # User pressed Connect then approved UAC - resume that one Connect only.
    if resume_after_elevate:
        sys.argv = [a for a in sys.argv if a != "--rpt-auto-connect"]

    # One cold-start GUI: second launch focuses existing window and exits
    # (elevated --rpt-auto-connect handoff is allowed as a second process).
    try:
        from client.windows.single_instance import guard_single_instance_or_activate

        cont, si_reason = guard_single_instance_or_activate(
            window_title=APP_TITLE,
            allow_handoff=bool(resume_after_elevate or is_elev_flag),
        )
        if not cont:
            # Second launch: existing window focused — exit quietly (not a crash).
            try:
                _launch_diag(f"single_instance_exit reason={si_reason}")
            except Exception:
                pass
            return 0
    except Exception:
        si_reason = "guard_failed"

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        os.chdir(root)
    except Exception:
        pass

    # Product surface is Tk - detach any leftover console host window.
    try:
        from client.windows.launch_gui import free_console_if_attached

        free_console_if_attached()
    except Exception:
        pass

    # Default: keep the GUI as a standard user. Residual privilege is requested
    # on Connect (UAC once) or via the one-time residual helper task — not by
    # forcing "Run as administrator" on every cold start.
    # Opt-in launch elevate: RPT_ELEVATE_ON_LAUNCH=1 (legacy / support).
    status = "skipped"
    want_launch_elev = os.environ.get("RPT_ELEVATE_ON_LAUNCH", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if want_launch_elev:
        status = elevate_if_needed()
        if should_exit_after_elevation(status):
            return 0

    try:
        _launch_diag(f"creating_app si_reason={si_reason!r}")
        app = TunnelClientApp()
        _launch_diag("app_created")
    except Exception as exc:
        try:
            _launch_diag(f"app_create_failed {type(exc).__name__}: {exc}")
        except Exception:
            pass
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                f"Restore Privacy failed to open:\n{exc}",
                "Restore Privacy",
                0x10,
            )
        except Exception:
            print(f"Restore Privacy failed to open: {exc}", file=sys.stderr)
        return 1

    if is_admin():
        app.root.after(
            100,
            lambda: app._log(
                "Running elevated — Connect will route residual public IP via the VPN node."
            ),
        )
    else:
        def _note_standard() -> None:
            try:
                from client.windows.residual_privilege import residual_privilege_status

                st = residual_privilege_status()
                if st.get("helper_installed"):
                    app._log(
                        "Standard user — residual helper installed; Connect uses it "
                        "without Run as administrator on this window."
                    )
                else:
                    app._log(
                        "Standard user — open the app normally. Connect asks for "
                        "Administrator once for residual routes (or install residual helper)."
                    )
            except Exception:
                app._log(
                    "Standard user — Connect will request Administrator for residual routing."
                )

        app.root.after(100, _note_standard)

    # Warm entitlement cache off the UI thread (never block launch on status host).
    # Session-only discovery does not unlock Connect without keygen.
    def _bg_bootstrap() -> None:
        try:
            bootstrap_payment_entitlement(bind_device=True)
        except Exception:
            pass

    threading.Thread(target=_bg_bootstrap, daemon=True).start()

    # Cold launch: first-run surfaces always run when install not fully unlocked
    # (licence → keygen demand → settings OK → main). Do not gate solely on
    # may_connect() — that previously skipped keygen when gates were inconsistent.
    assert non_admin_connect_allowed()
    if resume_after_elevate and is_admin():
        # Elevated handoff: surface immediately (user just clicked Connect).
        def _raise_elevated_shell() -> None:
            try:
                app._bring_shell_forward(force_visible=True)
            except Exception:
                pass

        app.root.after(50, _raise_elevated_shell)

        def _resume_user_connect() -> None:
            # User already pressed Connect before UAC (or residual elevate).
            # Still block if keygen missing (cannot bypass unlock via elevate).
            try:
                app._bring_shell_forward(force_visible=True)
            except Exception:
                pass
            if needs_keygen_unlock():
                app._log(
                    "Elevated resume blocked — enter keygen to unlock install first."
                )
                app._show_keygen_prompt()
                return
            app._log("Resuming Connect after elevation...")
            app._start_connect()

        app.root.after(350, _resume_user_connect)
    elif resume_after_elevate and not is_admin():
        app.root.after(
            100,
            lambda: app._log(
                "Elevated Connect requested but process is not Administrator - "
                "press Connect again and approve UAC."
            ),
        )
    else:
        def _cold_start_first_run() -> None:
            surface = first_run_next_surface()
            app._log(f"Cold start first-run surface: {surface}")
            if surface != "main":
                # licence / renew / keygen / settings — always present when needed
                app._present_first_run_surface()
                return
            # Fully onboarded: optional Settings autoconnect
            if should_autoconnect_on_launch():
                if needs_keygen_unlock():
                    app._log(
                        "Settings: autoconnect skipped — enter keygen to unlock."
                    )
                    app._show_keygen_prompt()
                    return
                app._log("Settings: autoconnect on launch - starting Connect...")
                app._start_connect()

        app.root.after(400, _cold_start_first_run)

    try:
        _launch_diag("mainloop_enter")
    except Exception:
        pass
    app.run()
    try:
        _launch_diag("mainloop_exit")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
