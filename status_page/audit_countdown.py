"""Next security-audit countdown (1-day cadence from last audit write).

Used by the public VPN APP Shop real-time counter.
Source of truth for last run: ``status_page/static/security_audit_latest.json``
``generated_at`` (written by ``scripts/run_security_audit.py --write``).
Period matches ``scripts/install_security_audit_timer.sh`` default ``PERIOD=1d``.

Honest job: security audit probes + public AUDIT refresh + temporary audit
scratch wipe — not a full VPS disk wipe or end-user **Restore Internet**.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Matches install_security_audit_timer.sh default and AUDIT.md cadence.
AUDIT_PERIOD = timedelta(days=1)
AUDIT_PERIOD_SECONDS = int(AUDIT_PERIOD.total_seconds())  # 86400

# Portal homepage: short label + one-line honesty (what the ~1d timer actually does)
TIME_TIL_NEXT_AUDIT_LABEL = "time til next audit / wipedown"
TIME_TIL_NEXT_AUDIT_BLURB = (
    "~every 1 day: security audit (node probes, package confidence, privacy checks) "
    "refreshes the public audit; temporary audit scratch is wiped — "
    "not a full server or device erase"
)

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_DEFAULT_JSON = _STATIC_DIR / "security_audit_latest.json"


def parse_audit_generated_at(value: str | None) -> datetime | None:
    """Parse ISO-8601 audit timestamps (``...Z`` or offset) to UTC datetime."""
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    # Support trailing Z
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Fallback: YYYY-MM-DDTHH:MM:SS only
        m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", s)
        if not m:
            return None
        try:
            dt = datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def next_audit_at(last_generated_at: datetime, period: timedelta | None = None) -> datetime:
    """Deadline for the next scheduled audit after ``last_generated_at``."""
    p = period if period is not None else AUDIT_PERIOD
    if last_generated_at.tzinfo is None:
        last_generated_at = last_generated_at.replace(tzinfo=timezone.utc)
    return last_generated_at.astimezone(timezone.utc) + p


def next_audit_at_rolling(
    last_generated_at: datetime,
    *,
    now: datetime | None = None,
    period: timedelta | None = None,
) -> datetime:
    """Next audit deadline, rolling forward by *period* while overdue.

    Prevents the public countdown from freezing at ``00:00:00`` when
    ``generated_at`` is stale relative to wall clock (common when the node
    timer still runs but status-host JSON has not been republished).
    """
    p = period if period is not None else AUDIT_PERIOD
    n = now if now is not None else datetime.now(timezone.utc)
    if n.tzinfo is None:
        n = n.replace(tzinfo=timezone.utc)
    n = n.astimezone(timezone.utc)
    last = last_generated_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    last = last.astimezone(timezone.utc)
    nxt = last + p
    # Cap iterations (e.g. years of stale timestamps still resolve quickly)
    for _ in range(50_000):
        if nxt > n:
            return nxt
        nxt = nxt + p
    return nxt


def remaining_seconds_until(
    deadline: datetime,
    *,
    now: datetime | None = None,
) -> int:
    """Whole seconds remaining until ``deadline`` (0 if overdue)."""
    n = now if now is not None else datetime.now(timezone.utc)
    if n.tzinfo is None:
        n = n.replace(tzinfo=timezone.utc)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    delta = deadline.astimezone(timezone.utc) - n.astimezone(timezone.utc)
    return max(0, int(delta.total_seconds()))


def split_countdown_units(seconds: int) -> dict[str, int]:
    """Split remaining seconds into days, hours, minutes, seconds."""
    total = max(0, int(seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    return {
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "seconds": secs,
    }


def format_countdown(seconds: int) -> str:
    """Human countdown ``Dd HH:MM:SS`` (always includes days, hours, minutes, seconds)."""
    parts = split_countdown_units(seconds)
    d, h, m, s = parts["days"], parts["hours"], parts["minutes"], parts["seconds"]
    return f"{d}d {h:02d}:{m:02d}:{s:02d}"


def load_last_audit_generated_at(
    path: Path | None = None,
) -> datetime | None:
    """Read ``generated_at`` from security_audit_latest.json when present."""
    p = path if path is not None else _DEFAULT_JSON
    try:
        if not p.is_file():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return parse_audit_generated_at(str(data.get("generated_at") or ""))


def countdown_state(
    *,
    now: datetime | None = None,
    last_generated_at: datetime | None = None,
    json_path: Path | None = None,
    period: timedelta | None = None,
) -> dict[str, Any]:
    """Compute countdown fields for UI / tests.

    Returns dict with:
      available, last_generated_at, next_audit_at, remaining_seconds, display,
      period_seconds, label
    """
    last = last_generated_at
    if last is None:
        last = load_last_audit_generated_at(json_path)
    p = period if period is not None else AUDIT_PERIOD
    if last is None:
        return {
            "available": False,
            "last_generated_at": None,
            "next_audit_at": None,
            "remaining_seconds": None,
            "display": "—",
            "period_seconds": int(p.total_seconds()),
            "label": TIME_TIL_NEXT_AUDIT_LABEL,
            "blurb": TIME_TIL_NEXT_AUDIT_BLURB,
        }
    # Roll forward when last+period is already past so UI never freezes at 00:00:00
    nxt = next_audit_at_rolling(last, now=now, period=p)
    rem = remaining_seconds_until(nxt, now=now)
    return {
        "available": True,
        "last_generated_at": last.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "next_audit_at": nxt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "remaining_seconds": rem,
        "display": format_countdown(rem),
        "period_seconds": int(p.total_seconds()),
        "label": TIME_TIL_NEXT_AUDIT_LABEL,
        "blurb": TIME_TIL_NEXT_AUDIT_BLURB,
        "rolled_forward": nxt > next_audit_at(last, p),
    }


def load_security_audit_latest(
    path: Path | None = None,
    *,
    public: bool = True,
) -> dict[str, Any] | None:
    """Load ``security_audit_latest.json`` when present (dict or None).

    When *public* is True (default), residual monopin IPv4s are redacted for
    any public consumer. Pass ``public=False`` for operator/admin tooling.
    """
    p = path if path is not None else _DEFAULT_JSON
    try:
        if not p.is_file():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if public:
        try:
            import sys
            from pathlib import Path as _P

            root = str(_P(__file__).resolve().parents[1])
            if root not in sys.path:
                sys.path.insert(0, root)
            from client.residual_public import public_security_audit_payload

            return public_security_audit_payload(data)
        except Exception:  # noqa: BLE001
            # Fail closed: blank known monopin hosts
            for key in ("node_host",):
                if key in data and isinstance(data[key], str):
                    data[key] = "VPN node"
            for sec_name in ("tcp_status", "udp", "http_status"):
                sec = data.get(sec_name)
                if isinstance(sec, dict) and "host" in sec:
                    sec["host"] = "VPN node"
    return data


def current_audit_rag_colour(
    *,
    json_path: Path | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map the latest audit overall package RAG to Green / Amber / Red.

    Prefers ``package_rag.overall``. Falls back to ``overall_ok`` boolean
    (True→Green, False→Red). When neither is available, ``available`` is False
    (honest unavailable — not a fake Green).

    Returns::
      {
        "available": bool,
        "colour": "Green"|"Amber"|"Red"|None,
        "css": "rag-green"|"rag-amber"|"rag-red"|None,
        "label": display label for discrete text,
      }
    """
    payload = data if data is not None else load_security_audit_latest(json_path)
    if not payload:
        return {
            "available": False,
            "colour": None,
            "css": None,
            "label": "unavailable",
        }
    colour: str | None = None
    pr = payload.get("package_rag")
    if isinstance(pr, dict):
        raw = str(pr.get("overall") or "").strip()
        low = raw.lower()
        if low == "green" or raw in ("🟩", "Green"):
            colour = "Green"
        elif low == "amber" or raw in ("🟧", "Amber"):
            colour = "Amber"
        elif low == "red" or raw in ("🟥", "Red"):
            colour = "Red"
    if colour is None and "overall_ok" in payload:
        ok = payload.get("overall_ok")
        if ok is True:
            colour = "Green"
        elif ok is False:
            colour = "Red"
    if colour is None:
        return {
            "available": False,
            "colour": None,
            "css": None,
            "label": "unavailable",
        }
    css_map = {
        "Green": "rag-green",
        "Amber": "rag-amber",
        "Red": "rag-red",
    }
    return {
        "available": True,
        "colour": colour,
        "css": css_map[colour],
        "label": colour,
    }


