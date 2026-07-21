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
CURRENT_LICENCE_ID = "MIT-2026"

CONNECT_BLOCKED_LICENCE_MSG = (
    "Accept the end-user licence before connecting. "
    "Open Settings or the licence prompt, review the licence, then Accept."
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


def assert_may_connect(path: Optional[Path] = None) -> tuple[bool, str]:
    """Return ``(True, \"\")`` if Connect may proceed; else ``(False, message)``.

    Always re-checks payment entitlement (remote refresh when session id is
    known) so refunds / failed charges cancel Connect for that install.
    """
    if not has_accepted_licence(path):
        return False, CONNECT_BLOCKED_LICENCE_MSG
    from client.payment_entitlement import assert_payment_may_connect

    ok_pay, pay_msg = assert_payment_may_connect(refresh=True)
    if not ok_pay:
        return False, pay_msg
    return True, ""


def licence_url() -> str:
    return end_user_licence_url()


def licence_label() -> str:
    return END_USER_LICENCE_LABEL


def short_licence_summary() -> str:
    """Plain-language summary shown in the Accept dialog (not the full MIT text)."""
    from client.payment_entitlement import PAYMENT_CONNECT_DISCLAIMER_PLAIN

    return (
        "Restore Privacy is provided under the MIT licence and related third-party "
        "terms (see End user licence / LICENSE). By accepting, you agree to use the "
        "software under those terms. Acceptance is stored only on this device. "
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
