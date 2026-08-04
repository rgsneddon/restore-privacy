"""Local end-user licence acceptance gate (must accept before Connect).

Acceptance is stored only on the device. This module never uploads acceptance
state to the node, VPN APP Shop, or any remote collector. Autoconnect and manual
Connect both call :func:`may_connect` / :func:`assert_may_connect`.
"""

from __future__ import annotations

import ast
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from client.legal_links import END_USER_LICENCE_LABEL, end_user_licence_url

LICENCE_FILENAME = "licence_acceptance.json"
KEY_ACCEPTED = "licence_accepted"
KEY_ACCEPTED_AT = "licence_accepted_at"
KEY_LICENCE_ID = "licence_id"

# Bump when product licence terms change and re-acceptance is required.
CURRENT_LICENCE_ID = "FULL-COPYRIGHT-2026"

CONNECT_BLOCKED_LICENCE_MSG = (
    "Accept the end-user licence before connecting. "
    "Open Settings or the licence prompt, review the licence, then Accept. "
    "After accepting, enter the keygen from your fulfilment email to unlock."
)

LICENCE_PROMPT_TITLE = "End-user licence"
LICENCE_ACCEPT_BUTTON = "Accept licence"
LICENCE_DECLINE_HINT = "You can use Settings later; Connect stays blocked until you accept."


@dataclass(frozen=True)
class LicenceAcceptance:
    accepted: bool = False
    accepted_at: float = 0.0
    licence_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            KEY_ACCEPTED: bool(self.accepted),
            KEY_ACCEPTED_AT: float(self.accepted_at),
            KEY_LICENCE_ID: str(self.licence_id or ""),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LicenceAcceptance":
        return cls(
            accepted=bool(data.get(KEY_ACCEPTED, False)),
            accepted_at=float(data.get(KEY_ACCEPTED_AT) or 0.0),
            licence_id=str(data.get(KEY_LICENCE_ID) or ""),
        )


