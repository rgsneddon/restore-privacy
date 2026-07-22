"""Public dual-line countdown: next entry (Node A) / exit (Node B) data clear.

Display for https://restoreprivacy.online/ homepage. Period matches the product
**weekly entry wipe** service (``OnUnitActiveSec=604800`` / ``7d``).

Honesty:
- **Node A (entry)** aligns with the real weekly entry wipe/rebuild cadence.
- **Node B (exit)** uses the same **display** period with a phase offset — the
  product weekly service is **entry-only** (never concurrent exit wipe from that
  timer). Exit line is a planned clear schedule for transparency, not a claim
  that live dual-VPS wipe is running.
- “DATA IS CLEARED” means the product wipe/rebuild cycle; it does **not** erase
  VPS provider off-box backups/netflow.
"""

from __future__ import annotations

import html
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# Exact OBJECTIVE labels (case/spacing preserved)
NODE_A_ENTRY_LABEL = "ALL NODE A (ENTRY NODE) DATA IS CLEARED in"
NODE_B_EXIT_LABEL = "ALL NODE B (EXIT NODE) DATA IS CLEARED IN"

# Matches weekly entry wipe timer (scripts/install_ephemeral_timer.sh PERIOD=7d)
NODE_WIPE_PERIOD = timedelta(days=7)
NODE_WIPE_PERIOD_SECONDS = int(NODE_WIPE_PERIOD.total_seconds())  # 604800

# Phase offset for Node B display so the two lines are not identical clocks.
# Half period keeps exit clear schedule staggered from entry (display only).
NODE_B_PHASE_SECONDS = NODE_WIPE_PERIOD_SECONDS // 2

HONESTY_BLURB = (
    "Node A: weekly entry wipe/rebuild cadence (~7d). "
    "Node B: planned exit clear display schedule (same period, staggered) — "
    "weekly live wipe service is entry-only. "
    "Product rebuild cycle; does not erase provider backups/netflow."
)


def _utc_now(now: datetime | None = None) -> datetime:
    n = now if now is not None else datetime.now(timezone.utc)
    if n.tzinfo is None:
        n = n.replace(tzinfo=timezone.utc)
    return n.astimezone(timezone.utc)


def parse_iso_utc(value: str | None) -> datetime | None:
    """Parse ISO-8601 (``...Z`` or offset) to UTC datetime."""
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def remaining_seconds_until(
    deadline: datetime,
    *,
    now: datetime | None = None,
) -> int:
    """Whole seconds remaining until *deadline* (0 if overdue)."""
    n = _utc_now(now)
    d = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
    delta = d.astimezone(timezone.utc) - n
    return max(0, int(delta.total_seconds()))


def format_countdown(seconds: int) -> str:
    """Human countdown ``HH:MM:SS`` (hours may exceed 24)."""
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def next_deadline_on_grid(
    *,
    now: datetime | None = None,
    period_seconds: int = NODE_WIPE_PERIOD_SECONDS,
    phase_seconds: int = 0,
) -> datetime:
    """Next clear deadline on a fixed period grid (unix epoch aligned + phase).

    When *now* lands exactly on a boundary, remaining is a full period (next cycle).
    """
    n = _utc_now(now)
    p = int(period_seconds)
    if p <= 0:
        raise ValueError("period_seconds must be positive")
    phase = int(phase_seconds) % p
    epoch = int(n.timestamp())
    # Position within the phased period
    pos = (epoch - phase) % p
    if pos == 0:
        wait = p
    else:
        wait = p - pos
    return datetime.fromtimestamp(epoch + wait, tz=timezone.utc)


def next_clear_from_last(
    last_clear_at: datetime,
    *,
    now: datetime | None = None,
    period: timedelta | None = None,
) -> datetime:
    """Roll *last_clear_at* + period forward until strictly after *now*."""
    n = _utc_now(now)
    p = period if period is not None else NODE_WIPE_PERIOD
    last = last_clear_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    last = last.astimezone(timezone.utc)
    nxt = last + p
    # Cap iterations for safety
    for _ in range(10_000):
        if nxt > n:
            return nxt
        nxt = nxt + p
    return nxt


def _env_last_clear(env_name: str) -> datetime | None:
    return parse_iso_utc(os.environ.get(env_name, "") or None)


def node_line_state(
    *,
    role: str,
    label: str,
    now: datetime | None = None,
    next_clear_at: datetime | None = None,
    last_clear_at: datetime | None = None,
    period_seconds: int | None = None,
    phase_seconds: int = 0,
) -> dict[str, Any]:
    """Pure state for one node clear countdown line."""
    n = _utc_now(now)
    p_sec = int(period_seconds if period_seconds is not None else NODE_WIPE_PERIOD_SECONDS)
    p = timedelta(seconds=p_sec)
    if next_clear_at is not None:
        nxt = next_clear_at if next_clear_at.tzinfo else next_clear_at.replace(
            tzinfo=timezone.utc
        )
        nxt = nxt.astimezone(timezone.utc)
        # If past, roll by period so UI never dies at zero forever without reset
        if nxt <= n:
            nxt = next_clear_from_last(nxt, now=n, period=p)
    elif last_clear_at is not None:
        nxt = next_clear_from_last(last_clear_at, now=n, period=p)
    else:
        nxt = next_deadline_on_grid(
            now=n, period_seconds=p_sec, phase_seconds=phase_seconds
        )
    rem = remaining_seconds_until(nxt, now=n)
    return {
        "role": role,
        "label": label,
        "available": True,
        "next_clear_at": nxt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "remaining_seconds": rem,
        "display": format_countdown(rem),
        "period_seconds": p_sec,
    }


