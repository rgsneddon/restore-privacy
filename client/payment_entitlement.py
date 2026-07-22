"""Payment entitlement for Connect — observe paid status; block on failure.

Successful Stripe fulfilment grants a **connect entitlement** bound to the
Checkout ``session_id``. Failed payment, refund, dispute, or explicit revoke
sets status to ``failed`` / ``revoked`` and **Connect is blocked** for that
install until a new successful payment is completed.

Local cache under the product data dir; optional refresh from the status host
``/api/connect-entitlement``. After pay the thank-you page auto-downloads
``payment_entitlement.json`` (discovered on first Connect — no manual session
paste required when the file lands next to the install or in Downloads). The
client also binds the local device Ed25519 pub to the paid session so the
**node** can refuse residual HELLO for non-entitled installs.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

# Local entitlement file (same data family as licence acceptance)
ENTITLEMENT_FILENAME = "payment_entitlement.json"
KEY_SESSION_ID = "session_id"
KEY_STATUS = "status"
KEY_PLATFORM = "platform"
KEY_REASON = "reason"
KEY_UPDATED_AT = "updated_at"
KEY_VALID_UNTIL = "valid_until"
KEY_KEYGEN = "keygen"

STATUS_ACTIVE = "active"
STATUS_FAILED = "failed"
STATUS_REVOKED = "revoked"
STATUS_UNKNOWN = "unknown"
STATUS_UNPAID = "unpaid"

CONNECT_BLOCKED_PAYMENT_MSG = (
    "Connect is blocked: payment failed or entitlement was revoked for this "
    "install. Successful payment is required. If payment fails at any time "
    "(checkout failure, failed charge, refund, dispute, or subscription period "
    "ended), the ability to Connect with the Restore Privacy app is cancelled "
    "until you complete a successful payment again on https://restoreprivacy.online/ "
    "(enter your keygen again after re-subscribe, re-download "
    "payment_entitlement.json, or use Settings → Payment entitlement / keygen)."
)

CONNECT_BLOCKED_NO_ENTITLEMENT_MSG = (
    "Connect is blocked: no successful payment entitlement on this install. "
    "After paying on https://restoreprivacy.online/, accept the licence, then "
    "enter the keygen from your fulfilment email (USE THIS KEYGEN TO UNLOCK "
    "YOUR RESTORE PRIVACY TRIAL) in Settings. Optional: keep "
    "payment_entitlement.json next to the installer for auto-import. "
    "Successful payment/active subscription is required; if payment fails or a "
    "subscription period ends, Connect is cancelled."
)

CONNECT_BLOCKED_KEYGEN_MSG = (
    "Connect is blocked: enter a valid keygen after accepting the licence. "
    "Your fulfilment email includes the keygen with the text "
    "USE THIS KEYGEN TO UNLOCK YOUR RESTORE PRIVACY TRIAL. "
    "The keygen only works while your subscription/payment is active."
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
    valid_until: float | None = None
    keygen: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            KEY_SESSION_ID: str(self.session_id or ""),
            KEY_STATUS: str(self.status or STATUS_UNKNOWN),
            KEY_PLATFORM: str(self.platform or ""),
            KEY_REASON: str(self.reason or ""),
            KEY_UPDATED_AT: float(self.updated_at or 0.0),
            KEY_KEYGEN: str(self.keygen or ""),
        }
        if self.valid_until is not None:
            d[KEY_VALID_UNTIL] = float(self.valid_until)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PaymentEntitlement":
        vu_raw = data.get(KEY_VALID_UNTIL)
        try:
            vu = float(vu_raw) if vu_raw is not None and str(vu_raw).strip() != "" else None
        except (TypeError, ValueError):
            vu = None
        return cls(
            session_id=str(data.get(KEY_SESSION_ID) or ""),
            status=str(data.get(KEY_STATUS) or STATUS_UNKNOWN).strip().lower(),
            platform=str(data.get(KEY_PLATFORM) or ""),
            reason=str(data.get(KEY_REASON) or ""),
            updated_at=float(data.get(KEY_UPDATED_AT) or 0.0),
            valid_until=vu,
            keygen=str(data.get(KEY_KEYGEN) or "").strip().upper(),
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
    valid_until: float | None = None,
    keygen: str = "",
) -> PaymentEntitlement:
    """Local cache after successful paid fulfilment."""
    t = now if now is not None else time.time()
    prev = load_payment_entitlement(path)
    ent = PaymentEntitlement(
        session_id=str(session_id or "").strip(),
        status=STATUS_ACTIVE,
        platform=str(platform or "").strip().lower(),
        reason="payment_succeeded",
        updated_at=t,
        valid_until=valid_until,
        keygen=str(keygen or prev.keygen or "").strip().upper(),
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
    status: str = STATUS_FAILED,
    keygen: str = "",
) -> PaymentEntitlement:
    """Local cache when payment failed or entitlement was revoked."""
    t = now if now is not None else time.time()
    prev = load_payment_entitlement(path)
    sid = str(session_id or prev.session_id or "").strip()
    st = str(status or STATUS_FAILED).strip().lower()
    if st not in (STATUS_FAILED, STATUS_REVOKED, STATUS_UNPAID):
        st = STATUS_FAILED
    ent = PaymentEntitlement(
        session_id=sid,
        status=st,
        platform=str(platform or prev.platform or "").strip().lower(),
        reason=str(reason or "payment_failed"),
        updated_at=t,
        keygen=str(keygen or prev.keygen or "").strip().upper(),
    )
    save_payment_entitlement(ent, path=path)
    return ent


def store_session_pending(
    session_id: str,
    *,
    platform: str = "",
    path: Optional[Path] = None,
    now: float | None = None,
    keygen: str = "",
) -> PaymentEntitlement:
    """Remember Checkout session id before remote verify (status still unknown)."""
    t = now if now is not None else time.time()
    prev = load_payment_entitlement(path)
    sid = str(session_id or "").strip()
    ent = PaymentEntitlement(
        session_id=sid,
        status=STATUS_UNKNOWN,
        platform=str(platform or prev.platform or "").strip().lower(),
        reason="session_import_pending",
        updated_at=t,
        keygen=str(keygen or prev.keygen or "").strip().upper(),
    )
    save_payment_entitlement(ent, path=path)
    return ent


def import_entitlement_from_dict(
    data: dict[str, Any],
    *,
    path: Optional[Path] = None,
    now: float | None = None,
) -> PaymentEntitlement:
    """Import entitlement dict (thank-you download / product data file)."""
    ent = PaymentEntitlement.from_dict(data if isinstance(data, dict) else {})
    t = now if now is not None else time.time()
    if not ent.updated_at:
        ent = PaymentEntitlement(
            session_id=ent.session_id,
            status=ent.status or STATUS_UNKNOWN,
            platform=ent.platform,
            reason=ent.reason or "imported_file",
            updated_at=t,
            keygen=ent.keygen,
        )
    save_payment_entitlement(ent, path=path)
    return ent


def import_entitlement_from_file(
    source: Path | str,
    *,
    path: Optional[Path] = None,
    now: float | None = None,
) -> PaymentEntitlement:
    """Load payment_entitlement.json from disk into the product data path."""
    src = Path(source)
    raw = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("entitlement file must be a JSON object")
    return import_entitlement_from_dict(raw, path=path, now=now)


def entitlement_discovery_candidates() -> list[Path]:
    """Common locations for a post-pay entitlement file next to the install."""
    out: list[Path] = []
    try:
        out.append(default_entitlement_path())
    except Exception:  # noqa: BLE001
        pass
    # CWD and parent (portable / SFX extract dir)
    try:
        cwd = Path.cwd()
        out.append(cwd / ENTITLEMENT_FILENAME)
        out.append(cwd.parent / ENTITLEMENT_FILENAME)
    except Exception:  # noqa: BLE001
        pass
    # Next to argv[0] when running a frozen/portable binary
    try:
        exe = Path(sys.argv[0]).resolve()
        out.append(exe.parent / ENTITLEMENT_FILENAME)
    except Exception:  # noqa: BLE001
        pass
    # User Downloads (thank-you auto-download often lands here)
    try:
        home = Path.home()
        out.append(home / "Downloads" / ENTITLEMENT_FILENAME)
        out.append(home / "downloads" / ENTITLEMENT_FILENAME)
    except Exception:  # noqa: BLE001
        pass
    # Dedupe while preserving order
    seen: set[str] = set()
    unique: list[Path] = []
    for p in out:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    return unique


def try_discover_entitlement_file(
    *,
    dest_path: Optional[Path] = None,
) -> PaymentEntitlement | None:
    """If payment_entitlement.json exists nearby, import it into product data."""
    dest = dest_path or default_entitlement_path()
    existing = load_payment_entitlement(dest)
    if existing.session_id and existing.status == STATUS_ACTIVE:
        return existing
    for cand in entitlement_discovery_candidates():
        if cand == dest:
            continue
        try:
            if not cand.is_file():
                continue
            ent = import_entitlement_from_file(cand, path=dest)
            if ent.session_id:
                return ent
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
    return None


def import_session_and_verify(
    session_id: str,
    *,
    path: Optional[Path] = None,
    base_url: str | None = None,
    platform: str = "",
    now: float | None = None,
    fetch: Any = None,
) -> PaymentEntitlement:
    """Provision local entitlement from Checkout session id and verify remotely.

    Fallback path: paste/import ``cs_…`` session id → status host confirms.
    Preferred product path is :func:`import_keygen_and_verify`.
    """
    sid = str(session_id or "").strip()
    if not sid:
        return load_payment_entitlement(path)
    store_session_pending(sid, platform=platform, path=path, now=now)
    return refresh_entitlement_from_remote(
        path=path,
        base_url=base_url,
        now=now,
        fetch=fetch,
    )


def normalize_local_keygen(keygen: str) -> str:
    """Uppercase / strip customer-entered keygen (client-side)."""
    s = (keygen or "").strip().upper().replace(" ", "")
    if s.startswith("RPTKEY") and "-" not in s and len(s) == 18:
        body = s[6:]
        s = f"RPT-KEY-{body[0:4]}-{body[4:8]}-{body[8:12]}"
    return s


# Product keygen prefix (status host mints RPT-KEY-XXXX-XXXX-XXXX).
KEYGEN_PREFIX = "RPT-KEY-"


def status_host_timeout_s() -> float:
    """Bounded timeout for status-host GET/POST (Connect must not hang the UI).

    Default **3s** (was 8s). Override with ``RPT_STATUS_HOST_TIMEOUT`` (seconds).
    Clamped to [1.0, 15.0] so mis-set env cannot freeze the shell for minutes.
    """
    raw = (os.environ.get("RPT_STATUS_HOST_TIMEOUT") or "").strip()
    if not raw:
        return 3.0
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return 3.0
    if v < 1.0:
        return 1.0
    if v > 15.0:
        return 15.0
    return v


def has_keygen_unlock(
    ent: PaymentEntitlement | None = None,
    *,
    path: Optional[Path] = None,
) -> bool:
    """True when this install has a fulfilment keygen (``RPT-KEY-…``) on file.

    Product rule: Connect requires an explicit keygen unlock step. A thank-you
    ``payment_entitlement.json`` with only ``session_id`` / status=active does
    **not** count — the user (or a download that includes ``keygen``) must
    satisfy this helper before residual HELLO may proceed.
    """
    e = ent if ent is not None else load_payment_entitlement(path)
    kg = normalize_local_keygen(e.keygen or "")
    return bool(kg) and kg.startswith(KEYGEN_PREFIX)


def import_keygen_and_verify(
    keygen: str,
    *,
    path: Optional[Path] = None,
    base_url: str | None = None,
    platform: str = "",
    now: float | None = None,
    fetch: Any = None,
    bind_device: bool = True,
) -> PaymentEntitlement:
    """Provision local entitlement from fulfilment **keygen** and verify remotely.

    Shipped first-run path after Install → accept licence → enter keygen:
    status host ``/api/connect-entitlement?keygen=…`` confirms active subscription.
    On success, binds this device so the residual node admits HELLO.
    """
    kg = normalize_local_keygen(keygen)
    if not kg:
        return load_payment_entitlement(path)
    t = now if now is not None else time.time()
    prev = load_payment_entitlement(path)
    pending = PaymentEntitlement(
        session_id=prev.session_id,
        status=STATUS_UNKNOWN,
        platform=str(platform or prev.platform or "").strip().lower(),
        reason="keygen_import_pending",
        updated_at=t,
        keygen=kg,
    )
    save_payment_entitlement(pending, path=path)
    local = refresh_entitlement_from_remote(
        path=path,
        base_url=base_url,
        now=now,
        fetch=fetch,
    )
    if (
        bind_device
        and local.status == STATUS_ACTIVE
        and payment_allows_connect(local, require=True)
        and local.session_id
    ):
        try:
            bind_device_to_remote(local.session_id, base_url=base_url)
        except Exception:  # noqa: BLE001
            pass
    return local


def maybe_bootstrap_from_env(
    *,
    path: Optional[Path] = None,
    base_url: str | None = None,
    fetch: Any = None,
) -> PaymentEntitlement | None:
    """If ``RPT_PAYMENT_SESSION_ID`` is set, import and verify once."""
    sid = (os.environ.get("RPT_PAYMENT_SESSION_ID") or "").strip()
    if not sid:
        return None
    return import_session_and_verify(
        sid, path=path, base_url=base_url, fetch=fetch
    )


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
    - active **and** keygen unlock (``RPT-KEY-…``) → True when require
    - active without keygen → False when require (discovery/session alone is not enough)
    - missing / unknown → False if require (product default), else True (self-host)
    """
    e = ent if ent is not None else load_payment_entitlement(path)
    req = payment_entitlement_required() if require is None else bool(require)
    st = (e.status or STATUS_UNKNOWN).strip().lower()
    if is_payment_blocking_status(st):
        return False
    if st == STATUS_ACTIVE:
        if e.valid_until is not None:
            try:
                if float(e.valid_until) <= time.time():
                    return False
            except (TypeError, ValueError):
                pass
        # Product: residual Connect needs keygen unlock, not session file alone.
        if req and not has_keygen_unlock(e):
            return False
        return True
    # unknown / empty
    if not req:
        return True
    # Required but no successful entitlement on file
    if not e.session_id and not e.keygen and st in (STATUS_UNKNOWN, ""):
        return False
    if st in (STATUS_UNKNOWN, "") and (e.session_id or e.keygen):
        # Have session/keygen but never confirmed active — block when required
        return False
    if st == STATUS_ACTIVE and req and not has_keygen_unlock(e):
        return False
    return st == STATUS_ACTIVE and (not req or has_keygen_unlock(e))


