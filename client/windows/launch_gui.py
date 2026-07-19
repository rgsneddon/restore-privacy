"""Launch the Windows GUI without leaving a Python console open.

On Windows, ``python.exe -m client.windows`` attaches a console that stays open
behind the Tk window. Prefer ``pythonw.exe`` (windowed) when available — for
cold entry **and** elevated UAC re-launch.

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
    # Also search parent of executable (pythoncore-*-64 layout)
    try:
        sibling_tree = exe.parent
        for hit in sibling_tree.rglob("pythonw.exe"):
            if hit.is_file():
                return hit
    except Exception:
        pass
    return None


def prefer_windowed_gui_launch() -> bool:
    """Policy: product GUI should not leave a bare console as primary UX."""
    return True


def is_console_python_host(python_exe: str | None = None) -> bool:
    """True when the interpreter is the console subsystem (python.exe)."""
    name = Path(python_exe or sys.executable).name.lower()
    return name in ("python.exe", "python")


def free_console_if_attached() -> bool:
    """Detach this process from a console so it is not left as a product surface.

    Used as fallback when pythonw is unavailable. Safe no-op when no console.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        if not ctypes.windll.kernel32.GetConsoleWindow():
            return False
        return bool(ctypes.windll.kernel32.FreeConsole())
    except Exception:
        return False


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


def should_reexec_to_windowed_host() -> bool:
    """True when we should spawn pythonw and exit the console parent."""
    if sys.platform != "win32":
        return False
    if getattr(sys, "frozen", False):
        return False
    if not prefer_windowed_gui_launch():
        return False
    me = Path(sys.executable).resolve()
    if me.name.lower() == "pythonw.exe":
        return False
    pyw = resolve_pythonw()
    return pyw is not None and pyw.resolve() != me


def spawn_windowed_gui(extra_args: list[str] | None = None) -> bool:
    """Start GUI under pythonw detached; return True if child was started."""
    if not should_reexec_to_windowed_host():
        return False
    import subprocess

    exe, args, cwd = launch_argv_windowed(extra_args=extra_args)
    # Pass through argv flags from this process when not supplied
    if extra_args is None and len(sys.argv) > 1:
        for a in sys.argv[1:]:
            if a not in args:
                args.append(a)
    creationflags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        creationflags |= subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP
    # CREATE_NO_WINDOW = 0x08000000 — hide any residual console for child
    creationflags |= 0x08000000
    subprocess.Popen(
        [exe, *args],
        cwd=cwd,
        creationflags=creationflags,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def main() -> int:
    """Re-exec under pythonw when launched via console python."""
    if spawn_windowed_gui():
        return 0

    # Already pythonw, non-Windows, or no pythonw found — run GUI in-process.
    # Hide/free console so python.exe fallback is not a product surface.
    free_console_if_attached()
    from client.windows.app import main as app_main

    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
