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
    """One accounting line with running balance after this row."""

    date_iso: str  # YYYY-MM-DD
    description: str
    gross_pence: int  # sale gross (0 for setup/fees-only)
    fee_pence: int  # negative or 0 (Stripe fee as minus)
    net_pence: int  # cash movement (gross + fee, fee ≤ 0)
    balance_pence: int  # running balance after this line
    kind: str  # setup | sale
    fee_source: str  # estimate | stored | n/a
    session_id: str = ""
    purchase_id: str = ""
    platform: str = ""
    amount_currency: str = CURRENCY


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
        desc = f"Paid sale ({plat or 'platform'})"
        if pid:
            desc += f" {pid}"
        out.append(
            {
                "date": d,
                "date_iso": d.isoformat(),
                "description": desc,
                "gross_pence": gross,
                "fee_pence": -fee_pos,
                "net_pence": gross - fee_pos,
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


def build_ledger(
    sales: Sequence[dict[str, Any]] | None = None,
    *,
    grants: Sequence[dict[str, Any]] | None = None,
    opening_date: date = OPENING_DATE,
    opening_balance_pence: int = OPENING_BALANCE_PENCE,
    opening_description: str = OPENING_DESCRIPTION,
) -> list[LedgerRow]:
    """Build full ledger: setup line then sales with running balance.

    If *sales* is None, derive from *grants* via :func:`sales_from_grants`.
    """
    if sales is None:
        sales = sales_from_grants(grants, opening=opening_date)

    rows: list[LedgerRow] = []
    bal = int(opening_balance_pence)
    # Setup is a pure debit (no gross/fee split)
    rows.append(
        LedgerRow(
            date_iso=opening_date.isoformat(),
            description=opening_description,
            gross_pence=0,
            fee_pence=0,
            net_pence=bal,
            balance_pence=bal,
            kind="setup",
            fee_source="n/a",
        )
    )
    for s in sales:
        net = int(s["net_pence"])
        bal = bal + net
        rows.append(
            LedgerRow(
                date_iso=str(s["date_iso"]),
                description=str(s["description"]),
                gross_pence=int(s["gross_pence"]),
                fee_pence=int(s["fee_pence"]),
                net_pence=net,
                balance_pence=bal,
                kind="sale",
                fee_source=str(s.get("fee_source") or "estimate"),
                session_id=str(s.get("session_id") or ""),
                purchase_id=str(s.get("purchase_id") or ""),
                platform=str(s.get("platform") or ""),
                amount_currency=str(s.get("currency") or CURRENCY),
            )
        )
    return rows


def load_grants_for_accounting() -> list[dict[str, Any]]:
    """Read paid grants from the live payment store (real path)."""
    try:
        from payments import list_all_grants  # type: ignore
    except Exception:  # noqa: BLE001
        from status_page.payments import list_all_grants  # type: ignore
    return list(list_all_grants() or [])


def build_ledger_from_payment_store() -> list[LedgerRow]:
    """Ledger from durable grants + opening setup costs."""
    return build_ledger(grants=load_grants_for_accounting())


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
    # Re-run balance from first selected row's own net sequence
    bal = 0
    out: list[LedgerRow] = []
    for r in selected:
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
            )
        )
    return out


def ledger_to_dicts(rows: Sequence[LedgerRow]) -> list[dict[str, Any]]:
    return [asdict(r) for r in rows]


# --- Export formats ---------------------------------------------------------

EXPORT_FORMATS = ("csv", "xlsx", "xls", "pdf", "rtf", "html", "json")


def _export_headers() -> list[str]:
    return [
        "Date",
        "Description",
        "Gross",
        "Stripe fee",
        "Net",
        "Balance",
        "Fee source",
        "Purchase ID",
        "Platform",
    ]


def _export_cells(row: LedgerRow) -> list[str]:
    return [
        row.date_iso,
        row.description,
        pence_to_pounds_str(row.gross_pence) if row.kind == "sale" else "",
        pence_to_pounds_str(row.fee_pence) if row.fee_pence else ("£0.00" if row.kind == "sale" else ""),
        pence_to_pounds_str(row.net_pence),
        pence_to_pounds_str(row.balance_pence),
        row.fee_source,
        row.purchase_id,
        row.platform,
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
