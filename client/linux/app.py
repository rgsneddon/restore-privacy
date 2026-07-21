#!/usr/bin/env python3
"""Ubuntu-family RPT client (Ubuntu LTS, Mint, Pop!_OS, …) — Connect/Disconnect Tk UI.

Residual public IP uses the VPN node only with root + TUN + dual /1 routes.
Close does not disconnect (user presses Disconnect or Quit).

Support floor: Ubuntu 20.04 LTS (Python 3.8+) and newer.
"""

from __future__ import annotations

import os
import sys
import threading
import webbrowser
import tkinter as tk
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from client.linux.ubuntu_compat import (  # noqa: E402
    python_meets_minimum,
    python_version_error_message,
    support_summary,
)

from client.connect import RptClient
from client.ui_theme import (
    APP_TITLE,
    BANNER_TITLE,
    BUTTON_CONNECT_BG,
    BUTTON_DISCONNECT_BG,
    BUTTON_FG,
    CHROME_BG,
    DISABLED_FG,
    PANEL_PAD,
    PRIMARY,
    PRIMARY_DARK,
    SCROLLING_PRIVACY_TEXT,
    STATUS_ERROR_FG,
    STATUS_OK,
    TEXT,
    TEXT_MUTED,
    WHITE,
    connect_button_label,
    plain_tunnel_status,
    resolve_logo_png,
    upgrade_banner_text,
    upgrade_download_url,
    catalog_latest_version,
    read_running_version,
)
from client.linux.elevate import (
    elevate_if_needed,
    is_root,
    should_exit_after_elevation,
)
from client.linux.tunnel_linux import (
    product_connect_requires_root,
    ipv6_residual_protected,
    residual_ip_capture_active,
    start_full_tunnel,
    stop_full_tunnel,
)
from client.licence_gate import (
    LICENCE_ACCEPT_BUTTON,
    LICENCE_PROMPT_TITLE,
    accept_licence,
    assert_may_connect,
    has_accepted_licence,
    licence_url,
    short_licence_summary,
)
from client.registration_copy import (
    ANON_REGISTRATION_SUMMARY,
    OS_PRIVILEGE_HONESTY,
    SEAMLESS_HINT,
    SEAMLESS_TAGLINE,
)
from client.transparency_copy import (
    CONNECTION_LOG_DISCLAIMER,
    CONNECTION_LOG_TITLE,
    DPI_MITIGATION_DISCLAIMER,
    DPI_MITIGATION_TITLE,
    LEAK_TEST_BUTTON,
    LEAK_TEST_DISCLAIMER,
    LEAK_TEST_TITLE,
)
from client.connection_log import (
    KIND_CONNECT,
    KIND_DISCONNECT,
    KIND_ERROR,
    KIND_SESSION,
    append_event,
    format_export,
    read_events,
)
from client.leak_test import run_product_leak_test


def disconnect_full_tunnel(tunnel, client, *, preserve_message: bool = False) -> None:
    try:
        stop_full_tunnel(tunnel, client, preserve_message=preserve_message)
    except Exception:
        try:
            if client is not None:
                client.disconnect()
        except Exception:
            pass


def attach_failure_user_message(original: str | None) -> str:
    msg = (original or "").strip() or "Tunnel setup failed"
    low = msg.lower()
    if "full teardown complete" in low or low.startswith("tunnel stopped"):
        return "Tunnel setup failed"
    return msg


def close_disconnects_tunnel() -> bool:
    return False


