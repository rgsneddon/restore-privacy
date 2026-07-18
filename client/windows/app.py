#!/usr/bin/env python3
"""Windows RPT client — rounded dark-blue UI with Connect/Disconnect control.

Tunnel stays up when the window is closed; only the Disconnect button runs full
teardown (dataplane, TUN, routes, session).
"""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont

# Repo root on path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from client.connect import ConnectState, RptClient
from client.ui_theme import (
    APP_TITLE,
    BANNER_TITLE,
    BUTTON_BG,
    BUTTON_BG_ACTIVE,
    BUTTON_FG,
    CHROME_BG,
    SCROLLING_PRIVACY_TEXT,
    STATUS_FG,
    WINDOW_BG,
    WINDOW_FG,
    connect_button_label,
    resolve_logo_png,
)
from client.windows.elevate import (
    elevate_if_needed,
    is_admin,
    should_exit_after_elevation,
)
from client.windows.tunnel_win import start_full_tunnel, stop_full_tunnel


def disconnect_full_tunnel(tunnel, client) -> None:
    """Idempotent full stop: routes/dataplane/TUN/session.

    Used only by the Disconnect button (not window close). Real entry point for tests.
    """
    try:
        stop_full_tunnel(tunnel, client)
    except Exception:
        try:
            if client is not None:
                client.disconnect()
        except Exception:
            pass


