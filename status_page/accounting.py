"""RASKUL LTD admin accounting — paid sales ledger net of Stripe fees.

Opening books: **1 August 2026** line **SET UP COSTS −£6,000.00** (starting balance).
Sales auto-load from durable payment grants (gross ``amount_pence``). Net cash =
gross − Stripe fee (fee shown as a negative amount).

Stripe UK standard card fee (estimate when actual fee not stored):
  **1.5% + £0.20** per successful charge (GBP catalog).
  Source: Stripe UK pricing (standard online card). International cards may be higher;
  page labels estimate vs stored fee.

Pre–1 Aug 2026 grants are excluded so the setup line is the true start of books.
"""

from __future__ import annotations

import csv
import html
import io
import json
import os
import re
import secrets
import sqlite3
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from xml.sax.saxutils import escape as xml_escape

# --- Policy constants -------------------------------------------------------

ENTITY_NAME = "RASKUL LTD"
OPENING_DATE = date(2026, 8, 1)
OPENING_DESCRIPTION = "SET UP COSTS"
OPENING_BALANCE_PENCE = -600_000  # −£6,000.00

# Stripe UK standard online card: 1.5% + 20p (GBP)
STRIPE_FEE_PERCENT_BPS = 150  # 1.5% in basis points
STRIPE_FEE_FIXED_PENCE = 20
STRIPE_FEE_POLICY_LABEL = (
    "Stripe UK standard card estimate: 1.5% + £0.20 per successful charge "
    "(actual fee used when stored on the sale record)"
)

CURRENCY = "GBP"


@dataclass(frozen=True)
class LedgerRow:
    """One accounting line with running END BALANCE after this row."""

    date_iso: str  # YYYY-MM-DD
    description: str
    gross_pence: int  # signed cash gross (0 for setup/fees-only)
    fee_pence: int  # fees as minus (≤ 0) or 0
    net_pence: int  # cash movement = gross + fee (fee ≤ 0)
    balance_pence: int  # running END BALANCE after this line
    kind: str  # setup | sale | manual
    fee_source: str  # estimate | stored | n/a | manual
    session_id: str = ""
    purchase_id: str = ""
    platform: str = ""
    amount_currency: str = CURRENCY
    row_id: str = ""  # setup | sale:… | manual:… for delete
    created_at: float = 0.0  # sort key: oldest first, newest last


def pence_to_pounds_str(pence: int) -> str:
    """Format signed pence as £x,xxx.xx (always two decimals)."""
    sign = "-" if pence < 0 else ""
    n = abs(int(pence))
    pounds, rem = divmod(n, 100)
    return f"{sign}£{pounds:,}.{rem:02d}"


def estimate_stripe_fee_pence(gross_pence: int) -> int:
    """UK standard card fee as **positive** pence amount (caller negates for ledger).

    fee = round(gross * 1.5%) + 20p, floored at 0. Gross ≤ 0 → 0.
    """
    g = int(gross_pence)
    if g <= 0:
        return 0
    # 1.5% = 15/1000; round half up to nearest pence
    percent = (g * 15 + 500) // 1000
    return int(percent + STRIPE_FEE_FIXED_PENCE)


def resolve_stripe_fee_pence(
    gross_pence: int,
    *,
    stored_fee_pence: int | None = None,
) -> tuple[int, str]:
    """Return (positive_fee_pence, source) preferring stored fee when present."""
    if stored_fee_pence is not None:
        try:
            f = int(stored_fee_pence)
        except (TypeError, ValueError):
            f = -1
        if f >= 0:
            return f, "stored"
    return estimate_stripe_fee_pence(gross_pence), "estimate"


def _utc_date_from_created(created_at: Any) -> date | None:
    try:
        ts = float(created_at)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).date()


# Operator / lab session prefixes — not customer Stripe Checkout cash.
_NON_CHECKOUT_SESSION_PREFIXES = (
    "seed_test_",
    "admin_keygen_",
    "admin_ondemand_",
    "admin_resend_",
    "admin_",  # any other admin_* mint/recovery path
    "tester_",
    "tester_month_",
)


