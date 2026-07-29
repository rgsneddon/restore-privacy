"""Admin authenticator (TOTP / RFC 6238) second factor.

Durable enrollment under the payment data dir family. Password alone never
grants a full admin session once this module is wired into login.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import struct
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

# Pending login (password OK, 2FA not finished) — not full admin access.
PENDING_COOKIE = "rpt_admin_pending"
PENDING_TTL_SEC = 10 * 60
TOTP_DIGITS = 6
TOTP_STEP_SEC = 30
TOTP_WINDOW = 1  # ±1 step for clock skew
ISSUER = "RestorePrivacy Admin"


def _data_dir() -> Path:
    try:
        from payments import payment_data_dir  # type: ignore

        return Path(payment_data_dir())
    except Exception:  # noqa: BLE001
        try:
            from status_page.payments import payment_data_dir  # type: ignore

            return Path(payment_data_dir())
        except Exception:  # noqa: BLE001
            raw = str(os.environ.get("RPT_PAYMENT_DATA_DIR", "") or "").strip()
            if raw:
                p = Path(raw)
                p.mkdir(parents=True, exist_ok=True)
                return p
            p = Path(__file__).resolve().parent / "data"
            p.mkdir(parents=True, exist_ok=True)
            return p


def totp_db_path() -> Path:
    return _data_dir() / "admin_2fa.sqlite3"


def _connect() -> sqlite3.Connection:
    path = totp_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_totp (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            secret_b32 TEXT NOT NULL,
            enrolled INTEGER NOT NULL DEFAULT 0,
            enrolled_at REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_pending (
            token_hash TEXT PRIMARY KEY,
            stage TEXT NOT NULL,
            secret_b32 TEXT,
            expires_at REAL NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def generate_totp_secret() -> str:
    """High-entropy base32 secret (no padding) for authenticator apps."""
    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _b32_decode(secret_b32: str) -> bytes:
    s = re.sub(r"\s+", "", (secret_b32 or "").strip().upper())
    pad = "=" * ((8 - len(s) % 8) % 8)
    return base64.b32decode(s + pad, casefold=True)


def totp_code_at(
    secret_b32: str,
    for_time: float,
    *,
    step: int = TOTP_STEP_SEC,
    digits: int = TOTP_DIGITS,
) -> str:
    """RFC 6238 TOTP (HMAC-SHA1) for *for_time*."""
    key = _b32_decode(secret_b32)
    counter = int(for_time // step)
    msg = struct.pack(">Q", counter)
    dig = hmac.new(key, msg, hashlib.sha1).digest()
    off = dig[-1] & 0x0F
    bin_code = (
        ((dig[off] & 0x7F) << 24)
        | (dig[off + 1] << 16)
        | (dig[off + 2] << 8)
        | dig[off + 3]
    )
    code = bin_code % (10**digits)
    return f"{code:0{digits}d}"


def verify_totp(
    secret_b32: str,
    code: str,
    *,
    now: float | None = None,
    window: int = TOTP_WINDOW,
) -> bool:
    """True if *code* matches TOTP for now ± window steps."""
    raw = re.sub(r"\s+", "", str(code or "").strip())
    if not re.fullmatch(r"\d{6}", raw):
        return False
    t = float(now if now is not None else time.time())
    for w in range(-int(window), int(window) + 1):
        expect = totp_code_at(secret_b32, t + w * TOTP_STEP_SEC)
        if hmac.compare_digest(expect, raw):
            return True
    return False


def otpauth_uri(
    secret_b32: str,
    *,
    account: str = "admin",
    issuer: str = ISSUER,
) -> str:
    """otpauth:// URI for Google Authenticator / Authy / etc."""
    label = quote(f"{issuer}:{account}")
    q = (
        f"secret={secret_b32}"
        f"&issuer={quote(issuer)}"
        f"&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_STEP_SEC}"
    )
    return f"otpauth://totp/{label}?{q}"


def is_totp_enrolled() -> bool:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT enrolled, secret_b32 FROM admin_totp WHERE id = 1"
        ).fetchone()
        if not row:
            return False
        return bool(int(row["enrolled"])) and bool(str(row["secret_b32"] or "").strip())
    finally:
        conn.close()


