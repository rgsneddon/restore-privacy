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
    SCROLLING_PRIVACY_TEXT,
    STATUS_ERROR,
    STATUS_ERROR_FG,
    STATUS_OK,
    TEXT,
    TEXT_MUTED,
    WHITE,
    catalog_latest_version,
    connect_button_label,
    plain_tunnel_status,
    read_running_version,
    resolve_logo_png,
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
    short_licence_summary,
)
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
from client.windows.settings_store import (
    ProductSettings,
    apply_run_at_startup,
    load_settings,
    save_settings,
    should_autoconnect_on_launch,
)
from client.windows.tray_win import (
    TRAY_DISPLAY_NAME,
    WindowsSystemTray,
    resolve_tray_icon_path,
)
from client.windows.tunnel_win import (
    ipv6_residual_protected,
    residual_ip_capture_active,
    start_full_tunnel,
    stop_full_tunnel,
)


def disconnect_full_tunnel(
    tunnel, client, *, preserve_message: bool = False
) -> None:
    """Idempotent full stop - Disconnect button, or cleanup after failed attach.

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
    return True


def product_connect_requires_admin() -> bool:
    """True: product residual public IP path needs Administrator (Wintun + dual /1)."""
    return True


def layout_pack_bottom_controls_first() -> bool:
    """Connect bar packs at bottom before expanding log (always-visible primary control)."""
    return True


class TunnelClientApp:
    """Seamless shell: hero status, Connect/Disconnect, Settings transparency."""

    DEFAULT_GEOMETRY = "540x560"
    MIN_WIDTH = 420
    MIN_HEIGHT = 480

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry(self.DEFAULT_GEOMETRY)
        self.root.configure(bg=CHROME_BG)
        self.root.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self._set_window_icon()
        # UI-only close - tunnel stays up until user presses Disconnect
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_ui_only)

        self._connected = False
        self._busy = False
        self._tunnel = None
        self._tray: WindowsSystemTray | None = None
        self.client = RptClient(status_cb=self._on_client_status)
        self._start_system_tray()

        # Outer chrome with padding (rounded language via spacing)
        self.chrome = tk.Frame(self.root, bg=CHROME_BG, padx=PANEL_PAD + 4, pady=PANEL_PAD + 4)
        self.chrome.pack(fill=tk.BOTH, expand=True)

        # --- Bottom: primary control first so it never disappears ---
        self.bottom = tk.Frame(self.chrome, bg=CHROME_BG)
        self.bottom.pack(side=tk.BOTTOM, fill=tk.X)

        self.btn_var = tk.StringVar(value=connect_button_label(False))
        self.connect_btn = tk.Button(
            self.bottom,
            textvariable=self.btn_var,
            command=self._on_toggle_connect,
            bg=BUTTON_CONNECT_BG,
            fg=BUTTON_FG,
            activebackground=PRIMARY,
            activeforeground=BUTTON_FG,
            disabledforeground=DISABLED_FG,
            font=("Segoe UI", 14, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=20,
            pady=16,
            bd=0,
            highlightthickness=0,
        )
        self.connect_btn.pack(side=tk.TOP, fill=tk.X, pady=(10, 6), ipady=8)

        self.hint_row = tk.Frame(self.bottom, bg=CHROME_BG)
        self.hint_row.pack(side=tk.TOP, fill=tk.X)
        self.hint = tk.Label(
            self.hint_row,
            text=SEAMLESS_HINT,
            bg=CHROME_BG,
            fg=TEXT_MUTED,
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
            bg=CHROME_BG,
            fg=TEXT_MUTED,
            activebackground=LIGHT_ACCENT,
            activeforeground=TEXT,
            relief=tk.FLAT,
            font=("Segoe UI", 8, "underline"),
            cursor="hand2",
            bd=0,
            padx=6,
        )
        self.quit_btn.pack(side=tk.RIGHT)

        # --- Header ---
        self.header = tk.Frame(self.chrome, bg=CHROME_BG)
        self.header.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        self._logo_photo = None
        logo = resolve_logo_png()
        if logo is not None:
            try:
                img = tk.PhotoImage(file=str(logo))
                if img.width() > 64:
                    factor = max(1, img.width() // 48)
                    img = img.subsample(factor, factor)
                self._logo_photo = img
                tk.Label(self.header, image=self._logo_photo, bg=CHROME_BG).pack(
                    side=tk.LEFT, padx=(0, 10)
                )
            except Exception:
                self._logo_photo = None

        title_col = tk.Frame(self.header, bg=CHROME_BG)
        title_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(
            title_col,
            text=APP_TITLE,
            bg=CHROME_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 18, "bold"),
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            title_col,
            text=BANNER_TITLE,
            bg=CHROME_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            title_col,
            text=SEAMLESS_TAGLINE,
            bg=CHROME_BG,
            fg=PRIMARY,
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))

        # Settings cog (gear)
        self.settings_btn = tk.Button(
            self.header,
            text="⚙",
            command=self._open_settings,
            bg=CHROME_BG,
            fg=PRIMARY_DARK,
            activebackground=LIGHT_ACCENT,
            activeforeground=PRIMARY_DARK,
            relief=tk.FLAT,
            font=("Segoe UI", 16),
            cursor="hand2",
            bd=0,
            padx=8,
        )
        self.settings_btn.pack(side=tk.RIGHT)
        self._settings = load_settings()

        # --- Upgrade banner (only if behind catalog) ---
        self.upgrade_frame = tk.Frame(
            self.chrome, bg=LIGHT_ACCENT, padx=10, pady=8, highlightbackground=BORDER, highlightthickness=1
        )
        self._upgrade_msg = upgrade_banner_text()
        if self._upgrade_msg:
            self.upgrade_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))
            tk.Label(
                self.upgrade_frame,
                text=self._upgrade_msg,
                bg=LIGHT_ACCENT,
                fg=TEXT,
                font=("Segoe UI", 9),
                anchor="w",
                wraplength=400,
                justify=tk.LEFT,
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Button(
                self.upgrade_frame,
                text="Get update",
                command=self._open_upgrade,
                bg=PRIMARY,
                fg=WHITE,
                activebackground=PRIMARY_DARK,
                activeforeground=WHITE,
                relief=tk.FLAT,
                font=("Segoe UI", 9, "bold"),
                cursor="hand2",
                padx=10,
                pady=4,
            ).pack(side=tk.RIGHT, padx=(8, 0))

        # --- Hero status card (plain language, residual-honest) ---
        self.status_card = tk.Frame(
            self.chrome,
            bg=PANEL_BG,
            padx=PANEL_PAD + 4,
            pady=PANEL_PAD + 4,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        self.status_card.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        hero_top = tk.Frame(self.status_card, bg=PANEL_BG)
        hero_top.pack(fill=tk.X)
        tk.Label(
            hero_top,
            text="VPN status",
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._licence_badge_var = tk.StringVar(
            value="Licence accepted" if may_connect() else "Licence required"
        )
        self._licence_badge = tk.Label(
            hero_top,
            textvariable=self._licence_badge_var,
            bg=LIGHT_ACCENT if may_connect() else "#FDECEC",
            fg=PRIMARY_DARK if may_connect() else STATUS_ERROR_FG,
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=2,
        )
        self._licence_badge.pack(side=tk.RIGHT)

        self.status_var = tk.StringVar(value=plain_tunnel_status("disconnected"))
        self.status_label = tk.Label(
            self.status_card,
            textvariable=self.status_var,
            bg=PANEL_BG,
            fg=TEXT,
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
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=460,
            justify=tk.LEFT,
        )
        self.detail_label.pack(fill=tk.X, pady=(6, 0))

        # Licence CTA when not yet accepted (seamless first-run)
        self._licence_cta = tk.Frame(self.status_card, bg=PANEL_BG)
        tk.Button(
            self._licence_cta,
            text=LICENCE_ACCEPT_BUTTON,
            command=self._show_licence_prompt,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            padx=12,
            pady=5,
        ).pack(side=tk.LEFT, pady=(10, 0))
        tk.Label(
            self._licence_cta,
            text="Required once before Connect",
            bg=PANEL_BG,
            fg=TEXT_MUTED,
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
        self._log(SCROLLING_PRIVACY_TEXT)
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
        native = Path(__file__).resolve().parent / "native"
        ico = native / "app_icon.ico"
        png = native / "app_icon.png"
        # Prefer brand logo path (same as tray / shortcuts)
        brand = resolve_tray_icon_path()
        if brand is not None and brand.suffix.lower() == ".ico":
            ico = brand
        elif brand is not None and brand.suffix.lower() == ".png":
            png = brand
        try:
            if ico.is_file():
                self.root.iconbitmap(default=str(ico))
            if png.is_file():
                img = tk.PhotoImage(file=str(png))
                self.root.iconphoto(True, img)
                self._icon_photo = img
        except Exception:
            pass

    def _start_system_tray(self) -> None:
        """Tray identity: Privacy Restored + product logo."""
        try:
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

    def _restore_from_tray(self) -> None:
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
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, line + "\n")
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
        if s == "connected" and residual_capture is not False:
            if ipv6_protected is False:
                self.status_label.configure(fg=STATUS_ERROR_FG)
                self.detail_var.set(
                    "IPv4 uses the VPN node, but IPv6 may still use your ISP - not fully protected."
                )
            else:
                self.status_label.configure(fg=STATUS_OK)
                self.detail_var.set(
                    "Your residual public IP uses the VPN node; IPv6 ISP path is blocked."
                )
            # Pass connected=True explicitly - _apply_control may not have run yet
            self._sync_tray_status(connected=True, residual=True)
        elif s == "connected":
            self.status_label.configure(fg=STATUS_ERROR_FG)
            self.detail_var.set(
                "Session up but residual public IP still uses your ISP - not fully protected."
            )
            self._sync_tray_status(connected=True, residual=False)
        elif s == "connecting":
            self.status_label.configure(fg=PRIMARY_DARK)
            self.detail_var.set("Please wait... setting up a secure connection.")
            self._sync_tray_status(connected=False, residual=False)
        elif s == "disconnecting":
            self.status_label.configure(fg=PRIMARY_DARK)
            self.detail_var.set("Stopping the tunnel and restoring normal internet...")
            # Still show connected tray until teardown finishes
            self._sync_tray_status(connected=True, residual=True)
        elif s in ("error", "failed"):
            self.status_label.configure(fg=STATUS_ERROR_FG)
            self.detail_var.set(detail or "Check the activity log, then try Connect again.")
            self._sync_tray_status(connected=False, residual=False)
        else:
            # disconnected
            self.status_label.configure(fg=TEXT)
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

    def _show_licence_prompt(self) -> None:
        """First-run / Settings: accept end-user licence (local only)."""
        win = tk.Toplevel(self.root)
        win.title(LICENCE_PROMPT_TITLE)
        win.configure(bg=CHROME_BG)
        win.geometry("460x420")
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass
        pad = tk.Frame(win, bg=CHROME_BG, padx=16, pady=14)
        pad.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            pad,
            text=LICENCE_PROMPT_TITLE,
            bg=CHROME_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            pad,
            text=short_licence_summary(),
            bg=CHROME_BG,
            fg=TEXT,
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=420,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            pad,
            text=ANON_REGISTRATION_SUMMARY,
            bg=CHROME_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=420,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            pad,
            text=OS_PRIVILEGE_HONESTY,
            bg=CHROME_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=420,
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
            bg=CHROME_BG,
            fg=PRIMARY,
            font=("Segoe UI", 9, "underline"),
            cursor="hand2",
            anchor="w",
        ).pack(fill=tk.X)
        pad.winfo_children()[-1].bind("<Button-1>", lambda _e: _open_full())

        btn_row = tk.Frame(pad, bg=CHROME_BG)
        btn_row.pack(fill=tk.X, pady=(16, 0))

        def _do_accept() -> None:
            accept_licence()
            self._log("Licence accepted (stored locally only).")
            self._connection_log("settings", "End-user licence accepted")
            self._refresh_licence_badge()
            self.detail_var.set("Licence accepted. Press Connect when ready.")
            try:
                win.destroy()
            except Exception:
                pass

        tk.Button(
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
        ).pack(side=tk.LEFT)
        tk.Button(
            btn_row,
            text="Not now",
            command=win.destroy,
            bg=CHROME_BG,
            fg=TEXT_MUTED,
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            padx=10,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=(10, 0))

    def _on_toggle_connect(self) -> None:
        if self._busy:
            return
        if self._connected:
            self._start_disconnect()
        else:
            self._start_connect()

    def _start_connect(self) -> None:
        # Licence gate — blocks Connect and autoconnect resume alike.
        ok_lic, lic_msg = assert_may_connect()
        if not ok_lic:
            self._log(lic_msg)
            self._set_status("error", detail=lic_msg)
            self.detail_var.set(lic_msg)
            self._show_licence_prompt()
            return

        # Residual public IP needs Administrator (Wintun + dual /1). Elevate first.
        if product_connect_requires_admin() and not is_admin():
            self._apply_control(connected=False, busy=True)
            self._set_status("connecting")
            self._log(
                "Connect - Administrator required so residual public IP uses "
                "the VPN node. Approving UAC will re-open and finish Connect..."
            )
            status = elevate_if_needed(extra_args=["--rpt-auto-connect"])
            if should_exit_after_elevation(status):
                # Elevated child resumes Connect via --rpt-auto-connect
                try:
                    self.root.destroy()
                except Exception:
                    pass
                return
            reason = status.split(":", 1)[-1] if status.startswith("failed:") else status
            err = (
                "Administrator required so your residual public IP uses the VPN node. "
                f"Approve UAC when prompted ({reason})."
            )
            self._log(f"Could not connect: {err}")
            self._set_status("error", detail=err)
            self._apply_control(connected=False, busy=False)
            return

        self._apply_control(connected=False, busy=True)
        self._set_status("connecting")
        self._log("Connect - starting secure session (full-tunnel residual path)...")
        self._connection_log(
            KIND_CONNECT, "Connect started (full-tunnel residual path)"
        )

        def work() -> None:
            result = self.client.connect(timeout=20.0)

            def done() -> None:
                try:
                    if not (result.ok and result.session and result.tunnel_plan):
                        msg = result.message or "Connection failed"
                        self._log(f"Could not connect: {msg}")
                        self._connection_log(KIND_ERROR, f"Connect failed: {msg}")
                        self._set_status("error", detail=msg)
                        self._apply_control(connected=False, busy=False)
                        return

                    vpn_ip = result.session.vpn_ip
                    self._log(f"Session ready (tunnel address {vpn_ip})")
                    self._connection_log(
                        KIND_SESSION, f"Session ready (tunnel address {vpn_ip})"
                    )
                    # Product residual path: Wintun + dual /1 only (no queue "Connected")
                    tun_res = start_full_tunnel(
                        self.client,
                        result.tunnel_plan,
                        result.session.endpoint.host,
                        prefer_system_capture=True,
                        require_system_capture=True,
                    )
                    self._tunnel = tun_res
                    if residual_ip_capture_active(tun_res):
                        v6 = ipv6_residual_protected(tun_res)
                        self._log(
                            "Tunnel active - residual public IP uses the VPN node "
                            f"(IF={getattr(tun_res, 'if_index', '?')}; "
                            f"ipv6_protected={v6})"
                        )
                        self._connection_log(
                            KIND_CONNECT,
                            "Connected — residual public IP uses the VPN node "
                            f"(ipv6_protected={v6})",
                        )
                        # Apply control first so _connected is True, then status+tray
                        self._apply_control(connected=True, busy=False)
                        self._set_status(
                            "connected",
                            vpn_ip=vpn_ip,
                            residual_capture=True,
                            ipv6_protected=v6,
                        )
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

                self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _open_upgrade(self) -> None:
        url = upgrade_download_url()
        self._log(f"Opening download page...")
        try:
            webbrowser.open(url)
        except Exception as exc:
            self._log(f"Could not open browser: {exc}. Visit: {url}")

    def _open_settings(self) -> None:
        """Settings: startup prefs, local connection log, leak test, DPI honesty."""
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.configure(bg=CHROME_BG)
        win.geometry("460x720")
        win.minsize(400, 520)
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass

        cur = load_settings()
        self._settings = cur
        run_var = tk.BooleanVar(value=cur.run_at_startup)
        auto_var = tk.BooleanVar(value=cur.autoconnect_on_launch)
        note_var = tk.StringVar(value="")
        leak_var = tk.StringVar(value="")

        # Scrollable body for taller transparency content
        canvas = tk.Canvas(win, bg=CHROME_BG, highlightthickness=0)
        scroll = tk.Scrollbar(win, orient=tk.VERTICAL, command=canvas.yview)
        pad = tk.Frame(canvas, bg=CHROME_BG, padx=16, pady=14)
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
            bg=CHROME_BG,
            fg=PRIMARY_DARK,
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 10))

        card = tk.Frame(
            pad,
            bg=PANEL_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        card.pack(fill=tk.X)

        def _row(parent, text, sub, var, on_toggle) -> None:
            row = tk.Frame(parent, bg=PANEL_BG)
            row.pack(fill=tk.X, pady=6)
            col = tk.Frame(row, bg=PANEL_BG)
            col.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(
                col,
                text=text,
                bg=PANEL_BG,
                fg=TEXT,
                font=("Segoe UI", 10, "bold"),
                anchor="w",
            ).pack(fill=tk.X)
            tk.Label(
                col,
                text=sub,
                bg=PANEL_BG,
                fg=TEXT_MUTED,
                font=("Segoe UI", 8),
                anchor="w",
                wraplength=280,
                justify=tk.LEFT,
            ).pack(fill=tk.X)
            sw = tk.Checkbutton(
                row,
                variable=var,
                command=on_toggle,
                bg=PANEL_BG,
                activebackground=PANEL_BG,
                onvalue=True,
                offvalue=False,
                indicatoron=True,
                selectcolor=PRIMARY,
                fg=PRIMARY_DARK,
            )
            sw.pack(side=tk.RIGHT, padx=(8, 0))

        def _save_run() -> None:
            s = ProductSettings(
                run_at_startup=bool(run_var.get()),
                autoconnect_on_launch=bool(auto_var.get()),
            )
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
            s = ProductSettings(
                run_at_startup=bool(run_var.get()),
                autoconnect_on_launch=bool(auto_var.get()),
            )
            save_settings(s)
            self._settings = s
            if s.autoconnect_on_launch:
                note_var.set("Autoconnect on launch ON - next cold start will Connect.")
            else:
                note_var.set("Autoconnect on launch OFF - Connect is manual.")
            self._log(f"Settings: autoconnect_on_launch={s.autoconnect_on_launch}")

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
            text="Both default off. Seamless power-up needs both on. "
            "Administrator / UAC may still be required for full tunnel.",
            bg=CHROME_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=400,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(8, 0))

        # --- Licence + anonymous registration honesty ---
        lic_card = tk.Frame(
            pad,
            bg=PANEL_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=12,
            pady=8,
        )
        lic_card.pack(fill=tk.X, pady=(14, 0))
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
        log_card = tk.Frame(
            pad,
            bg=PANEL_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=12,
            pady=8,
        )
        log_card.pack(fill=tk.X, pady=(14, 0))
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
        leak_card = tk.Frame(
            pad,
            bg=PANEL_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=12,
            pady=8,
        )
        leak_card.pack(fill=tk.X, pady=(14, 0))
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
        dpi_card = tk.Frame(
            pad,
            bg=PANEL_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=12,
            pady=8,
        )
        dpi_card.pack(fill=tk.X, pady=(14, 0))
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

        docs_card = tk.Frame(
            pad,
            bg=PANEL_BG,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=12,
            pady=8,
        )
        docs_card.pack(fill=tk.X, pady=(14, 0))
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

        tk.Button(
            pad,
            text="Close",
            command=win.destroy,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
            font=("Segoe UI", 9, "bold"),
            padx=14,
            pady=6,
            cursor="hand2",
        ).pack(anchor="e", pady=(14, 0))

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

    def _quit_app(self) -> None:
        """Explicit quit: stop tunnel then exit process (safe route cleanup)."""
        try:
            self._log("Quit - stopping tunnel and exiting...")
        except Exception:
            pass
        if self._tray is not None:
            try:
                self._tray.stop()
            except Exception:
                pass
            self._tray = None
        tunnel = self._tunnel
        self._tunnel = None
        try:
            disconnect_full_tunnel(tunnel, self.client)
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self) -> None:
        # No finally-teardown on hide: tunnel is user-controlled (Disconnect / Quit)
        self.root.mainloop()


# Back-compat alias for imports / older tests
RetroClientApp = TunnelClientApp


def main() -> int:
    """Launch UI; residual Connect elevates (Wintun + dual /1). No cold auto-connect."""
    if "--rpt-elevated" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--rpt-elevated"]
    # User pressed Connect then approved UAC - resume that one Connect only.
    resume_after_elevate = "--rpt-auto-connect" in sys.argv
    if resume_after_elevate:
        sys.argv = [a for a in sys.argv if a != "--rpt-auto-connect"]

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

    # Optional launch elevate so Connect can apply residual routes without a second UAC.
    # Elevated child prefers pythonw (windowed host). If cancelled, UI still opens.
    status = elevate_if_needed()
    if should_exit_after_elevation(status):
        return 0

    try:
        app = TunnelClientApp()
    except Exception as exc:
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

    if status.startswith("failed:"):
        reason = status.split(":", 1)[-1]

        def _note_elev_fail() -> None:
            app._log(
                f"Elevation skipped at launch ({reason}). "
                "Press Connect and approve UAC so residual public IP uses the VPN node."
            )

        app.root.after(100, _note_elev_fail)
    elif status == "already_admin" or is_admin():
        app.root.after(
            100,
            lambda: app._log(
                "Running elevated - Connect will route residual public IP via the VPN node."
            ),
        )
    else:
        app.root.after(
            100,
            lambda: app._log(
                "Standard user - Connect will request Administrator for residual routing."
            ),
        )

    # Cold launch: optional user autoconnect (Settings); resume after UAC Connect.
    assert non_admin_connect_allowed()
    if resume_after_elevate and is_admin():

        def _resume_user_connect() -> None:
            # User already pressed Connect before UAC (or residual elevate).
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
    elif should_autoconnect_on_launch() and not resume_after_elevate:

        def _settings_autoconnect() -> None:
            # assert_may_connect inside _start_connect — never bypass licence.
            if not may_connect():
                app._log(
                    "Settings: autoconnect skipped — accept the end-user licence first."
                )
                app._show_licence_prompt()
                return
            app._log("Settings: autoconnect on launch - starting Connect...")
            app._start_connect()

        app.root.after(450, _settings_autoconnect)
    elif not may_connect():
        # First-run seamless path: surface licence before the user hunts for it.
        app.root.after(500, app._show_licence_prompt)

    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