def _is_real_paid_grant(g: dict[str, Any]) -> bool:
    """Exclude seeds, admin recovery mints, free testers, revoked empty rows.

    Real books only count customer Checkout (or equivalent cash) sessions —
    not re-downloads, on-demand failsafe mints, or fulfilment resends.
    """
    st = str(g.get("status") or g.get("display_status") or "").strip().lower()
    if st in ("revoked", "expired", "failed"):
        return False
    try:
        amount = int(g.get("amount_pence") or 0)
    except (TypeError, ValueError):
        amount = 0
    if amount <= 0:
        return False
    sid = str(g.get("session_id") or "")
    sid_l = sid.lower()
    for pref in _NON_CHECKOUT_SESSION_PREFIXES:
        if sid_l.startswith(pref):
            return False
    if "tester_month" in sid_l:
        return False
    pid = str(g.get("purchase_id") or "")
    if pid.upper().startswith("RPT-TESTER") or pid == "TESTER":
        return False
    return True


def _sale_dedupe_key(g: dict[str, Any]) -> str:
    """One cash sale per purchase_id; else per session_id (Checkout session)."""
    pid = str(g.get("purchase_id") or "").strip()
    if pid:
        return f"pid:{pid}"
    sid = str(g.get("session_id") or "").strip()
    if sid:
        return f"sid:{sid}"
    # Last resort: token (unique grant) — should be rare
    return f"tok:{g.get('token') or id(g)}"


def sales_from_grants(
    grants: Sequence[dict[str, Any]] | None,
    *,
    opening: date = OPENING_DATE,
) -> list[dict[str, Any]]:
    """Normalize paid grant rows into sale dicts on/after opening date.

    Deduplicates reissues: multiple download tokens for the same purchase_id
    (or same Checkout session_id) count as **one** sale — earliest grant wins.
    """
    candidates: list[dict[str, Any]] = []
    for g in grants or ():
        if not isinstance(g, dict) or not _is_real_paid_grant(g):
            continue
        d = _utc_date_from_created(g.get("created_at"))
        if d is None or d < opening:
            continue
        try:
            gross = int(g.get("amount_pence") or 0)
        except (TypeError, ValueError):
            continue
        if gross <= 0:
            continue
        candidates.append(g)

    # Earliest created_at per purchase/session (reissue mints share purchase_id)
    def _created_key(g: dict[str, Any]) -> float:
        try:
            return float(g.get("created_at") or 0)
        except (TypeError, ValueError):
            return 0.0

    candidates.sort(key=lambda g: (_sale_dedupe_key(g), _created_key(g)))
    seen: set[str] = set()
    chosen: list[dict[str, Any]] = []
    for g in candidates:
        key = _sale_dedupe_key(g)
        if key in seen:
            continue
        seen.add(key)
        chosen.append(g)

    out: list[dict[str, Any]] = []
    for g in chosen:
        d = _utc_date_from_created(g.get("created_at"))
        assert d is not None  # filtered above
        gross = int(g.get("amount_pence") or 0)
        stored_fee = g.get("stripe_fee_pence")
        if stored_fee is None:
            stored_fee = g.get("fee_pence")
        fee_pos, fee_src = resolve_stripe_fee_pence(
            gross,
            stored_fee_pence=(
                int(stored_fee) if stored_fee is not None else None
            ),
        )
        plat = str(g.get("platform") or "")
        pid = str(g.get("purchase_id") or "")
        sid = str(g.get("session_id") or "")
        # Stripe context lives in Description so the Fees column stays generic
        desc = f"Paid sale ({plat or 'platform'})"
        if pid:
            desc += f" {pid}"
        if fee_pos > 0:
            if fee_src == "stored":
                desc += " — Stripe fee (stored)"
            else:
                desc += " — Stripe fee (estimate 1.5% + £0.20)"
        out.append(
            {
                "date": d,
                "date_iso": d.isoformat(),
                "description": desc,
                "gross_pence": gross,
                "fee_pence": -fee_pos,
                "net_pence": compute_net_pence(gross, -fee_pos),
                "fee_source": fee_src,
                "session_id": sid,
                "purchase_id": pid,
                "platform": plat,
                "currency": str(g.get("currency") or CURRENCY).upper() or CURRENCY,
                "created_at": g.get("created_at"),
            }
        )
    out.sort(key=lambda r: (r["date_iso"], str(r.get("created_at") or ""), r["session_id"]))
    return out


