"""KEYGEN-free residual trial (72h) bound to device Ed25519 public key.

Server-authoritative clock. Does **not** issue or substitute a paid KEYGEN.
Paid KEYGEN / Stripe entitlement remains the durable paid path.

Privacy: trial rows store only ``device_pub_hex`` (admission material already used
for paid bind), optional install marker, timestamps, and status — no email, card,
or connection logs.

Anti-reinstall (best-effort):
- Same ``device_pub_hex`` cannot claim a second full 72h after expiry.
- Optional client ``install_id`` (durable install marker) cannot start a second
  full trial after first claim/expiry even if a new device key is minted while
  that marker survives wipe (prefs / keychain restore).
A full wipe that clears both keystore **and** install marker still yields a new
trial (honest residual; no PII fingerprinting).
"""

from __future__ import annotations

import re
import time
from typing import Any

# Continuous residual trial window (3 days).
TRIAL_SECONDS = 72 * 3600

STATUS_ACTIVE = "active"
STATUS_EXPIRED = "expired"
STATUS_REVOKED = "revoked"

# Synthetic session id prefix when binding trial into device_entitlements for nodes
# that only understand paid bind rows (optional; get_device_entitlement checks trial table).
TRIAL_SESSION_PREFIX = "trial:"

_INSTALL_ID_RE = re.compile(r"^[a-f0-9\-]{8,64}$", re.I)


def trial_ends_at(started_at: float, *, duration_sec: float = TRIAL_SECONDS) -> float:
    return float(started_at) + float(duration_sec)


def normalize_install_id(raw: str | None) -> str:
    """Best-effort durable install marker (client-generated UUID). Empty if invalid."""
    s = (raw or "").strip().lower().replace(" ", "")
    if not s or len(s) < 8 or len(s) > 64:
        return ""
    if not _INSTALL_ID_RE.match(s):
        return ""
    return s


def trial_is_active(
    *,
    started_at: float | None,
    ends_at: float | None,
    status: str | None,
    now: float,
) -> bool:
    """Pure clock: active trial allows residual Connect without KEYGEN."""
    st = (status or "").strip().lower()
    if st == STATUS_REVOKED:
        return False
    if ends_at is None or started_at is None:
        return False
    if float(now) >= float(ends_at):
        return False
    # Treat missing/unknown status as active if still inside window (forward-compat).
    if st in ("", STATUS_ACTIVE, "trial"):
        return True
    if st == STATUS_EXPIRED:
        return False
    return False


def decide_trial_claim(
    existing: dict[str, Any] | None,
    *,
    now: float,
    duration_sec: float = TRIAL_SECONDS,
    install_exhausted: bool = False,
) -> dict[str, Any]:
    """Pure claim decision for a device_pub trial row.

    Returns action create|reuse|deny plus fields for persistence / client.
    *install_exhausted*: durable install marker already used a full trial window.
    """
    t = float(now)
    if install_exhausted and not existing:
        # New device_pub but install marker already exhausted a trial.
        return {
            "action": "deny",
            "status": STATUS_EXPIRED,
            "started_at": None,
            "ends_at": None,
            "connect_allowed": False,
            "remaining_sec": 0.0,
            "error": "trial_exhausted",
        }
    if not existing:
        ends = trial_ends_at(t, duration_sec=duration_sec)
        return {
            "action": "create",
            "status": STATUS_ACTIVE,
            "started_at": t,
            "ends_at": ends,
            "connect_allowed": True,
            "remaining_sec": max(0.0, ends - t),
            "error": None,
        }
    started = float(existing.get("started_at") or 0.0)
    ends = float(existing.get("ends_at") or 0.0)
    status = str(existing.get("status") or STATUS_ACTIVE)
    if trial_is_active(
        started_at=started, ends_at=ends, status=status, now=t
    ):
        return {
            "action": "reuse",
            "status": STATUS_ACTIVE,
            "started_at": started,
            "ends_at": ends,
            "connect_allowed": True,
            "remaining_sec": max(0.0, ends - t),
            "error": None,
        }
    # Expired or revoked — no second full window for this device_pub (or install).
    return {
        "action": "deny",
        "status": STATUS_EXPIRED if status != STATUS_REVOKED else STATUS_REVOKED,
        "started_at": started,
        "ends_at": ends,
        "connect_allowed": False,
        "remaining_sec": 0.0,
        "error": "trial_exhausted",
    }


def connect_allowed_trial_or_paid(
    *,
    keygen_connect_allowed: bool,
    trial_connect_allowed: bool,
) -> bool:
    """Single Connect decision: trial active **or** paid KEYGEN OK."""
    return bool(keygen_connect_allowed) or bool(trial_connect_allowed)