class TunnelClientApp:
    """Manual Connect/Disconnect shell for Linux (Ubuntu-family residual path).

    Licence acceptance is required before Connect (parity with Windows/Android).
    Handshake + TUN attach run off the Tk UI thread.
    """

    DEFAULT_GEOMETRY = "520x520"
    MIN_WIDTH = 400
    MIN_HEIGHT = 420

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"{APP_TITLE} (Linux)")
        self.root.geometry(self.DEFAULT_GEOMETRY)
        self.root.configure(bg=CHROME_BG)
        self.root.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_ui_only)

        self._connected = False
        self._busy = False
        self._tunnel = None
        self.client = RptClient(status_cb=self._on_client_status)

        self.chrome = tk.Frame(
            self.root, bg=CHROME_BG, padx=PANEL_PAD + 4, pady=PANEL_PAD + 4
        )
        self.chrome.pack(fill=tk.BOTH, expand=True)

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
            font=("DejaVu Sans", 13, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            padx=20,
            pady=14,
        )
        self.connect_btn.pack(fill=tk.X, pady=(8, 4))

        quit_row = tk.Frame(self.bottom, bg=CHROME_BG)
        quit_row.pack(fill=tk.X)
        tk.Button(
            quit_row,
            text="Settings",
            command=self._open_settings,
            bg=CHROME_BG,
            fg=PRIMARY_DARK,
            relief=tk.FLAT,
            font=("DejaVu Sans", 9, "bold"),
        ).pack(side=tk.LEFT)
        tk.Button(
            quit_row,
            text="Quit",
            command=self._quit_app,
            bg=CHROME_BG,
            fg=TEXT_MUTED,
            relief=tk.FLAT,
            font=("DejaVu Sans", 9),
        ).pack(side=tk.RIGHT)

        top = tk.Frame(self.chrome, bg=CHROME_BG)
        top.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        banner = tk.Frame(top, bg=PRIMARY_DARK, padx=12, pady=10)
        banner.pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            banner,
            text=BANNER_TITLE + " - Ubuntu / Linux",
            bg=PRIMARY_DARK,
            fg=WHITE,
            font=("DejaVu Sans", 12, "bold"),
        ).pack(anchor="w")
        tk.Label(
            banner,
            text=SEAMLESS_TAGLINE,
            bg=PRIMARY_DARK,
            fg=WHITE,
            font=("DejaVu Sans", 8, "bold"),
        ).pack(anchor="w", pady=(2, 0))
        tk.Label(
            banner,
            text=SCROLLING_PRIVACY_TEXT,
            bg=PRIMARY_DARK,
            fg=WHITE,
            font=("DejaVu Sans", 8),
            wraplength=460,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(4, 0))

        self.status_var = tk.StringVar(
            value=plain_tunnel_status("disconnected")
        )
        self.detail_var = tk.StringVar(
            value=(
                "Accept the licence, then press Connect for residual protection."
                if not has_accepted_licence()
                else "Not connected. Press Connect when you want protection."
            )
        )
        status_card = tk.Frame(top, bg=WHITE, padx=12, pady=10)
        status_card.pack(fill=tk.X, pady=(0, 8))
        self.status_label = tk.Label(
            status_card,
            textvariable=self.status_var,
            bg=WHITE,
            fg=TEXT,
            font=("DejaVu Sans", 11, "bold"),
            anchor="w",
        )
        self.status_label.pack(fill=tk.X)
        badge_row = tk.Frame(status_card, bg=WHITE)
        badge_row.pack(fill=tk.X, pady=(2, 0))
        self._licence_badge_var = tk.StringVar(
            value="Licence accepted" if has_accepted_licence() else "Licence required"
        )
        self._licence_badge = tk.Label(
            badge_row,
            textvariable=self._licence_badge_var,
            bg="#E8F5E9" if has_accepted_licence() else "#FDECEC",
            fg=PRIMARY_DARK if has_accepted_licence() else STATUS_ERROR_FG,
            font=("DejaVu Sans", 8, "bold"),
            padx=6,
            pady=2,
        )
        self._licence_badge.pack(side=tk.RIGHT)
        tk.Label(
            status_card,
            textvariable=self.detail_var,
            bg=WHITE,
            fg=TEXT_MUTED,
            font=("DejaVu Sans", 9),
            anchor="w",
            wraplength=460,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(4, 0))
        self._licence_cta = tk.Frame(status_card, bg=WHITE)
        tk.Button(
            self._licence_cta,
            text=LICENCE_ACCEPT_BUTTON,
            command=self._show_licence_prompt,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
            font=("DejaVu Sans", 9, "bold"),
            padx=10,
            pady=4,
        ).pack(anchor="w", pady=(6, 0))
        if not has_accepted_licence():
            self._licence_cta.pack(fill=tk.X)

        # Optional upgrade banner
        try:
            msg = upgrade_banner_text(
                read_running_version(), catalog_latest_version()
            )
        except Exception:
            msg = None
        if msg:
            up = tk.Frame(top, bg="#FFF3CD", padx=8, pady=6)
            up.pack(fill=tk.X, pady=(0, 6))
            tk.Label(up, text=msg, bg="#FFF3CD", fg=TEXT, font=("DejaVu Sans", 8)).pack(
                side=tk.LEFT
            )
            tk.Button(
                up,
                text="Get update",
                command=self._open_upgrade,
                relief=tk.FLAT,
                bg="#FFF3CD",
            ).pack(side=tk.RIGHT)

        log_frame = tk.Frame(top, bg=CHROME_BG)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.output = tk.Text(
            log_frame,
            height=10,
            bg="#1e1e1e",
            fg="#d4d4d4",
            font=("DejaVu Sans Mono", 8),
            state=tk.DISABLED,
            wrap=tk.WORD,
        )
        self.output.pack(fill=tk.BOTH, expand=True)
        self._log(f"Linux client ready. {support_summary()}")
        self._log(SEAMLESS_HINT)
        if is_root():
            self._log("Running as root - Connect can set residual routes.")
        else:
            self._log(
                "Not root - Connect will request elevation (pkexec/sudo) for full tunnel."
            )
        if not has_accepted_licence():
            self._log("Accept the end-user licence before Connect.")
            self.root.after(200, self._show_licence_prompt)

    def connect_button_text(self) -> str:
        return self.btn_var.get()

    def _log(self, line: str) -> None:
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, line + "\n")
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)

    def _on_client_status(self, msg: str) -> None:
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
        elif s == "connected":
            self.status_label.configure(fg=STATUS_ERROR_FG)
            self.detail_var.set(
                "Session up but residual public IP still uses your ISP - not fully protected."
            )
        elif s == "connecting":
            self.status_label.configure(fg=PRIMARY_DARK)
            self.detail_var.set("Please wait... setting up a secure connection.")
        elif s == "disconnecting":
            self.status_label.configure(fg=PRIMARY_DARK)
            self.detail_var.set("Stopping the tunnel and restoring normal internet...")
        elif s in ("error", "failed"):
            self.status_label.configure(fg=STATUS_ERROR_FG)
            self.detail_var.set(
                detail or "Check the activity log, then try Connect again."
            )
        else:
            self.status_label.configure(fg=TEXT)
            self.detail_var.set("Not connected. Press Connect when you want protection.")

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

    def _on_toggle_connect(self) -> None:
        if self._busy:
            return
        if self._connected:
            self._start_disconnect()
        else:
            self._start_connect()

    def _refresh_licence_badge(self) -> None:
        ok = has_accepted_licence()
        self._licence_badge_var.set("Licence accepted" if ok else "Licence required")
        try:
            self._licence_badge.configure(
                bg="#E8F5E9" if ok else "#FDECEC",
                fg=PRIMARY_DARK if ok else STATUS_ERROR_FG,
            )
        except Exception:
            pass
        try:
            if ok:
                self._licence_cta.pack_forget()
            else:
                self._licence_cta.pack(fill=tk.X)
        except Exception:
            pass

    def _show_licence_prompt(self) -> None:
        win = tk.Toplevel(self.root)
        win.title(LICENCE_PROMPT_TITLE)
        win.configure(bg=CHROME_BG)
        win.transient(self.root)
        win.grab_set()
        frm = tk.Frame(win, bg=WHITE, padx=14, pady=12)
        frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        tk.Label(
            frm,
            text=LICENCE_PROMPT_TITLE,
            bg=WHITE,
            fg=PRIMARY_DARK,
            font=("DejaVu Sans", 12, "bold"),
        ).pack(anchor="w")
        tk.Label(
            frm,
            text=short_licence_summary(),
            bg=WHITE,
            fg=TEXT,
            font=("DejaVu Sans", 9),
            wraplength=420,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(8, 4))
        tk.Label(
            frm,
            text=ANON_REGISTRATION_SUMMARY,
            bg=WHITE,
            fg=TEXT_MUTED,
            font=("DejaVu Sans", 8),
            wraplength=420,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(4, 2))
        tk.Label(
            frm,
            text=OS_PRIVILEGE_HONESTY,
            bg=WHITE,
            fg=TEXT_MUTED,
            font=("DejaVu Sans", 8),
            wraplength=420,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(2, 8))

        def open_lic() -> None:
            try:
                webbrowser.open(licence_url())
            except Exception as exc:
                self._log(f"Could not open licence: {exc}")

        tk.Button(
            frm,
            text="View full end-user licence (LICENSE)",
            command=open_lic,
            relief=tk.FLAT,
            bg=WHITE,
            fg=PRIMARY,
            font=("DejaVu Sans", 8, "underline"),
            cursor="hand2",
        ).pack(anchor="w")

        def do_accept() -> None:
            accept_licence()
            append_event("settings", "End-user licence accepted")
            self._refresh_licence_badge()
            self.detail_var.set(
                "Licence accepted. Press Connect when you want protection."
            )
            self._log("Licence accepted (stored locally only).")
            try:
                win.destroy()
            except Exception:
                pass

        row = tk.Frame(frm, bg=WHITE)
        row.pack(fill=tk.X, pady=(12, 0))
        tk.Button(
            row,
            text=LICENCE_ACCEPT_BUTTON,
            command=do_accept,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
            font=("DejaVu Sans", 10, "bold"),
            padx=12,
            pady=6,
        ).pack(side=tk.LEFT)
        tk.Button(
            row,
            text="Not now",
            command=win.destroy,
            bg=WHITE,
            fg=TEXT_MUTED,
            relief=tk.FLAT,
        ).pack(side=tk.LEFT, padx=(10, 0))

    def _open_settings(self) -> None:
        """Settings: licence, local connection log, leak test, DPI honesty."""
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.configure(bg=CHROME_BG)
        win.geometry("480x520")
        frm = tk.Frame(win, bg=WHITE, padx=12, pady=10)
        frm.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        tk.Label(
            frm,
            text="Settings",
            bg=WHITE,
            fg=PRIMARY_DARK,
            font=("DejaVu Sans", 12, "bold"),
        ).pack(anchor="w")
        tk.Label(
            frm,
            text=LICENCE_PROMPT_TITLE
            + (": accepted" if has_accepted_licence() else ": required before Connect"),
            bg=WHITE,
            fg=TEXT,
            font=("DejaVu Sans", 9),
        ).pack(anchor="w", pady=(8, 2))
        tk.Button(
            frm,
            text=LICENCE_ACCEPT_BUTTON if not has_accepted_licence() else "Review licence",
            command=lambda: (win.destroy(), self._show_licence_prompt()),
            bg=PRIMARY if not has_accepted_licence() else CHROME_BG,
            fg=WHITE if not has_accepted_licence() else PRIMARY_DARK,
            relief=tk.FLAT,
        ).pack(anchor="w", pady=(0, 8))

        tk.Label(
            frm,
            text=CONNECTION_LOG_TITLE,
            bg=WHITE,
            fg=PRIMARY_DARK,
            font=("DejaVu Sans", 10, "bold"),
        ).pack(anchor="w", pady=(6, 2))
        tk.Label(
            frm,
            text=CONNECTION_LOG_DISCLAIMER,
            bg=WHITE,
            fg=TEXT_MUTED,
            font=("DejaVu Sans", 8),
            wraplength=440,
            justify=tk.LEFT,
        ).pack(anchor="w")
        log_box = tk.Text(
            frm,
            height=8,
            bg="#1e1e1e",
            fg="#d4d4d4",
            font=("DejaVu Sans Mono", 8),
            wrap=tk.WORD,
        )
        log_box.pack(fill=tk.BOTH, expand=True, pady=(4, 4))
        try:
            events = read_events(limit=40)
            log_box.insert(tk.END, format_export(events) if events else "(no local events yet)\n")
        except Exception as exc:
            log_box.insert(tk.END, f"(could not read log: {exc})\n")
        log_box.configure(state=tk.DISABLED)

        tk.Label(
            frm,
            text=LEAK_TEST_TITLE,
            bg=WHITE,
            fg=PRIMARY_DARK,
            font=("DejaVu Sans", 10, "bold"),
        ).pack(anchor="w", pady=(8, 2))
        tk.Label(
            frm,
            text=LEAK_TEST_DISCLAIMER,
            bg=WHITE,
            fg=TEXT_MUTED,
            font=("DejaVu Sans", 8),
            wraplength=440,
            justify=tk.LEFT,
        ).pack(anchor="w")
        leak_var = tk.StringVar(value="")
        tk.Label(frm, textvariable=leak_var, bg=WHITE, fg=TEXT, font=("DejaVu Sans", 8), wraplength=440, justify=tk.LEFT).pack(anchor="w")

        def run_leak() -> None:
            leak_var.set("Running leak test…")
            win.update_idletasks()

            def work() -> None:
                try:
                    res = run_product_leak_test(
                        residual_capture_active=residual_ip_capture_active(self._tunnel)
                        if self._tunnel
                        else False,
                        ipv6_protected=ipv6_residual_protected(self._tunnel)
                        if self._tunnel
                        else False,
                    )
                    msg = getattr(res, "summary", None) or str(res)
                except Exception as exc:
                    msg = f"Leak test error: {exc}"

                def done() -> None:
                    leak_var.set(msg[:400])
                    append_event(KIND_CONNECT if "PASS" in msg else KIND_ERROR, f"Leak test: {msg[:120]}")

                self.root.after(0, done)

            threading.Thread(target=work, daemon=True).start()

        tk.Button(
            frm,
            text=LEAK_TEST_BUTTON,
            command=run_leak,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
        ).pack(anchor="w", pady=(4, 8))

        tk.Label(
            frm,
            text=DPI_MITIGATION_TITLE,
            bg=WHITE,
            fg=PRIMARY_DARK,
            font=("DejaVu Sans", 10, "bold"),
        ).pack(anchor="w", pady=(4, 2))
        tk.Label(
            frm,
            text=DPI_MITIGATION_DISCLAIMER,
            bg=WHITE,
            fg=TEXT_MUTED,
            font=("DejaVu Sans", 8),
            wraplength=440,
            justify=tk.LEFT,
        ).pack(anchor="w")

    def _start_connect(self) -> None:
        ok_lic, lic_msg = assert_may_connect()
        if not ok_lic:
            self._log(lic_msg)
            self._set_status("error", detail=lic_msg)
            self.detail_var.set(lic_msg)
            self._show_licence_prompt()
            return

        if product_connect_requires_root() and not is_root():
            self._apply_control(connected=False, busy=True)
            self._set_status("connecting")
            self._log(
                "Connect - root required so residual public IP uses the VPN node. "
                "Approving elevation will re-open and finish Connect..."
            )
            status = elevate_if_needed(extra_args=["--rpt-auto-connect"])
            if should_exit_after_elevation(status):
                try:
                    self.root.destroy()
                except Exception:
                    pass
                return
            reason = status.split(":", 1)[-1] if status.startswith("failed:") else status
            err = (
                "Root required so your residual public IP uses the VPN node. "
                f"Run with sudo/pkexec ({reason})."
            )
            self._log(f"Could not connect: {err}")
            self._set_status("error", detail=err)
            self._apply_control(connected=False, busy=False)
            return

        self._apply_control(connected=False, busy=True)
        self._set_status("connecting")
        self._log("Connect - starting secure session (full-tunnel residual path)...")
        append_event(KIND_CONNECT, "Connect started (full-tunnel residual path)")

        def work() -> None:
            # Handshake + residual TUN/routes off the Tk UI thread.
            # Flyclient-style: tip residual state + prefetch default route during HELLO.
            from concurrent.futures import ThreadPoolExecutor

            from client.linux.tunnel_linux import resolve_default_route

            prior = self._tunnel
            residual_ready = residual_ip_capture_active(prior)
            with ThreadPoolExecutor(max_workers=1) as pool:
                route_fut = pool.submit(resolve_default_route)
                result = self.client.connect(
                    timeout=20.0,
                    residual_ready=residual_ready,
                )
                try:
                    prefetched_route = route_fut.result(timeout=8)
                except Exception:
                    prefetched_route = (None, None)

            if not (result.ok and result.session and result.tunnel_plan):
                msg = result.message or "Connection failed"

                def fail_hs() -> None:
                    self._log(f"Could not connect: {msg}")
                    append_event(KIND_ERROR, f"Connect failed: {msg}")
                    self._set_status("error", detail=msg)
                    self._apply_control(connected=False, busy=False)

                self.root.after(0, fail_hs)
                return

            vpn_ip = result.session.vpn_ip

            def note_session() -> None:
                self._log(f"Session ready (tunnel address {vpn_ip})")
                append_event(KIND_SESSION, f"Session ready (tunnel address {vpn_ip})")
                if residual_ready:
                    self._log("Flyclient tip: residual already active — fast path…")
                else:
                    self._log("Attaching residual tunnel (TUN + dual /1 routes)…")

            self.root.after(0, note_session)

            plan = result.tunnel_plan
            plan.tunnel_iface = "rpt0"
            try:
                tun_res = start_full_tunnel(
                    self.client,
                    plan,
                    result.session.endpoint.host,
                    require_system_capture=True,
                    prior=prior if residual_ready else None,
                    prefetched_default_route=prefetched_route,
                )
            except Exception as exc:
                err = f"Tunnel attach error: {exc}"

                def fail_exc() -> None:
                    self._log(f"Could not connect: {err[:160]}")
                    append_event(KIND_ERROR, f"Connect failed: {err[:160]}")
                    self._set_status("error", detail=err)
                    self._apply_control(connected=False, busy=False)

                self.root.after(0, fail_exc)
                return

            def done() -> None:
                try:
                    self._tunnel = tun_res
                    if residual_ip_capture_active(tun_res):
                        v6 = ipv6_residual_protected(tun_res)
                        self._log(
                            "Tunnel active - residual public IP uses the VPN node "
                            f"(iface={getattr(tun_res, 'iface', '?')}; "
                            f"ipv6_protected={v6})"
                        )
                        append_event(
                            KIND_CONNECT,
                            "Connected — residual public IP uses the VPN node "
                            f"(ipv6_protected={v6})",
                        )
                        self._apply_control(connected=True, busy=False)
                        self._set_status(
                            "connected",
                            vpn_ip=vpn_ip,
                            residual_capture=True,
                            ipv6_protected=v6,
                        )
                    else:
                        original_err = getattr(tun_res, "message", None)
                        try:
                            disconnect_full_tunnel(
                                tun_res, self.client, preserve_message=True
                            )
                        except Exception:
                            pass
                        self._tunnel = None
                        err = attach_failure_user_message(original_err)
                        self._log(f"Could not connect: {err[:160]}")
                        append_event(KIND_ERROR, f"Connect failed: {err[:160]}")
                        self._set_status("error", detail=err)
                        self._apply_control(connected=False, busy=False)
                finally:
                    if self._busy:
                        self._apply_control(connected=self._connected, busy=False)

            self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _disconnect_tunnel(self) -> None:
        tunnel = self._tunnel
        self._tunnel = None
        disconnect_full_tunnel(tunnel, self.client)

    def _start_disconnect(self) -> None:
        self._apply_control(connected=True, busy=True)
        self._set_status("disconnecting")
        self._log("Disconnect - stopping tunnel...")

        def work() -> None:
            try:
                self._disconnect_tunnel()
            finally:

                def done() -> None:
                    self._apply_control(connected=False, busy=False)
                    self._set_status("disconnected")
                    self._log("Disconnected.")

                self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _open_upgrade(self) -> None:
        url = upgrade_download_url()
        self._log("Opening download page...")
        try:
            webbrowser.open(url)
        except Exception as exc:
            self._log(f"Could not open browser: {exc}")

    def _on_close_ui_only(self) -> None:
        self._log(
            "Window closed - tunnel keeps running until Disconnect or Quit."
        )
        try:
            self.root.withdraw()
        except Exception:
            try:
                self.root.iconify()
            except Exception:
                pass

    def _quit_app(self) -> None:
        self._log("Quit - stopping tunnel and exiting...")
        try:
            self._disconnect_tunnel()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    if not python_meets_minimum():
        print(python_version_error_message(), file=sys.stderr)
        return 1

    resume = "--rpt-auto-connect" in sys.argv
    if resume:
        sys.argv = [a for a in sys.argv if a != "--rpt-auto-connect"]

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        os.chdir(root)
    except Exception:
        pass

    try:
        app = TunnelClientApp()
    except Exception as exc:
        print(f"Restore Privacy failed to open: {exc}", file=sys.stderr)
        return 1

    if resume and is_root():
        app.root.after(350, app._start_connect)
    elif resume and not is_root():
        app.root.after(
            100,
            lambda: app._log(
                "Elevated Connect requested but process is not root - "
                "press Connect again and approve elevation."
            ),
        )

    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