def licence_data_dir() -> Path:
    """Same product local data family as settings / connection log."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(
            Path.home() / "AppData" / "Local"
        )
        return Path(base) / "RestorePrivacy"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "restore-privacy"
    return Path.home() / ".local" / "share" / "restore-privacy"


def default_licence_path() -> Path:
    return licence_data_dir() / LICENCE_FILENAME


def load_licence_acceptance(path: Optional[Path] = None) -> LicenceAcceptance:
    p = path or default_licence_path()
    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return LicenceAcceptance()
        return LicenceAcceptance.from_dict(data)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return LicenceAcceptance()


def save_licence_acceptance(
    state: LicenceAcceptance, path: Optional[Path] = None
) -> Path:
    p = path or default_licence_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    return p


def has_accepted_licence(
    path: Optional[Path] = None,
    *,
    required_id: str = CURRENT_LICENCE_ID,
) -> bool:
    """True when local store records acceptance of the current licence id."""
    st = load_licence_acceptance(path)
    if not st.accepted:
        return False
    # Empty licence_id from older drafts: treat as not current.
    if required_id and st.licence_id and st.licence_id != required_id:
        return False
    if required_id and not st.licence_id:
        return False
    return True


def accept_licence(
    path: Optional[Path] = None,
    *,
    licence_id: str = CURRENT_LICENCE_ID,
    ts: Optional[float] = None,
) -> LicenceAcceptance:
    """Record local acceptance (user-initiated). Returns saved state."""
    state = LicenceAcceptance(
        accepted=True,
        accepted_at=float(ts if ts is not None else time.time()),
        licence_id=str(licence_id or CURRENT_LICENCE_ID),
    )
    save_licence_acceptance(state, path=path)
    return state


def clear_licence_acceptance(path: Optional[Path] = None) -> None:
    """Revoke local acceptance (tests / user reset)."""
    p = path or default_licence_path()
    try:
        if p.is_file():
            p.unlink()
    except OSError:
        pass
    # Also write explicit false for clarity if parent exists
    try:
        save_licence_acceptance(LicenceAcceptance(), path=path)
    except OSError:
        pass


def may_connect(path: Optional[Path] = None, *, refresh_payment: bool = False) -> bool:
    """Product Connect gate: licence + (paid KEYGEN **or** free trial window).

    Payment **failed / revoked / unpaid** always blocks Connect — free trial
    does **not** override a blocking entitlement status. Free trial only
    covers “no KEYGEN yet” (unknown/empty/session-only), with the 72h clock
    from first successful residual Connect (see :mod:`client.device_trial`).
    """
    if not has_accepted_licence(path):
        return False
    from client.device_trial import trial_allows_residual_connect
    from client.payment_entitlement import (
        assert_payment_may_connect,
        is_payment_blocking_status,
        load_payment_entitlement,
        payment_allows_connect,
    )

    if refresh_payment:
        ok, _ = assert_payment_may_connect(refresh=True)
        if ok:
            return True
        ent = load_payment_entitlement()
        if is_payment_blocking_status(ent.status):
            return False
        return trial_allows_residual_connect()
    if payment_allows_connect():
        return True
    ent = load_payment_entitlement()
    if is_payment_blocking_status(ent.status):
        return False
    return trial_allows_residual_connect()


def assert_may_connect(
    path: Optional[Path] = None,
    *,
    refresh: bool | None = None,
) -> tuple[bool, str]:
    """Return ``(True, \"\")`` if Connect may proceed; else ``(False, message)``.

    Payment entitlement: remote refresh when needed for cold path / near
    expiry (see :func:`client.payment_entitlement.connect_status_host_refresh_needed`).
    Pass ``refresh=True`` to force status-host re-check (e.g. Settings verify).

    Free trial (72h from first successful residual Connect) allows Connect
    without KEYGEN **only when payment is not failed/revoked/unpaid**.
    """
    if not has_accepted_licence(path):
        return False, CONNECT_BLOCKED_LICENCE_MSG
    from client.device_trial import trial_allows_residual_connect
    from client.payment_entitlement import (
        assert_payment_may_connect,
        is_payment_blocking_status,
        load_payment_entitlement,
    )

    # Payment store is always the product entitlement path (not licence path).
    ok_pay, pay_msg = assert_payment_may_connect(refresh=refresh)
    if ok_pay:
        return True, ""
    # Revoked / failed / unpaid: never fall through to free trial
    ent = load_payment_entitlement()
    if is_payment_blocking_status(ent.status):
        return False, pay_msg
    if trial_allows_residual_connect():
        return True, ""
    return False, pay_msg


def needs_licence_renewal(path: Optional[Path] = None) -> bool:
    """True when licence is accepted but subscription is EXPIRED (renew, not keygen).

    Local-only: true for failed / revoked / unpaid status, or an active grant
    whose ``valid_until`` has passed. Does **not** fire for active installs
    that still need a keygen entry (use :func:`needs_keygen_unlock`).

    ``path`` is the **licence** acceptance path only.
    """
    if not has_accepted_licence(path):
        return False
    from client.payment_entitlement import (
        LICENCE_STATUS_EXPIRED,
        load_payment_entitlement,
        is_payment_blocking_status,
        licence_status_from_payment_entitlement,
        has_keygen_unlock,
    )

    ent = load_payment_entitlement()
    if is_payment_blocking_status(ent.status):
        return True
    # Period ended (keygen already on file) — renew, do not re-prompt keygen
    if has_keygen_unlock(ent) and (
        licence_status_from_payment_entitlement(ent) == LICENCE_STATUS_EXPIRED
    ):
        return True
    return False


def needs_keygen_unlock(path: Optional[Path] = None) -> bool:
    """True when KEYGEN is **mandatory** (trial expired / no free residual left).

    Used by Windows UI to refuse dismissing step 2 without a KEYGEN and to
    block residual Connect after trial end.

    Local-only (no network):
    - False when licence not accepted (licence surface first)
    - False when payment is blocking (renew surface — see
      :func:`needs_licence_renewal`)
    - False when durable ``RPT-KEY-…`` unlock is on file
    - False while free trial is not_started or active (Continue trial OK)
    - True only when free trial is **expired** and no KEYGEN unlock

    Step 2 may still be *shown* while trial is available (time-left + optional
    KEYGEN) — that is :func:`client.first_run_flow.needs_step2_trial_keygen_surface`,
    not this helper.

    **Upgrade rollover:** package version / ``client/VERSION`` is never read
    here. Durable ``licence_acceptance.json`` + ``payment_entitlement.json``
    under the product data dir survive install-over-install; an active keygen
    on file continues to unlock without re-accept or re-paste after upgrade.

    ``path`` is the **licence** acceptance path only.
    """
    if not has_accepted_licence(path):
        return False
    if needs_licence_renewal(path):
        return False
    from client.payment_entitlement import has_keygen_unlock, payment_allows_connect

    if payment_allows_connect() or has_keygen_unlock():
        return False
    from client.device_trial import trial_allows_residual_connect

    # Free trial still open → KEYGEN not mandatory
    if trial_allows_residual_connect():
        return False
    return True


def licence_url() -> str:
    return end_user_licence_url()


def licence_label() -> str:
    return END_USER_LICENCE_LABEL


def short_licence_summary() -> str:
    """Plain-language summary shown in the Accept dialog (not the full licence text)."""
    from client.payment_entitlement import PAYMENT_CONNECT_DISCLAIMER_PLAIN

    return (
        "Restore Privacy is proprietary full copyright: client packages may be "
        "used only to run a device with residual VPN Connect, with no warranty (AS IS). "
        "Copy or transmission of the product architecture is not permitted. "
        "Third-party components keep their own licences (see LICENSE / CREDITS). "
        "By accepting, you agree to those terms. Acceptance is stored only on this device. "
        "Residual Connect includes a free 3-day (72-hour) trial on this device "
        "(no card required). After the trial ends, enter a KEYGEN from /pay "
        "(£3.00 per month or £30.00 per year — USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY). "
        "Business-Class options require a separate £3000 deposit — they are not free. "
        + PAYMENT_CONNECT_DISCLAIMER_PLAIN
    )


def licence_gate_is_local_only() -> bool:
    """Structural honesty: this module must not import network upload clients."""
    src = Path(__file__).read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    banned = {"urllib", "requests", "httpx", "socket", "aiohttp", "ftplib"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".", 1)[0] in banned:
                    return False
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".", 1)[0] in banned:
                return False
    low = src.lower()
    return "local" in low and ("never upload" in low or "only on the device" in low)