def format_last_audit_run_display(iso_z: str | None) -> str:
    """Human-readable last audit run for public UI (UTC)."""
    if not iso_z:
        return "not available"
    dt = parse_audit_generated_at(str(iso_z))
    if dt is None:
        return str(iso_z)
    # e.g. 2026-07-22 12:45:00 UTC
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def render_audit_countdown_html(
    *,
    now: datetime | None = None,
    json_path: Path | None = None,
) -> str:
    """HTML fragment: label + countdown + honest blurb + last audit run."""
    state = countdown_state(now=now, json_path=json_path)
    label = html.escape(str(state["label"]))
    blurb = html.escape(str(state.get("blurb") or TIME_TIL_NEXT_AUDIT_BLURB))
    display = html.escape(str(state["display"]))
    next_iso = html.escape(str(state.get("next_audit_at") or ""))
    last_raw = state.get("last_generated_at")
    last_disp = html.escape(format_last_audit_run_display(last_raw if isinstance(last_raw, str) else None))
    available = "1" if state["available"] else "0"
    # data-next-audit is ISO Z used by client JS; empty when unavailable
    return f"""  <div class="audit-countdown" id="audit-countdown" data-available="{available}" data-next-audit="{next_iso}" data-period-seconds="{state['period_seconds']}" data-last-audit="{html.escape(str(last_raw or ''))}">
    <div class="audit-countdown-row">
      <span class="audit-countdown-label">{label}</span>
      <span class="audit-countdown-value" id="audit-countdown-value" aria-live="polite">{display}</span>
    </div>
    <p class="audit-countdown-blurb" id="audit-countdown-blurb">{blurb}</p>
    <p class="audit-last-run" id="audit-last-run">last audit run: <time id="audit-last-run-time" datetime="{html.escape(str(last_raw or ''))}">{last_disp}</time></p>
  </div>
  <script id="audit-last-run-helpers-script" src="/static/audit_last_run_helpers.js"></script>
  <script id="audit-countdown-script" src="/static/audit_countdown.js"></script>
"""


