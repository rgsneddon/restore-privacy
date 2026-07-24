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
from typing import Any


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


# Win32 process-creation flags (values stable across Python versions)
_CREATE_BREAKAWAY_FROM_JOB = 0x01000000
_CREATE_NO_WINDOW = 0x08000000


def _creation_flag_sets() -> list[tuple[str, int]]:
    """Ordered CreateProcess flag sets to try (most isolated first).

    ``CREATE_BREAKAWAY_FROM_JOB`` can raise **WinError 5 Access is denied** when
    the parent is not allowed to break away (common on desktop + some agents).
    Always fall through to sets without breakaway so launch still works.
    """
    import subprocess

    base = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        base |= int(subprocess.DETACHED_PROCESS)  # type: ignore[attr-defined]
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        base |= int(subprocess.CREATE_NEW_PROCESS_GROUP)
    return [
        ("detached+breakaway+no_window", base | _CREATE_BREAKAWAY_FROM_JOB | _CREATE_NO_WINDOW),
        ("detached+no_window", base | _CREATE_NO_WINDOW),
        ("detached", base),
        ("new_group_only", int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) or 0),
        ("none", 0),
    ]


def spawn_windowed_gui(extra_args: list[str] | None = None) -> bool:
    """Start GUI under pythonw detached; return True if child was started.

    Tries multiple CreateProcess flag sets. ``CREATE_BREAKAWAY_FROM_JOB`` is
    attempted first (survives parent Job Objects when permitted) but **must not**
    be required — on many Windows desktops it fails with Access denied and
    previously caused spawn to return False so the parent exited without a
    durable windowed child.

    Optional ``RPT_LAUNCH_LOG`` path captures spawn diagnostics / child stderr.
    """
    if not should_reexec_to_windowed_host():
        return False
    import subprocess
    import time

    exe, args, cwd = launch_argv_windowed(extra_args=extra_args)
    # Pass through argv flags from this process when not supplied
    if extra_args is None and len(sys.argv) > 1:
        for a in sys.argv[1:]:
            if a not in args:
                args.append(a)

    if not Path(exe).is_file():
        _launch_log(f"spawn_windowed_gui: missing exe {exe}")
        return False

    log_path = (os.environ.get("RPT_LAUNCH_LOG") or "").strip()
    log_fh = None
    stdout: Any = subprocess.DEVNULL
    stderr: Any = subprocess.DEVNULL
    if log_path:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            log_fh = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
            log_fh.write(f"\n# spawn_windowed_gui {exe} {args} cwd={cwd}\n")
            log_fh.flush()
            stdout = log_fh
            stderr = log_fh
        except OSError:
            log_fh = None
            stdout = subprocess.DEVNULL
            stderr = subprocess.DEVNULL

    env = os.environ.copy()  # preserve LOCALAPPDATA / entitlement gates
    last_err: str | None = None
    for label, creationflags in _creation_flag_sets():
        try:
            proc = subprocess.Popen(
                [exe, *args],
                cwd=cwd,
                creationflags=creationflags,
                close_fds=log_fh is None,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                env=env,
            )
        except OSError as exc:
            last_err = f"{label}: OSError {exc}"
            _launch_log(f"spawn try failed: {last_err}")
            continue
        # Brief settle: if child dies immediately, try next flag set
        time.sleep(0.35)
        code = proc.poll()
        if code is not None:
            last_err = f"{label}: child exited immediately code={code}"
            _launch_log(f"spawn try failed: {last_err}")
            continue
        _launch_log(f"spawn ok: {label} pid={proc.pid}")
        if log_fh is not None:
            try:
                log_fh.flush()
            except OSError:
                pass
        return True

    _launch_log(f"spawn_windowed_gui: all flag sets failed last={last_err}")
    if log_fh is not None:
        try:
            log_fh.close()
        except OSError:
            pass
    return False


def _launch_log(message: str) -> None:
    """Append a line to RPT_LAUNCH_LOG when set (best-effort)."""
    log_path = (os.environ.get("RPT_LAUNCH_LOG") or "").strip()
    if not log_path:
        return
    try:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(message.rstrip() + "\n")
    except OSError:
        pass


def main() -> int:
    """Re-exec under pythonw when launched via console python.

    Returns 0 when a windowed child was started, or the in-process GUI exit
    code. Does **not** pretend success when spawn failed and in-process GUI
    cannot start.
    """
    if spawn_windowed_gui():
        return 0

    # Spawn failed or already on pythonw — run GUI in this process.
    # Only free the console after we know Tk can be imported (avoids a
    # headless-looking "crash" if free_console runs and then import fails).
    try:
        import tkinter  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        _launch_log(f"in-process GUI blocked: tkinter import failed: {exc}")
        print(f"Restore Privacy failed to open (tkinter): {exc}", file=sys.stderr)
        return 1

    free_console_if_attached()
    try:
        from client.windows.app import main as app_main

        return int(app_main() or 0)
    except Exception as exc:  # noqa: BLE001
        _launch_log(f"in-process GUI crashed: {exc}")
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


if __name__ == "__main__":
    raise SystemExit(main())
