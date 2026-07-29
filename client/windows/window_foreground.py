"""Windows product shell z-order / foreground policy (no permanent always-on-top).

Problem: Tk ``lift()`` + ``focus_force()`` alone often leave the main shell
buried under other apps after Settings/keygen close, tray Show, or long Connect
status updates. Windows also restricts ``SetForegroundWindow`` for background
threads.

Policy:
- Raise only when the window is still a *user-facing* shell (mapped/normal), or
  when *force_visible* (tray Show / explicit restore).
- Never force a withdrawn/iconified window forward unless force_visible.
- Prefer a **temporary** ``-topmost`` pulse (cleared on a timer), never leave
  permanent always-on-top.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

# Brief topmost pulse so Windows allows z-order change without sticky pin.
DEFAULT_TOPMOST_PULSE_MS = 120


@dataclass(frozen=True)
class ForegroundDecision:
    """Pure policy result for whether to raise a product window."""

    should_raise: bool
    reason: str
    force_visible: bool = False


def normalize_wm_state(state: str | None) -> str:
    """Normalize Tk ``wm_state`` / ``state()`` to a short token."""
    s = (state or "").strip().lower()
    if s in ("iconic", "icon", "minimized"):
        return "iconic"
    if s in ("withdrawn", "withdraw"):
        return "withdrawn"
    if s in ("zoomed", "maximize", "maximized"):
        return "zoomed"
    if s in ("normal", "", "interactive"):
        return "normal"
    return s or "normal"


def should_raise_window(
    *,
    viewable: bool,
    wm_state: str | None,
    force_visible: bool = False,
) -> ForegroundDecision:
    """Decide whether the product window may be brought forward.

    - *force_visible*: tray Show / explicit restore — deiconify + raise.
    - User-minimized (iconic) or tray-hidden (withdrawn) without force → no raise
      (user ordered the window away).
    - Visible normal/zoomed → raise allowed (in-app return to shell).
    """
    st = normalize_wm_state(wm_state)
    if force_visible:
        return ForegroundDecision(
            should_raise=True,
            reason="force_visible",
            force_visible=True,
        )
    if st == "withdrawn":
        return ForegroundDecision(
            should_raise=False,
            reason="withdrawn_user_tray",
            force_visible=False,
        )
    if st == "iconic":
        return ForegroundDecision(
            should_raise=False,
            reason="iconic_user_minimized",
            force_visible=False,
        )
    if not viewable:
        return ForegroundDecision(
            should_raise=False,
            reason="not_viewable",
            force_visible=False,
        )
    return ForegroundDecision(
        should_raise=True,
        reason="visible_active_shell",
        force_visible=False,
    )


def read_tk_window_state(win: Any) -> tuple[bool, str]:
    """Best-effort (viewable, wm_state) from a Tk widget. Fail-soft defaults."""
    viewable = True
    state = "normal"
    try:
        viewable = bool(win.winfo_viewable())
    except Exception:  # noqa: BLE001
        viewable = True
    try:
        # Tk: state() on root; wm_state on some platforms
        if hasattr(win, "state"):
            state = str(win.state() or "normal")
        elif hasattr(win, "wm_state"):
            state = str(win.wm_state() or "normal")
    except Exception:  # noqa: BLE001
        state = "normal"
    return viewable, normalize_wm_state(state)


def _clear_topmost(win: Any) -> None:
    try:
        win.attributes("-topmost", False)
    except Exception:  # noqa: BLE001
        pass


def _win32_set_foreground(win: Any) -> bool:
    """Best-effort Win32 foreground; never raises. Returns True if call ran."""
    try:
        import ctypes
        import sys

        if sys.platform != "win32":
            return False
        hwnd = int(win.winfo_id())
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        GA_ROOT = 2
        try:
            root_hwnd = int(user32.GetAncestor(hwnd, GA_ROOT) or hwnd)
        except Exception:  # noqa: BLE001
            root_hwnd = hwnd
        try:
            # ASFW_ANY = -1 — best-effort; may be ignored under UIPI.
            user32.AllowSetForegroundWindow(-1)
        except Exception:  # noqa: BLE001
            pass
        try:
            user32.ShowWindow(root_hwnd, 9)  # SW_RESTORE
        except Exception:  # noqa: BLE001
            pass
        return bool(user32.SetForegroundWindow(root_hwnd))
    except Exception:  # noqa: BLE001
        return False


def bring_tk_window_forward(
    win: Any,
    *,
    force_visible: bool = False,
    pulse_ms: int = DEFAULT_TOPMOST_PULSE_MS,
    after: Optional[Callable[[int, Callable[[], None]], Any]] = None,
) -> str:
    """Bring a Tk root/Toplevel forward without permanent always-on-top.

    Returns a short action note (``raised:<reason>``, ``skipped:<reason>``, …).
    *after* defaults to ``win.after`` for clearing the topmost pulse.
    """
    if win is None:
        return "skipped:no_window"
    try:
        if not win.winfo_exists():
            return "skipped:destroyed"
    except Exception:  # noqa: BLE001
        return "skipped:no_window"

    viewable, wm_state = read_tk_window_state(win)
    decision = should_raise_window(
        viewable=viewable,
        wm_state=wm_state,
        force_visible=bool(force_visible),
    )
    if not decision.should_raise:
        return f"skipped:{decision.reason}"

    try:
        if decision.force_visible or normalize_wm_state(wm_state) in (
            "iconic",
            "withdrawn",
        ):
            try:
                win.deiconify()
            except Exception:  # noqa: BLE001
                pass
        try:
            win.lift()
        except Exception:  # noqa: BLE001
            pass
        # Temporary topmost pulse (must clear — never leave permanent pin)
        pulse = max(0, int(pulse_ms))
        try:
            win.attributes("-topmost", True)
            try:
                win.update_idletasks()
            except Exception:  # noqa: BLE001
                pass
            schedule = after
            if schedule is None:
                schedule = getattr(win, "after", None)
            if pulse > 0 and callable(schedule):
                schedule(pulse, lambda w=win: _clear_topmost(w))
            else:
                _clear_topmost(win)
        except Exception:  # noqa: BLE001
            pass
        try:
            win.focus_force()
        except Exception:  # noqa: BLE001
            pass
        _win32_set_foreground(win)
        return f"raised:{decision.reason}"
    except Exception as exc:  # noqa: BLE001
        return f"error:{type(exc).__name__}"