def assert_payment_may_connect(
    path: Optional[Path] = None,
    *,
    require: bool | None = None,
    refresh: bool = True,
    base_url: str | None = None,
    fetch: Any = None,
) -> tuple[bool, str]:
    """Gate Connect on payment entitlement + keygen unlock.

    When ``refresh`` is true (product default on Connect):
    - discover/import nearby entitlement file or ``RPT_PAYMENT_SESSION_ID``
    - re-query the status host so refunds/revokes cancel Connect promptly

    Discovery of an active session **without** keygen still fails closed with
    :data:`CONNECT_BLOCKED_KEYGEN_MSG` (user must enter keygen unlock).
    """
    if refresh:
        ensure_entitlement_for_connect(
            path=path, base_url=base_url, fetch=fetch
        )
    if payment_allows_connect(path=path, require=require):
        return True, ""
    ent = load_payment_entitlement(path)
    if is_payment_blocking_status(ent.status):
        return False, CONNECT_BLOCKED_PAYMENT_MSG
    # Active/session present but no RPT-KEY-… unlock → force keygen surface
    if not has_keygen_unlock(ent):
        return False, CONNECT_BLOCKED_KEYGEN_MSG
    if not ent.session_id and not ent.keygen:
        return False, CONNECT_BLOCKED_KEYGEN_MSG
    return False, CONNECT_BLOCKED_NO_ENTITLEMENT_MSG