def normalize_device_pub_hex(raw: str) -> str:
    """Reuse payments normalizer when available."""
    try:
        from payments import normalize_device_pub_hex as _n

        return _n(raw)
    except Exception:  # noqa: BLE001
        s = (raw or "").strip().lower().replace(":", "").replace(" ", "")
        if s.startswith("0x"):
            s = s[2:]
        if len(s) != 64:
            return ""
        try:
            bytes.fromhex(s)
        except ValueError:
            return ""
        return s


def _ensure_device_trials_table(conn: Any) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS device_trials (
            device_pub_hex TEXT PRIMARY KEY,
            started_at REAL NOT NULL,
            ends_at REAL NOT NULL,
            status TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_device_trials_ends ON device_trials(ends_at)"
    )
    # Best-effort install marker: survives device key rotation when client keeps it.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS device_trial_installs (
            install_id TEXT PRIMARY KEY,
            device_pub_hex TEXT NOT NULL,
            started_at REAL NOT NULL,
            ends_at REAL NOT NULL,
            status TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_device_trial_installs_pub "
        "ON device_trial_installs(device_pub_hex)"
    )


def ensure_device_trials_schema() -> None:
    from payments import _connect, init_db

    init_db()
    conn = _connect()
    try:
        _ensure_device_trials_table(conn)
        conn.commit()
    finally:
        conn.close()


def _row_to_existing(row: Any) -> dict[str, Any] | None:
    if not row:
        return None
    if hasattr(row, "keys"):
        return {
            "started_at": float(row["started_at"]),
            "ends_at": float(row["ends_at"]),
            "status": str(row["status"]),
        }
    return {
        "started_at": float(row[1]),
        "ends_at": float(row[2]),
        "status": str(row[3]),
    }


def _install_row_exhausted(row: Any, *, now: float) -> bool:
    """True if install marker already used a trial that is no longer active."""
    if not row:
        return False
    existing = _row_to_existing(row)
    if not existing:
        return False
    return not trial_is_active(
        started_at=existing["started_at"],
        ends_at=existing["ends_at"],
        status=existing["status"],
        now=now,
    )


