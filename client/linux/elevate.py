"""Linux privilege helpers for residual full tunnel (Mint / Ubuntu)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Optional


def is_root() -> bool:
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def elevate_command(extra_args: Optional[list[str]] = None) -> list[str]:
    """Build a re-exec command under pkexec or sudo (does not run it)."""
    py = sys.executable
    # Prefer module entry so install layout works
    args = [py, "-m", "client.linux"]
    if extra_args:
        args.extend(extra_args)
    pkexec = shutil.which("pkexec")
    if pkexec:
        return [pkexec, *args]
    sudo = shutil.which("sudo")
    if sudo:
        return [sudo, "-E", *args]
    return args


def elevate_if_needed(*, extra_args: Optional[list[str]] = None) -> str:
    """Try to re-launch elevated. Returns status string for the UI.

    - ``already_root`` when euid==0
    - ``spawned`` when child launched (caller should exit)
    - ``failed:...`` when elevation unavailable
    """
    if is_root():
        return "already_root"
    if sys.platform != "linux":
        return "failed:not_linux"
    cmd = elevate_command(extra_args=extra_args)
    if cmd[0] == sys.executable:
        return "failed:no_pkexec_or_sudo"
    try:
        subprocess.Popen(cmd, cwd=os.getcwd())
        return "spawned"
    except Exception as exc:  # noqa: BLE001
        return f"failed:{exc}"


def should_exit_after_elevation(status: str) -> bool:
    return status == "spawned"
