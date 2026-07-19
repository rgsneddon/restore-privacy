"""Linux privilege helpers for residual full tunnel (Ubuntu / Mint family)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import List, Optional


def is_root() -> bool:
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def _repo_root() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
    )


def elevate_env() -> dict:
    """Env for elevated child: keep DISPLAY/XAUTHORITY and PYTHONPATH (Ubuntu GUIs)."""
    env = os.environ.copy()
    root = _repo_root()
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = root + (os.pathsep + prev if prev else "")
    # Preserve GUI session for pkexec on Ubuntu desktops
    for key in ("DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def elevate_command(extra_args: Optional[List[str]] = None) -> List[str]:
    """Build a re-exec command under pkexec or sudo (does not run it)."""
    py = sys.executable
    args = [py, "-m", "client.linux"]
    if extra_args:
        args.extend(extra_args)
    root = _repo_root()
    pkexec = shutil.which("pkexec")
    if pkexec:
        # pkexec clears env; pass PYTHONPATH/DISPLAY explicitly
        return [
            pkexec,
            "env",
            f"PYTHONPATH={root}",
            f"DISPLAY={os.environ.get('DISPLAY', ':0')}",
            f"XAUTHORITY={os.environ.get('XAUTHORITY', '')}",
            *args,
        ]
    sudo = shutil.which("sudo")
    if sudo:
        return [sudo, "-E", f"PYTHONPATH={root}", *args]
    return args


def elevate_if_needed(*, extra_args: Optional[List[str]] = None) -> str:
    """Try to re-launch elevated. Returns status string for the UI.

    - ``already_root`` when euid==0
    - ``spawned`` when child launched (caller should exit)
    - ``failed:...`` when elevation unavailable
    """
    if is_root():
        return "already_root"
    if not sys.platform.startswith("linux"):
        return "failed:not_linux"
    cmd = elevate_command(extra_args=extra_args)
    if not cmd or cmd[0] == sys.executable:
        return "failed:no_pkexec_or_sudo"
    try:
        subprocess.Popen(
            cmd,
            cwd=_repo_root(),
            env=elevate_env(),
        )
        return "spawned"
    except Exception as exc:  # noqa: BLE001
        return f"failed:{exc}"


def should_exit_after_elevation(status: str) -> bool:
    return status == "spawned"