def dual_node_wipe_state(
    *,
    now: datetime | None = None,
    entry_next: datetime | None = None,
    exit_next: datetime | None = None,
    entry_last: datetime | None = None,
    exit_last: datetime | None = None,
    period_seconds: int | None = None,
) -> dict[str, Any]:
    """State for both Node A (entry) and Node B (exit) countdown lines."""
    p_sec = int(period_seconds if period_seconds is not None else NODE_WIPE_PERIOD_SECONDS)
    # Optional env anchors (operator override)
    if entry_last is None:
        entry_last = _env_last_clear("RPT_NODE_A_LAST_CLEAR")
    if exit_last is None:
        exit_last = _env_last_clear("RPT_NODE_B_LAST_CLEAR")
    if entry_next is None:
        entry_next = parse_iso_utc(os.environ.get("RPT_NODE_A_NEXT_CLEAR", "") or None)
    if exit_next is None:
        exit_next = parse_iso_utc(os.environ.get("RPT_NODE_B_NEXT_CLEAR", "") or None)

    entry = node_line_state(
        role="entry",
        label=NODE_A_ENTRY_LABEL,
        now=now,
        next_clear_at=entry_next,
        last_clear_at=entry_last,
        period_seconds=p_sec,
        phase_seconds=0,
    )
    exit_line = node_line_state(
        role="exit",
        label=NODE_B_EXIT_LABEL,
        now=now,
        next_clear_at=exit_next,
        last_clear_at=exit_last,
        period_seconds=p_sec,
        phase_seconds=NODE_B_PHASE_SECONDS if exit_next is None and exit_last is None else 0,
    )
    return {
        "period_seconds": p_sec,
        "entry": entry,
        "exit": exit_line,
        "blurb": HONESTY_BLURB,
        "labels": {
            "entry": NODE_A_ENTRY_LABEL,
            "exit": NODE_B_EXIT_LABEL,
        },
    }


def render_node_wipe_countdown_html(
    *,
    now: datetime | None = None,
    entry_next: datetime | None = None,
    exit_next: datetime | None = None,
    entry_last: datetime | None = None,
    exit_last: datetime | None = None,
) -> str:
    """Two-line HTML fragment + 1s client tick for remaining time."""
    state = dual_node_wipe_state(
        now=now,
        entry_next=entry_next,
        exit_next=exit_next,
        entry_last=entry_last,
        exit_last=exit_last,
    )
    a = state["entry"]
    b = state["exit"]
    label_a = html.escape(str(a["label"]))
    label_b = html.escape(str(b["label"]))
    disp_a = html.escape(str(a["display"]))
    disp_b = html.escape(str(b["display"]))
    next_a = html.escape(str(a["next_clear_at"]))
    next_b = html.escape(str(b["next_clear_at"]))
    blurb = html.escape(str(state["blurb"]))
    period = int(state["period_seconds"])

    return f"""  <div class="node-wipe-countdown" id="node-wipe-countdown"
       data-period-seconds="{period}"
       data-next-entry="{next_a}"
       data-next-exit="{next_b}">
    <div class="node-wipe-row" id="node-wipe-row-entry">
      <span class="node-wipe-label" id="node-wipe-label-entry">{label_a}</span>
      <span class="node-wipe-value" id="node-wipe-value-entry" aria-live="polite">{disp_a}</span>
    </div>
    <div class="node-wipe-row" id="node-wipe-row-exit">
      <span class="node-wipe-label" id="node-wipe-label-exit">{label_b}</span>
      <span class="node-wipe-value" id="node-wipe-value-exit" aria-live="polite">{disp_b}</span>
    </div>
    <p class="node-wipe-blurb" id="node-wipe-blurb">{blurb}</p>
  </div>
  <script>
  (function () {{
    var root = document.getElementById("node-wipe-countdown");
    var elA = document.getElementById("node-wipe-value-entry");
    var elB = document.getElementById("node-wipe-value-exit");
    if (!root || !elA || !elB) return;
    var nextA = root.getAttribute("data-next-entry") || "";
    var nextB = root.getAttribute("data-next-exit") || "";
    var period = parseInt(root.getAttribute("data-period-seconds") || "604800", 10);
    if (!period || period < 1) period = 604800;
    function pad(n) {{ return n < 10 ? "0" + n : String(n); }}
    function fmt(sec) {{
      sec = Math.max(0, Math.floor(sec));
      var h = Math.floor(sec / 3600);
      var m = Math.floor((sec % 3600) / 60);
      var s = sec % 60;
      return pad(h) + ":" + pad(m) + ":" + pad(s);
    }}
    function roll(iso) {{
      var d = Date.parse(iso);
      if (isNaN(d)) return null;
      var now = Date.now();
      while (d <= now) {{ d += period * 1000; }}
      return d;
    }}
    var deadlineA = roll(nextA);
    var deadlineB = roll(nextB);
    function tick() {{
      var now = Date.now();
      if (deadlineA != null) {{
        while (deadlineA <= now) {{ deadlineA += period * 1000; }}
        elA.textContent = fmt(Math.max(0, Math.floor((deadlineA - now) / 1000)));
      }} else {{ elA.textContent = "—"; }}
      if (deadlineB != null) {{
        while (deadlineB <= now) {{ deadlineB += period * 1000; }}
        elB.textContent = fmt(Math.max(0, Math.floor((deadlineB - now) / 1000)));
      }} else {{ elB.textContent = "—"; }}
    }}
    tick();
    setInterval(tick, 1000);
  }})();
  </script>
"""