def get_enrolled_secret() -> str | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT enrolled, secret_b32 FROM admin_totp WHERE id = 1"
        ).fetchone()
        if not row or not int(row["enrolled"]):
            return None
        s = str(row["secret_b32"] or "").strip()
        return s or None
    finally:
        conn.close()


def clear_all_pending() -> None:
    """Drop all pending setup/verify tokens (after successful enroll)."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM admin_pending")
        conn.commit()
    finally:
        conn.close()


def enroll_totp_secret(secret_b32: str, *, now: float | None = None) -> dict[str, Any]:
    """Persist enrolled TOTP secret once. Refuses if already enrolled.

    Does **not** overwrite an existing enrolled secret (blocks leftover setup
    pendings from replacing the authenticator). Clears all pending tokens on
    success.
    """
    s = re.sub(r"\s+", "", (secret_b32 or "").strip().upper()).rstrip("=")
    if len(s) < 16:
        raise ValueError("secret too short")
    # Validate decodable
    _b32_decode(s)
    t = float(now if now is not None else time.time())
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT enrolled, secret_b32 FROM admin_totp WHERE id = 1"
        ).fetchone()
        if row and int(row["enrolled"]) and str(row["secret_b32"] or "").strip():
            raise ValueError(
                "authenticator already enrolled — sign in with your existing app code"
            )
        conn.execute(
            """
            INSERT INTO admin_totp(id, secret_b32, enrolled, enrolled_at)
            VALUES (1, ?, 1, ?)
            ON CONFLICT(id) DO UPDATE SET
                secret_b32 = excluded.secret_b32,
                enrolled = 1,
                enrolled_at = excluded.enrolled_at
            WHERE admin_totp.enrolled = 0 OR admin_totp.secret_b32 = ''
            """,
            (s, t),
        )
        # Re-check: if still not enrolled, concurrent enroll won
        check = conn.execute(
            "SELECT enrolled, secret_b32 FROM admin_totp WHERE id = 1"
        ).fetchone()
        if not check or not int(check["enrolled"]):
            raise ValueError(
                "authenticator already enrolled — sign in with your existing app code"
            )
        if str(check["secret_b32"] or "").strip() != s:
            raise ValueError(
                "authenticator already enrolled — sign in with your existing app code"
            )
        conn.execute("DELETE FROM admin_pending")
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "enrolled": True}


def clear_totp_enrollment_for_tests() -> None:
    """Test helper: wipe enrollment (not exposed via HTTP)."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM admin_totp")
        conn.execute("DELETE FROM admin_pending")
        conn.commit()
    finally:
        conn.close()


def _pending_hmac_key() -> bytes:
    try:
        from admin_panel import admin_session_secret  # type: ignore

        base = admin_session_secret() or "rpt-admin-2fa-fallback"
    except Exception:  # noqa: BLE001
        base = os.environ.get("RPT_ADMIN_SESSION_SECRET", "") or "rpt-admin-2fa-fallback"
    return hashlib.sha256(f"rpt-pending-2fa|{base}".encode("utf-8")).digest()


def mint_pending_token(
    *,
    stage: str,
    secret_b32: str | None = None,
    now: float | None = None,
) -> str:
    """Create short-lived pending login token (setup | verify). Returns cookie value."""
    st = (stage or "").strip().lower()
    if st not in ("setup", "verify"):
        raise ValueError("invalid stage")
    t = int(now if now is not None else time.time())
    nonce = secrets.token_hex(16)
    body = f"{t}:{nonce}:{st}"
    sig = hmac.new(_pending_hmac_key(), body.encode("utf-8"), hashlib.sha256).hexdigest()
    token = f"{body}:{sig}"
    th = hashlib.sha256(token.encode("utf-8")).hexdigest()
    exp = float(t + PENDING_TTL_SEC)
    conn = _connect()
    try:
        # prune expired
        conn.execute("DELETE FROM admin_pending WHERE expires_at < ?", (float(t),))
        conn.execute(
            """
            INSERT INTO admin_pending(token_hash, stage, secret_b32, expires_at, created_at)
            VALUES (?,?,?,?,?)
            """,
            (th, st, (secret_b32 or None), exp, float(t)),
        )
        conn.commit()
    finally:
        conn.close()
    return token


