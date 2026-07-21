"""Paid download fulfilment: Stripe Checkout (£2.45 GBP) + single-use tokens.

Stripe is the paid-download gateway (settles to the operator Stripe account when
live keys are set). Buy Me a Coffee is tip/support only — see coffee_link.py and
docs/PAID_DOWNLOADS_HOWTO.md.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from downloads import RELEASE_ASSETS, available_downloads

# £2.45 per selected package download
PRICE_PENCE = 245
PRICE_CURRENCY = "gbp"
PRICE_LABEL = "£2.45"

DEFAULT_SUCCESS_PATH = "/download/success"
DEFAULT_CANCEL_PATH = "/download/cancel"
TOKEN_TTL_SEC = int(os.environ.get("RPT_DOWNLOAD_TOKEN_TTL_SEC", "3600"))


def _data_dir() -> Path:
    raw = os.environ.get("RPT_PAYMENT_DATA_DIR", "").strip()
    if raw:
        p = Path(raw)
    else:
        p = Path(__file__).resolve().parent / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return _data_dir() / "paid_downloads.sqlite3"


def stripe_secret_key() -> str:
    return os.environ.get("STRIPE_SECRET_KEY", "").strip()


def stripe_webhook_secret() -> str:
    return os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()


def stripe_price_id() -> str:
    """Optional pre-created Price id; if empty, Checkout uses unit_amount=245."""
    return os.environ.get("STRIPE_PRICE_ID", "").strip()


def public_base_url() -> str:
    """Canonical public site URL for success/cancel/webhook (no trailing slash)."""
    return os.environ.get("RPT_PUBLIC_BASE_URL", "http://127.0.0.1:10000").rstrip("/")


def stripe_configured() -> bool:
    return bool(stripe_secret_key())


@dataclass(frozen=True)
class CheckoutRequest:
    platform: str
    filename: str
    success_url: str
    cancel_url: str


def platform_filename(platform: str) -> str | None:
    for a in available_downloads():
        if a.platform == platform:
            return a.filename
    return None


def asset_download_url(filename: str) -> str | None:
    for a in RELEASE_ASSETS:
        if a.filename == filename:
            return a.url
    return None


# --- SQLite store -----------------------------------------------------------------


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path()), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS grants (
                token TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                platform TEXT NOT NULL,
                session_id TEXT,
                amount_pence INTEGER NOT NULL,
                currency TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                used_at REAL,
                status TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_grants_session ON grants(session_id);
            CREATE INDEX IF NOT EXISTS idx_grants_created ON grants(created_at);
            """
        )
    finally:
        conn.close()


def mint_download_token(
    *,
    filename: str,
    platform: str,
    session_id: str | None,
    amount_pence: int = PRICE_PENCE,
    currency: str = PRICE_CURRENCY,
    ttl_sec: int = TOKEN_TTL_SEC,
    now: float | None = None,
) -> str:
    """Create a single-use expiring download token bound to a release asset."""
    init_db()
    t = now if now is not None else time.time()
    token = secrets.token_urlsafe(32)
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO grants(
                token, filename, platform, session_id, amount_pence, currency,
                created_at, expires_at, used_at, status
            ) VALUES (?,?,?,?,?,?,?,?,NULL,'granted')
            """,
            (
                token,
                filename,
                platform,
                session_id or "",
                int(amount_pence),
                currency,
                t,
                t + ttl_sec,
            ),
        )
    finally:
        conn.close()
    return token


def redeem_download_token(
    token: str, *, now: float | None = None
) -> dict[str, Any] | None:
    """Return grant dict and mark used if valid unused non-expired token."""
    init_db()
    t = now if now is not None else time.time()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM grants WHERE token = ?", (token,)
        ).fetchone()
        if row is None:
            return None
        if row["status"] != "granted" or row["used_at"] is not None:
            return None
        if float(row["expires_at"]) < t:
            return None
        conn.execute(
            "UPDATE grants SET used_at = ?, status = 'used' WHERE token = ?",
            (t, token),
        )
        return {
            "token": row["token"],
            "filename": row["filename"],
            "platform": row["platform"],
            "session_id": row["session_id"],
            "amount_pence": row["amount_pence"],
            "currency": row["currency"],
            "url": asset_download_url(row["filename"]),
        }
    finally:
        conn.close()


def list_recent_grants(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT token, filename, platform, session_id, amount_pence, currency,
                   created_at, expires_at, used_at, status
            FROM grants ORDER BY created_at DESC LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        out = []
        for r in rows:
            out.append({k: r[k] for k in r.keys()})
        return out
    finally:
        conn.close()


def find_grant_by_session(
    session_id: str, *, now: float | None = None, unused_only: bool = True
) -> dict[str, Any] | None:
    """Map Stripe Checkout session id → grant (token + filename), if present.

    Does **not** mark the token used — that happens on /download redeem.
    """
    sid = (session_id or "").strip()
    if not sid:
        return None
    init_db()
    t = now if now is not None else time.time()
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT token, filename, platform, session_id, amount_pence, currency,
                   created_at, expires_at, used_at, status
            FROM grants WHERE session_id = ? ORDER BY created_at DESC LIMIT 1
            """,
            (sid,),
        ).fetchone()
        if row is None:
            return None
        if float(row["expires_at"]) < t:
            return None
        if unused_only and (row["status"] != "granted" or row["used_at"] is not None):
            return None
        return {
            "token": row["token"],
            "filename": row["filename"],
            "platform": row["platform"],
            "session_id": row["session_id"],
            "amount_pence": row["amount_pence"],
            "currency": row["currency"],
            "status": row["status"],
            "used_at": row["used_at"],
            "download_path": f"/download?token={row['token']}",
            "url": asset_download_url(row["filename"]),
        }
    finally:
        conn.close()


