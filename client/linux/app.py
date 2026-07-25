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
    PANEL_BG,
    PANEL_PAD,
    PRIMARY,
    PRIMARY_DARK,
    PRIVACY_MESSAGE_TEXT,
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
from client.registration_copy import (
    ANON_REGISTRATION_SUMMARY,
    OS_PRIVILEGE_HONESTY,
    SEAMLESS_HINT,
    SEAMLESS_TAGLINE,
)
from client.startup_bootstrap import bootstrap_payment_entitlement
from client.transparency_copy import (
    CONNECTION_LOG_DISCLAIMER,
    CONNECTION_LOG_TITLE,
    DPI_MITIGATION_DISCLAIMER,
    DPI_MITIGATION_TITLE,
    LEAK_TEST_BUTTON,
    LEAK_TEST_DISCLAIMER,
    LEAK_TEST_TITLE,
)
from client.linux.settings_store import (
    ProductSettings,
    apply_run_at_startup,
    load_settings,
    save_settings,
    should_autoconnect_on_launch,
)
from client.legal_links import LEGAL_DOC_LINKS
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
            text=PRIVACY_MESSAGE_TEXT,
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

    def _show_renew_licence_prompt(self) -> None:
        """EXPIRED hard-lock: renew your licence *here* + platform pay portal."""
        ent = load_payment_entitlement()
        plat = (ent.platform or "linux").strip().lower() or "linux"
        url = renew_licence_url(plat, renew_url=ent.renew_url)
        body = renew_licence_message(plat, renew_url=ent.renew_url)
        win = tk.Toplevel(self.root)
        win.title("Renew your licence")
        win.configure(bg=CHROME_BG)
        win.geometry("500x320")
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass
        pad = tk.Frame(win, bg=CHROME_BG, padx=16, pady=14)
        pad.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            pad,
            text="Renew your licence",
            bg=CHROME_BG,
            fg=PRIMARY_DARK,
            font=("DejaVu Sans", 14, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            pad,
            text="Your subscription is EXPIRED. Renew your licence *here*:",
            bg=CHROME_BG,
            fg=TEXT,
            font=("DejaVu Sans", 10),
            anchor="w",
            wraplength=460,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 6))
        link = tk.Label(
            pad,
            text=url,
            bg=CHROME_BG,
            fg=PRIMARY,
            font=("DejaVu Sans", 9, "underline"),
            cursor="hand2",
            anchor="w",
            wraplength=460,
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
            bg=CHROME_BG,
            fg=TEXT_MUTED,
            font=("DejaVu Sans", 8),
            anchor="w",
            wraplength=460,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 10))
        btn_row = tk.Frame(pad, bg=CHROME_BG)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        tk.Button(
            btn_row,
            text="Open payment portal",
            command=_open_portal,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
            font=("DejaVu Sans", 9, "bold"),
            padx=12,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.LEFT)
        tk.Button(
            btn_row,
            text="Close",
            command=win.destroy,
            bg=PANEL_BG,
            fg=TEXT,
            relief=tk.FLAT,
            font=("DejaVu Sans", 9),
            padx=10,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=(8, 0))

    def _show_keygen_prompt(self) -> None:
        """Forced modal: enter fulfilment keygen to unlock Connect (parity with Windows)."""
        if needs_licence_renewal():
            self._show_renew_licence_prompt()
            return
        win = tk.Toplevel(self.root)
        win.title("Enter licence keygen")
        win.configure(bg=CHROME_BG)
        win.geometry("480x360")
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass
        pad = tk.Frame(win, bg=CHROME_BG, padx=16, pady=14)
        pad.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            pad,
            text="Enter licence keygen",
            bg=CHROME_BG,
            fg=PRIMARY_DARK,
            font=("DejaVu Sans", 14, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            pad,
            text=(
                "Your fulfilment email includes a keygen with the text "
                "USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY "
                "(format RPT-KEY-…). Paste it below to unlock Connect. "
                "Download alone does not unlock residual VPN."
            ),
            bg=CHROME_BG,
            fg=TEXT,
            font=("DejaVu Sans", 9),
            anchor="w",
            wraplength=440,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            pad,
            text=CONNECT_BLOCKED_KEYGEN_MSG,
            bg=CHROME_BG,
            fg=TEXT_MUTED,
            font=("DejaVu Sans", 8),
            anchor="w",
            wraplength=440,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 10))
        key_var = tk.StringVar()
        entry = tk.Entry(
            pad,
            textvariable=key_var,
            font=("DejaVu Sans", 11),
            bg=WHITE,
            fg=TEXT,
            relief=tk.SOLID,
            bd=1,
        )
        entry.pack(fill=tk.X, pady=(0, 8))
        try:
            entry.focus_set()
        except Exception:
            pass
        status_var = tk.StringVar(value="")
        tk.Label(
            pad,
            textvariable=status_var,
            bg=CHROME_BG,
            fg=TEXT_MUTED,
            font=("DejaVu Sans", 8),
            anchor="w",
            wraplength=440,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 8))
        btn_row = tk.Frame(pad, bg=CHROME_BG)
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
                        f"Unlocked — Connect allowed (status={ent.status})."
                        if ok
                        else (
                            f"Keygen not active (status={ent.status}). "
                            "Check the email code and that your subscription is active."
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    ok = False
                    msg = f"Could not verify keygen: {exc}"

                def done() -> None:
                    status_var.set(msg)
                    self._log(msg)
                    self._refresh_licence_badge()
                    if ok:
                        self.detail_var.set(
                            "Keygen verified. Press Connect for residual protection."
                        )
                        try:
                            win.destroy()
                        except Exception:
                            pass
                    else:
                        self.detail_var.set(msg)

                try:
                    self.root.after(0, done)
                except Exception:
                    pass

            import threading

            threading.Thread(target=work, daemon=True).start()

        tk.Button(
            btn_row,
            text="Unlock Connect",
            command=_unlock,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
            font=("DejaVu Sans", 9, "bold"),
            padx=12,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.LEFT)
        tk.Button(
            btn_row,
            text="Cancel",
            command=win.destroy,
            bg=PANEL_BG,
            fg=TEXT,
            relief=tk.FLAT,
            font=("DejaVu Sans", 9),
            padx=10,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=(8, 0))
        try:
            win.bind("<Return>", lambda _e: _unlock())
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
                "Licence accepted. Enter your keygen from the fulfilment email to unlock Connect."
            )
            self._log("Licence accepted (stored locally only).")
            try:
                win.destroy()
            except Exception:
                pass
            if needs_licence_renewal():
                try:
                    self.root.after(200, self._show_renew_licence_prompt)
                except Exception:
                    self._show_renew_licence_prompt()
            elif needs_keygen_unlock():
                try:
                    self.root.after(200, self._show_keygen_prompt)
                except Exception:
                    self._show_keygen_prompt()

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
        """Settings: startup prefs, licence, payment, log, leak test, docs, DPI."""
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.configure(bg=CHROME_BG)
        win.geometry("500x640")
        # Scrollable body for full product Settings surface
        canvas = tk.Canvas(win, bg=CHROME_BG, highlightthickness=0)
        scroll = tk.Scrollbar(win, orient=tk.VERTICAL, command=canvas.yview)
        frm = tk.Frame(canvas, bg=WHITE, padx=12, pady=10)
        frm.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=frm, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        cur = load_settings()
        run_var = tk.BooleanVar(value=cur.run_at_startup)
        auto_var = tk.BooleanVar(value=cur.autoconnect_on_launch)
        note_var = tk.StringVar(value="")

        tk.Label(
            frm,
            text="Settings",
            bg=WHITE,
            fg=PRIMARY_DARK,
            font=("DejaVu Sans", 12, "bold"),
        ).pack(anchor="w")
        tk.Label(
            frm,
            text="Seamless power-up (both default off)",
            bg=WHITE,
            fg=PRIMARY_DARK,
            font=("DejaVu Sans", 10, "bold"),
        ).pack(anchor="w", pady=(10, 2))

        def _save_prefs() -> None:
            s = ProductSettings(
                run_at_startup=bool(run_var.get()),
                autoconnect_on_launch=bool(auto_var.get()),
            )
            save_settings(s)
            st = apply_run_at_startup(s.run_at_startup)
            note_var.set(
                f"Saved. Run at startup: {st}. "
                f"Autoconnect: {'on' if s.autoconnect_on_launch else 'off'}."
            )
            self._log(
                f"Settings: run_at_startup={s.run_at_startup} ({st}); "
                f"autoconnect={s.autoconnect_on_launch}"
            )

        tk.Checkbutton(
            frm,
            text="Run at device startup (XDG autostart)",
            variable=run_var,
            command=_save_prefs,
            bg=WHITE,
            fg=TEXT,
            activebackground=WHITE,
            selectcolor=WHITE,
            font=("DejaVu Sans", 9),
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))
        tk.Checkbutton(
            frm,
            text="Autoconnect on launch (same Connect gates)",
            variable=auto_var,
            command=_save_prefs,
            bg=WHITE,
            fg=TEXT,
            activebackground=WHITE,
            selectcolor=WHITE,
            font=("DejaVu Sans", 9),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            frm,
            textvariable=note_var,
            bg=WHITE,
            fg=PRIMARY_DARK,
            font=("DejaVu Sans", 8),
            wraplength=440,
            justify=tk.LEFT,
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
            text="Payment entitlement / keygen",
            bg=WHITE,
            fg=PRIMARY_DARK,
            font=("DejaVu Sans", 10, "bold"),
        ).pack(anchor="w", pady=(6, 2))
        tk.Label(
            frm,
            text=PAYMENT_CONNECT_DISCLAIMER_PLAIN,
            bg=WHITE,
            fg=TEXT_MUTED,
            font=("DejaVu Sans", 8),
            wraplength=440,
            justify=tk.LEFT,
        ).pack(anchor="w")
        _pay = load_payment_entitlement()
        pay_note = tk.StringVar(
            value=f"Status: {_pay.status or 'unknown'}"
            + (f" (keygen {_pay.keygen[:16]}…)" if _pay.keygen else "")
            + (f" ({_pay.session_id[:16]}…)" if _pay.session_id else "")
        )
        tk.Label(
            frm,
            textvariable=pay_note,
            bg=WHITE,
            fg=TEXT,
            font=("DejaVu Sans", 8),
            wraplength=440,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(2, 2))
        session_var = tk.StringVar(value=_pay.keygen or _pay.session_id or "")
        tk.Entry(frm, textvariable=session_var, font=("DejaVu Sans", 9)).pack(
            fill=tk.X, pady=(2, 4)
        )

        def _verify_pay() -> None:
            from client.payment_entitlement import import_keygen_and_verify

            raw = (session_var.get() or "").strip()
            pay_note.set("Verifying…")
            win.update_idletasks()
            try:
                if raw.upper().startswith("RPT-KEY") or raw.upper().startswith(
                    "RPTKEY"
                ):
                    ent = import_keygen_and_verify(raw)
                elif raw.startswith("cs_") or raw.startswith("cs_test"):
                    ent = import_session_and_verify(raw)
                elif raw:
                    ent = import_keygen_and_verify(raw)
                else:
                    # Auto-import payment_entitlement.json (Downloads / install dir)
                    ent = ensure_entitlement_for_connect(bind_device=True)
                ok = payment_allows_connect()
                if ent and getattr(ent, "keygen", None):
                    session_var.set(ent.keygen)
                elif ent and getattr(ent, "session_id", None):
                    session_var.set(ent.session_id)
                pay_note.set(
                    f"Status: {getattr(ent, 'status', '?') if ent else load_payment_entitlement().status}"
                    + (" — Connect allowed." if ok else " — Connect blocked.")
                )
                self._log(
                    "Payment verified." if ok else "Payment not active for Connect."
                )
            except Exception as exc:  # noqa: BLE001
                pay_note.set(f"Verify failed: {exc}")

        tk.Button(
            frm,
            text="Verify keygen / unlock Connect",
            command=_verify_pay,
            bg=PRIMARY,
            fg=WHITE,
            relief=tk.FLAT,
        ).pack(anchor="w", pady=(0, 2))
        tk.Label(
            frm,
            text="Enter keygen from email (USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY). "
            "Leave blank to auto-import payment_entitlement.json from Downloads.",
            bg=WHITE,
            fg=TEXT_MUTED,
            font=("DejaVu Sans", 8),
            wraplength=440,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 8))

        tk.Label(
            frm,
            text="Documents",
            bg=WHITE,
            fg=PRIMARY_DARK,
            font=("DejaVu Sans", 10, "bold"),
        ).pack(anchor="w", pady=(6, 2))
        for link in LEGAL_DOC_LINKS:
            tk.Button(
                frm,
                text=link.label,
                command=lambda u=link.url, t=link.label: (
                    webbrowser.open(u),
                    self._log(f"Opened {t}"),
                ),
                bg=CHROME_BG,
                fg=PRIMARY_DARK,
                relief=tk.FLAT,
                font=("DejaVu Sans", 9),
                anchor="w",
            ).pack(fill=tk.X, pady=1)

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
        # Local-only gate first (no status-host I/O on the Tk UI thread).
        # Keygen unlock required before residual HELLO — session discovery alone
        # does not skip the keygen surface.
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
            msg = renew_licence_message(ent.platform or "linux")
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
            self._show_keygen_prompt()
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
        append_event(
            KIND_CONNECT,
            "Connect started (full-tunnel residual path)",
            detail={"outcome": "start", "residual_capture": "pending"},
        )

        def work() -> None:
            # Status-host refresh + residual HELLO off the Tk UI thread.
            try:
                bootstrap_payment_entitlement(bind_device=True)
            except Exception:
                pass
            ok_lic, lic_msg = assert_may_connect()
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

            # Handshake + residual TUN/routes off the Tk UI thread.
            # Prefetch default route while HELLO runs to shorten residual attach.
            from concurrent.futures import ThreadPoolExecutor

            from client.linux.tunnel_linux import resolve_default_route

            prior = self._tunnel
            residual_ready = residual_ip_capture_active(prior)
            with ThreadPoolExecutor(max_workers=1) as pool:
                route_fut = pool.submit(resolve_default_route)
                result = self.client.connect(timeout=20.0)
                try:
                    prefetched_route = route_fut.result(timeout=8)
                except Exception:
                    # Do not pass (None, None) — that would skip re-resolve in
                    # start_full_tunnel. None means "resolve live".
                    prefetched_route = None

            if not (result.ok and result.session and result.tunnel_plan):
                msg = result.message or "Connection failed"

                def fail_hs() -> None:
                    self._log(f"Could not connect: {msg}")
                    append_event(
                        KIND_ERROR,
                        f"Connect failed: {msg}",
                        detail={"outcome": "fail", "error": msg[:300]},
                    )
                    self._set_status("error", detail=msg)
                    self._apply_control(connected=False, busy=False)

                self.root.after(0, fail_hs)
                return

            vpn_ip = result.session.vpn_ip

            def note_session() -> None:
                self._log(f"Session ready (tunnel address {vpn_ip})")
                append_event(
                    KIND_SESSION,
                    f"Session ready (tunnel address {vpn_ip})",
                    detail={
                        "outcome": "ok",
                        "session_vpn_ip": str(vpn_ip or ""),
                        "residual_capture": "attaching",
                    },
                )
                if residual_ready:
                    self._log("Residual already active — confirming tunnel attach…")
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
                    append_event(
                        KIND_ERROR,
                        f"Connect failed: {err[:160]}",
                        detail={"outcome": "fail", "error": err[:300]},
                    )
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
                        append_event(
                        KIND_ERROR,
                        f"Connect failed: {err[:160]}",
                        detail={"outcome": "fail", "error": err[:300]},
                    )
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

    # Warm entitlement cache off the UI thread (never block launch on status host).
    def _bg_bootstrap() -> None:
        try:
            bootstrap_payment_entitlement(bind_device=True)
        except Exception:
            pass

    threading.Thread(target=_bg_bootstrap, daemon=True).start()

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
    elif should_autoconnect_on_launch():
        def _settings_autoconnect() -> None:
            # Local-only gate on UI thread; network/residual stay in _start_connect.
            if not has_accepted_licence():
                app._log(
                    "Settings: autoconnect skipped — accept licence first."
                )
                app._show_licence_prompt()
                return
            if needs_licence_renewal():
                app._log(
                    "Settings: autoconnect skipped — renew licence (EXPIRED)."
                )
                app._show_renew_licence_prompt()
                return
            if needs_keygen_unlock():
                app._log(
                    "Settings: autoconnect skipped — enter keygen to unlock Connect."
                )
                app._show_keygen_prompt()
                return
            app._log("Settings: autoconnect on launch — starting Connect…")
            app._start_connect()

        app.root.after(450, _settings_autoconnect)
    elif not may_connect():
        def _first_run_gates() -> None:
            if not has_accepted_licence():
                app._show_licence_prompt()
            elif needs_licence_renewal():
                app._show_renew_licence_prompt()
            elif needs_keygen_unlock():
                app._show_keygen_prompt()

        app.root.after(500, _first_run_gates)

    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
