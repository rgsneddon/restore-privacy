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
    """Product Connect gate: licence accepted **and** payment entitlement allows.

    Payment failure / revoked entitlement always blocks Connect (see
    :mod:`client.payment_entitlement`). UI badges use local cache only
    (``refresh_payment=False``). The Connect entry path uses
    :func:`assert_may_connect`, which refreshes remote entitlement.
    """
    if not has_accepted_licence(path):
        return False
    from client.payment_entitlement import (
        assert_payment_may_connect,
        payment_allows_connect,
    )

    if refresh_payment:
        ok, _ = assert_payment_may_connect(refresh=True)
        return ok
    return payment_allows_connect()


def assert_may_connect(
    path: Optional[Path] = None,
    *,
    refresh: bool | None = None,
) -> tuple[bool, str]:
    """Return ``(True, \"\")`` if Connect may proceed; else ``(False, message)``.

    Payment entitlement: remote refresh when needed for cold path / near
    expiry (see :func:`client.payment_entitlement.connect_status_host_refresh_needed`).
    Pass ``refresh=True`` to force status-host re-check (e.g. Settings verify).
    """
    if not has_accepted_licence(path):
        return False, CONNECT_BLOCKED_LICENCE_MSG
    from client.payment_entitlement import assert_payment_may_connect

    # Payment store is always the product entitlement path (not licence path).
    ok_pay, pay_msg = assert_payment_may_connect(refresh=refresh)
    if not ok_pay:
        return False, pay_msg
    return True, ""


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
    """True when licence is accepted but a keygen entry is still required.

    Used by Windows (and other) UI to force a keygen entry surface before
    residual Connect — not Settings-only.

    Local-only (no network): true when licence is accepted,
    subscription is **not** EXPIRED (see :func:`needs_licence_renewal`), and
    :func:`client.payment_entitlement.payment_allows_connect` is false —
    including active session/thank-you file **without** a ``RPT-KEY-…``
    keygen unlock on file.

    Returns **False** when payment is blocking (failed/revoked/unpaid) so the
    UI shows the renew-licence surface instead of the keygen modal.

    **Upgrade rollover:** package version / ``client/VERSION`` is never read
    here. Durable ``licence_acceptance.json`` + ``payment_entitlement.json``
    under the product data dir survive install-over-install; an active keygen
    on file continues to unlock without re-accept or re-paste after upgrade.

    ``path`` is the **licence** acceptance path only (same as
    :func:`has_accepted_licence`). Payment entitlement is always read from the
    product entitlement path — do not pass the licence file into
    :func:`~client.payment_entitlement.payment_allows_connect`.
    """
    if not has_accepted_licence(path):
        return False
    if needs_licence_renewal(path):
        return False
    from client.payment_entitlement import payment_allows_connect

    # Durable product-data entitlement path (not install tree) — version bump
    # does not clear keygen; payment_allows_connect reads that store only.
    return not payment_allows_connect()


def licence_url() -> str:
    return end_user_licence_url()


def licence_label() -> str:
    return END_USER_LICENCE_LABEL


def short_licence_summary() -> str:
    """Plain-language summary shown in the Accept dialog (not the full licence text)."""
    from client.payment_entitlement import PAYMENT_CONNECT_DISCLAIMER_PLAIN

    return (
        "Restore Privacy is proprietary full copyright: client packages may be used "
        "only to run a device on the Restore Privacy VPN, with no warranty (AS IS). "
        "Copy or transmission of the product architecture is not permitted. "
        "Third-party components keep their own licences (see LICENSE / CREDITS). "
        "By accepting, you agree to those terms. Acceptance is stored only on this device. "
        "After you accept, enter the keygen from your fulfilment email "
        "(USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY) to unlock Connect. "
        "Your subscription (£3.00 per month or £30.00 per year) includes a 3-day free trial — "
        "no money is taken until after the trial ends. "
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