def get_device_trial_row(
    device_pub_hex: str, *, now: float | None = None
) -> dict[str, Any] | None:
    pub = normalize_device_pub_hex(device_pub_hex)
    if not pub:
        return None
    ensure_device_trials_schema()
    from payments import _connect

    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT device_pub_hex, started_at, ends_at, status, created_at, updated_at "
            "FROM device_trials WHERE device_pub_hex = ?",
            (pub,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    keys = (
        "device_pub_hex",
        "started_at",
        "ends_at",
        "status",
        "created_at",
        "updated_at",
    )
    if hasattr(row, "keys"):
        data = {k: row[k] for k in keys}
    else:
        data = dict(zip(keys, row))
    t = float(now if now is not None else time.time())
    active = trial_is_active(
        started_at=float(data["started_at"]),
        ends_at=float(data["ends_at"]),
        status=str(data["status"]),
        now=t,
    )
    # Soft-mark expired rows for readers (do not rewrite DB on every GET).
    status = STATUS_ACTIVE if active else (
        STATUS_REVOKED if str(data["status"]).lower() == STATUS_REVOKED else STATUS_EXPIRED
    )
    return {
        "device_pub_hex": pub,
        "started_at": float(data["started_at"]),
        "ends_at": float(data["ends_at"]),
        "status": status,
        "connect_allowed": active,
        "remaining_sec": max(0.0, float(data["ends_at"]) - t) if active else 0.0,
        "kind": "device_trial",
    }


def claim_device_trial(
    device_pub_hex: str,
    *,
    now: float | None = None,
    duration_sec: float = TRIAL_SECONDS,
    install_id: str | None = None,
) -> dict[str, Any]:
    """Create or reuse a 72h trial for *device_pub_hex*; refuse after expiry.

    Optional *install_id*: durable client install marker. When present, a second
    full trial is denied if that marker already exhausted a window (even with a
    new device_pub).
    """
    pub = normalize_device_pub_hex(device_pub_hex)
    if not pub:
        return {
            "ok": False,
            "connect_allowed": False,
            "error": "bad_device_pub",
            "status": "unknown",
        }
    iid = normalize_install_id(install_id)
    t = float(now if now is not None else time.time())
    ensure_device_trials_schema()
    from payments import _connect

    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT device_pub_hex, started_at, ends_at, status "
            "FROM device_trials WHERE device_pub_hex = ?",
            (pub,),
        )
        row = cur.fetchone()
        existing = _row_to_existing(row)

        install_exhausted = False
        install_existing = None
        if iid:
            icur = conn.execute(
                "SELECT install_id, started_at, ends_at, status, device_pub_hex "
                "FROM device_trial_installs WHERE install_id = ?",
                (iid,),
            )
            irow = icur.fetchone()
            if irow:
                install_existing = _row_to_existing(irow)
                install_exhausted = _install_row_exhausted(irow, now=t)
                # If install has active window but different pub, reuse that window
                # against the install's original pub row (no second create).
                if (
                    install_existing
                    and not install_exhausted
                    and trial_is_active(
                        started_at=install_existing["started_at"],
                        ends_at=install_existing["ends_at"],
                        status=install_existing["status"],
                        now=t,
                    )
                ):
                    # Prefer install window as existing for decide (reuse).
                    if not existing:
                        existing = install_existing

        decision = decide_trial_claim(
            existing,
            now=t,
            duration_sec=duration_sec,
            install_exhausted=install_exhausted and not (
                existing
                and trial_is_active(
                    started_at=float(existing["started_at"]),
                    ends_at=float(existing["ends_at"]),
                    status=str(existing["status"]),
                    now=t,
                )
            ),
        )
        if decision["action"] == "create":
            conn.execute(
                """
                INSERT INTO device_trials(
                    device_pub_hex, started_at, ends_at, status, created_at, updated_at
                ) VALUES (?,?,?,?,?,?)
                """,
                (
                    pub,
                    decision["started_at"],
                    decision["ends_at"],
                    STATUS_ACTIVE,
                    t,
                    t,
                ),
            )
            if iid:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO device_trial_installs(
                        install_id, device_pub_hex, started_at, ends_at, status,
                        created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        iid,
                        pub,
                        decision["started_at"],
                        decision["ends_at"],
                        STATUS_ACTIVE,
                        t,
                        t,
                    ),
                )
            conn.commit()
        elif decision["action"] == "reuse":
            # Keep original ends_at; refresh updated_at only.
            conn.execute(
                "UPDATE device_trials SET updated_at = ?, status = ? WHERE device_pub_hex = ?",
                (t, STATUS_ACTIVE, pub),
            )
            # If pub row missing but install reuse, ensure pub row exists.
            if not row and existing:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO device_trials(
                        device_pub_hex, started_at, ends_at, status, created_at, updated_at
                    ) VALUES (?,?,?,?,?,?)
                    """,
                    (
                        pub,
                        existing["started_at"],
                        existing["ends_at"],
                        STATUS_ACTIVE,
                        t,
                        t,
                    ),
                )
            if iid:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO device_trial_installs(
                        install_id, device_pub_hex, started_at, ends_at, status,
                        created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        iid,
                        pub,
                        decision["started_at"],
                        decision["ends_at"],
                        STATUS_ACTIVE,
                        t,
                        t,
                    ),
                )
            conn.commit()
        elif decision["action"] == "deny":
            # Persist expired status for device_pub and install marker.
            if existing:
                conn.execute(
                    "UPDATE device_trials SET status = ?, updated_at = ? WHERE device_pub_hex = ?",
                    (decision["status"], t, pub),
                )
            if iid:
                # Mark install exhausted even if create never happened for this pub.
                ends_mark = decision.get("ends_at") or t
                started_mark = decision.get("started_at") or (t - duration_sec)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO device_trial_installs(
                        install_id, device_pub_hex, started_at, ends_at, status,
                        created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        iid,
                        pub,
                        started_mark,
                        ends_mark,
                        decision["status"],
                        t,
                        t,
                    ),
                )
            conn.commit()
    finally:
        conn.close()

    out = {
        "ok": bool(decision.get("connect_allowed")),
        "device_pub_hex": pub,
        "kind": "device_trial",
        "status": decision["status"],
        "started_at": decision.get("started_at"),
        "ends_at": decision.get("ends_at"),
        "connect_allowed": bool(decision.get("connect_allowed")),
        "remaining_sec": float(decision.get("remaining_sec") or 0.0),
        "trial_seconds": float(duration_sec),
        "action": decision.get("action"),
        "error": decision.get("error"),
        "licence_status": "TRIAL" if decision.get("connect_allowed") else "EXPIRED",
        # No KEYGEN issued
        "keygen": "",
        "requires_keygen": not bool(decision.get("connect_allowed")),
        "shop_pay_path": "/pay",
        "install_id": iid or None,
    }
    return out


def trial_allows_device(device_pub_hex: str, *, now: float | None = None) -> bool:
    row = get_device_trial_row(device_pub_hex, now=now)
    return bool(row and row.get("connect_allowed"))