def ensure_entitlement_for_connect(
    path: Optional[Path] = None,
    *,
    base_url: str | None = None,
    fetch: Any = None,
    bind_device: bool = True,
) -> PaymentEntitlement:
    """Bootstrap + remote refresh used by every shipped Connect entry path.

    Auto-provisions from ``payment_entitlement.json`` next to the install or in
    Downloads (thank-you auto-download), then binds the local device pub so the
    residual node can admit HELLO. Keygen-only installs refresh by keygen.
    """
    local = load_payment_entitlement(path)
    if not local.session_id and not local.keygen:
        discovered = try_discover_entitlement_file(dest_path=path)
        if discovered is not None and (discovered.session_id or discovered.keygen):
            local = discovered
        else:
            boot = maybe_bootstrap_from_env(
                path=path, base_url=base_url, fetch=fetch
            )
            if boot is not None:
                local = boot
    if local.session_id or local.keygen:
        local = refresh_entitlement_from_remote(
            path=path, base_url=base_url, fetch=fetch
        )
        # Bind only when keygen unlock + active allow Connect (not session-only).
        if (
            bind_device
            and local.status == STATUS_ACTIVE
            and has_keygen_unlock(local)
            and payment_allows_connect(local, require=True)
            and local.session_id
        ):
            try:
                bind_device_to_remote(local.session_id, base_url=base_url)
            except Exception:  # noqa: BLE001
                pass
        return local
    return local


