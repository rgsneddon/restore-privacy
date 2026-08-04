"""Local KEYGEN-free residual trial (72 hours) — pure durable policy.

Product rule (Windows residual first-run step 2):
- User may **continue trial** after licence acceptance without a KEYGEN.
- The 72-hour clock starts at the first **successful residual Connect**
  (not on button click alone).
- Until that first Connect, remaining time is the full 72h window.
- After expiry without a paid KEYGEN unlock, Connect and Settings entry
  require a KEYGEN (buy/pay link on step 2).

Stored only on device under the product data dir (same family as licence /
settings). Remaining-time display is local; **node residual HELLO** also needs
a status-host trial row (see :func:`claim_remote_device_trial`) because fleet
nodes gate HELLO via ``GET /api/device-entitlement`` (paid bind **or** active
host trial). Without the remote claim, the node silent-drops HELLO and the
client surfaces a UDP timeout — the free-trial “no reply from VPN node” bug.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional

# Continuous residual trial window (3 days).
TRIAL_SECONDS = 72 * 3600
TRIAL_FILENAME = "device_trial.json"
KEY_FIRST_CONNECT_AT = "first_connect_at"
# Durable install marker (anti-reinstall on status host). Same privacy class as
# Flutter SharedPreferences install_id — not a KEYGEN, not PII.
INSTALL_ID_FILENAME = "device_trial_install_id.txt"
KEY_INSTALL_ID = "install_id"

TrialPhase = Literal["not_started", "active", "expired"]

# Clear copy when host trial cannot admit residual HELLO.
REMOTE_TRIAL_CLAIM_FAILED_MSG = (
    "Free trial could not register this device with the status host, so the "
    "VPN node will not admit residual Connect. Check internet access to "
    "restoreprivacy.online, try Connect again, or enter a KEYGEN from your "
    "fulfilment email (Settings → Payment entitlement / keygen)."
)
REMOTE_TRIAL_EXHAUSTED_MSG = (
    "Your free residual trial has ended on this device. Enter a KEYGEN from "
    "your fulfilment email (Settings → Payment entitlement / keygen) or buy "
    "a plan on restoreprivacy.online/pay."
)


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


def default_install_id_path() -> Path:
    return trial_data_dir() / INSTALL_ID_FILENAME


def ensure_device_trial_install_id(path: Optional[Path] = None) -> str:
    """Return durable install marker (create once). Used for host anti-reinstall."""
    p = path or default_install_id_path()
    try:
        if p.is_file():
            raw = (p.read_text(encoding="utf-8") or "").strip().lower()
            if 8 <= len(raw) <= 64:
                return raw
    except OSError:
        pass
    iid = uuid.uuid4().hex
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(iid + "\n", encoding="utf-8")
    except OSError:
        pass
    return iid


def claim_remote_device_trial(
    *,
    device_pub_hex: str | None = None,
    install_id: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    urlopen: Any | None = None,
) -> dict[str, Any]:
    """POST ``/api/device-trial/claim`` so residual HELLO is admitted without KEYGEN.

    Fleet nodes call ``GET /api/device-entitlement?device_pub=…`` and silent-drop
    CLIENT_HELLO when ``connect_allowed`` is false. Desktop must claim the host
    trial before HELLO (Flutter already does). Local 72h clock still starts only
    on first successful residual Connect via :func:`mark_first_successful_connect`.
    """
    pub = (device_pub_hex or "").strip().lower()
    if not pub:
        try:
            from client.payment_entitlement import local_device_pub_hex

            pub = (local_device_pub_hex() or "").strip().lower()
        except Exception:  # noqa: BLE001
            pub = ""
    if len(pub) != 64:
        return {
            "ok": False,
            "connect_allowed": False,
            "error": "missing_device_pub",
        }

    base = (base_url or os.environ.get("RPT_PUBLIC_BASE_URL") or "").strip()
    if not base:
        base = "https://restoreprivacy.online"
    base = base.rstrip("/")
    try:
        from client.payment_entitlement import status_host_timeout_s

        default_to = float(status_host_timeout_s())
    except Exception:  # noqa: BLE001
        default_to = 12.0
    to = float(timeout) if timeout is not None else default_to

    iid = (install_id or "").strip().lower()
    if not iid:
        iid = ensure_device_trial_install_id()

    url = f"{base}/api/device-trial/claim"
    payload: dict[str, Any] = {"device_pub": pub}
    if iid:
        payload["install_id"] = iid
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": "RestorePrivacy-device-trial/1.1.9",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    open_url = urlopen or urllib.request.urlopen
    try:
        with open_url(req, timeout=to) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        if isinstance(data, dict):
            # Normalise ok flag for callers
            allowed = bool(data.get("connect_allowed")) or bool(data.get("ok"))
            out = dict(data)
            out["ok"] = allowed
            out["connect_allowed"] = bool(data.get("connect_allowed", allowed))
            return out
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        return {"ok": False, "connect_allowed": False, "error": str(exc)}
    return {"ok": False, "connect_allowed": False, "error": "bad_response"}


def ensure_remote_trial_for_node_hello(
    *,
    path: Optional[Path] = None,
    base_url: str | None = None,
    claim: Any | None = None,
    device_pub_hex: str | None = None,
) -> tuple[bool, str]:
    """When local trial allows residual Connect, ensure status-host trial row.

    Returns ``(True, \"\")`` when the host reports ``connect_allowed`` for trial
    (create or reuse). Paid KEYGEN path is **not** handled here — callers that
    already have payment entitlement should skip this.

    Returns ``(False, message)`` when claim is exhausted or network fails so
    Connect can fail closed with a clear message instead of a HELLO timeout.
    """
    if not trial_allows_residual_connect(path=path):
        return False, REMOTE_TRIAL_EXHAUSTED_MSG

    claim_fn = claim if callable(claim) else claim_remote_device_trial
    try:
        remote = claim_fn(device_pub_hex=device_pub_hex, base_url=base_url)
    except Exception as exc:  # noqa: BLE001
        return False, f"{REMOTE_TRIAL_CLAIM_FAILED_MSG} ({exc})"

    if not isinstance(remote, dict):
        return False, REMOTE_TRIAL_CLAIM_FAILED_MSG

    if bool(remote.get("connect_allowed")) or bool(remote.get("ok")):
        return True, ""

    err = str(remote.get("error") or "").strip().lower()
    if err in ("trial_exhausted", "exhausted") or str(
        remote.get("status") or ""
    ).strip().lower() in ("expired", "revoked"):
        return False, REMOTE_TRIAL_EXHAUSTED_MSG

    detail = str(remote.get("error") or remote.get("reason") or "").strip()
    if detail:
        return False, f"{REMOTE_TRIAL_CLAIM_FAILED_MSG} ({detail})"
    return False, REMOTE_TRIAL_CLAIM_FAILED_MSG
