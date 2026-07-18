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
from client.windows.tunnel_win import start_full_tunnel, stop_full_tunnel


def disconnect_full_tunnel(tunnel, client) -> None:
    """Idempotent full stop — used only by Disconnect (not window close)."""
    try:
        stop_full_tunnel(tunnel, client)
    except Exception:
        try:
            if client is not None:
                client.disconnect()
        except Exception:
            pass


def auto_connect_on_launch_enabled() -> bool:
    """Product policy: never auto-connect."""
    return False


def close_disconnects_tunnel() -> bool:
    """Product policy: closing the window leaves the tunnel running."""
    return False


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
        self.client = RptClient(status_cb=self._on_client_status)

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
        try:
            if ico.is_file():
                self.root.iconbitmap(default=str(ico))
            if png.is_file():
                img = tk.PhotoImage(file=str(png))
                self.root.iconphoto(True, img)
                self._icon_photo = img
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

    def _set_status(self, state: str, *, vpn_ip: str | None = None, detail: str | None = None) -> None:
        self.status_var.set(plain_tunnel_status(state, vpn_ip=vpn_ip, detail=detail))
        if state == "connected":
            self.status_label.configure(fg=STATUS_OK)
            self.detail_var.set("Your internet traffic is going through the private tunnel.")
        elif state == "connecting":
            self.status_label.configure(fg=PRIMARY_DARK)
            self.detail_var.set("Please wait… setting up a secure connection.")
        elif state == "disconnecting":
            self.status_label.configure(fg=PRIMARY_DARK)
            self.detail_var.set("Stopping the tunnel and restoring normal internet…")
        elif state == "error":
            self.status_label.configure(fg=STATUS_ERROR)
            self.detail_var.set(detail or "Check the activity log, then try Connect again.")
        else:
            self.status_label.configure(fg=TEXT)
            self.detail_var.set("Not connected. Press Connect when you want protection.")

    def _apply_control(self, *, connected: bool, busy: bool) -> None:
        self._connected = connected
        self._busy = busy
        if busy and not connected:
            label = "Connecting…"
        elif busy and connected:
            label = "Disconnecting…"
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

    def _on_toggle_connect(self) -> None:
        if self._busy:
            return
        if self._connected:
            self._start_disconnect()
        else:
            self._start_connect()

    def _start_connect(self) -> None:
        self._apply_control(connected=False, busy=True)
        self._set_status("connecting")
        self._log("Connect — starting secure session…")

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
                    tun_res = start_full_tunnel(
                        self.client,
                        result.tunnel_plan,
                        result.session.endpoint.host,
                    )
                    self._tunnel = tun_res
                    # Keep log concise — one line for tunnel outcome
                    if tun_res.ok and tun_res.dataplane and tun_res.dataplane.is_running():
                        residual = getattr(tun_res, "routes_applied", False)
                        self._log(
                            "Tunnel active"
                            + (" — full system protection" if residual else " — session protected")
                        )
                        self._set_status("connected", vpn_ip=vpn_ip)
                        self._apply_control(connected=True, busy=False)
                    elif tun_res.ok:
                        self._log("Tunnel started with limited protection — see details if needed")
                        self._set_status("connected", vpn_ip=vpn_ip)
                        self._apply_control(connected=True, busy=False)
                    else:
                        try:
                            disconnect_full_tunnel(tun_res, self.client)
                        except Exception:
                            pass
                        self._tunnel = None
                        err = tun_res.message or "Tunnel setup failed"
                        self._log(f"Tunnel setup failed: {err[:120]}")
                        self._set_status("error", detail=err)
                        self._apply_control(connected=False, busy=False)
                finally:
                    if self._busy:
                        self._apply_control(connected=self._connected, busy=False)

            self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _start_disconnect(self) -> None:
        self._apply_control(connected=True, busy=True)
        self._set_status("disconnecting")
        self._log("Disconnect — stopping tunnel…")

        def work() -> None:
            try:
                tunnel = self._tunnel
                self._tunnel = None
                disconnect_full_tunnel(tunnel, self.client)
            finally:

                def done() -> None:
                    self._apply_control(connected=False, busy=False)
                    self._set_status("disconnected")
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

    def _on_close_ui_only(self) -> None:
        """Hide UI; keep process + tunnel alive (taskbar). Disconnect is separate.

        Destroying the window would end mainloop and kill residual dual /1 routes
        without rollback — so we iconify instead of destroy.
        """
        try:
            self._log(
                "Window hidden — VPN keeps running if connected. "
                "Restore from the taskbar. Press Disconnect to stop, or Quit to exit."
            )
        except Exception:
            pass
        try:
            self.root.iconify()
        except Exception:
            try:
                self.root.withdraw()
            except Exception:
                pass

    def _quit_app(self) -> None:
        """Explicit quit: stop tunnel then exit process (safe route cleanup)."""
        try:
            self._log("Quit — stopping tunnel and exiting…")
        except Exception:
            pass
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
    """Launch UI with UAC elevation for full-tunnel routes; never auto-connect."""
    if "--rpt-elevated" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--rpt-elevated"]
    # Ignore legacy auto-connect flags — connect is always manual
    if "--rpt-auto-connect" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--rpt-auto-connect"]

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        os.chdir(root)
    except Exception:
        pass

    # Elevate once at launch so Wintun dual /1 can apply; do not auto-connect after.
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
                f"Administrator elevation failed ({reason}). "
                "You can still open the app; full system routes may need UAC."
            )

        app.root.after(100, _note_elev_fail)
    elif status == "already_admin" or is_admin():
        app.root.after(
            100,
            lambda: app._log("Running elevated — full tunnel routes available when you Connect."),
        )

    # Never schedule auto-connect
    assert not auto_connect_on_launch_enabled()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
