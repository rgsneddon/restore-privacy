"""Run child processes without flashing a console window (Windows).

Connect residual steps (PowerShell IPv6 disable, firewall allows, netsh, kill
switch) previously used ``shell=True`` / bare ``powershell`` which can flash a
console. This helper always:

* hides the window (``SW_HIDE`` + ``CREATE_NO_WINDOW`` on Windows)
* uses ``DEVNULL`` for stdin
* keeps capture_output for callers that parse stdout

Non-Windows: normal ``subprocess.run`` with capture.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any, Mapping, Optional, Sequence, Union

# Win32 process creation: no console window for the child
CREATE_NO_WINDOW = 0x08000000
SW_HIDE = 0


def powershell_quiet_prefix() -> str:
    """Argv prefix for a fast, non-interactive, hidden PowerShell host."""
    return (
        "powershell -NoLogo -NoProfile -NonInteractive -WindowStyle Hidden "
        "-ExecutionPolicy Bypass"
    )


def windows_hidden_popen_kwargs() -> dict[str, Any]:
    """Kwargs for subprocess on Windows so no console is shown."""
    if sys.platform != "win32":
        return {"stdin": subprocess.DEVNULL}
    # STARTUPINFO + CREATE_NO_WINDOW — double coverage for shell=True and list argv
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = SW_HIDE
    return {
        "stdin": subprocess.DEVNULL,
        "startupinfo": si,
        "creationflags": CREATE_NO_WINDOW,
    }


def run_hidden(
    args: Union[str, Sequence[str]],
    *,
    shell: bool = False,
    timeout: Optional[float] = None,
    text: bool = True,
    check: bool = False,
    env: Optional[Mapping[str, str]] = None,
    cwd: Optional[str] = None,
    **extra: Any,
) -> subprocess.CompletedProcess:
    """``subprocess.run`` with a hidden window on Windows (quick, no flash)."""
    kw: dict[str, Any] = {
        "args": args,
        "shell": shell,
        "capture_output": True,
        "text": text,
        "check": check,
    }
    if timeout is not None:
        kw["timeout"] = timeout
    if env is not None:
        kw["env"] = env
    if cwd is not None:
        kw["cwd"] = cwd
    kw.update(windows_hidden_popen_kwargs())
    # Caller extras win for rare overrides (but keep no-window defaults)
    for k, v in extra.items():
        if k in ("startupinfo", "creationflags", "stdin") and sys.platform == "win32":
            continue  # do not allow re-showing the console
        kw[k] = v
    return subprocess.run(**kw)