def sale_row_id(purchase_id: str = "", session_id: str = "") -> str:
    """Stable row id for an auto sale (used by delete/hide)."""
    pid = (purchase_id or "").strip()
    if pid:
        return f"sale:pid:{pid}"
    sid = (session_id or "").strip()
    if sid:
        return f"sale:sid:{sid}"
    return f"sale:unknown:{secrets.token_hex(4)}"


def _accounting_data_dir() -> Path:
    """Same durable dir family as paid_downloads (RPT_PAYMENT_DATA_DIR)."""
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


def accounting_db_path() -> Path:
    """SQLite for manual lines + hidden auto rows (sibling of payment DB)."""
    return _accounting_data_dir() / "accounting_manual.sqlite3"


def _acct_connect() -> sqlite3.Connection:
    path = accounting_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS manual_entries (
            id TEXT PRIMARY KEY,
            date_iso TEXT NOT NULL,
            description TEXT NOT NULL,
            gross_pence INTEGER NOT NULL,
            fee_pence INTEGER NOT NULL,
            net_pence INTEGER NOT NULL,
            fee_source TEXT NOT NULL,
            purchase_id TEXT NOT NULL DEFAULT '',
            platform TEXT NOT NULL DEFAULT '',
            currency TEXT NOT NULL DEFAULT 'GBP',
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS hidden_rows (
            row_id TEXT PRIMARY KEY,
            hidden_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def list_hidden_row_ids() -> set[str]:
    conn = _acct_connect()
    try:
        rows = conn.execute("SELECT row_id FROM hidden_rows").fetchall()
        return {str(r["row_id"]) for r in rows}
    finally:
        conn.close()


def list_manual_entries() -> list[dict[str, Any]]:
    conn = _acct_connect()
    try:
        rows = conn.execute(
            "SELECT * FROM manual_entries ORDER BY date_iso ASC, created_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def parse_money_to_pence(raw: str | int | float | None) -> int:
    """Parse £ / pounds string (or int pence) to signed pence.

    Accepts ``12.34``, ``-12.34``, ``£12.34``, ``(12.34)``, plain ints as pence
    only when already int-typed; bare digit strings with a decimal are pounds.
    """
    if raw is None:
        return 0
    if isinstance(raw, bool):
        raise ValueError("invalid money")
    if isinstance(raw, int):
        return int(raw)
    if isinstance(raw, float):
        return int(round(raw * 100))
    s = str(raw).strip()
    if not s:
        return 0
    s = s.replace("£", "").replace(",", "").replace("GBP", "").replace("gbp", "").strip()
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()
    if s.startswith("-"):
        neg = True
        s = s[1:].strip()
    if s.startswith("+"):
        s = s[1:].strip()
    if not s:
        return 0
    if not re.fullmatch(r"\d+(\.\d{1,2})?", s):
        raise ValueError(f"invalid money amount: {raw!r}")
    if "." in s:
        pounds, frac = s.split(".", 1)
        frac = (frac + "00")[:2]
        pence = int(pounds or "0") * 100 + int(frac)
    else:
        # Whole pounds when no decimal (operator UI enters pounds)
        pence = int(s) * 100
    return -pence if neg else pence


def normalize_fee_pence(fee_pence: int) -> int:
    """Fees always reduce cash: store as ≤ 0 (positive form input → minus)."""
    fee = int(fee_pence)
    if fee > 0:
        return -fee
    return fee


def compute_net_pence(gross_pence: int, fee_pence: int = 0) -> int:
    """Net cash movement = gross ± fees (fees are ≤ 0 after normalize)."""
    return int(gross_pence) + normalize_fee_pence(fee_pence)


def resolve_manual_gross_pence(
    gross_raw: str | int | float | None,
    *,
    sign: str = "+",
) -> int:
    """Gross for manual entry: + adds to END BALANCE, − deducts.

    Explicit minus (or parentheses) in the amount field wins over the sign
    control. Otherwise *sign* ``+`` / ``-`` applies to the absolute amount.
    """
    parsed = parse_money_to_pence(gross_raw)
    if parsed < 0:
        return parsed
    s = (sign or "+").strip().lower()
    if s in ("-", "minus", "debit", "out", "−"):
        return -abs(parsed)
    return abs(parsed)


def add_manual_entry(
    *,
    date_iso: str,
    description: str,
    gross_pence: int = 0,
    fee_pence: int = 0,
    net_pence: int | None = None,  # ignored: net always gross ± fees
    fee_source: str = "manual",
    purchase_id: str = "",
    platform: str = "",
    currency: str = CURRENCY,
    entry_id: str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Insert a durable manual ledger line.

    Net is **always** :func:`compute_net_pence` (gross ± fees). *net_pence* is
    accepted for API compatibility but never used — avoids stale overrides that
    leave END BALANCE unchanged when gross is set.
    """
    del net_pence  # always derived from gross + fees
    d = (date_iso or "").strip()
    try:
        date.fromisoformat(d)
    except ValueError as exc:
        raise ValueError(f"invalid date_iso: {date_iso!r}") from exc
    desc = (description or "").strip()
    if not desc:
        raise ValueError("description required")
    gross = int(gross_pence)
    fee = normalize_fee_pence(fee_pence)
    net = compute_net_pence(gross, fee)
    eid = (entry_id or "").strip() or f"manual:{secrets.token_hex(8)}"
    if not eid.startswith("manual:"):
        eid = f"manual:{eid}"
    t = now if now is not None else time.time()
    conn = _acct_connect()
    try:
        conn.execute(
            """
            INSERT INTO manual_entries(
                id, date_iso, description, gross_pence, fee_pence, net_pence,
                fee_source, purchase_id, platform, currency, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                eid,
                d,
                desc[:500],
                gross,
                fee,
                net,
                (fee_source or "manual")[:40],
                (purchase_id or "")[:120],
                (platform or "")[:40],
                (currency or CURRENCY)[:8],
                float(t),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "ok": True,
        "id": eid,
        "date_iso": d,
        "description": desc,
        "gross_pence": gross,
        "fee_pence": fee,
        "net_pence": net,
    }


def hide_ledger_row(row_id: str, *, now: float | None = None) -> dict[str, Any]:
    """Hide an auto setup/sale row (or no-op if already hidden)."""
    rid = (row_id or "").strip()
    if not rid:
        raise ValueError("row_id required")
    t = now if now is not None else time.time()
    conn = _acct_connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO hidden_rows(row_id, hidden_at) VALUES (?,?)",
            (rid, float(t)),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "row_id": rid, "action": "hidden"}


def delete_manual_entry(entry_id: str) -> dict[str, Any]:
    """Permanently delete a manual entry by id."""
    eid = (entry_id or "").strip()
    if not eid:
        raise ValueError("entry_id required")
    if not eid.startswith("manual:"):
        eid = f"manual:{eid}"
    conn = _acct_connect()
    try:
        cur = conn.execute("DELETE FROM manual_entries WHERE id = ?", (eid,))
        conn.commit()
        n = int(cur.rowcount or 0)
    finally:
        conn.close()
    if n <= 0:
        raise ValueError(f"manual entry not found: {eid}")
    return {"ok": True, "row_id": eid, "action": "deleted", "deleted": n}


def delete_ledger_row(row_id: str, *, now: float | None = None) -> dict[str, Any]:
    """Delete manual entry or hide auto setup/sale so balances recompute."""
    rid = (row_id or "").strip()
    if not rid:
        raise ValueError("row_id required")
    if rid.startswith("manual:"):
        return delete_manual_entry(rid)
    return hide_ledger_row(rid, now=now)


def recompute_running_balances(lines: Sequence[LedgerRow]) -> list[LedgerRow]:
    """Recompute END BALANCE (balance_pence) from nets in order (pure)."""
    bal = 0
    out: list[LedgerRow] = []
    for r in lines:
        bal = bal + int(r.net_pence)
        out.append(
            LedgerRow(
                date_iso=r.date_iso,
                description=r.description,
                gross_pence=r.gross_pence,
                fee_pence=r.fee_pence,
                net_pence=r.net_pence,
                balance_pence=bal,
                kind=r.kind,
                fee_source=r.fee_source,
                session_id=r.session_id,
                purchase_id=r.purchase_id,
                platform=r.platform,
                amount_currency=r.amount_currency,
                row_id=r.row_id,
                created_at=r.created_at,
            )
        )
    return out


def build_ledger(
    sales: Sequence[dict[str, Any]] | None = None,
    *,
    grants: Sequence[dict[str, Any]] | None = None,
    opening_date: date = OPENING_DATE,
    opening_balance_pence: int = OPENING_BALANCE_PENCE,
    opening_description: str = OPENING_DESCRIPTION,
    manual_entries: Sequence[dict[str, Any]] | None = None,
    hidden_row_ids: Sequence[str] | set[str] | None = None,
    include_manual_store: bool = False,
) -> list[LedgerRow]:
    """Build full ledger: setup + sales + manual lines with running END BALANCE.

    Order is oldest → newest (most recent last). Net for every non-setup row is
    recomputed as gross ± fees so display and export stay consistent.
    """
    if sales is None:
        sales = sales_from_grants(grants, opening=opening_date)

    hidden: set[str]
    if hidden_row_ids is not None:
        hidden = set(str(x) for x in hidden_row_ids)
    elif include_manual_store:
        hidden = list_hidden_row_ids()
    else:
        hidden = set()

    manuals: list[dict[str, Any]]
    if manual_entries is not None:
        manuals = list(manual_entries)
    elif include_manual_store:
        manuals = list_manual_entries()
    else:
        manuals = []

    lines: list[LedgerRow] = []
    # Setup is a pure debit (no gross/fee split)
    if "setup" not in hidden:
        lines.append(
            LedgerRow(
                date_iso=opening_date.isoformat(),
                description=opening_description,
                gross_pence=0,
                fee_pence=0,
                net_pence=int(opening_balance_pence),
                balance_pence=0,  # filled by recompute
                kind="setup",
                fee_source="n/a",
                row_id="setup",
                created_at=0.0,
            )
        )
    for s in sales:
        rid = sale_row_id(
            purchase_id=str(s.get("purchase_id") or ""),
            session_id=str(s.get("session_id") or ""),
        )
        if rid in hidden:
            continue
        try:
            ca = float(s.get("created_at") or 0)
        except (TypeError, ValueError):
            ca = 0.0
        g = int(s["gross_pence"])
        f = normalize_fee_pence(int(s["fee_pence"]))
        lines.append(
            LedgerRow(
                date_iso=str(s["date_iso"]),
                description=str(s["description"]),
                gross_pence=g,
                fee_pence=f,
                net_pence=compute_net_pence(g, f),
                balance_pence=0,
                kind="sale",
                fee_source=str(s.get("fee_source") or "estimate"),
                session_id=str(s.get("session_id") or ""),
                purchase_id=str(s.get("purchase_id") or ""),
                platform=str(s.get("platform") or ""),
                amount_currency=str(s.get("currency") or CURRENCY),
                row_id=rid,
                created_at=ca,
            )
        )
    for m in manuals:
        mid = str(m.get("id") or "")
        if not mid or mid in hidden:
            continue
        try:
            ca = float(m.get("created_at") or 0)
        except (TypeError, ValueError):
            ca = 0.0
        g = int(m.get("gross_pence") or 0)
        f = normalize_fee_pence(int(m.get("fee_pence") or 0))
        lines.append(
            LedgerRow(
                date_iso=str(m.get("date_iso") or ""),
                description=str(m.get("description") or ""),
                gross_pence=g,
                fee_pence=f,
                net_pence=compute_net_pence(g, f),
                balance_pence=0,
                kind="manual",
                fee_source=str(m.get("fee_source") or "manual"),
                purchase_id=str(m.get("purchase_id") or ""),
                platform=str(m.get("platform") or ""),
                amount_currency=str(m.get("currency") or CURRENCY),
                row_id=mid,
                created_at=ca,
            )
        )
    lines = sort_ledger_oldest_first(lines)
    return recompute_running_balances(lines)


def _parse_ledger_date(date_iso: str) -> date:
    """Parse YYYY-MM-DD for sort; unknown/empty → far-future so they sink last."""
    raw = str(date_iso or "").strip()
    if not raw:
        return date(9999, 12, 31)
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        # Last resort: keep lexicographic fallback via epoch-like sentinel
        return date(9999, 12, 30)


def sort_ledger_oldest_first(lines: Sequence[LedgerRow]) -> list[LedgerRow]:
    """Stable chronological order: oldest first, **most recent last** (bottom of table).

    Primary key is calendar date ascending; then ``created_at``; then kind
    (setup before same-day sales/manuals); then ``row_id``.
    Never reverse=True — books read top→bottom as first transaction → newest.
    """
    kind_order = {"setup": 0, "sale": 1, "manual": 2}

    def _sort_key(r: LedgerRow) -> tuple:
        try:
            ca = float(r.created_at or 0)
        except (TypeError, ValueError):
            ca = 0.0
        return (
            _parse_ledger_date(str(r.date_iso or "")),
            ca,
            kind_order.get(str(r.kind or ""), 9),
            str(r.row_id or ""),
        )

    # Explicit reverse=False so display cannot silently flip to newest-first.
    return sorted(lines, key=_sort_key, reverse=False)


def ensure_ledger_oldest_first(lines: Sequence[LedgerRow]) -> list[LedgerRow]:
    """Sort oldest→newest and recompute END BALANCE (safe for render/export paths)."""
    return recompute_running_balances(sort_ledger_oldest_first(list(lines)))


def load_grants_for_accounting() -> list[dict[str, Any]]:
    """Read paid grants from the live payment store (real path)."""
    try:
        from payments import list_all_grants  # type: ignore
    except Exception:  # noqa: BLE001
        from status_page.payments import list_all_grants  # type: ignore
    return list(list_all_grants() or [])


def build_ledger_from_payment_store() -> list[LedgerRow]:
    """Ledger from durable grants + setup + manual entries − hidden rows."""
    return build_ledger(
        grants=load_grants_for_accounting(),
        include_manual_store=True,
    )


def filter_ledger_by_period(
    rows: Sequence[LedgerRow],
    *,
    year: int | None = None,
    month: int | None = None,
    from_year: int | None = None,
    from_month: int | None = None,
    to_year: int | None = None,
    to_month: int | None = None,
) -> list[LedgerRow]:
    """Filter rows by calendar month or inclusive month range.

    When filtering, **recompute running balance** within the export window so
    the first included row (often setup if in range) anchors correctly.
    If setup is outside the window, start balance at 0 and only sum included nets.
    """
    def in_range(d: date) -> bool:
        if year is not None and month is not None:
            return d.year == year and d.month == month
        if from_year is not None and from_month is not None and to_year is not None and to_month is not None:
            start = (from_year, from_month)
            end = (to_year, to_month)
            cur = (d.year, d.month)
            return start <= cur <= end
        return True

    selected = [r for r in rows if in_range(date.fromisoformat(r.date_iso))]
    # Keep chronological order after filter (oldest → newest).
    return ensure_ledger_oldest_first(selected)


def ledger_to_dicts(rows: Sequence[LedgerRow]) -> list[dict[str, Any]]:
    return [asdict(r) for r in rows]


# --- Export formats ---------------------------------------------------------

EXPORT_FORMATS = ("csv", "xlsx", "xls", "pdf", "rtf", "html", "json")


def _export_headers() -> list[str]:
    return [
        "Date",
        "Description",
        "Gross",
        "Fees",
        "Net",
        "Fee source",
        "Purchase ID",
        "Platform",
        "END BALANCE",
    ]


def _export_cells(row: LedgerRow) -> list[str]:
    show_money = row.kind in ("sale", "manual")
    return [
        row.date_iso,
        row.description,
        pence_to_pounds_str(row.gross_pence) if show_money else "",
        (
            pence_to_pounds_str(row.fee_pence)
            if row.fee_pence
            else ("£0.00" if show_money else "")
        ),
        pence_to_pounds_str(row.net_pence),
        row.fee_source,
        row.purchase_id,
        row.platform,
        pence_to_pounds_str(row.balance_pence),
    ]


def export_csv(rows: Sequence[LedgerRow]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_export_headers())
    for r in rows:
        w.writerow(_export_cells(r))
    return buf.getvalue().encode("utf-8-sig")


def export_json(rows: Sequence[LedgerRow]) -> bytes:
    payload = {
        "entity": ENTITY_NAME,
        "currency": CURRENCY,
        "fee_policy": STRIPE_FEE_POLICY_LABEL,
        "opening_date": OPENING_DATE.isoformat(),
        "rows": ledger_to_dicts(rows),
    }
    return (json.dumps(payload, indent=2) + "\n").encode("utf-8")


def export_html(rows: Sequence[LedgerRow]) -> bytes:
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'/>",
        f"<title>{html.escape(ENTITY_NAME)} accounts</title>",
        "<style>table{border-collapse:collapse;font-family:sans-serif;font-size:12px}"
        "th,td{border:1px solid #ccc;padding:4px 8px;text-align:left}"
        "th{background:#eee}.num{text-align:right}</style></head><body>",
        f"<h1>{html.escape(ENTITY_NAME)} — accounting export</h1>",
        f"<p>{html.escape(STRIPE_FEE_POLICY_LABEL)}</p>",
        "<table><thead><tr>",
    ]
    for h in _export_headers():
        parts.append(f"<th>{html.escape(h)}</th>")
    parts.append("</tr></thead><tbody>")
    for r in rows:
        cells = _export_cells(r)
        parts.append("<tr>")
        for i, c in enumerate(cells):
            cls = " class='num'" if i in (2, 3, 4, 5) else ""
            parts.append(f"<td{cls}>{html.escape(c)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table></body></html>")
    return "".join(parts).encode("utf-8")


def export_rtf(rows: Sequence[LedgerRow]) -> bytes:
    """Simple RTF table-like lines (Word/LibreOffice open)."""
    def rtf_escape(s: str) -> str:
        return (
            s.replace("\\", "\\\\")
            .replace("{", "\\{")
            .replace("}", "\\}")
            .replace("£", "\\'a3")
        )

    lines = [
        r"{\rtf1\ansi\deff0",
        r"{\fonttbl{\f0 Arial;}}",
        r"\f0\fs20 ",
        rtf_escape(f"{ENTITY_NAME} accounting export") + r"\par\par ",
        rtf_escape(STRIPE_FEE_POLICY_LABEL) + r"\par\par ",
    ]
    lines.append(rtf_escape(" | ".join(_export_headers())) + r"\par ")
    lines.append(r"\par ")
    for r in rows:
        lines.append(rtf_escape(" | ".join(_export_cells(r))) + r"\par ")
    lines.append("}")
    return "".join(lines).encode("utf-8")


def export_pdf(rows: Sequence[LedgerRow]) -> bytes:
    """Minimal single-page-stream PDF (Helvetica text lines)."""
    lines_out = [
        f"{ENTITY_NAME} accounting export",
        STRIPE_FEE_POLICY_LABEL,
        "",
        " | ".join(_export_headers()),
        "-" * 72,
    ]
    for r in rows:
        lines_out.append(" | ".join(_export_cells(r)))
    # PDF content stream
    y = 800
    content_parts = ["BT /F1 9 Tf 40 800 Td 12 TL"]
    for i, line in enumerate(lines_out[:60]):
        safe = (
            line.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .replace("£", "GBP ")
        )
        if i == 0:
            content_parts.append(f"({safe[:120]}) Tj")
        else:
            content_parts.append(f"T* ({safe[:120]}) Tj")
    content_parts.append("ET")
    stream = "\n".join(content_parts).encode("latin-1", errors="replace")

    objs: list[bytes] = []
    objs.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objs.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objs.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objs.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode()
        + stream
        + b"\nendstream\nendobj\n"
    )
    objs.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objs:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)


