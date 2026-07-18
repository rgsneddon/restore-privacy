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


def repo_root_for_dev() -> Path:
    """Directory that must be cwd so ``python -m client.windows`` can import."""
    # client/windows/elevate.py → repo root is parents[2]
    return Path(__file__).resolve().parents[2]


def launch_argv_for_elevation() -> tuple[str, str, Optional[str]]:
    """Return (executable, parameter string, cwd) for re-launching elevated."""
    if getattr(sys, "frozen", False):
        exe = str(Path(sys.executable).resolve())
        args = [a for a in sys.argv[1:] if a != "--rpt-elevated"]
        params = subprocess_list2cmdline(args) if args else ""
        cwd = str(Path(exe).resolve().parent)
        return exe, params, cwd

    # Dev: must run from repo root so ``-m client.windows`` resolves
    exe = str(Path(sys.executable).resolve())
    parts: list[str] = ["-m", "client.windows"]
    extra = [a for a in sys.argv[1:] if a != "--rpt-elevated"]
    # When launched as ``python -m client.windows``, argv[0] is __main__.py path
    # and argv[1:] are user args — already filtered above.
    # When launched as ``python path/to/app.py``, still use -m form.
    parts.extend(extra)
    params = subprocess_list2cmdline(parts)
    cwd = str(repo_root_for_dev())
    return exe, params, cwd


def subprocess_list2cmdline(seq: list[str]) -> str:
    """Windows cmdline quoting (stdlib-compatible)."""
    import subprocess

    return subprocess.list2cmdline(seq)


def elevate_if_needed(
    *,
    force: bool = False,
    marker_env: str = "RPT_ELEVATED",
) -> str:
    """If not admin, re-launch elevated and signal caller to exit.

    Returns:
      ``"already_admin"`` — continue running
      ``"relaunched"`` — elevated child started; current process should exit 0
      ``"skipped"`` — non-Windows or elevation disabled
      ``"failed:<reason>"`` — UAC cancelled or ShellExecute failed

    Set env ``RPT_NO_AUTO_ELEVATE=1`` to disable (tests / debugging).
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

    exe, params, cwd = launch_argv_for_elevation()
    # ShellExecute does not pass custom env; append flag so child can detect loops
    elev_flag = "--rpt-elevated"
    if elev_flag not in (params or ""):
        params = (params + " " + elev_flag).strip() if params else elev_flag

    if not cwd:
        try:
            cwd = str(repo_root_for_dev()) if not getattr(sys, "frozen", False) else str(
                Path(exe).resolve().parent
            )
        except Exception:
            cwd = os.getcwd()

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