def entitlement_status_url(
    session_id: str = "",
    *,
    base_url: str | None = None,
    keygen: str = "",
) -> str:
    """Status-host query URL for entitlement (session_id and/or keygen)."""
    base = (base_url or os.environ.get("RPT_PUBLIC_BASE_URL") or "").strip()
    if not base:
        base = "https://restoreprivacy.online"
    base = base.rstrip("/")
    params: dict[str, str] = {}
    if (keygen or "").strip():
        params["keygen"] = normalize_local_keygen(keygen)
    elif (session_id or "").strip():
        params["session_id"] = (session_id or "").strip()
    q = urllib.parse.urlencode(params)
    return f"{base}/api/connect-entitlement?{q}"


def fetch_remote_entitlement_status(
    session_id: str = "",
    *,
    base_url: str | None = None,
    timeout: float | None = None,
    keygen: str = "",
) -> dict[str, Any]:
    """GET status host entitlement; returns dict with status key.

    Uses :func:`status_host_timeout_s` when ``timeout`` is omitted so Connect
    never stacks multi-second unbounded waits on a dead status host.
    """
    sid = (session_id or "").strip()
    kg = normalize_local_keygen(keygen)
    if not sid and not kg:
        return {"status": STATUS_UNKNOWN, "error": "missing_session_id_or_keygen"}
    to = float(timeout) if timeout is not None else status_host_timeout_s()
    url = entitlement_status_url(sid, base_url=base_url, keygen=kg)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "RestorePrivacy-payment-entitlement/0.3.6",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=to) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
        return {"status": STATUS_UNKNOWN, "error": str(exc)}
    return {"status": STATUS_UNKNOWN, "error": "bad_response"}


