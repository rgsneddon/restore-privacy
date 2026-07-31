"""Mac / desktop residual **node operator** GUI app entry.

Primary window is a local operator shell (HTTP GUI; optional Tk when available).
Launch::

  python -m node_operator
  # or:  python node_operator/app.py

Lab mode works on macOS without Linux TUN. Full mode spawns ``python -m node``.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from node.operator_admin import NodeOperatorController  # noqa: E402
from node_operator import APP_TITLE  # noqa: E402
from node_operator.gui_html import handle_operator_post, render_operator_page  # noqa: E402

# Shared controller for GUI process
_CTRL: NodeOperatorController | None = None
_FLASH = ""


def get_controller() -> NodeOperatorController:
    global _CTRL
    if _CTRL is None:
        _CTRL = NodeOperatorController(repo_root=_ROOT)
    return _CTRL


def try_tk_gui(ctrl: NodeOperatorController) -> bool:
    """Open a minimal Tk window if _tkinter is available. Returns True if shown."""
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except Exception:
        return False

    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("720x520")
    root.minsize(560, 400)

    state_var = tk.StringVar(value="State: stopped")
    detail_var = tk.StringVar(value="")
    sessions_var = tk.StringVar(value="Sessions: 0")

    def refresh() -> None:
        st = ctrl.get_state()
        state_var.set(f"State: {st.state} · mode={st.mode} · pid={st.pid or '—'}")
        detail_var.set(st.detail or "")
        sessions_var.set(f"Sessions: {len(ctrl.list_sessions_admin())}")

    frm = ttk.Frame(root, padding=12)
    frm.pack(fill=tk.BOTH, expand=True)
    ttk.Label(frm, text=APP_TITLE, font=("", 14, "bold")).pack(anchor=tk.W)
    ttk.Label(
        frm,
        text="Operator shell for this Mac as residual node host (not end-user Connect).",
        wraplength=680,
    ).pack(anchor=tk.W, pady=(0, 8))
    ttk.Label(frm, textvariable=state_var).pack(anchor=tk.W)
    ttk.Label(frm, textvariable=detail_var, wraplength=680).pack(anchor=tk.W)
    ttk.Label(frm, textvariable=sessions_var).pack(anchor=tk.W, pady=(4, 8))

    bf = ttk.Frame(frm)
    bf.pack(anchor=tk.W, pady=4)

    def on_start_lab() -> None:
        ctrl.start(mode="lab")
        refresh()

    def on_stop() -> None:
        ctrl.stop()
        refresh()

    def on_lab_sess() -> None:
        if ctrl.get_state().state != "running":
            ctrl.start(mode="lab")
        ctrl.inject_lab_session()
        refresh()

    def on_priority() -> None:
        rows = ctrl.list_sessions_admin()
        if len(rows) < 1:
            messagebox.showinfo(APP_TITLE, "No sessions — add a lab session first.")
            return
        # Highest priority on first, lower on second if present
        ctrl.set_client_priority(rows[0]["client_id"], 100)
        if len(rows) > 1:
            ctrl.set_client_priority(rows[1]["client_id"], 1)
        order = ctrl.service_order()
        messagebox.showinfo(APP_TITLE, f"Service order (high→low):\n" + "\n".join(order[:8]))
        refresh()

    def on_push() -> None:
        r = ctrl.push_update(
            version="0.5.9",
            url="https://restoreprivacy.online/",
            message="Operator update push",
        )
        messagebox.showinfo(APP_TITLE, f"Push: {r}")
        refresh()

    ttk.Button(bf, text="Start lab node", command=on_start_lab).pack(side=tk.LEFT, padx=2)
    ttk.Button(bf, text="Stop", command=on_stop).pack(side=tk.LEFT, padx=2)
    ttk.Button(bf, text="Add lab session", command=on_lab_sess).pack(side=tk.LEFT, padx=2)
    ttk.Button(bf, text="Prioritise clients", command=on_priority).pack(side=tk.LEFT, padx=2)
    ttk.Button(bf, text="Push update", command=on_push).pack(side=tk.LEFT, padx=2)

    refresh()
    root.after(1500, lambda: None)  # keep event loop alive marker
    root.mainloop()
    return True


def run_http_gui(
    ctrl: NodeOperatorController,
    *,
    host: str = "127.0.0.1",
    port: int = 18765,
    open_browser: bool = True,
) -> ThreadingHTTPServer:
    """Start the operator HTML GUI HTTP server (blocking serve in caller)."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            global _FLASH
            path = (self.path or "/").split("?", 1)[0]
            if path in ("/", "/index.html", "/op", "/op/"):
                body = render_operator_page(ctrl, flash=_FLASH).encode("utf-8")
                _FLASH = ""
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if path in ("/api/state",):
                import json

                data = json.dumps(ctrl.get_state().to_dict()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            global _FLASH
            path = (self.path or "/").split("?", 1)[0]
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else b""
            code, flash = handle_operator_post(ctrl, path, body)
            _FLASH = flash
            # Redirect back to main window
            self.send_response(303 if code < 400 else code)
            if code < 400:
                self.send_header("Location", "/?ok=" + quote(flash[:80]))
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                page = render_operator_page(ctrl, flash=flash).encode("utf-8")
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)

    httpd = ThreadingHTTPServer((host, int(port)), Handler)
    url = f"http://{host}:{int(port)}/"
    if open_browser and str(os.environ.get("RPT_NODE_OP_NO_BROWSER", "")).strip() not in (
        "1",
        "true",
        "yes",
    ):
        try:
            webbrowser.open(url)
        except Exception:
            pass
    return httpd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument(
        "--gui",
        choices=("auto", "http", "tk", "none"),
        default="auto",
        help="GUI backend (default auto: tk if present else http)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser for the HTTP GUI",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Import/controller smoke only (no serve forever)",
    )
    args = parser.parse_args(argv)

    ctrl = get_controller()
    if args.smoke:
        # Structural smoke: title + controller start/stop lab
        st = ctrl.start(mode="lab")
        assert st.state == "running", st
        pub = ctrl.public_status_title_only()
        assert pub.get("title") == "RESTORE PRIVACY", pub
        assert "live" not in pub and "sessions" not in pub
        ctrl.stop()
        print(f"SMOKE_OK title={APP_TITLE!r} state_after_stop={ctrl.get_state().state}")
        return 0

    gui = args.gui
    if gui == "auto":
        if try_tk_gui(ctrl):
            return 0
        gui = "http"
    if gui == "tk":
        if not try_tk_gui(ctrl):
            print("Tk GUI unavailable; falling back to HTTP GUI", file=sys.stderr)
            gui = "http"
        else:
            return 0
    if gui == "none":
        print(f"{APP_TITLE}: controller ready (no GUI). Use --smoke or --gui http.")
        return 0

    # HTTP GUI (primary path on this Mac without _tkinter)
    if args.no_browser:
        os.environ["RPT_NODE_OP_NO_BROWSER"] = "1"
    httpd = run_http_gui(
        ctrl,
        host=args.host,
        port=args.port,
        open_browser=False,  # open via platform helper below for reliability on Mac
    )
    url = f"http://{args.host}:{int(args.port)}/"
    print(f"{APP_TITLE}")
    print(f"Operator GUI: {url}")
    if not args.no_browser and str(
        os.environ.get("RPT_NODE_OP_NO_BROWSER", "")
    ).strip().lower() not in ("1", "true", "yes"):
        opened = False
        # macOS: open default browser to the GUI (best “app window” without Tk)
        if sys.platform == "darwin":
            try:
                import subprocess

                subprocess.Popen(
                    ["open", url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                opened = True
            except Exception:
                opened = False
        if not opened:
            try:
                webbrowser.open(url)
            except Exception:
                pass
    print("Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            ctrl.disconnect_residual()
        except Exception:
            pass
        ctrl.stop()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