def render_audit_page_ticker_html(
    *,
    now: datetime | None = None,
    json_path: Path | None = None,
    rag: dict[str, Any] | None = None,
) -> str:
    """Countdown + last-run + current-run RAG for the public **/AUDIT.md** page.

    Placed under the audit H1. Uses unique element ids so it does not collide
    with the homepage ``#audit-countdown`` widget.

    **Last-run** always comes from ``security_audit_latest.json`` ``generated_at``
    (updated by every ``run_security_audit.py --write``), not a stale markdown cell.
    """
    state = countdown_state(now=now, json_path=json_path)
    rag_state = rag if rag is not None else current_audit_rag_colour(json_path=json_path)
    display = html.escape(str(state["display"]))
    next_iso = html.escape(str(state.get("next_audit_at") or ""))
    available = "1" if state["available"] else "0"
    period = int(state["period_seconds"])
    last_raw = state.get("last_generated_at")
    last_iso = html.escape(str(last_raw or ""))
    last_disp = html.escape(
        format_last_audit_run_display(last_raw if isinstance(last_raw, str) else None)
    )

    if rag_state.get("available") and rag_state.get("css") and rag_state.get("colour"):
        css = html.escape(str(rag_state["css"]))
        colour = html.escape(str(rag_state["colour"]))
        colour_attr = colour.lower()
        rag_block = f"""
    <div class="audit-page-current-run" id="audit-page-current-run"
         data-rag-colour="{colour_attr}">
      <span class="rag-swatch {css}" title="{colour}"
            role="img" aria-label="{colour}"></span>
      <span class="audit-page-current-run-text" id="audit-page-current-run-text">
        The current audit run is <strong id="audit-page-current-run-colour">{colour}</strong>.
      </span>
    </div>"""
    else:
        rag_block = """
    <div class="audit-page-current-run audit-page-current-run-unavailable"
         id="audit-page-current-run" data-rag-colour="unavailable">
      <span class="audit-page-current-run-text" id="audit-page-current-run-text">
        The current audit run colour is <strong>unavailable</strong>.
      </span>
    </div>"""

    return f"""
  <div class="audit-page-ticker" id="audit-page-ticker"
       data-available="{available}" data-next-audit="{next_iso}"
       data-period-seconds="{period}" data-last-audit="{last_iso}">
    <div class="audit-page-countdown-row">
      <span class="audit-page-countdown-label" id="audit-page-countdown-label">
        Time until next audit
      </span>
      <span class="audit-page-countdown-value" id="audit-page-countdown-value"
            aria-live="polite">{display}</span>
    </div>
    <p class="audit-page-last-run" id="audit-page-last-run">
      last audit run:
      <time id="audit-page-last-run-time" datetime="{last_iso}">{last_disp}</time>
    </p>
    {rag_block}
    <p class="audit-page-ticker-blurb" id="audit-page-ticker-blurb">
      ~every 1 day automated security pass (node probes, package confidence, privacy
      checks). Last-run timestamp refreshes on every
      <code>run_security_audit.py --write</code> via
      <code>/static/security_audit_latest.json</code> (also while this page stays open).
    </p>
  </div>
  <script id="audit-last-run-helpers-script" src="/static/audit_last_run_helpers.js"></script>
  <script id="audit-page-ticker-script" src="/static/audit_page_ticker.js"></script>
"""


