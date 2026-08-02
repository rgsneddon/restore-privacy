"""rpOS testing sandbox window — dry-run only, never formats the host.

Runs the same smoke path as ``python3 -m rpos.installer smoke`` inside a
temporary prefix. Host disks are not touched (wipe adapter is dry-run).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import traceback
from pathlib import Path
from typing import Any

from . import NED_NAME, PRODUCT, __version__
from .advisories import advisory_text_blob
from .gate import evaluate_confirmation, gate_preview
from .wipe_adapter import DryRunWipeAdapter


def run_sandbox_smoke() -> dict[str, Any]:
    """Execute installer smoke in-process (temp prefix; dry-run wipe)."""
    from . import __main__ as installer_main

    # Capture stdout from cmd_smoke
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = installer_main.cmd_smoke()
    raw = buf.getvalue()
    payload: dict[str, Any] = {"returncode": code, "stdout": raw}
    try:
        # last JSON object in output
        payload["result"] = json.loads(raw)
    except json.JSONDecodeError:
        payload["result"] = None
    payload["ok"] = code == 0 and bool(payload.get("result", {}).get("ok"))
    payload["wipe_mode"] = "dry_run"
    payload["host_disk_touched"] = False
    payload["sandbox"] = True
    return payload


def sandbox_status() -> dict[str, Any]:
    """Static safety facts for the sandbox window header."""
    wipe = DryRunWipeAdapter().run_absolute_format_intent()
    return {
        "product": PRODUCT,
        "version": __version__,
        "ned": NED_NAME,
        "wipe_default": "dry_run",
        "host_disk_touched": wipe.get("host_disk_touched", False),
        "wiped": wipe.get("wiped", False),
        "confirm_phrase": gate_preview()["confirm_phrase"],
        "message": wipe.get("message"),
        "sandbox": True,
        "formats_host": False,
    }


def main(argv: list[str] | None = None) -> int:
    try:
        import tkinter as tk
        from tkinter import scrolledtext
    except Exception as e:
        print(f"Sandbox GUI requires tkinter: {e}", file=sys.stderr)
        print(json.dumps(run_sandbox_smoke(), indent=2))
        return 0

    root = tk.Tk()
    root.title(f"{PRODUCT} testing sandbox — dry-run only")
    root.geometry("720x560")
    root.configure(bg="#f4f6f9")

    header = tk.Frame(root, bg="#e8edf4", padx=12, pady=10)
    header.pack(fill=tk.X)
    tk.Label(
        header,
        text=f"{PRODUCT} · testing sandbox",
        bg="#e8edf4",
        fg="#1a2332",
        font=("Helvetica", 16, "bold"),
    ).pack(anchor="w")
    tk.Label(
        header,
        text="Does NOT format this machine. Wipe intent is dry-run only. "
        "Install/tour runs in a temporary sandbox prefix.",
        bg="#e8edf4",
        fg="#2d3748",
        font=("Helvetica", 11),
        wraplength=680,
        justify=tk.LEFT,
    ).pack(anchor="w", pady=(4, 0))

    status = sandbox_status()
    info = tk.Label(
        root,
        text=(
            f"version {status['version']} · wipe_default={status['wipe_default']} · "
            f"host_disk_touched={status['host_disk_touched']} · formats_host={status['formats_host']}"
        ),
        bg="#f4f6f9",
        fg="#4a5568",
        font=("Menlo", 10),
        anchor="w",
    )
    info.pack(fill=tk.X, padx=12, pady=6)

    log = scrolledtext.ScrolledText(
        root,
        wrap=tk.WORD,
        bg="#ffffff",
        fg="#1a2332",
        font=("Menlo", 11),
        height=22,
        relief=tk.SOLID,
        bd=1,
    )
    log.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)
    log.insert(tk.END, "Ready. Click “Run dry-run smoke” to test the current rpOS installer path.\n")
    log.insert(tk.END, "Advisories preview (not a wipe):\n")
    log.insert(tk.END, advisory_text_blob()[:800] + "\n…\n")
    log.configure(state=tk.DISABLED)

    btn_row = tk.Frame(root, bg="#f4f6f9")
    btn_row.pack(fill=tk.X, padx=12, pady=10)

    def append(msg: str) -> None:
        log.configure(state=tk.NORMAL)
        log.insert(tk.END, msg + "\n")
        log.see(tk.END)
        log.configure(state=tk.DISABLED)

    def run_smoke() -> None:
        run_btn.configure(state=tk.DISABLED)
        append("\n—— Running sandbox smoke (temp dir, dry-run wipe)… ——\n")

        def work() -> None:
            try:
                result = run_sandbox_smoke()
            except Exception:
                result = {"ok": False, "error": traceback.format_exc(), "host_disk_touched": False}

            def done() -> None:
                append(json.dumps(result, indent=2, default=str))
                if result.get("ok"):
                    append("\n✓ Sandbox smoke PASSED — host was not formatted.")
                else:
                    append("\n✗ Sandbox smoke reported failure (still no host format).")
                run_btn.configure(state=tk.NORMAL)

            root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    run_btn = tk.Button(
        btn_row,
        text="Run dry-run smoke",
        command=run_smoke,
        bg="#2b6cb0",
        fg="#ffffff",
        activebackground="#3b7cc0",
        relief=tk.FLAT,
        padx=14,
        pady=8,
        font=("Helvetica", 12, "bold"),
    )
    run_btn.pack(side=tk.LEFT, padx=(0, 8))

    tk.Button(
        btn_row,
        text="Show wipe safety",
        command=lambda: append(json.dumps(sandbox_status(), indent=2)),
        bg="#dce4ef",
        fg="#1a2332",
        relief=tk.FLAT,
        padx=12,
        pady=8,
        font=("Helvetica", 12),
    ).pack(side=tk.LEFT, padx=4)

    tk.Button(
        btn_row,
        text="Close",
        command=root.destroy,
        bg="#dce4ef",
        fg="#1a2332",
        relief=tk.FLAT,
        padx=12,
        pady=8,
        font=("Helvetica", 12),
    ).pack(side=tk.RIGHT)

    # Optional auto-run via CLI
    if argv and "--auto-run" in argv:
        root.after(300, run_smoke)

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
