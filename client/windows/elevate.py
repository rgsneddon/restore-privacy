"""Windows elevation helpers — avoid manual “Run as administrator”.

Full-system VPN (Wintun adapter + dual /1 routes) requires elevated rights.
There is no safe fully-unprivileged path for OS-wide capture on stock Windows
without a pre-installed privileged service.

Workaround: if the process is not elevated, re-launch the same executable with
a single UAC consent prompt (ShellExecute ``runas``). The user clicks **Yes**
once; they do not need to right-click the shortcut.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def is_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _shell_execute_runas(exe: str, params: str, cwd: Optional[str] = None) -> int:
    """Return value > 32 means success (ShellExecute)."""
    import ctypes
    from ctypes import wintypes

    SEE_MASK_NOCLOSEPROCESS = 0x00000040
    SW_SHOWNORMAL = 1

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", ctypes.c_ulong),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIcon", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.hwnd = None
    info.lpVerb = "runas"
    info.lpFile = exe
    info.lpParameters = params or None
    info.lpDirectory = cwd
    info.nShow = SW_SHOWNORMAL
    ok = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info))
    if not ok:
        err = ctypes.get_last_error()
        return -err if err else 0
    # hInstApp > 32 means launched
    return int(info.hInstApp) if info.hInstApp else 1


def elevation_working_directory() -> str:
    """cwd for elevated re-launch (repo root for -m, exe dir when frozen)."""
    if getattr(sys, "frozen", False):
        try:
            return str(Path(sys.executable).resolve().parent)
        except Exception:
            return os.getcwd()
    # client/windows/elevate.py → repo root
    try:
        return str(Path(__file__).resolve().parents[2])
    except Exception:
        return os.getcwd()


def launch_argv_for_elevation(
    extra_args: Optional[list[str]] = None,
) -> tuple[str, str]:
    """Return (executable, parameter string) for re-launching this process elevated."""
    extra = list(extra_args or [])
    if getattr(sys, "frozen", False):
        exe = str(Path(sys.executable).resolve())
        # Pass through any args after the exe
        args = list(sys.argv[1:])
        for a in extra:
            if a not in args:
                args.append(a)
        params = subprocess_list2cmdline(args) if args else ""
        return exe, params

    # Dev: python -m client.windows …
    exe = str(Path(sys.executable).resolve())
    # Rebuild: -m client.windows [args…]
    parts: list[str] = []
    # Prefer module form when launched as __main__ of client.windows
    if len(sys.argv) >= 1:
        # sys.argv[0] is script path; use -m client.windows for stability
        parts.extend(["-m", "client.windows"])
        # If user passed extra args after script, keep them
        # When running `python -m client.windows`, argv[0] is full path to __main__.py
        # Extra args start at argv[1]
        if len(sys.argv) > 1:
            parts.extend(sys.argv[1:])
    for a in extra:
        if a not in parts:
            parts.append(a)
    params = subprocess_list2cmdline(parts)
    return exe, params


def subprocess_list2cmdline(seq: list[str]) -> str:
    """Windows cmdline quoting (stdlib-compatible)."""
    import subprocess

    return subprocess.list2cmdline(seq)


def elevate_if_needed(
    *,
    force: bool = False,
    marker_env: str = "RPT_ELEVATED",
    extra_args: Optional[list[str]] = None,
) -> str:
    """If not admin, re-launch elevated and signal caller to exit.

    Returns:
      ``"already_admin"`` — continue running
      ``"relaunched"`` — elevated child started; current process should exit 0
      ``"skipped"`` — non-Windows or elevation disabled
      ``"failed:<reason>"`` — UAC cancelled or ShellExecute failed

    Set env ``RPT_NO_AUTO_ELEVATE=1`` to disable (tests / debugging).

    ``extra_args`` are appended to the elevated child (e.g. ``--rpt-auto-connect``
    after the user pressed Connect so residual routing can complete elevated).
    """
    if sys.platform != "win32":
        return "skipped"
    if os.environ.get("RPT_NO_AUTO_ELEVATE", "").strip() in ("1", "true", "yes"):
        return "skipped"
    if is_admin() and not force:
        return "already_admin"
    # Avoid elevation loops
    if os.environ.get(marker_env, "").strip() == "1" and is_admin():
        return "already_admin"
    if os.environ.get(marker_env, "").strip() == "1" and not is_admin():
        return "failed:elevated_flag_set_but_still_not_admin"

    exe, params = launch_argv_for_elevation(extra_args=extra_args)
    # Child inherits env; set marker so we can detect loops
    # ShellExecute does not easily pass custom env; append a no-op arg flag instead
    elev_flag = "--rpt-elevated"
    if elev_flag not in (params or "") and elev_flag not in sys.argv:
        params = (params + " " + elev_flag).strip() if params else elev_flag

    cwd = elevation_working_directory()

    try:
        rc = _shell_execute_runas(exe, params, cwd=cwd)
    except Exception as exc:
        return f"failed:{exc}"

    if rc <= 32:
        # 1223 = ERROR_CANCELLED (user denied UAC)
        if rc == -1223 or rc == 1223:
            return "failed:uac_cancelled"
        return f"failed:shellexecute_{rc}"
    return "relaunched"


def should_exit_after_elevation(status: str) -> bool:
    return status == "relaunched"
