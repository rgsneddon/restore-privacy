#!/usr/bin/env python3
"""Windows RPT client — dark-blue UI with always-visible Connect/Disconnect.

Tunnel stays up when the window is closed; only Disconnect runs full teardown.
Connect works without Administrator: RPT session + dataplane start for all users;
system-wide dual-/1 routes apply only when elevated (best-effort).
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
from client.windows.elevate import is_admin
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


def layout_pack_bottom_controls_first() -> bool:
    """Policy flag for tests: bottom Connect bar is packed before expanding log."""
    return True


def non_admin_connect_allowed() -> bool:
    """Connect must not require elevation (session starts without Run as admin)."""
    return True


class TunnelClientApp:
    """Dark-blue chrome, black log, logo + title, always-visible Connect/Disconnect."""

    DEFAULT_GEOMETRY = "560x520"
    MIN_WIDTH = 400
    MIN_HEIGHT = 420

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry(self.DEFAULT_GEOMETRY)
        self.root.configure(bg=CHROME_BG)
        self.root.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self._set_window_icon()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_ui_only)

        self._connected = False
        self._busy = False
        self._tunnel = None
        self.client = RptClient(status_cb=self._on_status)

        # Outer chrome
        self.chrome = tk.Frame(self.root, bg=CHROME_BG, padx=14, pady=14)
        self.chrome.pack(fill=tk.BOTH, expand=True)

        # --- BOTTOM controls FIRST so expand=True log never hides them ---
        self.bottom = tk.Frame(self.chrome, bg=CHROME_BG)
        self.bottom.pack(side=tk.BOTTOM, fill=tk.X)

        self.btn_var = tk.StringVar(value=connect_button_label(False))
        self.connect_btn = tk.Button(
            self.bottom,
            textvariable=self.btn_var,
            command=self._on_toggle_connect,
            bg=BUTTON_BG,
            fg=BUTTON_FG,
            activebackground="#2563EB",
            activeforeground=BUTTON_FG,
            disabledforeground="#CCCCCC",
            font=("Segoe UI", 14, "bold"),
            relief=tk.RAISED,
            cursor="hand2",
            padx=20,
            pady=14,
            bd=2,
            highlightthickness=2,
            highlightbackground="#93C5FD",
            highlightcolor="#FFFFFF",
        )
        self.connect_btn.pack(side=tk.TOP, fill=tk.X, pady=(8, 6), ipady=4)

        self.status_var = tk.StringVar(value="Ready — press Connect to start the tunnel")
        self.status_label = tk.Label(
            self.bottom,
            textvariable=self.status_var,
            bg=CHROME_BG,
            fg=STATUS_FG,
            font=("Consolas", 9),
            anchor="w",
            wraplength=500,
            justify=tk.LEFT,
        )
        self.status_label.pack(side=tk.TOP, fill=tk.X)

        # --- TOP header ---
        self.header = tk.Frame(self.chrome, bg=CHROME_BG)
        self.header.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))

        self._logo_photo = None
        logo_path = resolve_logo_png()
        if logo_path is not None:
            try:
                img = tk.PhotoImage(file=str(logo_path))
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

        # --- MIDDLE log (fills remaining space only) ---
        self.log_shell = tk.Frame(self.chrome, bg="#1E3A8A", padx=3, pady=3)
        self.log_shell.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 4))
        self.output = tk.Text(
            self.log_shell,
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
            height=8,
        )
        self.output.pack(fill=tk.BOTH, expand=True)

        self._log(f"{APP_TITLE} tunnel client")
        self._log(SCROLLING_PRIVACY_TEXT)
        self._log("Press Connect to attach to the RPT node — no Administrator required.")
        self._log(
            "Closing this window does not disconnect — use Disconnect to stop the tunnel."
        )
        if is_admin():
            self._log("Running elevated — full-system routes available when Connect succeeds.")
        else:
            self._log(
                "Running as standard user — VPN session starts without admin; "
                "system-wide catch-all routes apply only if elevated."
            )

    def connect_button_visible(self) -> bool:
        """True when the Connect control is mapped (for tests / probes)."""
        try:
            return bool(self.connect_btn.winfo_ismapped() or self.connect_btn.winfo_viewable())
        except Exception:
            return False

    def connect_button_text(self) -> str:
        return self.btn_var.get()

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
        self._log("Connect — starting RPT handshake (no admin required)…")

        def work() -> None:
            result = self.client.connect(timeout=20.0)

            def done() -> None:
                try:
                    if result.ok and result.session and result.tunnel_plan:
                        self._log(f"Session OK — VPN IP {result.session.vpn_ip}")
                        # Prefer system Wintun when possible; falls back without admin
                        tun_res = start_full_tunnel(
                            self.client,
                            result.tunnel_plan,
                            result.session.endpoint.host,
                            prefer_system_capture=True,
                        )
                        self._tunnel = tun_res
                        self._log(tun_res.message)
                        if tun_res.dataplane and tun_res.dataplane.is_running():
                            self._log(
                                f"DATA plane active (tun_mode={getattr(tun_res.tun, 'mode', '?')})"
                            )
                        for c in (tun_res.applied_commands or [])[:6]:
                            self._log(f"  plan: {c}")

                        # Session success is enough for Connect — admin only for full routes
                        if self.client.state == ConnectState.CONNECTED:
                            if tun_res.ok and getattr(tun_res, "routes_applied", False):
                                self.status_var.set(
                                    f"CONNECTED — full tunnel {result.session.vpn_ip}"
                                )
                            elif tun_res.ok:
                                self.status_var.set(
                                    f"CONNECTED — session {result.session.vpn_ip} "
                                    "(dataplane up; system routes need admin if desired)"
                                )
                            else:
                                self.status_var.set(
                                    f"CONNECTED — session {result.session.vpn_ip} "
                                    f"(tunnel adapter: {tun_res.message[:80]})"
                                )
                            self._set_connected_ui(True)
                        else:
                            self.status_var.set("Session incomplete — see log")
                            self._set_connected_ui(False)
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
        """Explicit Disconnect — full tunnel stop."""
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
        tunnel = self._tunnel
        self._tunnel = None
        disconnect_full_tunnel(tunnel, self.client)

    def _on_close_ui_only(self) -> None:
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


RetroClientApp = TunnelClientApp


def main() -> int:
    """Launch UI without requiring Run as administrator.

    Auto-elevate is opt-in via RPT_AUTO_ELEVATE=1 (for users who want system routes).
    Connect always works for the RPT session as a standard user.
    """
    if "--rpt-elevated" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--rpt-elevated"]

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        os.chdir(root)
    except Exception:
        pass

    # Default: do NOT force UAC — Connect must work without admin.
    # Set RPT_AUTO_ELEVATE=1 to opt into ShellExecute runas for full-system routes.
    status = "skipped"
    if os.environ.get("RPT_AUTO_ELEVATE", "").strip().lower() in ("1", "true", "yes"):
        from client.windows.elevate import elevate_if_needed, should_exit_after_elevation

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
                f"Optional elevation failed ({reason}). "
                "Connect still works without admin for the RPT session."
            ),
        )
    elif status == "already_admin":
        app.root.after(
            100, lambda: app._log("Running elevated — full-system routes available.")
        )

    # Ensure button is drawn after first layout
    def _ensure_btn() -> None:
        try:
            app.connect_btn.lift()
            app.bottom.lift()
        except Exception:
            pass

    app.root.after(50, _ensure_btn)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
