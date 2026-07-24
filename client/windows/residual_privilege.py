"""Residual privilege boundary for Windows product residual (honest).

Stock Windows cannot apply **Wintun + dual /1 residual routes** without a
privileged process somewhere. This module separates:

* **GUI process** — may stay a standard user day-to-day
* **Residual privilege** — Administrator (or a one-time-installed elevated
  helper task) when residual public IP must use the VPN node

There is **no** fully unprivileged residual path that stays residual-honest.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Scheduled task installed once (elevated) so Connect need not re-elevate the GUI.
RESIDUAL_HELPER_TASK = r"RestorePrivacy\ResidualConnect"
RESIDUAL_HELPER_TASK_LEGACY = "RestorePrivacyResidualConnect"

# User-visible (tests assert these builders / substrings)
MSG_RESIDUAL_NEEDS_PRIVILEGE = (
    "Residual public IP capture needs Administrator rights once "
    "(Wintun adapter + dual /1 routes). The app window can stay a normal user; "
    "approve UAC when Connect asks, or install the residual helper once."
)
MSG_ELEVATE_DISABLED = (
    "Residual Connect is blocked because automatic elevation is disabled "
    "(RPT_NO_AUTO_ELEVATE). Unset that env, approve UAC on Connect, or install "
    "the residual helper (one-time Administrator)."
)
MSG_UAC_CANCELLED = (
    "UAC was cancelled. Residual protection needs Administrator approval "
    "to change your public IP path. Press Connect again and choose Yes."
)
MSG_HELPER_MISSING = (
    "Install residual privilege once: Settings → install residual helper, "
    "or approve UAC when Connect prompts (no need to Run as administrator "
    "for the whole app every time)."
)
MSG_HELPER_READY = (
    "Residual helper is installed — Connect uses privileged residual without "
    "Run as administrator on the app shortcut."
)


def residual_requires_os_privilege() -> bool:
    """True: honest residual always needs privilege somewhere (not pure user-mode)."""
    return True


def gui_may_run_as_standard_user() -> bool:
    """Product shell (Tk) is allowed without elevating the whole process."""
    return True


def auto_elevate_disabled() -> bool:
    return os.environ.get("RPT_NO_AUTO_ELEVATE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def is_process_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        from client.windows.elevate import is_admin

        return bool(is_admin())
    except Exception:
        return False


def residual_helper_task_names() -> tuple[str, ...]:
    return (RESIDUAL_HELPER_TASK, RESIDUAL_HELPER_TASK_LEGACY)


def residual_helper_installed() -> bool:
    """True when the one-time residual Connect scheduled task is registered."""
    if sys.platform != "win32":
        return False
    for name in residual_helper_task_names():
        try:
            r = subprocess.run(
                ["schtasks", "/Query", "/TN", name],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if r.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            continue
    return False


def residual_privilege_available() -> bool:
    """True when residual capture can proceed without elevating *this* GUI process.

    Available if this process is already Administrator, or the residual helper
    task is installed (Connect will start residual via that task / elevation).
    """
    if is_process_admin():
        return True
    if residual_helper_installed():
        return True
    # Elevation can still be prompted (not "available without elevating GUI",
    # but residual is still possible). Callers use status() for nuance.
    return False


def residual_privilege_status() -> dict[str, Any]:
    """Structured residual privilege state for Connect / Settings / tests."""
    admin = is_process_admin()
    helper = residual_helper_installed()
    disabled = auto_elevate_disabled()
    if admin:
        mode = "already_admin"
        may_connect_without_gui_elevation = True
        message = "Running elevated — residual Connect can apply Wintun routes."
    elif helper:
        # Helper task carries residual privilege; GUI need not elevate.
        mode = "helper_installed"
        may_connect_without_gui_elevation = True
        message = MSG_HELPER_READY
    elif disabled:
        mode = "elevate_disabled"
        may_connect_without_gui_elevation = False
        message = MSG_ELEVATE_DISABLED
    else:
        mode = "needs_uac_on_connect"
        may_connect_without_gui_elevation = False
        message = MSG_RESIDUAL_NEEDS_PRIVILEGE
    return {
        "platform": sys.platform,
        "mode": mode,
        "process_is_admin": admin,
        "helper_installed": helper,
        "auto_elevate_disabled": disabled,
        "residual_requires_os_privilege": residual_requires_os_privilege(),
        "gui_may_run_as_standard_user": gui_may_run_as_standard_user(),
        "may_connect_without_gui_elevation": may_connect_without_gui_elevation,
        "message": message,
        "helper_task": RESIDUAL_HELPER_TASK,
    }


def residual_connect_block_message(status: dict[str, Any] | None = None) -> str:
    """User-visible block line when residual cannot start (actionable)."""
    st = status if isinstance(status, dict) else residual_privilege_status()
    mode = str(st.get("mode") or "")
    if mode == "elevate_disabled":
        return MSG_ELEVATE_DISABLED
    if mode == "needs_uac_on_connect":
        return MSG_HELPER_MISSING
    if mode == "helper_installed":
        return MSG_HELPER_READY
    return str(st.get("message") or MSG_RESIDUAL_NEEDS_PRIVILEGE)


def elevation_result_user_message(elevate_status: str) -> str:
    """Map elevate_if_needed() return → user-facing residual error."""
    s = (elevate_status or "").strip()
    if s == "skipped":
        return MSG_ELEVATE_DISABLED
    if s.startswith("failed:"):
        reason = s.split(":", 1)[-1]
        if "uac_cancelled" in reason or "1223" in reason:
            return MSG_UAC_CANCELLED
        return (
            f"{MSG_RESIDUAL_NEEDS_PRIVILEGE} "
            f"(elevation failed: {reason})"
        )
    if s == "relaunched":
        return "Approving UAC re-opens the app elevated to finish Connect…"
    return residual_connect_block_message()


def _launch_command_for_helper() -> tuple[str, str]:
    """Return (exe, arguments) for the residual Connect helper task."""
    from client.windows.elevate import launch_argv_for_elevation

    return launch_argv_for_elevation(
        extra_args=["--rpt-auto-connect", "--rpt-elevated"]
    )


def build_install_residual_helper_command() -> list[str]:
    """schtasks Create argv for one-time residual helper (must run elevated)."""
    exe, params = _launch_command_for_helper()
    # /TR wants a single command string
    tr = f'"{exe}" {params}'.strip() if params else f'"{exe}"'
    return [
        "schtasks",
        "/Create",
        "/TN",
        RESIDUAL_HELPER_TASK,
        "/TR",
        tr,
        "/SC",
        "ONCE",
        "/ST",
        "00:00",
        "/RL",
        "HIGHEST",
        "/F",
    ]


def install_residual_helper(*, dry_run: bool = False) -> dict[str, Any]:
    """Register one-time residual Connect helper task (requires Administrator).

    After install, standard-user GUI can start residual via
    :func:`run_residual_helper_connect` without "Run as administrator" on the
    desktop shortcut. Creating the task itself needs one elevated install step.
    """
    if sys.platform != "win32":
        return {"ok": False, "error": "not_windows"}
    cmd = build_install_residual_helper_command()
    if dry_run:
        return {"ok": True, "dry_run": True, "command": cmd, "task": RESIDUAL_HELPER_TASK}
    if not is_process_admin():
        return {
            "ok": False,
            "error": "admin_required",
            "detail": "Install residual helper once with Administrator (UAC).",
            "command": cmd,
            "task": RESIDUAL_HELPER_TASK,
        }
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": "schtasks_failed", "detail": str(exc), "command": cmd}
    ok = r.returncode == 0
    return {
        "ok": ok,
        "error": None if ok else "schtasks_nonzero",
        "returncode": r.returncode,
        "stdout": (r.stdout or "")[:500],
        "stderr": (r.stderr or "")[:500],
        "command": cmd,
        "task": RESIDUAL_HELPER_TASK,
        "helper_installed": residual_helper_installed() if ok else False,
    }


def run_residual_helper_connect() -> dict[str, Any]:
    """Start residual Connect via installed helper task (GUI stays non-admin)."""
    if sys.platform != "win32":
        return {"ok": False, "error": "not_windows"}
    if not residual_helper_installed():
        return {"ok": False, "error": "helper_not_installed", "message": MSG_HELPER_MISSING}
    last_err = ""
    for name in residual_helper_task_names():
        try:
            r = subprocess.run(
                ["schtasks", "/Run", "/TN", name],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            last_err = str(exc)
            continue
        if r.returncode == 0:
            return {
                "ok": True,
                "task": name,
                "message": "Residual helper started — finishing Connect elevated.",
            }
        last_err = (r.stderr or r.stdout or f"code={r.returncode}")[:300]
    return {"ok": False, "error": "helper_run_failed", "detail": last_err}


def product_connect_requires_admin_process() -> bool:
    """True when *this* process must be admin to apply residual now.

    False when already admin **or** residual helper can take residual work.
    """
    if is_process_admin():
        return False
    if residual_helper_installed():
        return False
    return residual_requires_os_privilege()
