#!/usr/bin/env python3
"""Windows RPT client — sleek manual Connect/Disconnect UI.

No auto-connect. Close does not disconnect (user must press Disconnect).
Palette from restorebritain.org.uk/contact (Cupertino theme tokens).
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
    residual_ip_capture_active,
    start_full_tunnel,
    stop_full_tunnel,
)


def disconnect_full_tunnel(
    tunnel, client, *, preserve_message: bool = False
) -> None:
    """Idempotent full stop — Disconnect button, or cleanup after failed attach.

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
    """Sleek shell: primary Connect/Disconnect, plain status panel, optional upgrade."""

    DEFAULT_GEOMETRY = "520x480"
    MIN_WIDTH = 400
    MIN_HEIGHT = 400

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry(self.DEFAULT_GEOMETRY)
        self.root.configure(bg=CHROME_BG)
        self.root.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self._set_window_icon()
        # UI-only close — tunnel stays up until user presses Disconnect
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
            font=("Segoe UI", 13, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=20,
            pady=14,
            bd=0,
            highlightthickness=0,
        )
        self.connect_btn.pack(side=tk.TOP, fill=tk.X, pady=(10, 6), ipady=6)

        self.hint_row = tk.Frame(self.bottom, bg=CHROME_BG)
        self.hint_row.pack(side=tk.TOP, fill=tk.X)
        self.hint = tk.Label(
            self.hint_row,
            text="Manual only — Connect starts, Disconnect stops. Close hides the window (VPN stays up).",
            bg=CHROME_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=380,
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

        # --- Status card (plain language) ---
        self.status_card = tk.Frame(
            self.chrome,
            bg=PANEL_BG,
            padx=PANEL_PAD,
            pady=PANEL_PAD,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        self.status_card.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        tk.Label(
            self.status_card,
            text="VPN status",
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill=tk.X)

        self.status_var = tk.StringVar(value=plain_tunnel_status("disconnected"))
        self.status_label = tk.Label(
            self.status_card,
            textvariable=self.status_var,
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI", 14, "bold"),
            anchor="w",
            wraplength=440,
            justify=tk.LEFT,
        )
        self.status_label.pack(fill=tk.X, pady=(4, 0))

        self.detail_var = tk.StringVar(value="Not connected. Press Connect when you want protection.")
        self.detail_label = tk.Label(
            self.status_card,
            textvariable=self.detail_var,
            bg=PANEL_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=440,
            justify=tk.LEFT,
        )
        self.detail_label.pack(fill=tk.X, pady=(6, 0))

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

        self._log(f"{APP_TITLE} — ready")
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

    def _on_client_status(self, msg: str) -> None:
        """Secondary log only — do not dump raw protocol into main status."""
        def ui() -> None:
            short = msg if len(msg) <= 100 else msg[:97] + "…"
            self._log(short)

        self.root.after(0, ui)

    def _set_status(
        self,
        state: str,
        *,
        vpn_ip: str | None = None,
        detail: str | None = None,
        residual_capture: bool | None = None,
    ) -> None:
        """Update main status dialogue and tray to match Connect/Disconnect state."""
        s = (state or "").strip().lower()
        self.status_var.set(
            plain_tunnel_status(
                s,
                vpn_ip=vpn_ip,
                detail=detail,
                residual_capture=residual_capture,
            )
        )
        if s == "connected" and residual_capture is not False:
            self.status_label.configure(fg=STATUS_OK)
            self.detail_var.set(
                "Your residual public IP uses the VPN node (full-tunnel routes active)."
            )
            # Pass connected=True explicitly — _apply_control may not have run yet
            self._sync_tray_status(connected=True, residual=True)
        elif s == "connected":
            self.status_label.configure(fg=STATUS_ERROR_FG)
            self.detail_var.set(
                "Session up but residual public IP still uses your ISP — not fully protected."
            )
            self._sync_tray_status(connected=True, residual=False)
        elif s == "connecting":
            self.status_label.configure(fg=PRIMARY_DARK)
            self.detail_var.set("Please wait… setting up a secure connection.")
            self._sync_tray_status(connected=False, residual=False)
        elif s == "disconnecting":
            self.status_label.configure(fg=PRIMARY_DARK)
            self.detail_var.set("Stopping the tunnel and restoring normal internet…")
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

    def _on_toggle_connect(self) -> None:
        if self._busy:
            return
        if self._connected:
            self._start_disconnect()
        else:
            self._start_connect()

    def _start_connect(self) -> None:
        # Residual public IP needs Administrator (Wintun + dual /1). Elevate first.
        if product_connect_requires_admin() and not is_admin():
            self._apply_control(connected=False, busy=True)
            self._set_status("connecting")
            self._log(
                "Connect — Administrator required so residual public IP uses "
                "the VPN node. Approving UAC will re-open and finish Connect…"
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
        self._log("Connect — starting secure session (full-tunnel residual path)…")

        def work() -> None:
            result = self.client.connect(timeout=20.0)

            def done() -> None:
                try:
                    if not (result.ok and result.session and result.tunnel_plan):
                        msg = result.message or "Connection failed"
                        self._log(f"Could not connect: {msg}")
                        self._set_status("error", detail=msg)
                        self._apply_control(connected=False, busy=False)
                        return

                    vpn_ip = result.session.vpn_ip
                    self._log(f"Session ready (tunnel address {vpn_ip})")
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
                        self._log(
                            "Tunnel active — residual public IP uses the VPN node "
                            f"(IF={getattr(tun_res, 'if_index', '?')})"
                        )
                        # Apply control first so _connected is True, then status+tray
                        self._apply_control(connected=True, busy=False)
                        self._set_status(
                            "connected",
                            vpn_ip=vpn_ip,
                            residual_capture=True,
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
        self._log("Disconnect — stopping tunnel…")

        def work() -> None:
            try:
                self._disconnect_tunnel()
            finally:

                def done() -> None:
                    self._apply_control(connected=False, busy=False)
                    self._set_status("disconnected")
                    self._sync_tray_status(connected=False, residual=False)
                    self._log("Disconnected.")

                self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _open_upgrade(self) -> None:
        url = upgrade_download_url()
        self._log(f"Opening download page…")
        try:
            webbrowser.open(url)
        except Exception as exc:
            self._log(f"Could not open browser: {exc}. Visit: {url}")

    def _open_settings(self) -> None:
        """Settings surface: run-at-startup + autoconnect-on-launch switches."""
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.configure(bg=CHROME_BG)
        win.geometry("420x280")
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

        pad = tk.Frame(win, bg=CHROME_BG, padx=16, pady=14)
        pad.pack(fill=tk.BOTH, expand=True)

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
            # Switch-style checkbutton (slider-like on/off)
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
                note_var.set("Autoconnect on launch ON — next cold start will Connect.")
            else:
                note_var.set("Autoconnect on launch OFF — Connect is manual.")
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
            wraplength=380,
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
            wraplength=380,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(8, 0))

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
        without rollback — so we withdraw to tray instead of destroy.
        """
        try:
            self._log(
                f"Window hidden — VPN keeps running if connected. "
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
            self._log("Quit — stopping tunnel and exiting…")
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
    # User pressed Connect then approved UAC — resume that one Connect only.
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

    # Product surface is Tk — detach any leftover console host window.
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
                "Running elevated — Connect will route residual public IP via the VPN node."
            ),
        )
    else:
        app.root.after(
            100,
            lambda: app._log(
                "Standard user — Connect will request Administrator for residual routing."
            ),
        )

    # Cold launch: optional user autoconnect (Settings); resume after UAC Connect.
    assert non_admin_connect_allowed()
    if resume_after_elevate and is_admin():

        def _resume_user_connect() -> None:
            # User already pressed Connect before UAC (or residual elevate).
            app._log("Resuming Connect after elevation…")
            app._start_connect()

        app.root.after(350, _resume_user_connect)
    elif resume_after_elevate and not is_admin():
        app.root.after(
            100,
            lambda: app._log(
                "Elevated Connect requested but process is not Administrator — "
                "press Connect again and approve UAC."
            ),
        )
    elif should_autoconnect_on_launch() and not resume_after_elevate:

        def _settings_autoconnect() -> None:
            app._log("Settings: autoconnect on launch — starting Connect…")
            app._start_connect()

        app.root.after(450, _settings_autoconnect)

    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
