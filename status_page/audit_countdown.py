"""Next security-audit countdown (4h cadence from last audit write).

Used by the public VPN APP Shop real-time counter.
Source of truth for last run: ``status_page/static/security_audit_latest.json``
``generated_at`` (written by ``scripts/run_security_audit.py --write``).
Period matches ``scripts/install_security_audit_timer.sh`` default ``PERIOD=4h``.

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
AUDIT_PERIOD = timedelta(hours=4)
AUDIT_PERIOD_SECONDS = int(AUDIT_PERIOD.total_seconds())  # 14400

# Portal homepage: short label + one-line honesty (what the ~4h timer actually does)
TIME_TIL_NEXT_AUDIT_LABEL = "time til next audit / wipedown"
TIME_TIL_NEXT_AUDIT_BLURB = (
    "~every 4h: security audit (node probes, package confidence, privacy checks) "
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


def format_countdown(seconds: int) -> str:
    """Human countdown ``HH:MM:SS`` (hours may exceed 24 for long periods)."""
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


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
    nxt = next_audit_at(last, p)
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
    }


def load_security_audit_latest(
    path: Path | None = None,
) -> dict[str, Any] | None:
    """Load ``security_audit_latest.json`` when present (dict or None)."""
    p = path if path is not None else _DEFAULT_JSON
    try:
        if not p.is_file():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


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


def render_audit_countdown_html(
    *,
    now: datetime | None = None,
    json_path: Path | None = None,
) -> str:
    """HTML fragment: label + countdown + honest blurb (1s ``setInterval``)."""
    state = countdown_state(now=now, json_path=json_path)
    label = html.escape(str(state["label"]))
    blurb = html.escape(str(state.get("blurb") or TIME_TIL_NEXT_AUDIT_BLURB))
    display = html.escape(str(state["display"]))
    next_iso = html.escape(str(state.get("next_audit_at") or ""))
    available = "1" if state["available"] else "0"
    # data-next-audit is ISO Z used by client JS; empty when unavailable
    return f"""  <div class="audit-countdown" id="audit-countdown" data-available="{available}" data-next-audit="{next_iso}" data-period-seconds="{state['period_seconds']}">
    <div class="audit-countdown-row">
      <span class="audit-countdown-label">{label}</span>
      <span class="audit-countdown-value" id="audit-countdown-value" aria-live="polite">{display}</span>
    </div>
    <p class="audit-countdown-blurb" id="audit-countdown-blurb">{blurb}</p>
  </div>
  <script>
  (function () {{
    var root = document.getElementById("audit-countdown");
    var el = document.getElementById("audit-countdown-value");
    if (!root || !el) return;
    var nextIso = root.getAttribute("data-next-audit") || "";
    var available = root.getAttribute("data-available") === "1";
    function pad(n) {{ return n < 10 ? "0" + n : String(n); }}
    function fmt(sec) {{
      sec = Math.max(0, Math.floor(sec));
      var h = Math.floor(sec / 3600);
      var m = Math.floor((sec % 3600) / 60);
      var s = sec % 60;
      return pad(h) + ":" + pad(m) + ":" + pad(s);
    }}
    function tick() {{
      if (!available || !nextIso) {{
        el.textContent = "—";
        return;
      }}
      var deadline = Date.parse(nextIso);
      if (isNaN(deadline)) {{
        el.textContent = "—";
        return;
      }}
      var rem = Math.max(0, Math.floor((deadline - Date.now()) / 1000));
      el.textContent = fmt(rem);
    }}
    tick();
    setInterval(tick, 1000);
  }})();
  </script>
"""


def render_audit_page_ticker_html(
    *,
    now: datetime | None = None,
    json_path: Path | None = None,
    rag: dict[str, Any] | None = None,
) -> str:
    """Countdown + current-run RAG colour for the public **/AUDIT.md** page.

    Placed under the audit H1. Uses unique element ids so it does not collide
    with the homepage ``#audit-countdown`` widget.
    """
    state = countdown_state(now=now, json_path=json_path)
    rag_state = rag if rag is not None else current_audit_rag_colour(json_path=json_path)
    display = html.escape(str(state["display"]))
    next_iso = html.escape(str(state.get("next_audit_at") or ""))
    available = "1" if state["available"] else "0"
    period = int(state["period_seconds"])

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
       data-period-seconds="{period}">
    <div class="audit-page-countdown-row">
      <span class="audit-page-countdown-label" id="audit-page-countdown-label">
        Time until next audit
      </span>
      <span class="audit-page-countdown-value" id="audit-page-countdown-value"
            aria-live="polite">{display}</span>
    </div>
    {rag_block}
    <p class="audit-page-ticker-blurb" id="audit-page-ticker-blurb">
      ~every 4h automated security pass (node probes, package confidence, privacy
      checks). Countdown from last written audit timestamp.
    </p>
  </div>
  <script>
  (function () {{
    var root = document.getElementById("audit-page-ticker");
    var el = document.getElementById("audit-page-countdown-value");
    if (!root || !el) return;
    var nextIso = root.getAttribute("data-next-audit") || "";
    var available = root.getAttribute("data-available") === "1";
    function pad(n) {{ return n < 10 ? "0" + n : String(n); }}
    function fmt(sec) {{
      sec = Math.max(0, Math.floor(sec));
      var h = Math.floor(sec / 3600);
      var m = Math.floor((sec % 3600) / 60);
      var s = sec % 60;
      return pad(h) + ":" + pad(m) + ":" + pad(s);
    }}
    function tick() {{
      if (!available || !nextIso) {{
        el.textContent = "—";
        return;
      }}
      var deadline = Date.parse(nextIso);
      if (isNaN(deadline)) {{
        el.textContent = "—";
        return;
      }}
      var rem = Math.max(0, Math.floor((deadline - Date.now()) / 1000));
      el.textContent = fmt(rem);
    }}
    tick();
    setInterval(tick, 1000);
  }})();
  </script>
"""