def _merge_remote_keygen(
    local: PaymentEntitlement,
    remote: dict[str, Any],
) -> str:
    """Keygen for local cache after a status-host refresh.

    Product rule: session-only / thank-you discovery must **not** gain a
    ``RPT-KEY-…`` unlock from a remote field alone. That would skip the user
    keygen step. Only keep/update keygen when local already has one (user
    entered it via :func:`import_keygen_and_verify`, or a file that already
    contained ``keygen``).
    """
    local_kg = normalize_local_keygen(local.keygen or "")
    if not local_kg or not local_kg.startswith(KEYGEN_PREFIX):
        return ""
    remote_kg = normalize_local_keygen(str(remote.get("keygen") or ""))
    if remote_kg and remote_kg.startswith(KEYGEN_PREFIX):
        return remote_kg
    return local_kg


def refresh_entitlement_from_remote(
    path: Optional[Path] = None,
    *,
    base_url: str | None = None,
    now: float | None = None,
    fetch: Callable[..., dict[str, Any]] | None = None,
) -> PaymentEntitlement:
    """Refresh local cache from status host when session_id or keygen is known.

    ``fetch`` may inject a test double; production uses
    :func:`fetch_remote_entitlement_status`.

    Does **not** copy a status-host ``keygen`` into a session-only local
    entitlement (prevents silent unlock without user keygen entry).
    """
    local = load_payment_entitlement(path)
    if not local.session_id and not local.keygen:
        return local
    if fetch is not None:
        # Support both session-only and keygen-aware test doubles
        try:
            remote = fetch(local.session_id, keygen=local.keygen)  # type: ignore[call-arg]
        except TypeError:
            remote = fetch(local.session_id or local.keygen)
    else:
        remote = fetch_remote_entitlement_status(
            local.session_id, base_url=base_url, keygen=local.keygen
        )
    if not isinstance(remote, dict):
        remote = {"status": STATUS_UNKNOWN, "error": "bad_response"}
    st = str(remote.get("status") or STATUS_UNKNOWN).strip().lower()
    t = now if now is not None else time.time()
    remote_sid = str(remote.get("session_id") or local.session_id or "").strip()
    merged_kg = _merge_remote_keygen(local, remote)
    if is_payment_blocking_status(st):
        return record_payment_failure(
            remote_sid,
            reason=str(remote.get("reason") or st),
            platform=local.platform,
            path=path,
            now=t,
            status=st if st in (STATUS_FAILED, STATUS_REVOKED, STATUS_UNPAID) else STATUS_FAILED,
            keygen=merged_kg,
        )
    if st == STATUS_ACTIVE:
        vu = remote.get("valid_until")
        try:
            vu_f = float(vu) if vu is not None and str(vu).strip() != "" else None
        except (TypeError, ValueError):
            vu_f = None
        # connect_allowed false with active status should not happen; still gate
        if remote.get("connect_allowed") is False:
            return record_payment_failure(
                remote_sid,
                reason=str(remote.get("reason") or "not_allowed"),
                platform=local.platform,
                path=path,
                now=t,
                status=STATUS_REVOKED,
                keygen=merged_kg,
            )
        return record_payment_success(
            remote_sid or local.session_id,
            platform=local.platform or str(remote.get("platform") or ""),
            path=path,
            now=t,
            valid_until=vu_f,
            keygen=merged_kg,
        )
    # Unknown remote (network blip): keep last known local status
    return local