def wait_for_grant_by_session(
    session_id: str,
    *,
    timeout_sec: float = 8.0,
    interval_sec: float = 0.25,
    now: float | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> dict[str, Any] | None:
    """Poll for webhook-minted grant after Checkout redirect (race-friendly)."""
    sleeper = sleep_fn or time.sleep
    start = time.time() if now is None else float(now)
    deadline = start + max(0.0, timeout_sec)
    while True:
        grant = find_grant_by_session(session_id, now=now)
        if grant is not None:
            return grant
        tcur = time.time() if now is None else float(now)
        if tcur >= deadline:
            return None
        sleeper(interval_sec)


# --- Stripe Checkout (stdlib HTTP) -----------------------------------------------


HttpPostFn = Callable[[str, dict[str, str], bytes], tuple[int, bytes]]


def _default_http_post(
    url: str, headers: dict[str, str], body: bytes
) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return int(resp.status), resp.read()
    except urllib.error.HTTPError as e:
        return int(e.code), e.read()


def build_checkout_form_body(req: CheckoutRequest) -> bytes:
    """application/x-www-form-urlencoded body for Stripe Checkout Session create."""
    fields: list[tuple[str, str]] = [
        ("mode", "payment"),
        ("success_url", req.success_url),
        ("cancel_url", req.cancel_url),
        ("client_reference_id", req.platform),
        ("metadata[platform]", req.platform),
        ("metadata[filename]", req.filename),
        ("metadata[amount_pence]", str(PRICE_PENCE)),
        ("metadata[currency]", PRICE_CURRENCY),
    ]
    price_id = stripe_price_id()
    if price_id:
        fields.append(("line_items[0][price]", price_id))
        fields.append(("line_items[0][quantity]", "1"))
    else:
        fields.extend(
            [
                ("line_items[0][price_data][currency]", PRICE_CURRENCY),
                ("line_items[0][price_data][unit_amount]", str(PRICE_PENCE)),
                (
                    "line_items[0][price_data][product_data][name]",
                    f"Restore Privacy download - {req.platform}",
                ),
                (
                    "line_items[0][price_data][product_data][description]",
                    req.filename,
                ),
                ("line_items[0][quantity]", "1"),
            ]
        )
    return urllib.parse.urlencode(fields).encode("utf-8")


def create_checkout_session(
    platform: str,
    *,
    base_url: str | None = None,
    http_post: HttpPostFn | None = None,
) -> dict[str, Any]:
    """Create a Stripe Checkout Session for one package at £2.45 GBP.

    Returns dict with keys: id, url (Stripe-hosted), platform, filename, amount_pence.
    Raises ValueError on bad platform or missing Stripe config / API failure.
    """
    filename = platform_filename(platform)
    if not filename:
        raise ValueError(f"unknown platform: {platform}")
    key = stripe_secret_key()
    if not key:
        raise ValueError("STRIPE_SECRET_KEY not configured")

    base = (base_url or public_base_url()).rstrip("/")
    success = (
        f"{base}{DEFAULT_SUCCESS_PATH}"
        f"?session_id={{CHECKOUT_SESSION_ID}}&platform={urllib.parse.quote(platform)}"
    )
    cancel = f"{base}{DEFAULT_CANCEL_PATH}?platform={urllib.parse.quote(platform)}"
    creq = CheckoutRequest(
        platform=platform,
        filename=filename,
        success_url=success,
        cancel_url=cancel,
    )
    body = build_checkout_form_body(creq)

    post = http_post or _default_http_post
    status, raw = post(
        "https://api.stripe.com/v1/checkout/sessions",
        {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body,
    )
    if status >= 400:
        raise ValueError(f"stripe checkout create failed HTTP {status}: {raw[:300]!r}")
    data = json.loads(raw.decode("utf-8"))
    url = data.get("url")
    sid = data.get("id")
    if not url or not sid:
        raise ValueError("stripe response missing url/id")
    return {
        "id": sid,
        "url": url,
        "platform": platform,
        "filename": filename,
        "amount_pence": PRICE_PENCE,
        "currency": PRICE_CURRENCY,
    }


# --- Webhook signature + grant ---------------------------------------------------


def verify_stripe_signature(
    payload: bytes,
    sig_header: str,
    secret: str,
    *,
    tolerance_sec: int = 300,
    now: float | None = None,
) -> bool:
    """Verify Stripe-Signature header (t=…,v1=…)."""
    if not secret or not sig_header:
        return False
    parts: dict[str, list[str]] = {}
    for item in sig_header.split(","):
        item = item.strip()
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        parts.setdefault(k.strip(), []).append(v.strip())
    if "t" not in parts or "v1" not in parts:
        return False
    try:
        ts = int(parts["t"][0])
    except ValueError:
        return False
    tnow = now if now is not None else time.time()
    if abs(tnow - ts) > tolerance_sec:
        return False
    signed = f"{ts}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    for cand in parts["v1"]:
        if hmac.compare_digest(expected, cand):
            return True
    return False


def process_checkout_completed_event(event: dict[str, Any]) -> str | None:
    """On checkout.session.completed, mint a download token. Returns token or None."""
    if event.get("type") != "checkout.session.completed":
        return None
    obj = event.get("data", {}).get("object") or {}
    meta = obj.get("metadata") or {}
    platform = str(meta.get("platform") or obj.get("client_reference_id") or "").strip()
    filename = str(meta.get("filename") or "").strip()
    if not filename:
        filename = platform_filename(platform) or ""
    if not platform or not filename:
        return None
    # Prefer metadata amount; fall back to product price
    try:
        amount = int(meta.get("amount_pence") or PRICE_PENCE)
    except (TypeError, ValueError):
        amount = PRICE_PENCE
    if amount != PRICE_PENCE:
        # Refuse wrong amount
        return None
    currency = str(meta.get("currency") or obj.get("currency") or PRICE_CURRENCY).lower()
    if currency != PRICE_CURRENCY:
        return None
    session_id = str(obj.get("id") or "")
    return mint_download_token(
        filename=filename,
        platform=platform,
        session_id=session_id,
        amount_pence=amount,
        currency=currency,
    )


def handle_stripe_webhook(
    payload: bytes,
    sig_header: str,
    *,
    secret: str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Verify signature and grant token when applicable.

    Returns {ok, granted, token?, error?}.
    """
    wh_secret = (secret if secret is not None else stripe_webhook_secret()).strip()
    if not verify_stripe_signature(payload, sig_header, wh_secret, now=now):
        return {"ok": False, "granted": False, "error": "invalid_signature"}
    try:
        event = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"ok": False, "granted": False, "error": "bad_json"}
    token = process_checkout_completed_event(event)
    if token:
        return {"ok": True, "granted": True, "token": token}
    return {"ok": True, "granted": False}


def checkout_amount_fields_for_tests() -> dict[str, Any]:
    """Expose pricing constants for unit tests (real shipped values)."""
    return {
        "amount_pence": PRICE_PENCE,
        "currency": PRICE_CURRENCY,
        "label": PRICE_LABEL,
    }