class TunnelClientApp:
    """Dark-blue chrome, black log, logo + title, single Connect/Disconnect button."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("560x480")
        self.root.configure(bg=CHROME_BG)
        self.root.minsize(420, 360)
        self._set_window_icon()
        # Close UI only — do NOT tear down tunnel (user controls Disconnect)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_ui_only)

        self._connected = False
        self._busy = False
        self._tunnel = None
        self.client = RptClient(status_cb=self._on_status)

        # Outer chrome (dark blue)
        self.chrome = tk.Frame(self.root, bg=CHROME_BG, padx=14, pady=14)
        self.chrome.pack(fill=tk.BOTH, expand=True)

        # Header: logo + title (high-contrast white)
        header = tk.Frame(self.chrome, bg=CHROME_BG)
        header.pack(fill=tk.X, pady=(0, 10))

        self._logo_photo = None
        logo_path = resolve_logo_png()
        if logo_path is not None:
            try:
                # Prefer PhotoImage; resize via subsample if large
                img = tk.PhotoImage(file=str(logo_path))
                if img.width() > 64:
                    factor = max(1, img.width() // 48)
                    img = img.subsample(factor, factor)
                self._logo_photo = img
                tk.Label(header, image=self._logo_photo, bg=CHROME_BG).pack(
                    side=tk.LEFT, padx=(0, 10)
                )
            except Exception:
                self._logo_photo = None

        title_col = tk.Frame(header, bg=CHROME_BG)
        title_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
        title_font = tkfont.Font(family="Segoe UI", size=16, weight="bold")
        tk.Label(
            title_col,
            text=APP_TITLE,
            bg=CHROME_BG,
            fg=WINDOW_FG,
            font=title_font,
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            title_col,
            text=BANNER_TITLE,
            bg=CHROME_BG,
            fg=STATUS_FG,
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(fill=tk.X)

        # Rounded-looking outer pad around black log (visual radius via padding + border)
        log_shell = tk.Frame(self.chrome, bg="#1E3A8A", padx=3, pady=3)
        log_shell.pack(fill=tk.BOTH, expand=True, pady=(4, 12))
        # Black output window (CLI-style)
        self.output = tk.Text(
            log_shell,
            bg=WINDOW_BG,
            fg=WINDOW_FG,
            insertbackground=WINDOW_FG,
            font=("Consolas", 11),
            relief=tk.FLAT,
            wrap=tk.WORD,
            state=tk.DISABLED,
            highlightthickness=0,
            borderwidth=0,
            padx=10,
            pady=10,
        )
        self.output.pack(fill=tk.BOTH, expand=True)

        # Single Connect / Disconnect control
        self.btn_var = tk.StringVar(value=connect_button_label(False))
        self.connect_btn = tk.Button(
            self.chrome,
            textvariable=self.btn_var,
            command=self._on_toggle_connect,
            bg=BUTTON_BG,
            fg=BUTTON_FG,
            activebackground="#2563EB",
            activeforeground=BUTTON_FG,
            font=("Segoe UI", 13, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=24,
            pady=12,
            bd=0,
            highlightthickness=0,
        )
        self.connect_btn.pack(fill=tk.X, pady=(0, 8))

        self.status_var = tk.StringVar(value="Ready — press Connect to start the tunnel")
        tk.Label(
            self.chrome,
            textvariable=self.status_var,
            bg=CHROME_BG,
            fg=STATUS_FG,
            font=("Consolas", 9),
            anchor="w",
            wraplength=500,
            justify=tk.LEFT,
        ).pack(fill=tk.X)

        self._log(f"{APP_TITLE} tunnel client")
        self._log(SCROLLING_PRIVACY_TEXT)
        self._log("Press Connect to attach to the RPT node (full tunnel when elevated).")
        self._log(
            "Closing this window does not disconnect — use Disconnect to stop the tunnel."
        )
        if not is_admin():
            self._log(
                "Not elevated — full tunnel needs admin (UAC). "
                "Auto-elevate runs on launch when possible."
            )

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

    def _on_status(self, msg: str) -> None:
        def ui() -> None:
            self.status_var.set(msg)
            self._log(msg)

        self.root.after(0, ui)

    def _set_connected_ui(self, connected: bool) -> None:
        self._connected = connected
        self.btn_var.set(connect_button_label(connected))
        self.connect_btn.configure(
            bg=BUTTON_BG_ACTIVE if connected else BUTTON_BG,
            activebackground="#059669" if connected else "#2563EB",
        )

    def _on_toggle_connect(self) -> None:
        if self._busy:
            return
        if self._connected:
            self._start_disconnect()
        else:
            self._start_connect()

    def _start_connect(self) -> None:
        self._busy = True
        self.connect_btn.configure(state=tk.DISABLED)
        self.status_var.set("Connecting…")
        self._log("Connect — starting RPT handshake…")

        def work() -> None:
            result = self.client.connect(timeout=20.0)

            def done() -> None:
                try:
                    if result.ok and result.session and result.tunnel_plan:
                        self._log(f"Session OK — VPN IP {result.session.vpn_ip}")
                        tun_res = start_full_tunnel(
                            self.client,
                            result.tunnel_plan,
                            result.session.endpoint.host,
                        )
                        self._tunnel = tun_res
                        self._log(tun_res.message)
                        if tun_res.dataplane and tun_res.dataplane.is_running():
                            self._log(
                                f"DATA plane active (tun_mode={getattr(tun_res.tun, 'mode', '?')})"
                            )
                        for c in tun_res.applied_commands[:6]:
                            self._log(f"  plan: {c}")
                        if self.client.state == ConnectState.CONNECTED and tun_res.ok:
                            if getattr(tun_res, "routes_applied", False):
                                self.status_var.set(
                                    f"CONNECTED — full tunnel {result.session.vpn_ip}"
                                )
                            else:
                                self.status_var.set(
                                    f"CONNECTED (session {result.session.vpn_ip}) — "
                                    "full-tunnel routes not applied (see log)"
                                )
                            self._set_connected_ui(True)
                        else:
                            self.status_var.set(
                                "Session up but dataplane incomplete — see log"
                            )
                            self._set_connected_ui(
                                self.client.state == ConnectState.CONNECTED
                            )
                    else:
                        self._log(f"ERROR: {result.message}")
                        self.status_var.set("ERROR — see log")
                        self._set_connected_ui(False)
                finally:
                    self._busy = False
                    self.connect_btn.configure(state=tk.NORMAL)

            self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _start_disconnect(self) -> None:
        """Explicit Disconnect — full tunnel stop (routes, TUN, dataplane, session)."""
        self._busy = True
        self.connect_btn.configure(state=tk.DISABLED)
        self.status_var.set("Disconnecting…")
        self._log("Disconnect — tearing down tunnel…")

        def work() -> None:
            try:
                self._disconnect_tunnel()
            finally:

                def done() -> None:
                    self._set_connected_ui(False)
                    self.status_var.set("Disconnected — press Connect to reconnect")
                    self._log("Disconnected.")
                    self._busy = False
                    self.connect_btn.configure(state=tk.NORMAL)

                self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _disconnect_tunnel(self) -> None:
        """Idempotent full stop used only by Disconnect button (not window close)."""
        tunnel = self._tunnel
        self._tunnel = None
        disconnect_full_tunnel(tunnel, self.client)

    def _on_close_ui_only(self) -> None:
        """WM_DELETE_WINDOW — close the UI without stopping the VPN."""
        try:
            self._log("Window closed — tunnel left running (use Disconnect to stop).")
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self) -> None:
        self.root.mainloop()


# Back-compat name for imports/tests
RetroClientApp = TunnelClientApp


def main() -> int:
    """Launch UI; auto-request UAC so full tunnel can apply routes when Connect is used."""
    if "--rpt-elevated" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--rpt-elevated"]

    # Ensure repo root is on path for elevated re-launch / odd cwd
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        os.chdir(root)
    except Exception:
        pass

    status = elevate_if_needed()
    if should_exit_after_elevation(status):
        # Elevated child should be starting (UAC). If it does not appear, run:
        #   set RPT_NO_AUTO_ELEVATE=1 && python -m client.windows
        return 0

    try:
        app = TunnelClientApp()
    except Exception as exc:
        # Visible failure when GUI cannot start (e.g. no display)
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                f"Restore Privacy failed to open:\n{exc}",
                "RESTORE PRIVACY",
                0x10,
            )
        except Exception:
            print(f"Restore Privacy failed to open: {exc}", file=sys.stderr)
        return 1

    if status.startswith("failed:"):
        reason = status.split(":", 1)[-1]
        app.root.after(
            100,
            lambda: app._log(
                f"Auto-elevation failed ({reason}). "
                "Full tunnel needs Administrator — approve UAC or run elevated. "
                "UI is still open so you can try Connect."
            ),
        )
    elif status == "already_admin":
        app.root.after(
            100, lambda: app._log("Running elevated — full tunnel available.")
        )
    elif status == "skipped":
        app.root.after(
            100,
            lambda: app._log(
                "Running without auto-elevate (RPT_NO_AUTO_ELEVATE). "
                "Connect still works for handshake; full-tunnel routes need admin."
            ),
        )
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
