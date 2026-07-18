#!/usr/bin/env python3
"""Windows RPT client — Win 3.1 retro CLI window, auto-connect on launch."""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from pathlib import Path

# Repo root on path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from client.connect import ConnectState, RptClient
from client.ui_theme import (
    APP_TITLE,
    BANNER_BG,
    BANNER_FG,
    BANNER_TITLE,
    SCROLLING_PRIVACY_TEXT,
    STATUS_FG,
    WINDOW_BG,
    WINDOW_FG,
)
from client.windows.elevate import (
    elevate_if_needed,
    is_admin,
    should_exit_after_elevation,
)
from client.windows.tunnel_win import start_full_tunnel, stop_full_tunnel


class RetroClientApp:
    """CLI-style window: dark blue banner, black bg, white text, scrolling privacy line."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("640x360")
        self.root.configure(bg=WINDOW_BG)
        self.root.minsize(480, 280)
        self._set_window_icon()
        # Full tunnel teardown on window close (X) so traffic reverts to device IP
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Dark blue top banner (Windows 3.1-ish title bar)
        self.banner = tk.Frame(self.root, bg=BANNER_BG, height=28)
        self.banner.pack(fill=tk.X, side=tk.TOP)
        self.banner.pack_propagate(False)
        self.banner_label = tk.Label(
            self.banner,
            text=BANNER_TITLE,
            bg=BANNER_BG,
            fg=BANNER_FG,
            font=("MS Sans Serif", 10, "bold"),
            anchor="w",
            padx=8,
        )
        self.banner_label.pack(fill=tk.BOTH, expand=True)

        # Scrolling privacy text strip
        self.scroll_frame = tk.Frame(self.root, bg=WINDOW_BG, height=22)
        self.scroll_frame.pack(fill=tk.X)
        self.scroll_frame.pack_propagate(False)
        self.scroll_label = tk.Label(
            self.scroll_frame,
            text=SCROLLING_PRIVACY_TEXT,
            bg=WINDOW_BG,
            fg=WINDOW_FG,
            font=("Consolas", 10),
            anchor="w",
        )
        self.scroll_label.place(x=0, y=2)
        self._scroll_x = 640
        self._scroll_text = SCROLLING_PRIVACY_TEXT + "   ·   "

        # Main CLI output area
        self.output = tk.Text(
            self.root,
            bg=WINDOW_BG,
            fg=WINDOW_FG,
            insertbackground=WINDOW_FG,
            font=("Consolas", 11),
            relief=tk.FLAT,
            wrap=tk.WORD,
            state=tk.DISABLED,
        )
        self.output.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.status_var = tk.StringVar(value="Launching…")
        self.status = tk.Label(
            self.root,
            textvariable=self.status_var,
            bg=WINDOW_BG,
            fg=STATUS_FG,
            font=("Consolas", 9),
            anchor="w",
            padx=8,
            pady=4,
        )
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

        self.client = RptClient(status_cb=self._on_status)
        self._tunnel = None
        self._animate_scroll()
        # Auto-connect on launch — primary flow (no Connect button required)
        self.root.after(200, self._auto_connect)

    def _set_window_icon(self) -> None:
        """Use brand app icon (assets/brand → native/app_icon.*) when present."""
        native = Path(__file__).resolve().parent / "native"
        ico = native / "app_icon.ico"
        png = native / "app_icon.png"
        try:
            if ico.is_file():
                self.root.iconbitmap(default=str(ico))
            if png.is_file():
                # iconphoto works well on Windows for taskbar/title bar
                img = tk.PhotoImage(file=str(png))
                self.root.iconphoto(True, img)
                self._icon_photo = img  # keep ref
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

    def _animate_scroll(self) -> None:
        self._scroll_x -= 2
        full = self._scroll_text * 3
        self.scroll_label.configure(text=full)
        self.scroll_label.place(x=self._scroll_x, y=2)
        if self._scroll_x < -len(self._scroll_text) * 7:
            self._scroll_x = self.root.winfo_width() or 640
        self.root.after(40, self._animate_scroll)

    def _auto_connect(self) -> None:
        self._log("RESTORE PRIVACY tunnel client")
        self._log(SCROLLING_PRIVACY_TEXT)
        self._log("Auto-connect on launch…")
        if not is_admin():
            self._log(
                "Not elevated — full tunnel needs admin. "
                "If no UAC prompt appeared, set shortcut to Run as administrator "
                "or allow elevation (auto-elevate runs on launch)."
            )

        def work() -> None:
            result = self.client.auto_connect_on_launch()

            def done() -> None:
                if result.ok and result.session and result.tunnel_plan:
                    self._log(f"Session OK — VPN IP {result.session.vpn_ip}")
                    # Create TUN + start sealed RPT DATA plane (seal/open on real session)
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
                    else:
                        self.status_var.set("CONNECTED (session) — check dataplane log")
                else:
                    self._log(f"ERROR: {result.message}")
                    self.status_var.set("ERROR — see log")

            self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _teardown_tunnel(self) -> None:
        """Stop dataplane, close TUN, delete full-tunnel routes, end session.

        Idempotent: safe when never connected or already torn down.
        """
        tunnel = self._tunnel
        self._tunnel = None
        try:
            stop_full_tunnel(tunnel, self.client)
        except Exception:
            # Never block exit on teardown errors
            try:
                self.client.disconnect()
            except Exception:
                pass

    def _on_close(self) -> None:
        """WM_DELETE_WINDOW — full disconnect before destroying the UI."""
        try:
            self._log("Closing — tearing down VPN tunnel…")
        except Exception:
            pass
        self._teardown_tunnel()
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self) -> None:
        try:
            self.root.mainloop()
        finally:
            # Ensure teardown if mainloop ends without WM_DELETE_WINDOW
            self._teardown_tunnel()


def main() -> int:
    """Launch UI; auto-request UAC so users need not right-click Run as admin."""
    # Strip internal elevation marker from argv so it does not affect logic
    if "--rpt-elevated" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--rpt-elevated"]

    status = elevate_if_needed()
    if should_exit_after_elevation(status):
        # Elevated child is starting; exit this non-admin instance
        return 0
    if status.startswith("failed:"):
        # Continue anyway so handshake still works; log will explain routes
        pass

    app = RetroClientApp()
    if status.startswith("failed:"):
        reason = status.split(":", 1)[-1]
        app.root.after(
            100,
            lambda: app._log(
                f"Auto-elevation failed ({reason}). "
                "Full tunnel needs Administrator — approve UAC or run elevated."
            ),
        )
    elif status == "already_admin":
        app.root.after(100, lambda: app._log("Running elevated — full tunnel available."))
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