def verify_pending_token(
    token: str,
    *,
    now: float | None = None,
    expect_stage: str | None = None,
) -> dict[str, Any] | None:
    """Return pending row info if token valid; else None."""
    if not token or token.count(":") != 3:
        return None
    ts_s, nonce, stage, sig = token.split(":", 3)
    try:
        ts = int(ts_s)
    except ValueError:
        return None
    tnow = float(now if now is not None else time.time())
    if tnow - ts > PENDING_TTL_SEC or ts > tnow + 60:
        return None
    body = f"{ts}:{nonce}:{stage}"
    expect = hmac.new(
        _pending_hmac_key(), body.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expect, sig):
        return None
    if expect_stage and stage != expect_stage:
        return None
    th = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT stage, secret_b32, expires_at FROM admin_pending WHERE token_hash = ?",
            (th,),
        ).fetchone()
        if not row:
            return None
        if float(row["expires_at"]) < tnow:
            conn.execute("DELETE FROM admin_pending WHERE token_hash = ?", (th,))
            conn.commit()
            return None
        return {
            "stage": str(row["stage"]),
            "secret_b32": str(row["secret_b32"] or "") or None,
            "token_hash": th,
            "token": token,
        }
    finally:
        conn.close()


def consume_pending_token(token: str) -> None:
    th = hashlib.sha256((token or "").encode("utf-8")).hexdigest()
    conn = _connect()
    try:
        conn.execute("DELETE FROM admin_pending WHERE token_hash = ?", (th,))
        conn.commit()
    finally:
        conn.close()


def pending_from_headers(headers: Any) -> str:
    cookie = ""
    try:
        cookie = headers.get("Cookie") or headers.get("cookie") or ""
    except Exception:  # noqa: BLE001
        cookie = ""
    from admin_panel import parse_cookie_header  # type: ignore

    return parse_cookie_header(cookie).get(PENDING_COOKIE, "")


def begin_login_after_password(*, now: float | None = None) -> dict[str, Any]:
    """After password OK: return stage + pending cookie value + optional secret."""
    if is_totp_enrolled():
        tok = mint_pending_token(stage="verify", now=now)
        return {"stage": "verify", "pending_token": tok, "secret_b32": None}
    secret = generate_totp_secret()
    tok = mint_pending_token(stage="setup", secret_b32=secret, now=now)
    return {"stage": "setup", "pending_token": tok, "secret_b32": secret}


def complete_setup(
    pending_token: str,
    code: str,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Verify first TOTP against pending secret and enroll durably.

    Refuses if an authenticator is already enrolled (leftover setup pendings
    cannot replace the secret).
    """
    if is_totp_enrolled():
        consume_pending_token(pending_token)
        clear_all_pending()
        raise ValueError(
            "authenticator already enrolled — sign in with your existing app code"
        )
    info = verify_pending_token(pending_token, now=now, expect_stage="setup")
    if not info or not info.get("secret_b32"):
        raise ValueError("setup session expired or invalid — sign in again")
    secret = str(info["secret_b32"])
    if not verify_totp(secret, code, now=now):
        raise ValueError("invalid authenticator code")
    # enroll_totp_secret refuses overwrite + clears all pending rows
    enroll_totp_secret(secret, now=now)
    return {"ok": True, "enrolled": True}


def complete_verify(
    pending_token: str,
    code: str,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Verify TOTP against enrolled secret."""
    info = verify_pending_token(pending_token, now=now, expect_stage="verify")
    if not info:
        raise ValueError("login session expired or invalid — sign in again")
    secret = get_enrolled_secret()
    if not secret:
        raise ValueError("authenticator not enrolled — sign in again to set up")
    if not verify_totp(secret, code, now=now):
        raise ValueError("invalid authenticator code")
    consume_pending_token(pending_token)
    return {"ok": True, "verified": True}