def _xlsx_sheet_xml(rows: Sequence[LedgerRow]) -> str:
    def cell(ref: str, value: str) -> str:
        return (
            f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(value)}</t></is></c>'
        )

    # Column letters A-I
    cols = "ABCDEFGHI"
    sheet_rows = []
    headers = _export_headers()
    cells = "".join(cell(f"{cols[i]}1", headers[i]) for i in range(len(headers)))
    sheet_rows.append(f'<row r="1">{cells}</row>')
    for ri, r in enumerate(rows, start=2):
        vals = _export_cells(r)
        cells = "".join(
            cell(f"{cols[i]}{ri}", vals[i]) for i in range(len(vals))
        )
        sheet_rows.append(f'<row r="{ri}">{cells}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"
    )


def export_xlsx(rows: Sequence[LedgerRow]) -> bytes:
    """Office Open XML spreadsheet (no third-party deps)."""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""
    wb = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Accounts" sheetId="1" r:id="rId1"/></sheets>
</workbook>
"""
    wb_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", wb)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        zf.writestr("xl/worksheets/sheet1.xml", _xlsx_sheet_xml(rows))
    return buf.getvalue()


def export_xls(rows: Sequence[LedgerRow]) -> bytes:
    """Excel 2003 XML Spreadsheet (opens in Excel as .xls)."""
    parts = [
        '<?xml version="1.0"?>',
        '<?mso-application progid="Excel.Sheet"?>',
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">',
        "<Worksheet ss:Name=\"Accounts\"><Table>",
    ]
    parts.append("<Row>")
    for h in _export_headers():
        parts.append(f'<Cell><Data ss:Type="String">{xml_escape(h)}</Data></Cell>')
    parts.append("</Row>")
    for r in rows:
        parts.append("<Row>")
        for c in _export_cells(r):
            parts.append(
                f'<Cell><Data ss:Type="String">{xml_escape(c)}</Data></Cell>'
            )
        parts.append("</Row>")
    parts.append("</Table></Worksheet></Workbook>")
    return "".join(parts).encode("utf-8")


def export_ledger(
    rows: Sequence[LedgerRow],
    *,
    fmt: str,
) -> tuple[bytes, str, str]:
    """Return (bytes, content_type, filename_suffix) for *fmt*."""
    f = (fmt or "csv").strip().lower().lstrip(".")
    if f in ("xlsx", "excel"):
        return export_xlsx(rows), (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ), "xlsx"
    if f == "xls":
        return (
            export_xls(rows),
            "application/vnd.ms-excel",
            "xls",
        )
    if f == "pdf":
        return export_pdf(rows), "application/pdf", "pdf"
    if f == "rtf":
        return export_rtf(rows), "application/rtf", "rtf"
    if f == "html":
        return export_html(rows), "text/html; charset=utf-8", "html"
    if f == "json":
        return export_json(rows), "application/json", "json"
    # default csv
    return export_csv(rows), "text/csv; charset=utf-8", "csv"


def parse_export_period(
    form: dict[str, str],
) -> dict[str, Any]:
    """Parse admin form fields into filter kwargs + filename stem."""
    mode = (form.get("period_mode") or form.get("mode") or "month").strip().lower()
    if mode in ("range", "year", "from_to", "period"):
        fy = int(form.get("from_year") or form.get("year") or OPENING_DATE.year)
        fm = int(form.get("from_month") or "1")
        ty = int(form.get("to_year") or form.get("year") or OPENING_DATE.year)
        tm = int(form.get("to_month") or "12")
        fm = max(1, min(12, fm))
        tm = max(1, min(12, tm))
        return {
            "filter": {
                "from_year": fy,
                "from_month": fm,
                "to_year": ty,
                "to_month": tm,
            },
            "stem": f"{fy}-{fm:02d}_to_{ty}-{tm:02d}",
        }
    # single month
    y = int(form.get("year") or form.get("month_year") or OPENING_DATE.year)
    m = int(form.get("month") or form.get("month_num") or OPENING_DATE.month)
    m = max(1, min(12, m))
    return {
        "filter": {"year": y, "month": m},
        "stem": f"{y}-{m:02d}",
    }