def local_device_pub_hex() -> str:
    """Hex of local product Ed25519 device public key (for status-host bind)."""
    try:
        from client.secrets_loader import (
            CLIENT_PUB_NAME,
            ensure_device_admission_key,
        )

        d = ensure_device_admission_key()
        pub_path = d / CLIENT_PUB_NAME
        if pub_path.is_file():
            raw = pub_path.read_bytes()
            if len(raw) == 32:
                return raw.hex().lower()
    except Exception:  # noqa: BLE001
        pass
    return ""


def bind_device_to_remote(
    session_id: str,
    *,
    device_pub_hex: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """POST /api/bind-device-entitlement so the node can admit this install.

    Bounded by :func:`status_host_timeout_s` when ``timeout`` is omitted.
    """
    sid = (session_id or "").strip()
    pub = (device_pub_hex or local_device_pub_hex() or "").strip().lower()
    if not sid or not pub:
        return {"ok": False, "error": "missing_session_or_device"}
    base = (base_url or os.environ.get("RPT_PUBLIC_BASE_URL") or "").strip()
    if not base:
        base = "https://restoreprivacy.online"
    base = base.rstrip("/")
    to = float(timeout) if timeout is not None else status_host_timeout_s()
    url = f"{base}/api/bind-device-entitlement"
    body = json.dumps({"session_id": sid, "device_pub": pub}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": "RestorePrivacy-payment-entitlement/0.3.4",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=to) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": False, "error": "bad_response"}


def auto_provision_and_bind(
    path: Optional[Path] = None,
    *,
    base_url: str | None = None,
    fetch: Any = None,
) -> PaymentEntitlement:
    """Discover post-pay entitlement file, verify remote, bind device for node HELLO.

    Primary auto path after Stripe thank-you (no manual session id paste).
    """
    ent = ensure_entitlement_for_connect(path=path, base_url=base_url, fetch=fetch)
    if ent.session_id and ent.status == STATUS_ACTIVE:
        bind_device_to_remote(ent.session_id, base_url=base_url)
    return ent


def provision_entitlement_from_installer_dirs(
    *search_dirs: Path | str,
    dest_path: Optional[Path] = None,
) -> PaymentEntitlement | None:
    """Copy payment_entitlement.json from pay-adjacent dirs into product data.

    Called by Windows/Linux installers when the thank-you file sits next to the
    downloaded package (auto-provision — no Settings paste).
    """
    dest = dest_path or default_entitlement_path()
    for d in search_dirs:
        try:
            p = Path(d) / ENTITLEMENT_FILENAME
            if p.is_file():
                return import_entitlement_from_file(p, path=dest)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
    return None

