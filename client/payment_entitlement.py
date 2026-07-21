"""Payment entitlement for Connect — observe paid status; block on failure.

Successful Stripe fulfilment grants a **connect entitlement** bound to the
Checkout ``session_id``. Failed payment, refund, dispute, or explicit revoke
sets status to ``failed`` / ``revoked`` and **Connect is blocked** for that
install until a new successful payment is completed.

Local cache under the product data dir; optional refresh from the status host
``/api/connect-entitlement``. Node residual still uses device crypto; this gate
is enforced on every product Connect entry path.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Local entitlement file (same data family as licence acceptance)
ENTITLEMENT_FILENAME = "payment_entitlement.json"
KEY_SESSION_ID = "session_id"
KEY_STATUS = "status"
KEY_PLATFORM = "platform"
KEY_REASON = "reason"
KEY_UPDATED_AT = "updated_at"

STATUS_ACTIVE = "active"
STATUS_FAILED = "failed"
STATUS_REVOKED = "revoked"
STATUS_UNKNOWN = "unknown"
STATUS_UNPAID = "unpaid"

CONNECT_BLOCKED_PAYMENT_MSG = (
    "Connect is blocked: payment failed or entitlement was revoked for this "
    "install. Successful payment is required. If payment fails at any time "
    "(checkout failure, failed charge, refund, or dispute), the ability to "
    "Connect with the Restore Privacy app is cancelled until you complete a "
    "successful payment again on https://restoreprivacy.online/"
)

# Strong disclaimer for README / portal / privacy / licence surfaces
PAYMENT_CONNECT_DISCLAIMER = (
    "**STRONG DISCLAIMER — PAYMENT REQUIRED FOR CONNECT:** Access to Connect "
    "and residual VPN use requires **successful payment**. If payment **fails "
    "at any time** (failed checkout, failed charge, refund, dispute, or "
    "revoked entitlement), the ability to **Connect with the Restore Privacy "
    "app is cancelled** for that purchase/install until a successful payment "
    "is completed."
)

PAYMENT_CONNECT_DISCLAIMER_PLAIN = (
    "STRONG DISCLAIMER — PAYMENT REQUIRED FOR CONNECT: Access to Connect and "
    "residual VPN use requires successful payment. If payment fails at any "
    "time (failed checkout, failed charge, refund, dispute, or revoked "
    "entitlement), the ability to Connect with the Restore Privacy app is "
    "cancelled for that purchase/install until a successful payment is completed."
)


@dataclass(frozen=True)
class PaymentEntitlement:
    session_id: str = ""
    status: str = STATUS_UNKNOWN
    platform: str = ""
    reason: str = ""
    updated_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            KEY_SESSION_ID: str(self.session_id or ""),
            KEY_STATUS: str(self.status or STATUS_UNKNOWN),
            KEY_PLATFORM: str(self.platform or ""),
            KEY_REASON: str(self.reason or ""),
            KEY_UPDATED_AT: float(self.updated_at or 0.0),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PaymentEntitlement":
        return cls(
            session_id=str(data.get(KEY_SESSION_ID) or ""),
            status=str(data.get(KEY_STATUS) or STATUS_UNKNOWN).strip().lower(),
            platform=str(data.get(KEY_PLATFORM) or ""),
            reason=str(data.get(KEY_REASON) or ""),
            updated_at=float(data.get(KEY_UPDATED_AT) or 0.0),
        )


def entitlement_data_dir() -> Path:
    """Same product local data family as licence / settings."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(
            Path.home() / "AppData" / "Local"
        )
        return Path(base) / "RestorePrivacy"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "restore-privacy"
    return Path.home() / ".local" / "share" / "restore-privacy"


def default_entitlement_path() -> Path:
    return entitlement_data_dir() / ENTITLEMENT_FILENAME


def payment_entitlement_required() -> bool:
    """Product default: require non-failed payment entitlement for Connect.

    Operators / self-host may set ``RPT_REQUIRE_PAYMENT_ENTITLEMENT=0``.
    """
    raw = os.environ.get("RPT_REQUIRE_PAYMENT_ENTITLEMENT", "1").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def load_payment_entitlement(path: Optional[Path] = None) -> PaymentEntitlement:
    p = path or default_entitlement_path()
    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return PaymentEntitlement.from_dict(data)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return PaymentEntitlement()