def overlay_audit_generated_in_markdown_html(
    body_html: str,
    *,
    json_path: Path | None = None,
) -> str:
    """Replace stale **Audit generated** table cells with live JSON ``generated_at``.

    The AUDIT.md body is regenerated on ``--write``, but status hosts can lag.
    The public HTML shell always prefers ``security_audit_latest.json`` so the
    visible last-run date advances after every successful audit write.
    """
    last = load_last_audit_generated_at(json_path)
    if last is None or not body_html:
        return body_html
    iso = last.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Human day line matches build_markdown style: "29 July 2026"
    human = last.astimezone(timezone.utc).strftime("%d %B %Y").lstrip("0")
    # Common markdownish table cell patterns after conversion
    patterns = [
        # <strong>27 July 2026</strong> (<code>2026-07-27T08:27:28Z</code>)
        (
            re.compile(
                r"(Audit generated</strong></td><td><strong>)[^<]+"
                r"(</strong>\s*\(<code>)[0-9T:\-Z]+(</code>)",
                re.IGNORECASE,
            ),
            rf"\g<1>{human}\g<2>{iso}\g<3>",
        ),
        (
            re.compile(
                r"(<strong>Audit generated</strong></td>\s*<td>)[^<]*"
                r"(<code>)[0-9T:\-Z]+(</code>)",
                re.IGNORECASE,
            ),
            rf"\g<1><strong>{human}</strong> (\g<2>{iso}\g<3>)",
        ),
    ]
    out = body_html
    for pat, repl in patterns:
        out2, n = pat.subn(repl, out, count=1)
        if n:
            return out2
    return out
