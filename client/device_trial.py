"""Local KEYGEN-free residual trial (72 hours) — pure durable policy.

Product rule (Windows residual first-run step 2):
- User may **continue trial** after licence acceptance without a KEYGEN.
- The 72-hour clock starts at the first **successful residual Connect**
  (not on button click alone).
- Until that first Connect, remaining time is the full 72h window.
- After expiry without a paid KEYGEN unlock, Connect and Settings entry
  require a KEYGEN (buy/pay link on step 2).

Stored only on device under the product data dir (same family as licence /
settings). No network required for remaining-time display.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional

# Continuous residual trial window (3 days).
TRIAL_SECONDS = 72 * 3600
TRIAL_FILENAME = "device_trial.json"
KEY_FIRST_CONNECT_AT = "first_connect_at"

TrialPhase = Literal["not_started", "active", "expired"]


@dataclass(frozen=True)
class DeviceTrialState:
    """Durable trial clock origin (None = never successfully connected)."""

    first_connect_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            KEY_FIRST_CONNECT_AT: (
                float(self.first_connect_at)
                if self.first_connect_at is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeviceTrialState":
        raw = data.get(KEY_FIRST_CONNECT_AT)
        if raw is None or raw == "" or raw is False:
            return cls(first_connect_at=None)
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return cls(first_connect_at=None)
        if v <= 0:
            return cls(first_connect_at=None)
        return cls(first_connect_at=v)


def trial_data_dir() -> Path:
    """Same product local data family as licence / settings / connection log."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(
            Path.home() / "AppData" / "Local"
        )
        return Path(base) / "RestorePrivacy"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "restore-privacy"
    return Path.home() / ".local" / "share" / "restore-privacy"


def default_trial_path() -> Path:
    return trial_data_dir() / TRIAL_FILENAME


def load_device_trial(path: Optional[Path] = None) -> DeviceTrialState:
    p = path or default_trial_path()
    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return DeviceTrialState()
        return DeviceTrialState.from_dict(data)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return DeviceTrialState()


def save_device_trial(
    state: DeviceTrialState, path: Optional[Path] = None
) -> Path:
    p = path or default_trial_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    return p


def clear_device_trial(path: Optional[Path] = None) -> None:
    """Tests / user reset — wipe trial clock."""
    p = path or default_trial_path()
    try:
        if p.is_file():
            p.unlink()
    except OSError:
        pass


def trial_phase(
    state: DeviceTrialState | None = None,
    *,
    now: float | None = None,
    duration_sec: float = TRIAL_SECONDS,
    path: Optional[Path] = None,
) -> TrialPhase:
    """not_started | active | expired (pure clock)."""
    st = state if state is not None else load_device_trial(path)
    t = float(now if now is not None else time.time())
    if st.first_connect_at is None:
        return "not_started"
    ends = float(st.first_connect_at) + float(duration_sec)
    if t < ends:
        return "active"
    return "expired"


def trial_remaining_sec(
    state: DeviceTrialState | None = None,
    *,
    now: float | None = None,
    duration_sec: float = TRIAL_SECONDS,
    path: Optional[Path] = None,
) -> float:
    """Seconds left in the free trial window.

    Before first successful Connect: full *duration_sec*.
    After start: max(0, ends - now).
    """
    st = state if state is not None else load_device_trial(path)
    t = float(now if now is not None else time.time())
    dur = float(duration_sec)
    if st.first_connect_at is None:
        return max(0.0, dur)
    ends = float(st.first_connect_at) + dur
    return max(0.0, ends - t)


def trial_allows_residual_connect(
    state: DeviceTrialState | None = None,
    *,
    now: float | None = None,
    duration_sec: float = TRIAL_SECONDS,
    path: Optional[Path] = None,
) -> bool:
    """True while trial not expired (includes not-yet-started clock)."""
    return trial_phase(
        state, now=now, duration_sec=duration_sec, path=path
    ) != "expired"


def mark_first_successful_connect(
    *,
    now: float | None = None,
    path: Optional[Path] = None,
) -> DeviceTrialState:
    """Start the 72h clock on first successful residual Connect only.

    Idempotent: later Connects do not move *first_connect_at*.
    """
    p = path or default_trial_path()
    st = load_device_trial(p)
    if st.first_connect_at is not None:
        return st
    t = float(now if now is not None else time.time())
    out = DeviceTrialState(first_connect_at=t)
    save_device_trial(out, path=p)
    return out


def format_trial_remaining(
    remaining_sec: float,
    *,
    phase: TrialPhase | None = None,
) -> str:
    """Short user-facing remaining string for step 2."""
    r = max(0.0, float(remaining_sec))
    if phase == "expired" or r <= 0:
        return "Trial ended — enter a KEYGEN to continue."
    if phase == "not_started":
        # Clock has not begun; show full window + start rule
        hours = int(TRIAL_SECONDS // 3600)
        return (
            f"{hours} hours free trial available "
            "(timer starts on your first successful Connect)."
        )
    total = int(r)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m remaining on your free trial."
    if hours > 0:
        return f"{hours}h {minutes}m remaining on your free trial."
    return f"{minutes}m remaining on your free trial."


def trial_status_blurb(
    state: DeviceTrialState | None = None,
    *,
    now: float | None = None,
    path: Optional[Path] = None,
) -> str:
    """One-line blurb for step 2 time-left label."""
    st = state if state is not None else load_device_trial(path)
    phase = trial_phase(st, now=now, path=path)
    rem = trial_remaining_sec(st, now=now, path=path)
    return format_trial_remaining(rem, phase=phase)
