"""Launch the Windows GUI without leaving a Python console open.

On Windows, ``python.exe -m client.windows`` attaches a console that stays open
behind the Tk window. Prefer ``pythonw.exe`` (windowed) when available.

Usage:
  python -m client.windows.launch_gui
  pythonw -m client.windows.launch_gui
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_pythonw(python_exe: str | None = None) -> Path | None:
    """Return pythonw.exe next to python.exe when present (Windows)."""
    exe = Path(python_exe or sys.executable).resolve()
    name = exe.name.lower()
    if name == "pythonw.exe":
        return exe
    # python.exe → pythonw.exe in same directory
    cand = exe.with_name("pythonw.exe")
    if cand.is_file():
        return cand
    # WindowsApps / store shims: try common Local Python installs
    for p in (
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Python",
    ):
        if not p.is_dir():
            continue
        for hit in p.rglob("pythonw.exe"):
            if hit.is_file():
                return hit
    return None


def prefer_windowed_gui_launch() -> bool:
    """Policy: product GUI should not leave a bare console as primary UX."""
    return True


def launch_argv_windowed(extra_args: list[str] | None = None) -> tuple[str, list[str], str]:
    """Return (executable, argv, cwd) for a console-free GUI launch."""
    root = Path(__file__).resolve().parents[2]
    args = ["-m", "client.windows"]
    if extra_args:
        args.extend(a for a in extra_args if a not in ("-m", "client.windows"))
    pyw = resolve_pythonw()
    if pyw is not None:
        return str(pyw), args, str(root)
    # Fallback: same interpreter (may keep console)
    return str(Path(sys.executable).resolve()), args, str(root)


def main() -> int:
    """Re-exec under pythonw when launched via console python."""
    if sys.platform == "win32" and prefer_windowed_gui_launch():
        pyw = resolve_pythonw()
        me = Path(sys.executable).resolve()
        if pyw is not None and pyw.resolve() != me:
            import subprocess

            root = Path(__file__).resolve().parents[2]
            # Detach so this console can exit; child is windowed
            creationflags = 0
            if hasattr(subprocess, "DETACHED_PROCESS"):
                creationflags |= subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
            if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP
            # CREATE_NO_WINDOW = 0x08000000 — hide any residual console for child
            creationflags |= 0x08000000
            subprocess.Popen(
                [str(pyw), "-m", "client.windows", *sys.argv[1:]],
                cwd=str(root),
                creationflags=creationflags,
                close_fds=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return 0

    # Already pythonw, non-Windows, or no pythonw found — run GUI in-process
    from client.windows.app import main as app_main

    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