def save_payment_entitlement(
    ent: PaymentEntitlement, path: Optional[Path] = None
) -> Path:
    p = path or default_entitlement_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(ent.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    return p


def record_payment_success(
    session_id: str,
    *,
    platform: str = "",
    path: Optional[Path] = None,
    now: float | None = None,
) -> PaymentEntitlement:
    """Local cache after successful paid fulfilment."""
    t = now if now is not None else time.time()
    ent = PaymentEntitlement(
        session_id=str(session_id or "").strip(),
        status=STATUS_ACTIVE,
        platform=str(platform or "").strip().lower(),
        reason="payment_succeeded",
        updated_at=t,
    )
    save_payment_entitlement(ent, path=path)
    return ent


def record_payment_failure(
    session_id: str = "",
    *,
    reason: str = "payment_failed",
    platform: str = "",
    path: Optional[Path] = None,
    now: float | None = None,
) -> PaymentEntitlement:
    """Local cache when payment failed or entitlement was revoked."""
    t = now if now is not None else time.time()
    prev = load_payment_entitlement(path)
    sid = str(session_id or prev.session_id or "").strip()
    ent = PaymentEntitlement(
        session_id=sid,
        status=STATUS_FAILED,
        platform=str(platform or prev.platform or "").strip().lower(),
        reason=str(reason or "payment_failed"),
        updated_at=t,
    )
    save_payment_entitlement(ent, path=path)
    return ent


def is_payment_blocking_status(status: str) -> bool:
    s = (status or "").strip().lower()
    return s in (STATUS_FAILED, STATUS_REVOKED, STATUS_UNPAID)


def payment_allows_connect(
    ent: PaymentEntitlement | None = None,
    *,
    path: Optional[Path] = None,
    require: bool | None = None,
) -> bool:
    """True when payment entitlement does not block Connect.

    - failed / revoked / unpaid → False always
    - active → True
    - missing / unknown → False if require (product default), else True (self-host)
    """
    e = ent if ent is not None else load_payment_entitlement(path)
    req = payment_entitlement_required() if require is None else bool(require)
    st = (e.status or STATUS_UNKNOWN).strip().lower()
    if is_payment_blocking_status(st):
        return False
    if st == STATUS_ACTIVE:
        return True
    # unknown / empty
    if not req:
        return True
    # Required but no successful entitlement on file
    if not e.session_id and st in (STATUS_UNKNOWN, ""):
        return False
    if st in (STATUS_UNKNOWN, "") and e.session_id:
        # Have a session but never confirmed active — block when required
        return False
    return st == STATUS_ACTIVE


def assert_payment_may_connect(
    path: Optional[Path] = None,
    *,
    require: bool | None = None,
) -> tuple[bool, str]:
    if payment_allows_connect(path=path, require=require):
        return True, ""
    return False, CONNECT_BLOCKED_PAYMENT_MSG


def entitlement_status_url(
    session_id: str,
    *,
    base_url: str | None = None,
) -> str:
    """Status-host query URL for entitlement (no secrets)."""
    base = (base_url or os.environ.get("RPT_PUBLIC_BASE_URL") or "").strip()
    if not base:
        base = "https://restoreprivacy.online"
    base = base.rstrip("/")
    q = urllib.parse.urlencode({"session_id": session_id})
    return f"{base}/api/connect-entitlement?{q}"


def fetch_remote_entitlement_status(
    session_id: str,
    *,
    base_url: str | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """GET status host entitlement; returns dict with status key."""
    sid = (session_id or "").strip()
    if not sid:
        return {"status": STATUS_UNKNOWN, "error": "missing_session_id"}
    url = entitlement_status_url(sid, base_url=base_url)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "RestorePrivacy-payment-entitlement/0.3.3",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
        return {"status": STATUS_UNKNOWN, "error": str(exc)}
    return {"status": STATUS_UNKNOWN, "error": "bad_response"}


def refresh_entitlement_from_remote(
    path: Optional[Path] = None,
    *,
    base_url: str | None = None,
    now: float | None = None,
) -> PaymentEntitlement:
    """Refresh local cache from status host when session_id is known."""
    local = load_payment_entitlement(path)
    if not local.session_id:
        return local
    remote = fetch_remote_entitlement_status(local.session_id, base_url=base_url)
    st = str(remote.get("status") or STATUS_UNKNOWN).strip().lower()
    t = now if now is not None else time.time()
    if is_payment_blocking_status(st):
        return record_payment_failure(
            local.session_id,
            reason=str(remote.get("reason") or st),
            platform=local.platform,
            path=path,
            now=t,
        )
    if st == STATUS_ACTIVE:
        return record_payment_success(
            local.session_id,
            platform=local.platform or str(remote.get("platform") or ""),
            path=path,
            now=t,
        )
    return local
