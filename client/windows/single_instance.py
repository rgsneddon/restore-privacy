"""One Restore Privacy GUI unless elevated Connect handoff is allowed."""

from __future__ import annotations

import ctypes
from typing import Any

# Named mutex — process-local namespace so other users are not blocked.
MUTEX_NAME = "Local\\RestorePrivacyClientSingleInstance"

_MUTEX_HANDLE: Any = None


def single_instance_decision(
    *,
    mutex_owned: bool,
    allow_handoff: bool,
) -> tuple[bool, str]:
    """Pure: continue? + reason. Handoff always continues (elevated Connect)."""
    if allow_handoff:
        return True, "handoff"
    if mutex_owned:
        return False, "already_running"
    return True, "primary"


def _try_acquire_mutex() -> bool:
    """True when this process newly owns the product mutex."""
    global _MUTEX_HANDLE
    kernel32 = ctypes.windll.kernel32
    kernel32.SetLastError(0)
    handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    last = int(kernel32.GetLastError() or 0)
    if not handle:
        return False
    _MUTEX_HANDLE = handle
    # ERROR_ALREADY_EXISTS
    return last != 183


def _activate_existing_window(window_title: str) -> None:
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, window_title)
    if not hwnd:
        return
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)


def guard_single_instance_or_activate(
    *,
    window_title: str,
    allow_handoff: bool = False,
) -> tuple[bool, str]:
    """Keep one GUI; second launch focuses the existing window and exits.

    ``allow_handoff`` is True for ``--rpt-auto-connect`` / ``--rpt-elevated``
    so UAC residual Connect can start the elevated child while the parent exits.
    """
    owned = False
    try:
        owned = not _try_acquire_mutex()
    except Exception:
        owned = False
    cont, reason = single_instance_decision(
        mutex_owned=owned, allow_handoff=bool(allow_handoff)
    )
    if not cont:
        try:
            _activate_existing_window(window_title)
        except Exception:
            pass
    return cont, reason
